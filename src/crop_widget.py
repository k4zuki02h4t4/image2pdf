"""
4点切り抜きウィジェット
マウスで4つの点を指定して画像の切り抜き範囲を設定するウィジェット
修正版：存在しないFluentIconを修正
"""

import logging
import math
from typing import List, Tuple, Optional, Union
from pathlib import Path

import numpy as np
import cv2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QSlider, QSpinBox, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QPixmap, QColor, QImage,
    QMouseEvent, QPaintEvent, QWheelEvent
)
from qfluentwidgets import (
    PushButton, BodyLabel, Slider, SpinBox,
    CardWidget, StrongBodyLabel, IconWidget,
    FluentIcon, Theme, isDarkTheme, PrimaryPushButton,
    TransparentPushButton, Dialog
)

from .utils import load_image_safely, resize_keeping_aspect_ratio


class InteractiveImageWidget(QWidget):
    """4点指定可能なインタラクティブ画像ウィジェット"""
    
    # シグナル定義
    points_changed = pyqtSignal(list)  # 4点の座標が変更された
    crop_requested = pyqtSignal()  # 切り抜きが要求された
    reset_requested = pyqtSignal()  # リセットが要求された
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        # objectNameを設定（qfluentwidgetsの要件）
        self.setObjectName("interactive-image-widget")
        
        # 画像データ
        self.original_pixmap: Optional[QPixmap] = None
        self.display_pixmap: Optional[QPixmap] = None
        self.image_rect = QRect()
        
        # 4つの制御点
        self.control_points: List[QPoint] = []
        self.dragging_point_index: int = -1
        self.point_radius = 8
        self.hover_point_index: int = -1
        
        # ズーム・パン機能
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self.pan_offset = QPoint(0, 0)
        self.last_pan_point = QPoint()
        self.is_panning = False
        
        # UI設定
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 描画色の設定
        self._setup_colors()
        
        # デバウンス用タイマー
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._emit_points_changed)
        
    def _setup_colors(self):
        """テーマに応じた色設定"""
        if isDarkTheme():
            self.point_color = QColor(100, 150, 255)
            self.line_color = QColor(100, 150, 255, 180)
            self.hover_color = QColor(255, 150, 100)
            self.selected_color = QColor(255, 100, 100)
            self.grid_color = QColor(255, 255, 255, 50)
            self.bg_color = QColor(50, 50, 50)
        else:
            self.point_color = QColor(30, 100, 200)
            self.line_color = QColor(30, 100, 200, 180)
            self.hover_color = QColor(255, 120, 50)
            self.selected_color = QColor(200, 50, 50)
            self.grid_color = QColor(0, 0, 0, 50)
            self.bg_color = QColor(240, 240, 240)
    
    def set_image(self, image_path: Union[str, Path]) -> bool:
        """
        画像を設定
        
        Args:
            image_path: 画像ファイルのパス
            
        Returns:
            設定が成功した場合True
        """
        try:
            pixmap = load_image_safely(image_path)
            if pixmap is None:
                self.logger.error(f"画像読み込み失敗: {image_path}")
                return False
            
            self.original_pixmap = pixmap
            self._reset_view()
            self._setup_default_points()
            self.update()
            
            self.logger.info(f"画像設定完了: {image_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"画像設定エラー: {image_path} - {e}")
            return False
    
    def _reset_view(self):
        """表示をリセット"""
        if not self.original_pixmap:
            return
        
        # ウィジェットサイズに合わせて画像をスケール
        widget_size = self.size()
        pixmap_size = self.original_pixmap.size()
        
        # アスペクト比を保持してリサイズ
        new_size = resize_keeping_aspect_ratio(
            (pixmap_size.width(), pixmap_size.height()),
            (widget_size.width() - 20, widget_size.height() - 20)
        )
        
        self.display_pixmap = self.original_pixmap.scaled(
            new_size[0], new_size[1],
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # 画像表示位置を中央に設定
        self.image_rect = QRect(
            (widget_size.width() - new_size[0]) // 2,
            (widget_size.height() - new_size[1]) // 2,
            new_size[0],
            new_size[1]
        )
        
        # ズーム・パンをリセット
        self.zoom_factor = 1.0
        self.pan_offset = QPoint(0, 0)
    
    def _setup_default_points(self):
        """デフォルトの4点を設定（画像の四隅）"""
        if not self.image_rect.isValid():
            return
        
        margin = 20
        self.control_points = [
            QPoint(self.image_rect.left() + margin, self.image_rect.top() + margin),  # 左上
            QPoint(self.image_rect.right() - margin, self.image_rect.top() + margin),  # 右上
            QPoint(self.image_rect.right() - margin, self.image_rect.bottom() - margin),  # 右下
            QPoint(self.image_rect.left() + margin, self.image_rect.bottom() - margin)  # 左下
        ]
        
        self._emit_points_changed()
    
    def get_crop_points_in_image_coordinates(self) -> List[Tuple[int, int]]:
        """
        画像座標系での切り抜き点を取得
        
        Returns:
            画像座標系での4点のリスト
        """
        if not self.original_pixmap or not self.display_pixmap or len(self.control_points) != 4:
            return []
        
        # 表示画像から元画像への変換比率を計算
        scale_x = self.original_pixmap.width() / self.display_pixmap.width()
        scale_y = self.original_pixmap.height() / self.display_pixmap.height()
        
        # ズーム・パンを考慮した座標変換
        image_points = []
        for point in self.control_points:
            # ウィジェット座標から画像座標への変換
            img_x = (point.x() - self.image_rect.x() - self.pan_offset.x()) / self.zoom_factor
            img_y = (point.y() - self.image_rect.y() - self.pan_offset.y()) / self.zoom_factor
            
            # 元画像座標に変換
            orig_x = int(img_x * scale_x)
            orig_y = int(img_y * scale_y)
            
            # 画像範囲内にクランプ
            orig_x = max(0, min(orig_x, self.original_pixmap.width() - 1))
            orig_y = max(0, min(orig_y, self.original_pixmap.height() - 1))
            
            image_points.append((orig_x, orig_y))
        
        return image_points
    
    def set_crop_points(self, points: List[Tuple[int, int]]):
        """
        画像座標系での切り抜き点を設定
        
        Args:
            points: 画像座標系での4点のリスト
        """
        if len(points) != 4 or not self.original_pixmap or not self.display_pixmap:
            return
        
        # 元画像から表示画像への変換比率を計算
        scale_x = self.display_pixmap.width() / self.original_pixmap.width()
        scale_y = self.display_pixmap.height() / self.original_pixmap.height()
        
        # ウィジェット座標に変換
        self.control_points = []
        for orig_x, orig_y in points:
            # 表示画像座標に変換
            img_x = orig_x * scale_x
            img_y = orig_y * scale_y
            
            # ウィジェット座標に変換（ズーム・パンを考慮）
            widget_x = self.image_rect.x() + img_x * self.zoom_factor + self.pan_offset.x()
            widget_y = self.image_rect.y() + img_y * self.zoom_factor + self.pan_offset.y()
            
            self.control_points.append(QPoint(int(widget_x), int(widget_y)))
        
        self.update()
        self._emit_points_changed()
    
    def reset_points(self):
        """制御点をリセット"""
        self._setup_default_points()
        self.update()
    
    def paintEvent(self, event: QPaintEvent):
        """描画イベント"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景を描画
        painter.fillRect(self.rect(), self.bg_color)
        
        # 画像を描画
        if self.display_pixmap:
            # ズーム・パンを適用した画像描画
            draw_rect = QRect(
                self.image_rect.x() + self.pan_offset.x(),
                self.image_rect.y() + self.pan_offset.y(),
                int(self.image_rect.width() * self.zoom_factor),
                int(self.image_rect.height() * self.zoom_factor)
            )
            
            scaled_pixmap = self.display_pixmap.scaled(
                draw_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            painter.drawPixmap(draw_rect.topLeft(), scaled_pixmap)
        
        # グリッドを描画（ズーム時）
        if self.zoom_factor > 2.0:
            self._draw_grid(painter)
        
        # 制御点と線を描画
        if len(self.control_points) >= 2:
            self._draw_crop_overlay(painter)
    
    def _draw_grid(self, painter: QPainter):
        """グリッドを描画"""
        if not self.image_rect.isValid():
            return
        
        painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.DotLine))
        
        grid_size = int(20 * self.zoom_factor)
        
        # 垂直線
        for x in range(self.image_rect.left(), self.image_rect.right(), grid_size):
            painter.drawLine(x, self.image_rect.top(), x, self.image_rect.bottom())
        
        # 水平線
        for y in range(self.image_rect.top(), self.image_rect.bottom(), grid_size):
            painter.drawLine(self.image_rect.left(), y, self.image_rect.right(), y)
    
    def _draw_crop_overlay(self, painter: QPainter):
        """切り抜きオーバーレイを描画"""
        if len(self.control_points) < 2:
            return
        
        # 線を描画
        if len(self.control_points) >= 2:
            painter.setPen(QPen(self.line_color, 2))
            for i in range(len(self.control_points)):
                next_i = (i + 1) % len(self.control_points)
                if next_i < len(self.control_points):
                    painter.drawLine(self.control_points[i], self.control_points[next_i])
        
        # 切り抜き領域を半透明で強調
        if len(self.control_points) == 4:
            painter.setBrush(QBrush(QColor(100, 150, 255, 30)))
            painter.setPen(Qt.PenStyle.NoPen)
            polygon_points = [point for point in self.control_points]
            painter.drawPolygon(polygon_points)
        
        # 制御点を描画
        for i, point in enumerate(self.control_points):
            if i == self.dragging_point_index:
                color = self.selected_color
                radius = self.point_radius + 2
            elif i == self.hover_point_index:
                color = self.hover_color
                radius = self.point_radius + 1
            else:
                color = self.point_color
                radius = self.point_radius
            
            # 外側の円
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(point, radius, radius)
            
            # 内側の円
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(point, radius // 2, radius // 2)
            
            # 点番号を描画
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.drawText(
                point.x() - 5, point.y() + 5,
                str(i + 1)
            )
    
    def mousePressEvent(self, event: QMouseEvent):
        """マウス押下イベント"""
        if event.button() == Qt.MouseButton.LeftButton:
            point_index = self._get_point_at_position(event.pos())
            
            if point_index >= 0:
                # 制御点をドラッグ開始
                self.dragging_point_index = point_index
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            elif len(self.control_points) < 4 and self._is_point_in_image(event.pos()):
                # 新しい制御点を追加
                self.control_points.append(event.pos())
                self.dragging_point_index = len(self.control_points) - 1
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.update()
            else:
                # パン開始
                self.is_panning = True
                self.last_pan_point = event.pos()
                self.setCursor(Qt.CursorShape.OpenHandCursor)
        
        elif event.button() == Qt.MouseButton.RightButton:
            # 右クリックで制御点を削除
            point_index = self._get_point_at_position(event.pos())
            if point_index >= 0 and len(self.control_points) > 2:
                self.control_points.pop(point_index)
                self.dragging_point_index = -1
                self.hover_point_index = -1
                self.update()
                self._emit_points_changed()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """マウス移動イベント"""
        if self.dragging_point_index >= 0:
            # 制御点をドラッグ
            self.control_points[self.dragging_point_index] = event.pos()
            self.update()
            # デバウンス付きで点変更イベントを発行
            self.update_timer.start(100)
            
        elif self.is_panning:
            # パン操作
            delta = event.pos() - self.last_pan_point
            self.pan_offset += delta
            self.last_pan_point = event.pos()
            self.update()
            
        else:
            # ホバー状態の更新
            old_hover = self.hover_point_index
            self.hover_point_index = self._get_point_at_position(event.pos())
            
            if self.hover_point_index >= 0:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            
            if old_hover != self.hover_point_index:
                self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """マウス離上イベント"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.dragging_point_index >= 0:
                self.dragging_point_index = -1
                self._emit_points_changed()
            
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def wheelEvent(self, event: QWheelEvent):
        """ホイールイベント（ズーム）"""
        if not self.image_rect.isValid():
            return
        
        # ズーム倍率を計算
        zoom_delta = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        new_zoom = self.zoom_factor * zoom_delta
        
        # ズーム範囲をチェック
        if new_zoom < self.min_zoom or new_zoom > self.max_zoom:
            return
        
        # マウス位置を中心にズーム
        mouse_pos = event.position().toPoint()
        
        # ズーム前の相対位置を計算
        relative_x = (mouse_pos.x() - self.image_rect.x() - self.pan_offset.x()) / self.zoom_factor
        relative_y = (mouse_pos.y() - self.image_rect.y() - self.pan_offset.y()) / self.zoom_factor
        
        # ズーム倍率を更新
        self.zoom_factor = new_zoom
        
        # パンオフセットを調整してマウス位置を維持
        new_x = mouse_pos.x() - self.image_rect.x() - relative_x * self.zoom_factor
        new_y = mouse_pos.y() - self.image_rect.y() - relative_y * self.zoom_factor
        self.pan_offset = QPoint(int(new_x), int(new_y))
        
        self.update()
        event.accept()
    
    def resizeEvent(self, event):
        """リサイズイベント"""
        super().resizeEvent(event)
        if self.original_pixmap:
            self._reset_view()
            self._setup_default_points()
    
    def _get_point_at_position(self, pos: QPoint) -> int:
        """指定位置にある制御点のインデックスを取得"""
        for i, point in enumerate(self.control_points):
            distance = math.sqrt((pos.x() - point.x())**2 + (pos.y() - point.y())**2)
            if distance <= self.point_radius + 5:
                return i
        return -1
    
    def _is_point_in_image(self, pos: QPoint) -> bool:
        """指定位置が画像領域内かどうかを判定"""
        if not self.image_rect.isValid():
            return False
        
        # ズーム・パンを考慮した画像領域
        draw_rect = QRect(
            self.image_rect.x() + self.pan_offset.x(),
            self.image_rect.y() + self.pan_offset.y(),
            int(self.image_rect.width() * self.zoom_factor),
            int(self.image_rect.height() * self.zoom_factor)
        )
        
        return draw_rect.contains(pos)
    
    def _emit_points_changed(self):
        """点変更イベントを発行"""
        if len(self.control_points) >= 2:
            image_points = self.get_crop_points_in_image_coordinates()
            self.points_changed.emit(image_points)


class CropWidget(CardWidget):
    """4点切り抜きウィジェット（メインウィジェット）"""
    
    # シグナル定義
    crop_completed = pyqtSignal(np.ndarray)  # 切り抜き完了
    image_rotated = pyqtSignal(float)  # 画像回転完了
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.current_image_path: Optional[Path] = None
        self.current_image: Optional[np.ndarray] = None
        
        # objectNameを設定（qfluentwidgetsの要件）
        self.setObjectName("crop-widget")
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """UI初期化"""
        layout = QVBoxLayout(self)
        
        # タイトル
        title_label = StrongBodyLabel("画像切り抜き")
        layout.addWidget(title_label)
        
        # インタラクティブ画像ウィジェット
        self.image_widget = InteractiveImageWidget()
        self.image_widget.setMinimumHeight(400)
        layout.addWidget(self.image_widget)
        
        # コントロールパネル
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)
        
        # ボタンパネル
        button_panel = self._create_button_panel()
        layout.addWidget(button_panel)
    
    def _create_control_panel(self) -> QWidget:
        """コントロールパネルの作成"""
        panel = QGroupBox("画像操作")
        layout = QHBoxLayout(panel)
        
        # 回転コントロール
        rotation_group = QGroupBox("回転")
        rotation_layout = QVBoxLayout(rotation_group)
        
        self.rotation_slider = Slider(Qt.Orientation.Horizontal)
        self.rotation_slider.setRange(-180, 180)
        self.rotation_slider.setValue(0)
        self.rotation_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.rotation_slider.setTickInterval(45)
        
        self.rotation_spinbox = SpinBox()
        self.rotation_spinbox.setRange(-180, 180)
        self.rotation_spinbox.setValue(0)
        self.rotation_spinbox.setSuffix("°")
        
        rotation_layout.addWidget(BodyLabel("角度:"))
        rotation_layout.addWidget(self.rotation_slider)
        rotation_layout.addWidget(self.rotation_spinbox)
        
        # 90度回転ボタン
        rotate_buttons_layout = QHBoxLayout()
        self.rotate_left_btn = PushButton("90°左回転")
        self.rotate_right_btn = PushButton("90°右回転")
        rotate_buttons_layout.addWidget(self.rotate_left_btn)
        rotate_buttons_layout.addWidget(self.rotate_right_btn)
        rotation_layout.addLayout(rotate_buttons_layout)
        
        layout.addWidget(rotation_group)
        
        # ズームコントロール
        zoom_group = QGroupBox("表示")
        zoom_layout = QVBoxLayout(zoom_group)
        
        self.zoom_label = BodyLabel("ズーム: 100%")
        self.points_label = BodyLabel("制御点: 0/4")
        
        # ズーム操作ボタン
        zoom_buttons_layout = QHBoxLayout()
        self.zoom_in_btn = PushButton("拡大")
        self.zoom_in_btn.setIcon(FluentIcon.ADD)  # ZOOM_IN → ADD
        self.zoom_out_btn = PushButton("縮小")
        self.zoom_out_btn.setIcon(FluentIcon.REMOVE)  # ZOOM_OUT → REMOVE
        self.zoom_fit_btn = PushButton("全体表示")
        self.zoom_fit_btn.setIcon(FluentIcon.VIEW)  # FIT_PAGE → VIEW
        
        zoom_buttons_layout.addWidget(self.zoom_in_btn)
        zoom_buttons_layout.addWidget(self.zoom_out_btn)
        zoom_buttons_layout.addWidget(self.zoom_fit_btn)
        
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(self.points_label)
        zoom_layout.addLayout(zoom_buttons_layout)
        
        layout.addWidget(zoom_group)
        
        # 画像情報パネル
        info_group = QGroupBox("画像情報")
        info_layout = QVBoxLayout(info_group)
        
        self.filename_label = BodyLabel("ファイル: 未選択")
        self.size_label = BodyLabel("サイズ: -")
        self.format_label = BodyLabel("フォーマット: -")
        
        info_layout.addWidget(self.filename_label)
        info_layout.addWidget(self.size_label)
        info_layout.addWidget(self.format_label)
        
        layout.addWidget(info_group)
        
        return panel
    
    def _create_button_panel(self) -> QWidget:
        """ボタンパネルの作成"""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        
        # 左側のボタン群
        left_buttons = QHBoxLayout()
        
        self.reset_points_btn = PushButton("制御点リセット")
        self.reset_points_btn.setIcon(FluentIcon.SYNC)  # REFRESH → SYNC
        
        self.auto_detect_btn = PushButton("自動検出")
        self.auto_detect_btn.setIcon(FluentIcon.ROBOT)
        self.auto_detect_btn.setToolTip("文書の輪郭を自動検出します")
        
        self.enhance_btn = PushButton("画質向上")
        self.enhance_btn.setIcon(FluentIcon.UPDATE)  # BRIGHTNESS → UPDATE
        self.enhance_btn.setToolTip("コントラスト調整とノイズ除去を行います")
        
        left_buttons.addWidget(self.reset_points_btn)
        left_buttons.addWidget(self.auto_detect_btn)
        left_buttons.addWidget(self.enhance_btn)
        
        layout.addLayout(left_buttons)
        layout.addStretch()
        
        # 右側のメインボタン
        self.preview_btn = PushButton("プレビュー")
        self.preview_btn.setIcon(FluentIcon.VIEW)
        self.crop_btn = PrimaryPushButton("切り抜き実行")
        self.crop_btn.setIcon(FluentIcon.CUT)
        
        layout.addWidget(self.preview_btn)
        layout.addWidget(self.crop_btn)
        
        return panel
    
    def _connect_signals(self):
        """シグナル接続"""
        # 画像ウィジェット
        self.image_widget.points_changed.connect(self._on_points_changed)
        
        # 回転コントロール
        self.rotation_slider.valueChanged.connect(self.rotation_spinbox.setValue)
        self.rotation_spinbox.valueChanged.connect(self.rotation_slider.setValue)
        self.rotation_slider.valueChanged.connect(self._on_rotation_changed)
        
        self.rotate_left_btn.clicked.connect(lambda: self._rotate_by_angle(-90))
        self.rotate_right_btn.clicked.connect(lambda: self._rotate_by_angle(90))
        
        # ズームコントロール
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        self.zoom_fit_btn.clicked.connect(self._zoom_fit)
        
        # ボタン
        self.reset_points_btn.clicked.connect(self.image_widget.reset_points)
        self.auto_detect_btn.clicked.connect(self._auto_detect_contours)
        self.enhance_btn.clicked.connect(self._enhance_image)
        self.preview_btn.clicked.connect(self._show_preview)
        self.crop_btn.clicked.connect(self._execute_crop)
    
    def set_image(self, image_path: Union[str, Path]) -> bool:
        """
        画像を設定
        
        Args:
            image_path: 画像ファイルのパス
            
        Returns:
            設定が成功した場合True
        """
        try:
            self.current_image_path = Path(image_path)
            
            # OpenCVで画像を読み込み
            self.current_image = cv2.imread(str(self.current_image_path))
            if self.current_image is None:
                return False
            
            # ウィジェットに画像を設定
            success = self.image_widget.set_image(image_path)
            if success:
                # 回転をリセット
                self.rotation_slider.setValue(0)
                self._update_ui_state()
                self._update_image_info()
            
            return success
            
        except Exception as e:
            self.logger.error(f"画像設定エラー: {image_path} - {e}")
            return False
    
    def _update_image_info(self):
        """画像情報を更新"""
        if not self.current_image_path or self.current_image is None:
            self.filename_label.setText("ファイル: 未選択")
            self.size_label.setText("サイズ: -")
            self.format_label.setText("フォーマット: -")
            return
        
        height, width = self.current_image.shape[:2]
        channels = self.current_image.shape[2] if len(self.current_image.shape) == 3 else 1
        
        self.filename_label.setText(f"ファイル: {self.current_image_path.name}")
        self.size_label.setText(f"サイズ: {width} × {height}")
        
        format_name = self.current_image_path.suffix.upper().lstrip('.')
        channel_info = f"カラー" if channels == 3 else f"グレースケール" if channels == 1 else f"{channels}ch"
        self.format_label.setText(f"フォーマット: {format_name} ({channel_info})")
    
    def _on_points_changed(self, points: List[Tuple[int, int]]):
        """制御点変更時の処理"""
        self.points_label.setText(f"制御点: {len(points)}/4")
        
        # ボタンの有効/無効設定
        has_four_points = len(points) == 4
        self.crop_btn.setEnabled(has_four_points)
        self.preview_btn.setEnabled(has_four_points)
        
        # ズーム情報を更新
        zoom_percent = int(self.image_widget.zoom_factor * 100)
        self.zoom_label.setText(f"ズーム: {zoom_percent}%")
    
    def _on_rotation_changed(self, angle: int):
        """回転角度変更時の処理"""
        # リアルタイム回転は重いので実装しない
        # 実際の回転は「切り抜き実行」時に行う
        pass
    
    def _rotate_by_angle(self, angle: int):
        """指定角度だけ回転"""
        current_angle = self.rotation_slider.value()
        new_angle = (current_angle + angle) % 360
        if new_angle > 180:
            new_angle -= 360
        self.rotation_slider.setValue(new_angle)
    
    def _zoom_in(self):
        """ズームイン"""
        if hasattr(self.image_widget, 'zoom_factor'):
            new_zoom = min(self.image_widget.zoom_factor * 1.2, self.image_widget.max_zoom)
            self.image_widget.zoom_factor = new_zoom
            self.image_widget.update()
            self._update_zoom_display()
    
    def _zoom_out(self):
        """ズームアウト"""
        if hasattr(self.image_widget, 'zoom_factor'):
            new_zoom = max(self.image_widget.zoom_factor / 1.2, self.image_widget.min_zoom)
            self.image_widget.zoom_factor = new_zoom
            self.image_widget.update()
            self._update_zoom_display()
    
    def _zoom_fit(self):
        """全体表示"""
        if hasattr(self.image_widget, 'zoom_factor'):
            self.image_widget.zoom_factor = 1.0
            self.image_widget.pan_offset = QPoint(0, 0)
            self.image_widget.update()
            self._update_zoom_display()
    
    def _update_zoom_display(self):
        """ズーム表示を更新"""
        if hasattr(self.image_widget, 'zoom_factor'):
            zoom_percent = int(self.image_widget.zoom_factor * 100)
            self.zoom_label.setText(f"ズーム: {zoom_percent}%")
    
    def _auto_detect_contours(self):
        """文書の輪郭を自動検出"""
        try:
            if self.current_image is None:
                QMessageBox.warning(self, "エラー", "画像が設定されていません")
                return
            
            # グレースケール変換
            gray = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2GRAY)
            
            # ガウシアンブラー
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # エッジ検出
            edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
            
            # 輪郭検出
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                QMessageBox.information(self, "情報", "文書の輪郭を検出できませんでした")
                return
            
            # 最大面積の輪郭を選択
            largest_contour = max(contours, key=cv2.contourArea)
            
            # 輪郭を4点に近似
            epsilon = 0.02 * cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, epsilon, True)
            
            if len(approx) == 4:
                # 4点が検出された場合
                points = [(int(point[0][0]), int(point[0][1])) for point in approx]
                self.image_widget.set_crop_points(points)
                QMessageBox.information(self, "成功", "文書の輪郭を自動検出しました")
            else:
                # 4点でない場合は画像の四隅に設定
                height, width = self.current_image.shape[:2]
                margin = min(width, height) // 20
                points = [
                    (margin, margin),
                    (width - margin, margin),
                    (width - margin, height - margin),
                    (margin, height - margin)
                ]
                self.image_widget.set_crop_points(points)
                QMessageBox.information(self, "情報", "4角形の輪郭が検出できなかったため、デフォルトの範囲を設定しました")
            
        except Exception as e:
            self.logger.error(f"自動検出エラー: {e}")
            QMessageBox.critical(self, "エラー", f"自動検出でエラーが発生しました:\n{e}")
    
    def _enhance_image(self):
        """画質向上を実行"""
        try:
            if self.current_image is None:
                QMessageBox.warning(self, "エラー", "画像が設定されていません")
                return
            
            from .image_processor import ImageProcessor
            processor = ImageProcessor()
            
            # 画質向上を実行
            enhanced_image = processor.enhance_image(self.current_image)
            
            if enhanced_image is not None:
                self.current_image = enhanced_image
                
                # 一時ファイルに保存して再表示
                from .utils import get_temp_dir
                temp_dir = get_temp_dir()
                temp_path = temp_dir / f"enhanced_{self.current_image_path.name}"
                
                cv2.imwrite(str(temp_path), enhanced_image)
                self.image_widget.set_image(temp_path)
                
                QMessageBox.information(self, "完了", "画質向上が完了しました")
                
        except Exception as e:
            self.logger.error(f"画質向上エラー: {e}")
            QMessageBox.critical(self, "エラー", f"画質向上でエラーが発生しました:\n{e}")
    
    def _show_preview(self):
        """切り抜きプレビューを表示"""
        try:
            if not self.current_image_path or self.current_image is None:
                QMessageBox.warning(self, "エラー", "画像が設定されていません")
                return
            
            # 制御点を取得
            crop_points = self.image_widget.get_crop_points_in_image_coordinates()
            if len(crop_points) != 4:
                QMessageBox.warning(self, "エラー", "4つの制御点を設定してください")
                return
            
            # プレビュー用の切り抜きを実行
            from .image_processor import ImageProcessor
            processor = ImageProcessor()
            
            working_image = self.current_image.copy()
            
            # 回転を適用
            rotation_angle = self.rotation_slider.value()
            if rotation_angle != 0:
                working_image = processor.rotate_image(working_image, rotation_angle)
            
            # 4点切り抜きを実行
            cropped_image = processor.crop_image_with_four_points(working_image, crop_points)
            
            if cropped_image is not None:
                # プレビューダイアログを表示
                self._show_preview_dialog(cropped_image)
            else:
                QMessageBox.warning(self, "エラー", "プレビュー生成に失敗しました")
                
        except Exception as e:
            self.logger.error(f"プレビューエラー: {e}")
            QMessageBox.critical(self, "エラー", f"プレビュー生成でエラーが発生しました:\n{e}")
    
    def _show_preview_dialog(self, preview_image: np.ndarray):
        """プレビューダイアログを表示"""
        try:
            # OpenCV画像をQPixmapに変換
            height, width = preview_image.shape[:2]
            if len(preview_image.shape) == 3:
                rgb_image = cv2.cvtColor(preview_image, cv2.COLOR_BGR2RGB)
                q_image = QImage(rgb_image.data, width, height, width * 3, QImage.Format.Format_RGB888)
            else:
                q_image = QImage(preview_image.data, width, height, width, QImage.Format.Format_Grayscale8)
            
            pixmap = QPixmap.fromImage(q_image)
            
            # プレビューウィンドウサイズに調整
            max_size = 600
            if pixmap.width() > max_size or pixmap.height() > max_size:
                pixmap = pixmap.scaled(
                    max_size, max_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            
            # ダイアログ作成
            dialog = Dialog("切り抜きプレビュー", "", self)
            dialog.setFixedSize(pixmap.width() + 40, pixmap.height() + 100)
            
            # プレビューラベル
            preview_label = QLabel()
            preview_label.setPixmap(pixmap)
            preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # ダイアログレイアウト
            layout = QVBoxLayout()
            layout.addWidget(preview_label)
            dialog.setLayout(layout)
            
            # ダイアログを表示
            dialog.exec()
            
        except Exception as e:
            self.logger.error(f"プレビューダイアログエラー: {e}")
            QMessageBox.critical(self, "エラー", f"プレビュー表示でエラーが発生しました:\n{e}")
    
    def _execute_crop(self):
        """切り抜きを実行"""
        try:
            if not self.current_image_path or self.current_image is None:
                QMessageBox.warning(self, "エラー", "画像が設定されていません")
                return
            
            # 制御点を取得
            crop_points = self.image_widget.get_crop_points_in_image_coordinates()
            if len(crop_points) != 4:
                QMessageBox.warning(self, "エラー", "4つの制御点を設定してください")
                return
            
            # 画像処理を実行
            from .image_processor import ImageProcessor
            
            processor = ImageProcessor()
            
            # 現在の画像をコピー
            working_image = self.current_image.copy()
            
            # 回転を適用
            rotation_angle = self.rotation_slider.value()
            if rotation_angle != 0:
                working_image = processor.rotate_image(working_image, rotation_angle)
                self.image_rotated.emit(rotation_angle)
            
            # 4点切り抜きを実行
            cropped_image = processor.crop_image_with_four_points(working_image, crop_points)
            
            if cropped_image is not None:
                self.crop_completed.emit(cropped_image)
                self.logger.info("切り抜き完了")
                
                # 成功メッセージ
                QMessageBox.information(self, "完了", "切り抜きが正常に完了しました。\n画像リストに追加されました。")
            else:
                QMessageBox.warning(self, "エラー", "切り抜き処理に失敗しました")
            
        except Exception as e:
            self.logger.error(f"切り抜き実行エラー: {e}")
            QMessageBox.critical(self, "エラー", f"切り抜き処理でエラーが発生しました:\n{e}")
    
    def _update_ui_state(self):
        """UI状態を更新"""
        has_image = self.current_image_path is not None
        
        # 回転コントロール
        self.rotation_slider.setEnabled(has_image)
        self.rotation_spinbox.setEnabled(has_image)
        self.rotate_left_btn.setEnabled(has_image)
        self.rotate_right_btn.setEnabled(has_image)
        
        # ズームコントロール
        self.zoom_in_btn.setEnabled(has_image)
        self.zoom_out_btn.setEnabled(has_image)
        self.zoom_fit_btn.setEnabled(has_image)
        
        # 操作ボタン
        self.reset_points_btn.setEnabled(has_image)
        self.auto_detect_btn.setEnabled(has_image)
        self.enhance_btn.setEnabled(has_image)
        
        # 切り抜き関連ボタンは制御点の数に依存
        # (_on_points_changed で制御)
    
    def get_current_image_info(self) -> Optional[dict]:
        """
        現在の画像情報を取得
        
        Returns:
            画像情報の辞書、画像が未設定の場合はNone
        """
        if not self.current_image_path or self.current_image is None:
            return None
        
        height, width = self.current_image.shape[:2]
        channels = self.current_image.shape[2] if len(self.current_image.shape) == 3 else 1
        
        return {
            'filename': self.current_image_path.name,
            'filepath': str(self.current_image_path),
            'width': width,
            'height': height,
            'channels': channels,
            'rotation_angle': self.rotation_slider.value(),
            'crop_points': self.image_widget.get_crop_points_in_image_coordinates(),
            'zoom_factor': getattr(self.image_widget, 'zoom_factor', 1.0)
        }