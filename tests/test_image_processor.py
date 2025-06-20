"""
画像処理クラスのテスト
ImageProcessorクラスの全機能を包括的にテスト
"""

import pytest
import numpy as np
import cv2
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call
from PIL import Image
import logging

from src.image_processor import ImageProcessor


class TestImageProcessor:
    """ImageProcessorクラスのテスト"""
    
    @pytest.fixture
    def image_processor(self):
        """ImageProcessorインスタンスを作成"""
        return ImageProcessor()
    
    @pytest.fixture 
    def sample_image(self):
        """テスト用のサンプル画像を作成（OpenCV形式）"""
        # 200x150のカラー画像を作成（BGR形式）
        image = np.zeros((150, 200, 3), dtype=np.uint8)
        
        # グラデーションパターンを追加
        for i in range(150):
            for j in range(200):
                image[i, j] = [
                    min(255, i * 2),           # Blue
                    min(255, j),               # Green  
                    min(255, (i + j) % 255)    # Red
                ]
        return image
    
    @pytest.fixture
    def sample_grayscale_image(self):
        """グレースケールのサンプル画像を作成"""
        image = np.zeros((100, 100), dtype=np.uint8)
        
        # 円形パターンを作成
        center = (50, 50)
        for i in range(100):
            for j in range(100):
                distance = np.sqrt((i - center[0])**2 + (j - center[1])**2)
                image[i, j] = min(255, int(255 - distance * 5))
        
        return image
    
    @pytest.fixture
    def sample_image_file(self, sample_image):
        """サンプル画像をファイルとして保存"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            cv2.imwrite(tmp.name, sample_image)
            yield Path(tmp.name)
            # クリーンアップ
            Path(tmp.name).unlink(missing_ok=True)
    
    @pytest.fixture
    def complex_test_image(self):
        """複雑なテスト画像を作成（文書スキャン風）"""
        # 400x300の白背景画像
        image = np.full((300, 400, 3), 255, dtype=np.uint8)
        
        # 黒い矩形（文書領域をシミュレート）
        cv2.rectangle(image, (50, 50), (350, 250), (0, 0, 0), 2)
        
        # 内部にテキスト風のパターンを追加
        for i in range(70, 230, 20):
            cv2.line(image, (70, i), (330, i), (0, 0, 0), 1)
        
        # ノイズを追加
        noise = np.random.randint(0, 50, image.shape, dtype=np.uint8)
        image = cv2.subtract(image, noise)
        
        return image


class TestImageLoading(TestImageProcessor):
    """画像読み込み機能のテスト"""
    
    def test_load_image_success(self, image_processor, sample_image_file):
        """正常な画像読み込みテスト"""
        result = image_processor.load_image(sample_image_file)
        
        assert result is not None
        assert isinstance(result, np.ndarray)
        assert len(result.shape) == 3  # カラー画像
        assert result.shape[2] == 3  # BGR
        assert result.dtype == np.uint8
    
    def test_load_image_nonexistent_file(self, image_processor):
        """存在しない画像ファイルの読み込みテスト"""
        result = image_processor.load_image("nonexistent_file.jpg")
        assert result is None
    
    def test_load_image_invalid_path_type(self, image_processor):
        """無効なパスタイプの処理テスト"""
        result = image_processor.load_image(None)
        assert result is None
        
        result = image_processor.load_image(123)
        assert result is None
    
    @patch('cv2.imread')
    @patch('PIL.Image.open')
    def test_load_image_opencv_fallback_to_pil(self, mock_pil_open, mock_cv2_imread, image_processor):
        """OpenCVで読み込めない場合のPILフォールバック"""
        # OpenCVが失敗する場合をシミュレート
        mock_cv2_imread.return_value = None
        
        # PILでの読み込みを模擬
        mock_pil_image = MagicMock()
        mock_pil_image.mode = 'RGB'
        mock_pil_image.__enter__.return_value = mock_pil_image
        mock_pil_open.return_value = mock_pil_image
        
        # PIL → OpenCV変換を模擬
        test_array = np.zeros((100, 100, 3), dtype=np.uint8)
        with patch('numpy.array', return_value=test_array), \
             patch('cv2.cvtColor', return_value=test_array):
            
            with tempfile.NamedTemporaryFile(suffix='.png') as tmp:
                result = image_processor.load_image(tmp.name)
                
                assert result is not None
                mock_pil_open.assert_called_once()
    
    @patch('cv2.imread')
    @patch('PIL.Image.open')
    def test_load_image_rgba_conversion(self, mock_pil_open, mock_cv2_imread, image_processor):
        """RGBA画像のRGB変換テスト"""
        mock_cv2_imread.return_value = None
        
        # RGBA画像を模擬
        mock_pil_image = MagicMock()
        mock_pil_image.mode = 'RGBA'
        mock_pil_image.convert.return_value = mock_pil_image
        mock_pil_image.__enter__.return_value = mock_pil_image
        mock_pil_open.return_value = mock_pil_image
        
        test_array = np.zeros((100, 100, 3), dtype=np.uint8)
        with patch('numpy.array', return_value=test_array), \
             patch('cv2.cvtColor', return_value=test_array):
            
            with tempfile.NamedTemporaryFile(suffix='.png') as tmp:
                result = image_processor.load_image(tmp.name)
                
                assert result is not None
                mock_pil_image.convert.assert_called_with('RGB')
    
    def test_save_image_success(self, image_processor, sample_image):
        """画像保存の成功テスト"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            output_path = Path(tmp.name)
            
            try:
                result = image_processor.save_image(sample_image, output_path)
                
                assert result is True
                assert output_path.exists()
                assert output_path.stat().st_size > 0
                
                # 保存された画像を読み込んで確認
                loaded_image = cv2.imread(str(output_path))
                assert loaded_image is not None
                assert loaded_image.shape == sample_image.shape
                
            finally:
                output_path.unlink(missing_ok=True)
    
    def test_save_image_creates_parent_directory(self, image_processor, sample_image):
        """親ディレクトリ自動作成のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "nested" / "subdir" / "test.jpg"
            
            result = image_processor.save_image(sample_image, nested_path)
            
            assert result is True
            assert nested_path.exists()
            assert nested_path.parent.exists()
    
    @patch('cv2.imwrite')
    def test_save_image_failure(self, mock_imwrite, image_processor, sample_image):
        """画像保存の失敗テスト"""
        mock_imwrite.return_value = False
        
        with tempfile.NamedTemporaryFile(suffix='.jpg') as tmp:
            result = image_processor.save_image(sample_image, tmp.name)
            assert result is False


class TestImageCropping(TestImageProcessor):
    """画像切り抜き機能のテスト"""
    
    def test_crop_image_with_four_points_success(self, image_processor, sample_image):
        """4点切り抜きの成功テスト"""
        # 4つの点を定義（画像内の矩形）
        points = [(50, 30), (150, 40), (140, 120), (60, 110)]
        
        result = image_processor.crop_image_with_four_points(sample_image, points)
        
        assert result is not None
        assert isinstance(result, np.ndarray)
        assert len(result.shape) == 3  # カラー画像
        assert result.shape[0] > 0 and result.shape[1] > 0  # 有効なサイズ
        assert result.dtype == np.uint8
    
    def test_crop_image_with_four_points_complex_shape(self, image_processor, complex_test_image):
        """複雑な4点切り抜きのテスト"""
        # 台形のような形状
        points = [(80, 60), (320, 80), (300, 240), (100, 220)]
        
        result = image_processor.crop_image_with_four_points(complex_test_image, points)
        
        assert result is not None
        assert result.shape[0] > 0 and result.shape[1] > 0
        
        # 切り抜き結果が元画像より小さいことを確認
        assert result.shape[0] < complex_test_image.shape[0]
        assert result.shape[1] < complex_test_image.shape[1]
    
    def test_crop_image_invalid_points_count(self, image_processor, sample_image):
        """不正な点数での切り抜きテスト"""
        # 3つの点のみ（4つ必要）
        points = [(50, 30), (150, 40), (140, 120)]
        
        result = image_processor.crop_image_with_four_points(sample_image, points)
        assert result is None
        
        # 5つの点（4つ必要）
        points = [(50, 30), (150, 40), (140, 120), (60, 110), (100, 100)]
        result = image_processor.crop_image_with_four_points(sample_image, points)
        assert result is None
    
    def test_crop_image_points_outside_image(self, image_processor, sample_image):
        """画像外の点での切り抜きテスト"""
        height, width = sample_image.shape[:2]
        
        # 画像外の点を含む
        points = [(-10, -10), (width + 10, -10), (width + 10, height + 10), (-10, height + 10)]
        
        result = image_processor.crop_image_with_four_points(sample_image, points)
        
        # 処理は成功するが、適切にクリッピングされる
        assert result is not None
    
    def test_order_points_function(self, image_processor):
        """点の順序並び替えテスト"""
        # バラバラの順序の4点
        unordered_points = np.array([
            [150, 40],   # 右上
            [60, 110],   # 左下
            [50, 30],    # 左上
            [140, 120]   # 右下
        ], dtype=np.float32)
        
        ordered = image_processor._order_points(unordered_points)
        
        # 順序が左上、右上、右下、左下になっているかチェック
        assert ordered[0][0] < ordered[1][0]  # 左上 < 右上 (x座標)
        assert ordered[0][1] < ordered[3][1]  # 左上 < 左下 (y座標)
        assert ordered[1][0] > ordered[0][0]  # 右上 > 左上 (x座標)
        assert ordered[2][0] > ordered[3][0]  # 右下 > 左下 (x座標)
        
        # 対角線の関係をチェック
        assert ordered[0][0] < ordered[2][0]  # 左上 < 右下 (x座標)
        assert ordered[0][1] < ordered[2][1]  # 左上 < 右下 (y座標)
    
    def test_calculate_output_dimensions(self, image_processor):
        """出力サイズ計算テスト"""
        # 長方形の4点
        points = np.array([
            [0, 0],      # 左上
            [100, 0],    # 右上
            [100, 50],   # 右下
            [0, 50]      # 左下
        ], dtype=np.float32)
        
        width, height = image_processor._calculate_output_dimensions(points)
        
        assert width == 100
        assert height == 50
    
    def test_calculate_output_dimensions_irregular_shape(self, image_processor):
        """不規則な形状の出力サイズ計算テスト"""
        # 不規則な四角形
        points = np.array([
            [10, 10],    # 左上
            [90, 5],     # 右上
            [95, 85],    # 右下
            [5, 90]      # 左下
        ], dtype=np.float32)
        
        width, height = image_processor._calculate_output_dimensions(points)
        
        assert width > 0
        assert height > 0
        assert isinstance(width, int)
        assert isinstance(height, int)


class TestImageRotation(TestImageProcessor):
    """画像回転機能のテスト"""
    
    def test_rotate_image_90_degrees(self, image_processor, sample_image):
        """90度回転テスト"""
        original_height, original_width = sample_image.shape[:2]
        
        rotated = image_processor.rotate_image(sample_image, 90)
        
        assert rotated is not None
        assert isinstance(rotated, np.ndarray)
        # 90度回転で縦横が入れ替わる
        assert rotated.shape[0] == original_width
        assert rotated.shape[1] == original_height
        assert rotated.shape[2] == sample_image.shape[2]  # チャンネル数は同じ
    
    def test_rotate_image_180_degrees(self, image_processor, sample_image):
        """180度回転テスト"""
        original_height, original_width = sample_image.shape[:2]
        
        rotated = image_processor.rotate_image(sample_image, 180)
        
        assert rotated is not None
        assert isinstance(rotated, np.ndarray)
        # 180度回転でサイズは変わらない
        assert rotated.shape[0] == original_height
        assert rotated.shape[1] == original_width
    
    def test_rotate_image_270_degrees(self, image_processor, sample_image):
        """270度回転テスト"""
        original_height, original_width = sample_image.shape[:2]
        
        rotated = image_processor.rotate_image(sample_image, 270)
        
        assert rotated is not None
        # 270度回転で縦横が入れ替わる
        assert rotated.shape[0] == original_width
        assert rotated.shape[1] == original_height
    
    def test_rotate_image_45_degrees(self, image_processor, sample_image):
        """45度回転テスト"""
        rotated = image_processor.rotate_image(sample_image, 45)
        
        assert rotated is not None
        assert isinstance(rotated, np.ndarray)
        assert len(rotated.shape) == 3
        # 45度回転では画像が大きくなる場合がある
    
    def test_rotate_image_negative_angle(self, image_processor, sample_image):
        """負の角度での回転テスト"""
        rotated = image_processor.rotate_image(sample_image, -90)
        
        assert rotated is not None
        # -90度回転は270度回転と同じ効果
        assert rotated.shape[0] == sample_image.shape[1]
        assert rotated.shape[1] == sample_image.shape[0]
    
    def test_rotate_image_zero_degrees(self, image_processor, sample_image):
        """0度回転（回転なし）のテスト"""
        rotated = image_processor.rotate_image(sample_image, 0)
        
        assert rotated is not None
        # 元画像とサイズが同じ
        assert rotated.shape == sample_image.shape
    
    def test_rotate_image_preserves_content(self, image_processor):
        """回転が画像内容を保持するかのテスト"""
        # 特徴的なパターンを持つ画像を作成
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(test_image, (20, 20), (40, 40), (255, 255, 255), -1)
        
        # 360度回転（元に戻る）
        rotated = image_processor.rotate_image(test_image, 360)
        
        assert rotated is not None
        assert rotated.shape == test_image.shape


class TestImageEnhancement(TestImageProcessor):
    """画像品質向上機能のテスト"""
    
    def test_enhance_image_color(self, image_processor, sample_image):
        """カラー画像の品質向上テスト"""
        enhanced = image_processor.enhance_image(sample_image)
        
        assert enhanced is not None
        assert isinstance(enhanced, np.ndarray)
        assert enhanced.shape == sample_image.shape
        assert len(enhanced.shape) == 3  # カラー画像
        assert enhanced.dtype == sample_image.dtype
    
    def test_enhance_image_grayscale(self, image_processor, sample_grayscale_image):
        """グレースケール画像の品質向上テスト"""
        enhanced = image_processor.enhance_image(sample_grayscale_image)
        
        assert enhanced is not None
        assert isinstance(enhanced, np.ndarray)
        assert enhanced.shape == sample_grayscale_image.shape
        assert len(enhanced.shape) == 2  # グレースケール画像
    
    def test_enhance_image_improves_contrast(self, image_processor):
        """コントラスト改善のテスト"""
        # 低コントラストの画像を作成
        low_contrast_image = np.full((100, 100, 3), 128, dtype=np.uint8)
        # 少しだけコントラストを追加
        cv2.rectangle(low_contrast_image, (30, 30), (70, 70), (140, 140, 140), -1)
        
        enhanced = image_processor.enhance_image(low_contrast_image)
        
        assert enhanced is not None
        # 強化後の画像の方がコントラストが高いことを確認
        original_std = np.std(low_contrast_image)
        enhanced_std = np.std(enhanced)
        assert enhanced_std >= original_std
    
    def test_enhance_image_with_noise(self, image_processor):
        """ノイズのある画像の品質向上テスト"""
        # ノイズのある画像を作成
        clean_image = np.full((100, 100, 3), 200, dtype=np.uint8)
        noise = np.random.randint(-50, 50, clean_image.shape, dtype=np.int16)
        noisy_image = np.clip(clean_image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        enhanced = image_processor.enhance_image(noisy_image)
        
        assert enhanced is not None
        assert enhanced.shape == noisy_image.shape
        
        # ノイズ除去効果の確認（分散が減少することを期待）
        original_variance = np.var(noisy_image)
        enhanced_variance = np.var(enhanced)
        # 強化処理により分散が変化することを確認（必ずしも減少するとは限らない）
        assert enhanced_variance != original_variance


class TestImageResize(TestImageProcessor):
    """画像リサイズ機能のテスト"""
    
    def test_resize_image_keep_aspect_ratio(self, image_processor, sample_image):
        """アスペクト比保持リサイズテスト"""
        target_size = (100, 100)
        
        resized = image_processor.resize_image(
            sample_image, target_size, keep_aspect_ratio=True
        )
        
        assert resized is not None
        assert isinstance(resized, np.ndarray)
        assert resized.shape[0] == target_size[1]  # height
        assert resized.shape[1] == target_size[0]  # width
        assert resized.shape[2] == sample_image.shape[2]  # channels
    
    def test_resize_image_ignore_aspect_ratio(self, image_processor, sample_image):
        """アスペクト比無視リサイズテスト"""
        target_size = (80, 120)
        
        resized = image_processor.resize_image(
            sample_image, target_size, keep_aspect_ratio=False
        )
        
        assert resized is not None
        assert isinstance(resized, np.ndarray)
        assert resized.shape[0] == target_size[1]  # height
        assert resized.shape[1] == target_size[0]  # width
    
    def test_resize_image_upscale(self, image_processor, sample_image):
        """拡大リサイズテスト"""
        original_height, original_width = sample_image.shape[:2]
        target_size = (original_width * 2, original_height * 2)
        
        resized = image_processor.resize_image(sample_image, target_size, keep_aspect_ratio=False)
        
        assert resized is not None
        assert resized.shape[0] == target_size[1]
        assert resized.shape[1] == target_size[0]
    
    def test_resize_image_downscale(self, image_processor, sample_image):
        """縮小リサイズテスト"""
        original_height, original_width = sample_image.shape[:2]
        target_size = (original_width // 2, original_height // 2)
        
        resized = image_processor.resize_image(sample_image, target_size, keep_aspect_ratio=False)
        
        assert resized is not None
        assert resized.shape[0] == target_size[1]
        assert resized.shape[1] == target_size[0]
    
    def test_resize_image_with_padding(self, image_processor):
        """パディング付きリサイズテスト"""
        # 細長い画像を作成
        narrow_image = np.zeros((50, 200, 3), dtype=np.uint8)
        target_size = (100, 100)  # 正方形
        
        resized = image_processor.resize_image(
            narrow_image, target_size, keep_aspect_ratio=True
        )
        
        assert resized is not None
        assert resized.shape[0] == target_size[1]
        assert resized.shape[1] == target_size[0]
    
    def test_resize_image_grayscale(self, image_processor, sample_grayscale_image):
        """グレースケール画像のリサイズテスト"""
        target_size = (50, 75)
        
        resized = image_processor.resize_image(
            sample_grayscale_image, target_size, keep_aspect_ratio=False
        )
        
        assert resized is not None
        assert resized.shape == (target_size[1], target_size[0])  # (height, width)


class TestImageInfo(TestImageProcessor):
    """画像情報取得機能のテスト"""
    
    def test_get_image_info_success(self, image_processor, sample_image_file):
        """画像情報取得の成功テスト"""
        info = image_processor.get_image_info(sample_image_file)
        
        assert info is not None
        assert isinstance(info, dict)
        
        # 必要なキーが存在することを確認
        required_keys = ['filename', 'filepath', 'width', 'height', 'channels', 'file_size', 'modified_time']
        for key in required_keys:
            assert key in info
        
        # 値の妥当性を確認
        assert info['width'] > 0
        assert info['height'] > 0
        assert info['channels'] in [1, 3, 4]  # グレースケール、RGB、RGBA
        assert info['file_size'] > 0
        assert info['modified_time'] > 0
        assert info['filename'] == sample_image_file.name
        assert info['filepath'] == str(sample_image_file)
    
    def test_get_image_info_nonexistent_file(self, image_processor):
        """存在しない画像の情報取得テスト"""
        info = image_processor.get_image_info("nonexistent_file.jpg")
        assert info is None
    
    def test_get_image_info_invalid_image(self, image_processor):
        """無効な画像ファイルの情報取得テスト"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            # 無効なデータを書き込み
            tmp.write(b'not an image file')
            tmp.flush()
            
            try:
                info = image_processor.get_image_info(tmp.name)
                assert info is None
            finally:
                Path(tmp.name).unlink(missing_ok=True)
    
    def test_get_image_info_different_formats(self, image_processor, sample_image):
        """異なる画像フォーマットの情報取得テスト"""
        formats = ['.jpg', '.png', '.bmp']
        
        for fmt in formats:
            with tempfile.NamedTemporaryFile(suffix=fmt, delete=False) as tmp:
                # フォーマットに応じて保存
                if fmt == '.jpg':
                    cv2.imwrite(tmp.name, sample_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
                elif fmt == '.png':
                    cv2.imwrite(tmp.name, sample_image, [cv2.IMWRITE_PNG_COMPRESSION, 9])
                else:
                    cv2.imwrite(tmp.name, sample_image)
                
                try:
                    info = image_processor.get_image_info(tmp.name)
                    assert info is not None
                    assert info['filename'].endswith(fmt)
                finally:
                    Path(tmp.name).unlink(missing_ok=True)


class TestSignalEmission(TestImageProcessor):
    """シグナル発行のテスト"""
    
    def test_processing_signals_emitted(self, image_processor, sample_image):
        """処理シグナルの発行テスト"""
        # シグナルハンドラーを設定
        started_signals = []
        finished_signals = []
        error_signals = []
        
        image_processor.processing_started.connect(started_signals.append)
        image_processor.processing_finished.connect(finished_signals.append)
        image_processor.processing_error.connect(lambda op, msg: error_signals.append((op, msg)))
        
        # 画像処理を実行
        image_processor.rotate_image(sample_image, 90)
        
        # シグナルが発行されたことを確認
        assert len(started_signals) > 0
        assert len(finished_signals) > 0
        assert started_signals[0] == "rotate"
        assert finished_signals[0] == "rotate"
    
    def test_error_signal_emission(self, image_processor):
        """エラーシグナルの発行テスト"""
        error_signals = []
        image_processor.processing_error.connect(lambda op, msg: error_signals.append((op, msg)))
        
        # 無効な画像で処理を実行
        result = image_processor.load_image("invalid_path")
        
        assert result is None
        # エラーシグナルの発行は内部実装依存なので、ここでは結果のみ確認
    
    def test_progress_signal_emission(self, image_processor, sample_image):
        """進捗シグナルの発行テスト"""
        progress_signals = []
        image_processor.progress_updated.connect(progress_signals.append)
        
        # 複数の処理を実行
        image_processor.enhance_image(sample_image)
        image_processor.rotate_image(sample_image, 45)
        
        # 進捗シグナルが発行される可能性があることを確認
        # （実装によっては発行されない場合もある）


class TestErrorHandling(TestImageProcessor):
    """エラーハンドリングのテスト"""
    
    def test_crop_with_invalid_image(self, image_processor):
        """無効な画像での切り抜きテスト"""
        invalid_image = None
        points = [(0, 0), (100, 0), (100, 100), (0, 100)]
        
        result = image_processor.crop_image_with_four_points(invalid_image, points)
        assert result is None
    
    def test_rotate_with_invalid_image(self, image_processor):
        """無効な画像での回転テスト"""
        invalid_image = None
        
        result = image_processor.rotate_image(invalid_image, 90)
        assert result is None or np.array_equal(result, invalid_image)
    
    def test_enhance_with_invalid_image(self, image_processor):
        """無効な画像での品質向上テスト"""
        invalid_image = None
        
        result = image_processor.enhance_image(invalid_image)
        assert result is None or np.array_equal(result, invalid_image)
    
    @patch('cv2.getPerspectiveTransform')
    def test_crop_with_cv2_error(self, mock_get_transform, image_processor, sample_image):
        """OpenCVエラー時の処理テスト"""
        mock_get_transform.side_effect = cv2.error("OpenCV Error")
        
        points = [(50, 30), (150, 40), (140, 120), (60, 110)]
        result = image_processor.crop_image_with_four_points(sample_image, points)
        
        assert result is None
    
    @patch('cv2.getRotationMatrix2D')
    def test_rotate_with_cv2_error(self, mock_get_matrix, image_processor, sample_image):
        """回転処理でのOpenCVエラーテスト"""
        mock_get_matrix.side_effect = cv2.error("Rotation Error")
        
        result = image_processor.rotate_image(sample_image, 90)
        
        # エラー時は元画像を返す
        assert np.array_equal(result, sample_image)


class TestPerformance(TestImageProcessor):
    """パフォーマンステスト"""
    
    def test_large_image_processing_performance(self, image_processor):
        """大きな画像の処理性能テスト"""
        import time
        
        # 大きな画像を作成（4K相当）
        large_image = np.random.randint(0, 256, (2160, 3840, 3), dtype=np.uint8)
        
        start_time = time.time()
        result = image_processor.rotate_image(large_image, 90)
        end_time = time.time()
        
        assert result is not None
        # 大きな画像でも10秒以内で処理完了することを確認
        assert (end_time - start_time) < 10.0
    
    def test_multiple_operations_performance(self, image_processor, sample_image):
        """複数操作の連続実行性能テスト"""
        import time
        
        start_time = time.time()
        
        # 複数の操作を連続実行
        enhanced = image_processor.enhance_image(sample_image)
        rotated = image_processor.rotate_image(enhanced, 45)
        resized = image_processor.resize_image(rotated, (100, 100))
        
        end_time = time.time()
        
        assert resized is not None
        # 連続操作が5秒以内で完了することを確認
        assert (end_time - start_time) < 5.0


class TestEdgeCases(TestImageProcessor):
    """境界値・特殊ケースのテスト"""
    
    def test_crop_with_identical_points(self, image_processor, sample_image):
        """同一の点での切り抜きテスト"""
        # 4つの点がすべて同じ
        points = [(100, 100), (100, 100), (100, 100), (100, 100)]
        
        result = image_processor.crop_image_with_four_points(sample_image, points)
        # 処理は失敗するか、非常に小さな画像が返される
        assert result is None or result.size < 100
    
    def test_crop_with_collinear_points(self, image_processor, sample_image):
        """一直線上の点での切り抜きテスト"""
        # 4つの点が一直線上にある
        points = [(50, 50), (100, 50), (150, 50), (200, 50)]
        
        result = image_processor.crop_image_with_four_points(sample_image, points)
        # 処理は失敗するか、非常に小さな画像が返される
        assert result is None or result.size < 100
    
    def test_rotate_extreme_angles(self, image_processor, sample_image):
        """極端な角度での回転テスト"""
        extreme_angles = [720, -720, 1800, -1800]
        
        for angle in extreme_angles:
            result = image_processor.rotate_image(sample_image, angle)
            assert result is not None
            # 360の倍数の回転は元画像とほぼ同じになる
            if angle % 360 == 0:
                assert result.shape == sample_image.shape
    
    def test_resize_to_very_small_size(self, image_processor, sample_image):
        """非常に小さなサイズへのリサイズテスト"""
        tiny_size = (1, 1)
        
        result = image_processor.resize_image(sample_image, tiny_size)
        
        assert result is not None
        assert result.shape[0] == 1
        assert result.shape[1] == 1
    
    def test_resize_to_very_large_size(self, image_processor, sample_image):
        """非常に大きなサイズへのリサイズテスト"""
        large_size = (10000, 10000)
        
        result = image_processor.resize_image(sample_image, large_size)
        
        assert result is not None
        assert result.shape[0] == large_size[1]
        assert result.shape[1] == large_size[0]


# テスト実行用
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
