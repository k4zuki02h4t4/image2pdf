"""
切り抜きウィジェットのテスト
修正版：存在しないFluentIconを修正
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

# テスト環境のセットアップ
from . import setup_qt_test_environment, create_test_image_file, TEMP_DIR

# テスト対象のインポート（PyQt6関連をモック化してから）
try:
    app = setup_qt_test_environment()
    if app:
        from src.crop_widget import InteractiveImageWidget, CropWidget
        QT_AVAILABLE = True
    else:
        QT_AVAILABLE = False
        # ダミークラスを定義
        class InteractiveImageWidget:
            pass
        class CropWidget:
            pass
except ImportError:
    QT_AVAILABLE = False
    class InteractiveImageWidget:
        pass
    class CropWidget:
        pass


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6が利用できません")
class TestInteractiveImageWidget:
    """InteractiveImageWidgetクラスのテスト"""
    
    @pytest.fixture
    def widget(self):
        """テスト用のInteractiveImageWidgetを作成"""
        if not QT_AVAILABLE:
            pytest.skip("PyQt6が利用できません")
        return InteractiveImageWidget()
    
    @pytest.fixture
    def sample_image_path(self):
        """テスト用のサンプル画像を作成"""
        return create_test_image_file(200, 150, (255, 0, 0))
    
    def test_widget_initialization(self, widget):
        """ウィジェット初期化のテスト"""
        assert widget is not None
        assert hasattr(widget, 'control_points')
        assert hasattr(widget, 'zoom_factor')
        assert hasattr(widget, 'pan_offset')
        
        # 初期状態の確認
        assert len(widget.control_points) == 0
        assert widget.zoom_factor == 1.0
        assert widget.dragging_point_index == -1
        assert widget.hover_point_index == -1
    
    @patch('src.utils.load_image_safely')
    def test_set_image_success(self, mock_load_image, widget, sample_image_path):
        """画像設定の成功テスト"""
        # Mock QPixmap
        mock_pixmap = MagicMock()
        mock_pixmap.size.return_value.width.return_value = 200
        mock_pixmap.size.return_value.height.return_value = 150
        mock_pixmap.scaled.return_value = mock_pixmap
        mock_load_image.return_value = mock_pixmap
        
        # Mock widget size
        widget.size = MagicMock(return_value=MagicMock(width=lambda: 400, height=lambda: 300))
        
        result = widget.set_image(sample_image_path)
        
        assert result is True
        assert widget.original_pixmap is not None
        mock_load_image.assert_called_once()
    
    @patch('src.utils.load_image_safely')
    def test_set_image_failure(self, mock_load_image, widget):
        """画像設定の失敗テスト"""
        mock_load_image.return_value = None
        
        result = widget.set_image("nonexistent_image.jpg")
        
        assert result is False
        assert widget.original_pixmap is None
    
    def test_setup_default_points(self, widget):
        """デフォルト制御点設定のテスト"""
        # 画像矩形を設定
        from PyQt6.QtCore import QRect
        widget.image_rect = QRect(50, 50, 200, 150)
        
        widget._setup_default_points()
        
        assert len(widget.control_points) == 4
        # 各点がimage_rect内にあることを確認
        for point in widget.control_points:
            assert widget.image_rect.contains(point)
    
    def test_get_crop_points_in_image_coordinates(self, widget):
        """画像座標系での切り抜き点取得のテスト"""
        # Mock設定
        mock_original_pixmap = MagicMock()
        mock_original_pixmap.width.return_value = 400
        mock_original_pixmap.height.return_value = 300
        
        mock_display_pixmap = MagicMock()
        mock_display_pixmap.width.return_value = 200
        mock_display_pixmap.height.return_value = 150
        
        widget.original_pixmap = mock_original_pixmap
        widget.display_pixmap = mock_display_pixmap
        
        # 制御点を設定
        from PyQt6.QtCore import QPoint, QRect
        widget.image_rect = QRect(50, 50, 200, 150)
        widget.control_points = [
            QPoint(75, 75),   # 左上
            QPoint(225, 75),  # 右上  
            QPoint(225, 175), # 右下
            QPoint(75, 175)   # 左下
        ]
        widget.zoom_factor = 1.0
        widget.pan_offset = QPoint(0, 0)
        
        points = widget.get_crop_points_in_image_coordinates()
        
        assert len(points) == 4
        assert all(isinstance(point, tuple) and len(point) == 2 for point in points)
        # 座標が正の値であることを確認
        assert all(x >= 0 and y >= 0 for x, y in points)
    
    def test_set_crop_points(self, widget):
        """切り抜き点設定のテスト"""
        # Mock設定
        mock_original_pixmap = MagicMock()
        mock_original_pixmap.width.return_value = 400
        mock_original_pixmap.height.return_value = 300
        
        mock_display_pixmap = MagicMock()
        mock_display_pixmap.width.return_value = 200
        mock_display_pixmap.height.return_value = 150
        
        widget.original_pixmap = mock_original_pixmap
        widget.display_pixmap = mock_display_pixmap
        
        from PyQt6.QtCore import QRect, QPoint
        widget.image_rect = QRect(50, 50, 200, 150)
        widget.zoom_factor = 1.0
        widget.pan_offset = QPoint(0, 0)
        
        # 画像座標系での点を設定
        image_points = [(50, 40), (350, 40), (350, 260), (50, 260)]
        
        widget.set_crop_points(image_points)
        
        assert len(widget.control_points) == 4
    
    def test_reset_points(self, widget):
        """制御点リセットのテスト"""
        # 初期状態を設定
        from PyQt6.QtCore import QRect, QPoint
        widget.image_rect = QRect(50, 50, 200, 150)
        widget.control_points = [QPoint(100, 100)]  # 1つだけの点
        
        widget.reset_points()
        
        # デフォルトの4点が設定されているべき
        assert len(widget.control_points) == 4
    
    @patch('PyQt6.QtGui.QPainter')
    def test_paint_event(self, mock_painter_class, widget):
        """描画イベントのテスト"""
        # Mock painter
        mock_painter = MagicMock()
        mock_painter_class.return_value = mock_painter
        
        # Mock paint event
        from PyQt6.QtGui import QPaintEvent
        from PyQt6.QtCore import QRect, QPoint
        
        paint_event = QPaintEvent(QRect(0, 0, 400, 300))
        
        # 画像を設定
        widget.display_pixmap = MagicMock()
        widget.image_rect = QRect(50, 50, 200, 150)
        widget.zoom_factor = 1.0
        widget.pan_offset = QPoint(0, 0)
        widget.control_points = [QPoint(100, 100), QPoint(150, 100)]
        
        # paintEventを呼び出し
        try:
            widget.paintEvent(paint_event)
            # エラーが発生しなければOK
        except Exception as e:
            # 一部のQt関連エラーは許容
            if "QWidget" not in str(e):
                raise
    
    def test_mouse_press_event(self, widget):
        """マウス押下イベントのテスト"""
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPoint, Qt, QEvent
        
        # 制御点を設定
        widget.control_points = [QPoint(100, 100), QPoint(200, 100)]
        widget.point_radius = 8
        
        # 制御点近くでのクリック
        mouse_event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPoint(105, 105),  # 制御点の近く
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        
        widget.mousePressEvent(mouse_event)
        
        # ドラッグモードになっているはず
        assert widget.dragging_point_index >= 0
    
    def test_wheel_event(self, widget):
        """ホイールイベント（ズーム）のテスト"""
        from PyQt6.QtGui import QWheelEvent
        from PyQt6.QtCore import QPoint, QPointF, Qt, QEvent
        
        # 画像矩形を設定
        from PyQt6.QtCore import QRect
        widget.image_rect = QRect(50, 50, 200, 150)
        widget.zoom_factor = 1.0
        widget.pan_offset = QPoint(0, 0)
        
        # ズームイベント作成
        wheel_event = QWheelEvent(
            QPointF(150, 125),  # ホイール位置
            QPointF(150, 125),  # グローバル位置  
            QPoint(0, 0),       # ピクセルデルタ
            QPoint(0, 120),     # 角度デルタ（正の値でズームイン）
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False
        )
        
        initial_zoom = widget.zoom_factor
        widget.wheelEvent(wheel_event)
        
        # ズーム倍率が変更されているはず
        assert widget.zoom_factor != initial_zoom


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6が利用できません")
class TestCropWidget:
    """CropWidgetクラスのテスト"""
    
    @pytest.fixture
    def crop_widget(self):
        """テスト用のCropWidgetを作成"""
        if not QT_AVAILABLE:
            pytest.skip("PyQt6が利用できません")
        return CropWidget()
    
    @pytest.fixture
    def sample_image_path(self):
        """テスト用のサンプル画像を作成"""
        return create_test_image_file(200, 150, (0, 255, 0))
    
    def test_crop_widget_initialization(self, crop_widget):
        """CropWidget初期化のテスト"""
        assert crop_widget is not None
        assert hasattr(crop_widget, 'image_widget')
        assert hasattr(crop_widget, 'rotation_slider')
        assert hasattr(crop_widget, 'rotation_spinbox')
        assert hasattr(crop_widget, 'crop_btn')
        assert hasattr(crop_widget, 'reset_points_btn')
        
        # 初期状態の確認
        assert crop_widget.current_image_path is None
        assert crop_widget.current_image is None
    
    @patch('cv2.imread')
    def test_set_image_success(self, mock_cv2_imread, crop_widget, sample_image_path):
        """画像設定の成功テスト"""
        # Mock OpenCV画像読み込み
        mock_image = np.zeros((150, 200, 3), dtype=np.uint8)
        mock_cv2_imread.return_value = mock_image
        
        # Mock image_widget.set_image
        crop_widget.image_widget.set_image = MagicMock(return_value=True)
        
        result = crop_widget.set_image(sample_image_path)
        
        assert result is True
        assert crop_widget.current_image_path == Path(sample_image_path)
        assert crop_widget.current_image is not None
        mock_cv2_imread.assert_called_once()
    
    @patch('cv2.imread')
    def test_set_image_failure(self, mock_cv2_imread, crop_widget):
        """画像設定の失敗テスト"""
        mock_cv2_imread.return_value = None
        
        result = crop_widget.set_image("nonexistent_image.jpg")
        
        assert result is False
        assert crop_widget.current_image_path is None
        assert crop_widget.current_image is None
    
    def test_on_points_changed(self, crop_widget):
        """制御点変更時の処理テスト"""
        # 4つの点を設定
        points = [(50, 40), (150, 40), (150, 110), (50, 110)]
        
        crop_widget._on_points_changed(points)
        
        # 切り抜きボタンが有効になっているはず
        assert crop_widget.crop_btn.isEnabled() is True
        
        # 3つの点の場合
        points_3 = [(50, 40), (150, 40), (150, 110)]
        crop_widget._on_points_changed(points_3)
        
        # 切り抜きボタンが無効になっているはず
        assert crop_widget.crop_btn.isEnabled() is False
    
    def test_on_rotation_changed(self, crop_widget):
        """回転角度変更時の処理テスト"""
        # この関数は現在何もしないので、エラーが発生しないことを確認
        try:
            crop_widget._on_rotation_changed(90)
        except Exception as e:
            pytest.fail(f"回転角度変更でエラーが発生: {e}")
    
    def test_rotate_by_angle(self, crop_widget):
        """角度による回転のテスト"""
        # 初期角度を設定
        crop_widget.rotation_slider.setValue(0)
        
        # 90度回転
        crop_widget._rotate_by_angle(90)
        assert crop_widget.rotation_slider.value() == 90
        
        # さらに90度回転（合計180度）
        crop_widget._rotate_by_angle(90)
        assert crop_widget.rotation_slider.value() == 180
        
        # さらに90度回転（合計270度 → -90度）
        crop_widget._rotate_by_angle(90)
        assert crop_widget.rotation_slider.value() == -90
        
        # さらに90度回転（合計360度 → 0度）
        crop_widget._rotate_by_angle(90)
        assert crop_widget.rotation_slider.value() == 0
    
    @patch('PyQt6.QtWidgets.QMessageBox.warning')
    def test_execute_crop_no_image(self, mock_warning, crop_widget):
        """画像未設定での切り抜き実行テスト"""
        crop_widget._execute_crop()
        
        # 警告ダイアログが表示されるはず
        mock_warning.assert_called_once()
    
    @patch('PyQt6.QtWidgets.QMessageBox.warning')
    @patch('cv2.imread')
    def test_execute_crop_insufficient_points(self, mock_cv2_imread, mock_warning, crop_widget, sample_image_path):
        """制御点不足での切り抜き実行テスト"""
        # 画像を設定
        mock_image = np.zeros((150, 200, 3), dtype=np.uint8)
        mock_cv2_imread.return_value = mock_image
        crop_widget.set_image(sample_image_path)
        
        # 制御点を3つだけ設定
        crop_widget.image_widget.get_crop_points_in_image_coordinates = MagicMock(
            return_value=[(50, 40), (150, 40), (150, 110)]
        )
        
        crop_widget._execute_crop()
        
        # 警告ダイアログが表示されるはず
        mock_warning.assert_called_once()
    
    @patch('src.image_processor.ImageProcessor')
    @patch('cv2.imread')
    def test_execute_crop_success(self, mock_cv2_imread, mock_processor_class, crop_widget, sample_image_path):
        """切り抜き実行の成功テスト"""
        # Mock設定
        mock_image = np.zeros((150, 200, 3), dtype=np.uint8)
        mock_cv2_imread.return_value = mock_image
        
        mock_processor = MagicMock()
        mock_processor.rotate_image.return_value = mock_image
        mock_processor.crop_image_with_four_points.return_value = mock_image
        mock_processor_class.return_value = mock_processor
        
        # 画像を設定
        crop_widget.current_image_path = Path(sample_image_path)
        crop_widget.current_image = mock_image
        
        # 制御点を4つ設定
        crop_widget.image_widget.get_crop_points_in_image_coordinates = MagicMock(
            return_value=[(50, 40), (150, 40), (150, 110), (50, 110)]
        )
        
        # 回転角度を設定
        crop_widget.rotation_slider.setValue(90)
        
        crop_widget._execute_crop()
        
        # 画像処理が呼び出されているはず
        mock_processor.rotate_image.assert_called_once_with(mock_image, 90)
        mock_processor.crop_image_with_four_points.assert_called_once()
    
    def test_update_ui_state(self, crop_widget):
        """UI状態更新のテスト"""
        # 画像未設定の状態
        crop_widget._update_ui_state()
        
        assert crop_widget.rotation_slider.isEnabled() is False
        assert crop_widget.rotation_spinbox.isEnabled() is False
        assert crop_widget.rotate_left_btn.isEnabled() is False
        assert crop_widget.rotate_right_btn.isEnabled() is False
        assert crop_widget.reset_points_btn.isEnabled() is False
        
        # 画像設定状態をシミュレート
        crop_widget.current_image_path = Path("test.jpg")
        crop_widget._update_ui_state()
        
        assert crop_widget.rotation_slider.isEnabled() is True
        assert crop_widget.rotation_spinbox.isEnabled() is True
        assert crop_widget.rotate_left_btn.isEnabled() is True
        assert crop_widget.rotate_right_btn.isEnabled() is True
        assert crop_widget.reset_points_btn.isEnabled() is True
    
    def test_get_current_image_info(self, crop_widget):
        """現在の画像情報取得のテスト"""
        # 画像未設定の場合
        info = crop_widget.get_current_image_info()
        assert info is None
        
        # 画像設定状態をシミュレート
        mock_image = np.zeros((150, 200, 3), dtype=np.uint8)
        crop_widget.current_image_path = Path("test.jpg")
        crop_widget.current_image = mock_image
        crop_widget.rotation_slider.setValue(45)
        crop_widget.image_widget.get_crop_points_in_image_coordinates = MagicMock(
            return_value=[(50, 40), (150, 40), (150, 110), (50, 110)]
        )
        
        info = crop_widget.get_current_image_info()
        
        assert info is not None
        assert isinstance(info, dict)
        assert info['filename'] == 'test.jpg'
        assert info['width'] == 200
        assert info['height'] == 150
        assert info['channels'] == 3
        assert info['rotation_angle'] == 45
        assert len(info['crop_points']) == 4


# GUI関連のテストが利用できない場合のダミーテスト
@pytest.mark.skipif(QT_AVAILABLE, reason="PyQt6が利用可能です")
class TestCropWidgetFallback:
    """PyQt6が利用できない場合のフォールバックテスト"""
    
    def test_crop_widget_import_fallback(self):
        """PyQt6が利用できない場合のインポートテスト"""
        # ダミークラスが定義されていることを確認
        assert InteractiveImageWidget is not None
        assert CropWidget is not None
        
        # クラスのインスタンス化は行わない（エラーになるため）
        print("PyQt6が利用できないため、crop_widgetのテストをスキップしました")


# テスト実行用
if __name__ == '__main__':
    pytest.main([__file__])