"""
メインウィンドウ
Image2PDF アプリケーションのメインGUIウィンドウ
ナビゲーション削除版：単一画面で全機能を統合
リサイズハンドル削除対応版
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import json

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QListWidget, QListWidgetItem, QGroupBox,
    QFileDialog, QProgressBar, QStatusBar, QTabWidget,
    QMenuBar, QMenu, QToolBar, QScrollArea, QHeaderView, QApplication
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QThread, QTimer, QSettings,
    QStandardPaths, QMimeData, QUrl
)
from PyQt6.QtGui import (
    QAction, QIcon, QPixmap, QDragEnterEvent, 
    QDropEvent, QCloseEvent, QKeySequence
)

from qfluentwidgets import (
    PushButton, ToolButton, CommandBar, Action,
    InfoBar, InfoBarPosition, MessageBox, Dialog,
    BodyLabel, StrongBodyLabel, ComboBox, SpinBox,
    CheckBox, LineEdit, PrimaryPushButton, TransparentPushButton,
    CardWidget, HeaderCardWidget, ElevatedCardWidget,
    ProgressRing, StateToolTip, TeachingTip, TeachingTipTailPosition,
    FluentIcon, Theme, isDarkTheme
)

from .utils import (
    is_image_file, get_image_filter_string, 
    validate_and_prepare_output_path, check_file_overwrite,
    format_file_size, get_temp_dir,
    get_pdf_page_size_list, get_pdf_margin_preset_list,
    PDF_PAGE_SIZES, PDF_MARGIN_PRESETS, PDF_GENERATION_MODES, PDF_DEFAULTS
)
from .image_processor import ImageProcessor
from .pdf_generator import PDFGenerator  
from .crop_widget import InteractiveImageWidget


class ImageListWidget(QListWidget):
    """画像リスト表示・並び替え可能ウィジェット"""
    
    # シグナル定義
    images_reordered = pyqtSignal(list)  # 画像順序変更
    image_selected = pyqtSignal(str)  # 画像選択
    image_removed = pyqtSignal(str)  # 画像削除
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        # ドラッグ&ドロップ設定
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        # 選択設定
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        
        # スタイル設定
        self.setAlternatingRowColors(True)
        self.setMinimumHeight(200)
        
        # シグナル接続
        self.itemClicked.connect(self._on_item_clicked)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        
        # 選択とドラッグ&ドロップの管理用
        self._drag_start_position = None
        self._is_dragging = False
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        """ドラッグ開始イベント"""
        if event.mimeData().hasUrls():
            # 外部ファイルのドラッグ
            urls = event.mimeData().urls()
            if any(is_image_file(url.toLocalFile()) for url in urls):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            # 内部アイテムの並び替え
            super().dragEnterEvent(event)
    
    def dragMoveEvent(self, event):
        """ドラッグ移動イベント"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)
    
    def dropEvent(self, event: QDropEvent):
        """ドロップイベント"""
        if event.mimeData().hasUrls():
            # 外部ファイルのドロップ
            urls = event.mimeData().urls()
            image_files = [url.toLocalFile() for url in urls if is_image_file(url.toLocalFile())]
            
            if image_files:
                # メインウィンドウに画像追加を依頼
                main_window = self.window()
                if hasattr(main_window, 'add_images'):
                    main_window.add_images(image_files)
            
            event.acceptProposedAction()
        else:
            # 内部アイテムの並び替え
            super().dropEvent(event)
            # 順序変更を通知（少し遅延させる）
            QTimer.singleShot(50, self._emit_reorder_signal)
    
    def _emit_reorder_signal(self):
        """順序変更シグナルを発行"""
        image_paths = []
        for i in range(self.count()):
            item = self.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole):
                image_paths.append(item.data(Qt.ItemDataRole.UserRole))
        
        self.images_reordered.emit(image_paths)
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """アイテムクリック時の処理"""
        # ドラッグ中でない場合のみ選択処理を実行
        if not self._is_dragging:
            self._handle_item_selection(item)
    
    def _on_selection_changed(self):
        """選択変更時の処理"""
        if not self._is_dragging:
            self._handle_item_selection(self.currentItem())
    
    def _handle_item_selection(self, item: QListWidgetItem):
        """統一された選択処理"""
        if item and item.data(Qt.ItemDataRole.UserRole):
            image_path = item.data(Qt.ItemDataRole.UserRole)
            self.image_selected.emit(image_path)
            self.logger.debug(f"画像選択イベント発火: {Path(image_path).name}")

        self.window().update_ui_state()
    
    def mousePressEvent(self, event):
        """マウスプレスイベント"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.position().toPoint()
            self._is_dragging = False

            # アイテムをクリック時に即座に選択
            item = self.itemAt(event.position().toPoint())
            if item:
                self.setCurrentItem(item)
                # 即座に選択処理を実行（ドラッグ判定前）
                self._handle_item_selection(item)
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """マウス移動イベント"""
        if (event.buttons() & Qt.MouseButton.LeftButton and 
            self._drag_start_position is not None):
            
            # ドラッグ距離を計算
            drag_distance = (event.position().toPoint() - self._drag_start_position).manhattanLength()
            
            # ドラッグが開始された場合
            if drag_distance >= QApplication.startDragDistance() and not self._is_dragging:
                self._is_dragging = True
                self.logger.debug("ドラッグ開始")
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """マウスリリースイベント"""
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._is_dragging
            self._drag_start_position = None
            self._is_dragging = False
            
            # ドラッグが行われていない場合、確実に選択処理を実行
            if not was_dragging:
                item = self.itemAt(event.position().toPoint())
                if item and item == self.currentItem():
                    self._handle_item_selection(item)
        
        super().mouseReleaseEvent(event)
    
    def add_image(self, image_path: str, thumbnail: Optional[QPixmap] = None) -> bool:
        """画像をリストに追加"""
        try:
            path = Path(image_path)
            if not path.exists():
                self.logger.warning(f"画像ファイルが存在しません: {image_path}")
                return False

            # アイテム作成
            item = QListWidgetItem()
            item.setText(f"{path.name}\n{format_file_size(path.stat().st_size)}")
            item.setData(Qt.ItemDataRole.UserRole, image_path)
            
            # サムネイル設定
            if thumbnail:
                # サムネイルサイズを調整
                scaled_thumbnail = thumbnail.scaled(
                    64, 64, 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                item.setIcon(QIcon(scaled_thumbnail))
            
            # ツールチップ設定
            item.setToolTip(f"ファイル: {path.name}\nパス: {image_path}")
            
            self.addItem(item)
            self.logger.info(f"画像をリストに追加: {path.name}")
            return True

        except Exception as e:
            self.logger.error(f"画像リスト追加エラー: {image_path} - {e}")
            return False
    
    def remove_current_image(self):
        """現在選択中の画像を削除"""
        current_item = self.currentItem()
        if current_item:
            image_path = current_item.data(Qt.ItemDataRole.UserRole)
            row = self.row(current_item)
            self.takeItem(row)
            
            if image_path:
                self.image_removed.emit(image_path)
                self.logger.info(f"画像をリストから削除: {Path(image_path).name}")
    
    def clear_all_images(self):
        """すべての画像をクリア"""
        self.clear()
        self.logger.info("画像リストをクリア")
    
    def get_all_image_paths(self) -> List[str]:
        """すべての画像パスを取得"""
        image_paths = []
        for i in range(self.count()):
            item = self.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole):
                image_paths.append(item.data(Qt.ItemDataRole.UserRole))
        return image_paths


class PDFGenerationThread(QThread):
    """PDF生成用ワーカースレッド"""
    
    # シグナル定義
    progress_updated = pyqtSignal(int, str)  # 進捗更新
    generation_finished = pyqtSignal(bool, str)  # 生成完了 (成功/失敗, メッセージ)
    
    def __init__(self, image_paths: List[str], output_path: str, settings: Dict[str, Any]):
        super().__init__()
        self.image_paths = image_paths
        self.output_path = output_path
        self.settings = settings
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """PDF生成実行"""
        try:
            self.progress_updated.emit(0, "PDF生成を開始...")
            
            # PDF生成器を作成
            generator = PDFGenerator()
            generator.progress_updated.connect(self.progress_updated)
            
            # 設定に応じて生成方法を選択
            if self.settings.get('advanced_mode', False):
                # 高度PDF生成
                success = generator.generate_pdf_advanced(
                    self.image_paths,
                    self.output_path,
                    page_size=self.settings.get('page_size', PDF_PAGE_SIZES[PDF_DEFAULTS['page_size']]),
                    margins=self.settings.get('margins', PDF_MARGIN_PRESETS[PDF_DEFAULTS['margin_preset']]),
                    title=self.settings.get('title', ''),
                    author=self.settings.get('author', ''),
                    subject=self.settings.get('subject', ''),
                    fit_to_page=self.settings.get('fit_to_page', PDF_DEFAULTS['fit_to_page']),
                    maintain_aspect_ratio=self.settings.get('maintain_aspect_ratio', PDF_DEFAULTS['maintain_aspect_ratio'])
                )
            else:
                # シンプルPDF生成
                success = generator.generate_pdf_simple(
                    self.image_paths,
                    self.output_path,
                    page_size=self.settings.get('page_size_name', PDF_DEFAULTS['page_size']),
                    fit_to_page=self.settings.get('fit_to_page', PDF_DEFAULTS['fit_to_page'])
                )
            
            if success:
                self.generation_finished.emit(True, f"PDFが正常に生成されました: {self.output_path}")
            else:
                self.generation_finished.emit(False, "PDF生成に失敗しました")
                
        except Exception as e:
            self.logger.error(f"PDF生成スレッドエラー: {e}")
            self.generation_finished.emit(False, f"エラーが発生しました: {e}")


class MainWindow(QMainWindow):
    """メインウィンドウクラス - 単一画面版（リサイズハンドル削除対応）"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # データ
        self.image_processor = ImageProcessor()
        self.pdf_generator = PDFGenerator()
        self.current_images: List[str] = []
        self.settings = QSettings('Image2PDF', 'Image2PDF')
        
        # UI コンポーネント
        self.image_list_widget: Optional[ImageListWidget] = None
        self.crop_widget: Optional[InteractiveImageWidget] = None
        
        # PDF生成スレッド
        self.pdf_thread: Optional[PDFGenerationThread] = None
        
        # 初期化
        self._setup_ui()
        self._connect_signals()
        self._load_settings()
        
        # ウィンドウ設定（リサイズ完全無効化）
        self._setup_window_properties()
        
        self.logger.info("メインウィンドウ初期化完了")
    
    def _setup_window_properties(self):
        """ウィンドウプロパティ設定（リサイズ完全無効化）"""
        # 固定サイズ設定
        self.setFixedSize(1200, 800)
        
        # ウィンドウフラグ設定（最大化ボタン無効化も含む）
        window_flags = (
            Qt.WindowType.Window |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        self.setWindowFlags(window_flags)
        
        # ウィンドウタイトル設定
        self.setWindowTitle("Image2PDF - 画像からPDF変換ツール")
    
    def _setup_ui(self):
        """UI初期化"""
        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # メインレイアウト（水平分割）
        main_layout = QHBoxLayout(central_widget)
        
        # スプリッター
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左パネル（画像リスト）
        left_panel = self._create_left_panel()
        
        # 右パネル（作業エリア）
        right_panel = self._create_right_panel()
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 1000])
        
        main_layout.addWidget(splitter)
    
    def _create_left_panel(self) -> QWidget:
        """左側パネル（画像リスト）作成"""
        panel = CardWidget()
        layout = QVBoxLayout(panel)
        
        # タイトル
        title_label = StrongBodyLabel("画像ファイル")
        layout.addWidget(title_label)
        
        # ボタン群
        button_layout = QHBoxLayout()
        
        self.add_files_btn = PushButton("ファイル追加")
        self.add_files_btn.setIcon(FluentIcon.ADD)
        
        self.remove_file_btn = PushButton("削除")
        self.remove_file_btn.setIcon(FluentIcon.DELETE)
        self.remove_file_btn.setEnabled(False)
        
        self.clear_all_btn = TransparentPushButton("すべてクリア")
        self.clear_all_btn.setIcon(FluentIcon.CANCEL)
        self.clear_all_btn.setEnabled(False)
        
        button_layout.addWidget(self.add_files_btn)
        button_layout.addWidget(self.remove_file_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.clear_all_btn)
        
        layout.addLayout(button_layout)
        
        # 画像リスト
        self.image_list_widget = ImageListWidget()
        layout.addWidget(self.image_list_widget)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """右側パネル（作業エリア）作成"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # タブウィジェット
        tab_widget = QTabWidget()
        
        # プレビュータブ
        preview_tab = self._create_preview_tab()
        tab_widget.addTab(preview_tab, "プレビュー")
        
        # 切り抜きタブ
        crop_tab = self._create_crop_tab()
        tab_widget.addTab(crop_tab, "切り抜き・編集")
        
        # PDF設定タブ
        pdf_tab = self._create_pdf_tab()
        tab_widget.addTab(pdf_tab, "PDF設定")
        
        layout.addWidget(tab_widget)
        
        # PDF生成ボタン（常に表示）
        self.generate_pdf_btn = PrimaryPushButton("PDF生成")
        self.generate_pdf_btn.setIcon(FluentIcon.SAVE)
        self.generate_pdf_btn.setEnabled(False)
        layout.addWidget(self.generate_pdf_btn)
        
        return panel
    
    def _create_preview_tab(self) -> QWidget:
        """プレビュータブ作成"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # プレビューエリア
        preview_card = HeaderCardWidget()
        preview_card.setTitle("画像プレビュー")
        
        self.preview_label = BodyLabel("画像を選択してください")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(400)
        self.preview_label.setStyleSheet("border: 2px dashed #ccc; border-radius: 8px;")
        
        preview_card.viewLayout.addWidget(self.preview_label)
        layout.addWidget(preview_card)
        
        # 画像情報カード
        info_card = HeaderCardWidget()
        info_card.setTitle("画像情報")
        
        self.filename_label = BodyLabel("ファイル: 未選択")
        self.size_label = BodyLabel("サイズ: -")
        self.format_label = BodyLabel("フォーマット: -")
        
        info_card.viewLayout.addWidget(self.filename_label)
        info_card.viewLayout.addWidget(self.size_label)
        info_card.viewLayout.addWidget(self.format_label)
        
        layout.addWidget(info_card)
        
        return tab
    
    def _create_crop_tab(self) -> QWidget:
        """切り抜きタブ作成"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 切り抜きウィジェット
        self.crop_widget = InteractiveImageWidget()
        self.crop_widget.setMinimumHeight(400)
        layout.addWidget(self.crop_widget)
        
        # 切り抜き操作パネル
        crop_control_panel = self._create_crop_control_panel()
        layout.addWidget(crop_control_panel)
        
        return tab
    
    def _create_crop_control_panel(self) -> QWidget:
        """切り抜き操作パネル作成"""
        panel = CardWidget()
        layout = QVBoxLayout(panel)
        
        # タイトル
        title_label = StrongBodyLabel("切り抜き操作")
        layout.addWidget(title_label)
        
        # 回転コントロール
        rotation_layout = QHBoxLayout()
        rotation_layout.addWidget(BodyLabel("回転角度:"))
        
        self.rotation_slider = ComboBox()
        self.rotation_slider.addItems(["0°", "90°", "180°", "270°"])
        rotation_layout.addWidget(self.rotation_slider)
        
        self.rotate_left_btn = PushButton("左90°")
        self.rotate_left_btn.setIcon(FluentIcon.LEFT_ARROW)
        
        self.rotate_right_btn = PushButton("右90°")
        self.rotate_right_btn.setIcon(FluentIcon.RIGHT_ARROW)
        
        rotation_layout.addWidget(self.rotate_left_btn)
        rotation_layout.addWidget(self.rotate_right_btn)
        rotation_layout.addStretch()
        
        layout.addLayout(rotation_layout)
        
        # 切り抜きボタン群
        crop_button_layout = QHBoxLayout()
        
        self.reset_points_btn = PushButton("制御点リセット")
        self.reset_points_btn.setIcon(FluentIcon.SYNC)
        
        self.auto_detect_btn = PushButton("自動検出")
        self.auto_detect_btn.setIcon(FluentIcon.ROBOT)
        
        self.crop_btn = PrimaryPushButton("切り抜き実行")
        self.crop_btn.setIcon(FluentIcon.CUT)
        self.crop_btn.setEnabled(False)
        
        crop_button_layout.addWidget(self.reset_points_btn)
        crop_button_layout.addWidget(self.auto_detect_btn)
        crop_button_layout.addStretch()
        crop_button_layout.addWidget(self.crop_btn)
        
        layout.addLayout(crop_button_layout)
        
        return panel
    
    def _create_pdf_tab(self) -> QWidget:
        """PDF設定タブ作成"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # PDF設定カード
        settings_card = HeaderCardWidget()
        settings_card.setTitle("PDF設定")
        
        # ページサイズ設定
        page_size_layout = QHBoxLayout()
        page_size_layout.addWidget(BodyLabel("ページサイズ:"))
        
        self.page_size_combo = ComboBox()
        self.page_size_combo.addItems(get_pdf_page_size_list())
        self.page_size_combo.setCurrentText("A4")
        
        page_size_layout.addWidget(self.page_size_combo)
        page_size_layout.addStretch()
        
        settings_card.viewLayout.addLayout(page_size_layout)
        
        # マージン設定
        margin_layout = QHBoxLayout()
        margin_layout.addWidget(BodyLabel("マージン:"))
        
        self.margin_preset_combo = ComboBox()
        self.margin_preset_combo.addItems(get_pdf_margin_preset_list())
        self.margin_preset_combo.setCurrentText("標準")
        margin_layout.addWidget(self.margin_preset_combo)
        
        # カスタムマージン入力
        self.margin_top_spinbox = SpinBox()
        self.margin_top_spinbox.setRange(0, 200)
        self.margin_top_spinbox.setValue(28)
        self.margin_top_spinbox.setSuffix(" pt")
        self.margin_top_spinbox.setEnabled(False)
        
        self.margin_right_spinbox = SpinBox()
        self.margin_right_spinbox.setRange(0, 200)
        self.margin_right_spinbox.setValue(28)
        self.margin_right_spinbox.setSuffix(" pt")
        self.margin_right_spinbox.setEnabled(False)
        
        self.margin_bottom_spinbox = SpinBox()
        self.margin_bottom_spinbox.setRange(0, 200) 
        self.margin_bottom_spinbox.setValue(28)
        self.margin_bottom_spinbox.setSuffix(" pt")
        self.margin_bottom_spinbox.setEnabled(False)
        
        self.margin_left_spinbox = SpinBox()
        self.margin_left_spinbox.setRange(0, 200)
        self.margin_left_spinbox.setValue(28)
        self.margin_left_spinbox.setSuffix(" pt")
        self.margin_left_spinbox.setEnabled(False)
        
        margin_layout.addStretch()
        settings_card.viewLayout.addLayout(margin_layout)
        
        # オプション設定
        self.fit_to_page_cb = CheckBox("ページに合わせる")
        self.fit_to_page_cb.setChecked(True)
        
        self.maintain_aspect_cb = CheckBox("アスペクト比を維持")
        self.maintain_aspect_cb.setChecked(True)
        
        settings_card.viewLayout.addWidget(self.fit_to_page_cb)
        settings_card.viewLayout.addWidget(self.maintain_aspect_cb)
        
        layout.addWidget(settings_card)
         
        # PDFメタデータ設定カード
        metadata_card = HeaderCardWidget()
        metadata_card.setTitle("PDFメタデータ")
        
        # タイトル設定
        title_layout = QHBoxLayout()
        title_layout.addWidget(BodyLabel("タイトル:"))
        self.pdf_title_edit = LineEdit()
        self.pdf_title_edit.setPlaceholderText("PDFのタイトルを入力")
        title_layout.addWidget(self.pdf_title_edit)
        metadata_card.viewLayout.addLayout(title_layout)
        
        # 作成者設定
        author_layout = QHBoxLayout()
        author_layout.addWidget(BodyLabel("作成者:"))
        self.pdf_author_edit = LineEdit()
        self.pdf_author_edit.setPlaceholderText("作成者名を入力")
        author_layout.addWidget(self.pdf_author_edit)
        metadata_card.viewLayout.addLayout(author_layout)
        
        # 件名設定
        subject_layout = QHBoxLayout()
        subject_layout.addWidget(BodyLabel("件名:"))
        self.pdf_subject_edit = LineEdit()
        self.pdf_subject_edit.setPlaceholderText("件名を入力")
        subject_layout.addWidget(self.pdf_subject_edit)
        metadata_card.viewLayout.addLayout(subject_layout)
        
        layout.addWidget(metadata_card)
        
        # ファイル名設定カード
        filename_card = HeaderCardWidget()
        filename_card.setTitle("出力設定")
        
        filename_layout = QHBoxLayout()
        filename_layout.addWidget(BodyLabel("ファイル名:"))
        
        self.filename_edit = LineEdit()
        self.filename_edit.setPlaceholderText("出力ファイル名を入力")
        
        self.browse_btn = ToolButton()
        self.browse_btn.setIcon(FluentIcon.FOLDER)
        self.browse_btn.setToolTip("保存場所を選択")
        
        filename_layout.addWidget(self.filename_edit)
        filename_layout.addWidget(self.browse_btn)
        
        filename_card.viewLayout.addLayout(filename_layout)
        layout.addWidget(filename_card)
        
        layout.addStretch()
        
        return tab
    
    def _connect_signals(self):
        """シグナル接続"""
        # 画像リスト
        if self.image_list_widget:
            self.image_list_widget.images_reordered.connect(self._on_images_reordered)
            self.image_list_widget.image_selected.connect(self._on_image_selected)
            self.image_list_widget.image_removed.connect(self._on_image_removed)
        
        # ボタン
        self.add_files_btn.clicked.connect(self._add_files_dialog)
        self.remove_file_btn.clicked.connect(self._remove_current_image)
        self.clear_all_btn.clicked.connect(self._clear_all_images)
        self.generate_pdf_btn.clicked.connect(self._generate_pdf_dialog)
        self.browse_btn.clicked.connect(self._browse_output_location)
        
        # 切り抜き関連
        # マージン設定の連動
        self.margin_preset_combo.currentTextChanged.connect(self._on_margin_preset_changed)
        
        if self.crop_widget:
            self.crop_widget.points_changed.connect(self._on_crop_points_changed)
        
        self.reset_points_btn.clicked.connect(self._reset_crop_points)
        self.auto_detect_btn.clicked.connect(self._auto_detect_contours)
        self.crop_btn.clicked.connect(self._execute_crop)
        
        self.rotate_left_btn.clicked.connect(lambda: self._rotate_image(-90))
        self.rotate_right_btn.clicked.connect(lambda: self._rotate_image(90))
        
        # 画像処理器
        self.image_processor.processing_error.connect(self._on_processing_error)
        
        # PDF生成器
        self.pdf_generator.generation_error.connect(self._on_pdf_generation_error)
    
    def _load_settings(self):
        """設定を読み込み"""
        try:
            # ウィンドウ位置・サイズ
            geometry = self.settings.value('geometry')
            if geometry:
                self.restoreGeometry(geometry)
            
            # PDF設定
            page_size = self.settings.value('pdf/page_size', 'A4')
            self.page_size_combo.setCurrentText(page_size)
            
            fit_to_page = self.settings.value('pdf/fit_to_page', True, type=bool)
            self.fit_to_page_cb.setChecked(fit_to_page)
            
            maintain_aspect = self.settings.value('pdf/maintain_aspect', True, type=bool)
            self.maintain_aspect_cb.setChecked(maintain_aspect)
            
            # マージン設定
            margin_preset = self.settings.value('pdf/margin_preset', '標準')
            self.margin_preset_combo.setCurrentText(margin_preset)
            
            # 最後の出力ディレクトリ
            last_output_dir = self.settings.value('output/last_directory', '')
            if last_output_dir:
                self.last_output_directory = Path(last_output_dir)
            else:
                self.last_output_directory = Path.home() / "Documents"
            
            self.logger.info("設定読み込み完了")
            
        except Exception as e:
            self.logger.error(f"設定読み込みエラー: {e}")
    
    def _save_settings(self):
        """設定を保存"""
        try:
            # ウィンドウ位置・サイズ
            self.settings.setValue('geometry', self.saveGeometry())
            
            # PDF設定
            self.settings.setValue('pdf/page_size', self.page_size_combo.currentText())
            self.settings.setValue('pdf/fit_to_page', self.fit_to_page_cb.isChecked())
            self.settings.setValue('pdf/maintain_aspect', self.maintain_aspect_cb.isChecked())
            self.settings.setValue('pdf/margin_preset', self.margin_preset_combo.currentText())
            
            # 最後の出力ディレクトリ
            if hasattr(self, 'last_output_directory'):
                self.settings.setValue('output/last_directory', str(self.last_output_directory))
            
            self.logger.info("設定保存完了")
            
        except Exception as e:
            self.logger.error(f"設定保存エラー: {e}")
    
    def closeEvent(self, event: QCloseEvent):
        """ウィンドウ閉じるイベント"""
        # 進行中のタスクがある場合は確認
        if self.pdf_thread and self.pdf_thread.isRunning():
            reply = MessageBox(
                "確認", 
                "PDF生成が進行中です。アプリケーションを終了しますか？",
                self
            ).exec()
            
            if not reply:
                event.ignore()
                return
            
            # スレッドを終了
            self.pdf_thread.terminate()
            self.pdf_thread.wait(3000)  # 3秒待機
        
        # 設定を保存
        self._save_settings()
        
        event.accept()
        self.logger.info("アプリケーション終了")
    
    def add_images(self, image_paths: List[str]):
        """画像を追加"""
        try:
            added_count = 0
            failed_count = 0
            
            for image_path in image_paths:
                if is_image_file(image_path) and image_path not in self.current_images:
                    # サムネイル生成
                    thumbnail = self._generate_thumbnail(image_path)
                    
                    # リストに追加
                    if self.image_list_widget.add_image(image_path, thumbnail):
                        self.current_images.append(image_path)
                        added_count += 1
                    else:
                        failed_count += 1
                        self.logger.warning(f"画像リストへの追加に失敗: {image_path}")
            
            if added_count > 0:
                self._update_ui_state()
                InfoBar.success(
                    title="画像追加完了",
                    content=f"{added_count} 個の画像を追加しました",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )
            
            if failed_count > 0:
                InfoBar.warning(
                    title="画像追加警告",
                    content=f"{failed_count} 個の画像の追加に失敗しました",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=5000,
                    parent=self
                )
            
            self.logger.info(f"画像追加: {added_count} 個")
            
        except Exception as e:
            self.logger.error(f"画像追加エラー: {e}")
            InfoBar.error(
                title="エラー",
                content=f"画像追加でエラーが発生しました: {e}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )
    
    def _generate_thumbnail(self, image_path: str) -> Optional[QPixmap]:
        """サムネイル生成"""
        try:
            from .utils import load_image_safely
            
            pixmap = load_image_safely(image_path)
            if pixmap:
                return pixmap.scaled(
                    64, 64, 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            return None
            
        except Exception as e:
            self.logger.error(f"サムネイル生成エラー: {image_path} - {e}")
            return None
    
    def update_ui_state(self):
        self._update_ui_state()
    
    def _update_ui_state(self):
        """UI状態を更新"""
        current_item = self.image_list_widget.currentItem()
        has_images = len(self.current_images) > 0
        has_selection = current_item is not None and current_item.data(Qt.ItemDataRole.UserRole) is not None
        
        # ボタン状態
        self.remove_file_btn.setEnabled(has_selection)
        self.clear_all_btn.setEnabled(has_images)
        self.generate_pdf_btn.setEnabled(has_images)
        
        # 切り抜き関連ボタン
        self.reset_points_btn.setEnabled(has_selection)
        self.auto_detect_btn.setEnabled(has_selection)
        
        # デフォルトファイル名設定
        if has_images and not self.filename_edit.text():
            self.filename_edit.setText("output.pdf")
    
    def _on_margin_preset_changed(self, preset_name: str):
        """マージンプリセット変更時の処理"""
        is_custom = preset_name == 'カスタム'
        
        # カスタムマージン入力の有効/無効切り替え
        self.margin_top_spinbox.setEnabled(is_custom)
        self.margin_right_spinbox.setEnabled(is_custom)
        self.margin_bottom_spinbox.setEnabled(is_custom)
        self.margin_left_spinbox.setEnabled(is_custom)
        
        # プリセット値を設定
        if not is_custom and preset_name in PDF_MARGIN_PRESETS:
            margins = PDF_MARGIN_PRESETS[preset_name]
            if margins:
                top, right, bottom, left = margins
                self.margin_top_spinbox.setValue(top)
                self.margin_right_spinbox.setValue(right)
                self.margin_bottom_spinbox.setValue(bottom)
                self.margin_left_spinbox.setValue(left)
    
    def _get_current_margins(self) -> Tuple[float, float, float, float]:
        """現在のマージン設定を取得"""
        return (
            self.margin_top_spinbox.value(),
            self.margin_right_spinbox.value(),
            self.margin_bottom_spinbox.value(),
            self.margin_left_spinbox.value()
        )
    
    # イベントハンドラー
    def _add_files_dialog(self):
        """ファイル追加ダイアログ"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "画像ファイルを選択",
            str(self.last_output_directory),
            get_image_filter_string()
        )
        
        if files:
            self.add_images(files)
    
    def _remove_current_image(self):
        """現在選択中の画像を削除"""
        self.image_list_widget.remove_current_image()
    
    def _clear_all_images(self):
        """すべての画像をクリア"""
        reply = MessageBox(
            "確認",
            "すべての画像をクリアします。よろしいですか？",
            self
        ).exec()
        
        if reply:
            self.image_list_widget.clear_all_images()
            self.current_images.clear()
            self._update_ui_state()
            
            # プレビューをクリア
            self.preview_label.clear()
            self.preview_label.setText("画像を選択してください")
            
            # 切り抜きウィジェットをクリア
            if self.crop_widget:
                self.crop_widget.original_pixmap = None
                self.crop_widget.display_pixmap = None
                self.crop_widget.control_points = []
                self.crop_widget.update()
    
    def _browse_output_location(self):
        """出力場所選択"""
        # デフォルトファイル名を生成
        default_name = "output.pdf"
        if self.current_images:
            # 最初の画像ファイル名を基にする
            first_image = Path(self.current_images[0])
            default_name = f"{first_image.stem}.pdf"
        
        default_path = self.last_output_directory / default_name
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "PDFファイル保存場所を選択", 
            str(default_path),
            "PDF files (*.pdf);;All files (*.*)"
        )
        
        if filename:
            # パスを検証・準備
            success, validated_path, error_msg = validate_and_prepare_output_path(filename)
            
            if success:
                self.filename_edit.setText(str(validated_path))
                self.last_output_directory = validated_path.parent
            else:
                InfoBar.error(
                    title="パスエラー",
                    content=error_msg,
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=5000,
                    parent=self
                )
    
    def _generate_pdf_dialog(self):
        """PDF生成実行"""
        try:
            if not self.current_images:
                InfoBar.warning(
                    title="警告",
                    content="画像が選択されていません",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )
                return
            
            # 出力ファイル名を取得・検証
            output_path = self.filename_edit.text().strip()
            if not output_path:
                InfoBar.warning(
                    title="警告", 
                    content="出力ファイル名を入力してください",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )
                return
            
            # パスを検証・準備
            success, validated_path, error_msg = validate_and_prepare_output_path(output_path)
            
            if not success:
                InfoBar.error(
                    title="パスエラー",
                    content=error_msg,
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=5000,
                    parent=self
                )
                return
            
            # ファイル上書き確認
            needs_overwrite, overwrite_msg = check_file_overwrite(validated_path)
            if needs_overwrite:
                reply = MessageBox(
                    "ファイル上書き確認",
                    overwrite_msg,
                    self
                ).exec()
                
                if not reply:
                    return  # ユーザーがキャンセル
            
            # 最終的な出力パスを設定
            final_output_path = str(validated_path)
            
            # 現在のマージン設定を取得
            margins = self._get_current_margins()
            
            # ページサイズを取得
            page_size_name = self.page_size_combo.currentText()
            page_size = PDF_PAGE_SIZES.get(page_size_name, PDF_PAGE_SIZES[PDF_DEFAULTS['page_size']])
            
            pdf_settings = {
                'page_size_name': self.page_size_combo.currentText(),
                'page_size': page_size,
                'margins': margins,
                'fit_to_page': self.fit_to_page_cb.isChecked(),
                'maintain_aspect_ratio': self.maintain_aspect_cb.isChecked(),
                'advanced_mode': 'advanced',
                'title': self.pdf_title_edit.text().strip(),
                'author': self.pdf_author_edit.text().strip(),
                'subject': self.pdf_subject_edit.text().strip(),
                'creator': PDF_DEFAULTS['creator']
            }
            
            # PDF生成スレッドを開始
            self._start_pdf_generation(final_output_path, pdf_settings)
            
        except Exception as e:
            self.logger.error(f"PDF生成開始エラー: {e}")
            InfoBar.error(
                title="エラー",
                content=f"PDF生成でエラーが発生しました: {e}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )
    
    def _start_pdf_generation(self, output_path: str, settings: Dict[str, Any]):
        """PDF生成開始"""
        try:
            self.state_tooltip = StateToolTip("PDF生成中", "しばらくお待ちください...", self)
            self.state_tooltip.show()
            
            # UI無効化
            self.generate_pdf_btn.setEnabled(False)
            
            # PDF生成スレッド作成・開始
            self.pdf_thread = PDFGenerationThread(
                self.current_images.copy(),
                output_path,
                settings
            )
            
            self.pdf_thread.progress_updated.connect(self._on_pdf_progress)
            self.pdf_thread.generation_finished.connect(self._on_pdf_generation_finished)
            self.pdf_thread.start()
            
            self.logger.info(f"PDF生成開始: {output_path}")
            
        except Exception as e:
            self.logger.error(f"PDF生成スレッド開始エラー: {e}")
            self._cleanup_pdf_generation()
            raise
    
    def _on_pdf_progress(self, progress: int, message: str):
        if hasattr(self, 'state_tooltip'):
            self.state_tooltip.setContent(f"{message} ({progress}%)")
    
    def _on_pdf_generation_finished(self, success: bool, message: str):
        """PDF生成完了"""
        self._cleanup_pdf_generation()
        
        if success:
            InfoBar.success(
                title="PDF生成完了",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )
            
            # ファイルを開くか確認
            reply = MessageBox(
                "PDF生成完了",
                f"{message}\n\nファイルを開きますか？",
                self
            ).exec()
            
            if reply:
                os.startfile(Path(message.split(": ")[1]))  # Windows
        else:
            InfoBar.error(
                title="PDF生成失敗",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )
    
    def _cleanup_pdf_generation(self):
        """PDF生成関連のクリーンアップ"""
        if hasattr(self, 'state_tooltip'):
            self.state_tooltip.setState(True)
            delattr(self, 'state_tooltip')
        
        self.generate_pdf_btn.setEnabled(True)
        
        if self.pdf_thread:
            self.pdf_thread = None
    
    # 画像関連イベントハンドラー
    def _on_images_reordered(self, image_paths: List[str]):
        """画像順序変更時の処理"""
        self.current_images = image_paths
        self.logger.info("画像順序を変更")
    
    def _on_image_selected(self, image_path: str):
        """画像選択時の処理"""
        try:
            # プレビュー更新
            thumbnail = self._generate_thumbnail(image_path)
            if thumbnail:
                # プレビューサイズに調整
                preview_pixmap = thumbnail.scaled(
                    400, 400,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.preview_label.setPixmap(preview_pixmap)
                self.preview_label.setText("")
            
            # 画像情報更新
            self._update_image_info(image_path)
            
            # 切り抜きウィジェットに画像を設定
            if self.crop_widget:
                self.crop_widget.set_image(image_path)
            
            # UI状態を強制的に更新
            self._update_ui_state()
            
        except Exception as e:
            self.logger.error(f"画像選択処理エラー: {image_path} - {e}")
    
    def _update_image_info(self, image_path: str):
        """画像情報を更新"""
        try:
            path = Path(image_path)
            
            # ファイル情報
            self.filename_label.setText(f"ファイル: {path.name}")
            self.format_label.setText(f"フォーマット: {path.suffix.upper().lstrip('.')}")
            
            # 画像サイズ情報
            pixmap = self._generate_thumbnail(image_path)
            if pixmap:
                # 元画像のサイズを取得（概算）
                from .utils import load_image_safely
                original_pixmap = load_image_safely(image_path)
                if original_pixmap:
                    width = original_pixmap.width()
                    height = original_pixmap.height()
                    self.size_label.setText(f"サイズ: {width} × {height}")
                else:
                    self.size_label.setText("サイズ: 不明")
            else:
                self.size_label.setText("サイズ: 不明")
                
        except Exception as e:
            self.logger.error(f"画像情報更新エラー: {e}")
    
    def _on_image_removed(self, image_path: str):
        """画像削除時の処理"""
        if image_path in self.current_images:
            self.current_images.remove(image_path)
        
        # プレビューをクリア
        self.preview_label.clear()
        self.preview_label.setText("画像を選択してください")
        
        # 画像情報をクリア
        self.filename_label.setText("ファイル: 未選択")
        self.size_label.setText("サイズ: -")
        self.format_label.setText("フォーマット: -")
        
        self._update_ui_state()
    
    # 切り抜き関連イベントハンドラー
    def _on_crop_points_changed(self, points: List):
        """切り抜き制御点変更時の処理"""
        has_four_points = len(points) == 4
        self.crop_btn.setEnabled(has_four_points)
    
    def _reset_crop_points(self):
        """切り抜き制御点をリセット"""
        if self.crop_widget:
            self.crop_widget.reset_points()
    
    def _auto_detect_contours(self):
        """自動輪郭検出"""
        try:
            current_item = self.image_list_widget.currentItem()
            if not current_item:
                MessageBox("警告", "画像を選択してください", self).exec()
                return
            
            image_path = current_item.data(Qt.ItemDataRole.UserRole)
            
            # OpenCVで画像を読み込み
            import cv2
            import numpy as np
            
            image = cv2.imread(image_path)
            if image is None:
                MessageBox("エラー", "画像の読み込みに失敗しました", self).exec()
                return
            
            # グレースケール変換
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # ガウシアンブラー
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # エッジ検出
            edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
            
            # 輪郭検出
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                MessageBox("情報", "文書の輪郭を検出できませんでした", self).exec()
                return
            
            # 最大面積の輪郭を選択
            largest_contour = max(contours, key=cv2.contourArea)
            
            # 輪郭を4点に近似
            epsilon = 0.02 * cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, epsilon, True)
            
            if len(approx) == 4:
                # 4点が検出された場合
                points = [(int(point[0][0]), int(point[0][1])) for point in approx]
                if self.crop_widget:
                    self.crop_widget.set_crop_points(points)
                MessageBox("成功", "文書の輪郭を自動検出しました", self).exec()
            else:
                # 4点でない場合は画像の四隅に設定
                height, width = image.shape[:2]
                margin = min(width, height) // 20
                points = [
                    (margin, margin),
                    (width - margin, margin),
                    (width - margin, height - margin),
                    (margin, height - margin)
                ]
                if self.crop_widget:
                    self.crop_widget.set_crop_points(points)
                MessageBox("情報", "4角形の輪郭が検出できなかったため、デフォルトの範囲を設定しました", self).exec()
            
        except Exception as e:
            self.logger.error(f"自動検出エラー: {e}")
            MessageBox("エラー", f"自動検出でエラーが発生しました:\n{e}", self).exec()
    
    def _execute_crop(self):
        """切り抜き実行"""
        try:
            current_item = self.image_list_widget.currentItem()
            if not current_item:
                MessageBox("警告", "画像を選択してください", self).exec()
                return
            
            image_path = current_item.data(Qt.ItemDataRole.UserRole)
            
            if not self.crop_widget:
                MessageBox("エラー", "切り抜きウィジェットが初期化されていません", self).exec()
                return
            
            # 制御点を取得
            crop_points = self.crop_widget.get_crop_points_in_image_coordinates()
            if len(crop_points) != 4:
                MessageBox("警告", "4つの制御点を設定してください", self).exec()
                return
            
            # 画像処理を実行
            import cv2
            
            image = cv2.imread(image_path)
            if image is None:
                MessageBox("エラー", "画像の読み込みに失敗しました", self).exec()
                return
            
            # 回転を適用（必要に応じて）
            rotation_angle = 0
            rotation_text = self.rotation_slider.currentText()
            if rotation_text == "90°":
                rotation_angle = 90
            elif rotation_text == "180°":
                rotation_angle = 180
            elif rotation_text == "270°":
                rotation_angle = 270
            
            if rotation_angle != 0:
                working_image = self.image_processor.rotate_image(image, rotation_angle)
            else:
                working_image = image
            
            # 4点切り抜きを実行
            cropped_image = self.image_processor.crop_image_with_four_points(working_image, crop_points)
            
            if cropped_image is not None:
                # 切り抜かれた画像を一時ファイルとして保存
                temp_dir = get_temp_dir()
                temp_path = temp_dir / f"cropped_image_{len(self.current_images)}.jpg"
                
                cv2.imwrite(str(temp_path), cropped_image)
                
                # 画像リストに追加
                self.add_images([str(temp_path)])
                
                InfoBar.success(
                    title="切り抜き完了",
                    content="切り抜かれた画像をリストに追加しました",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )
            else:
                MessageBox("エラー", "切り抜き処理に失敗しました", self).exec()
            
        except Exception as e:
            self.logger.error(f"切り抜き実行エラー: {e}")
            MessageBox("エラー", f"切り抜き処理でエラーが発生しました:\n{e}", self).exec()
    
    def _rotate_image(self, angle: int):
        """画像回転"""
        current_rotation = self.rotation_slider.currentText()
        current_angle = 0
        if current_rotation == "90°":
            current_angle = 90
        elif current_rotation == "180°":
            current_angle = 180
        elif current_rotation == "270°":
            current_angle = 270
        
        new_angle = (current_angle + angle) % 360
        
        if new_angle == 0:
            self.rotation_slider.setCurrentText("0°")
        elif new_angle == 90:
            self.rotation_slider.setCurrentText("90°")
        elif new_angle == 180:
            self.rotation_slider.setCurrentText("180°")
        elif new_angle == 270:
            self.rotation_slider.setCurrentText("270°")
    
    # エラーハンドラー
    def _on_processing_error(self, operation: str, error_message: str):
        """画像処理エラー時の処理"""
        InfoBar.error(
            title="画像処理エラー",
            content=f"{operation}: {error_message}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self
        )
    
    def _on_pdf_generation_error(self, error_message: str):
        """PDF生成エラー時の処理"""
        self._cleanup_pdf_generation()
        InfoBar.error(
            title="PDF生成エラー",
            content=error_message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self
        )
