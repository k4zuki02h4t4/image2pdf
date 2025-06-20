"""
ユーティリティ関数のテスト
包括的なテストケースでutils.pyの全機能を検証
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import logging

# テスト対象のインポート
from src.utils import (
    setup_logging,
    get_resource_path,
    is_image_file,
    get_supported_image_formats,
    get_image_filter_string,
    sanitize_filename,
    validate_pdf_filename,
    get_temp_dir,
    format_file_size,
    load_image_safely,
    calculate_aspect_ratio,
    resize_keeping_aspect_ratio
)


class TestLoggingSetup:
    """ログ設定のテスト"""
    
    @pytest.fixture
    def temp_log_dir(self):
        """一時ログディレクトリを作成"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_setup_logging_creates_log_file(self, temp_log_dir):
        """ログファイル作成のテスト"""
        log_file = temp_log_dir / "test.log"
        
        setup_logging(log_file, logging.DEBUG)
        
        # ログファイルが作成されることを確認
        logger = logging.getLogger("test_logger")
        logger.info("テストメッセージ")
        
        # ログファイルの存在を確認
        assert log_file.exists()
        
        # ログ内容を確認
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "テストメッセージ" in content
    
    def test_setup_logging_with_debug_flag(self, temp_log_dir):
        """デバッグフラグ付きログ設定のテスト"""
        log_file = temp_log_dir / "debug.log"
        
        # --debug引数をシミュレート
        with patch.object(sys, 'argv', ['script.py', '--debug']):
            setup_logging(log_file, logging.DEBUG)
            
            # コンソールハンドラーが追加されることを確認
            root_logger = logging.getLogger()
            console_handlers = [
                h for h in root_logger.handlers 
                if h.__class__.__name__ == 'StreamHandler'
            ]
            assert len(console_handlers) > 0
    
    def test_setup_logging_creates_parent_directory(self):
        """親ディレクトリ自動作成のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_log_file = Path(temp_dir) / "nested" / "subdir" / "test.log"
            
            setup_logging(nested_log_file)
            
            # 親ディレクトリが作成されることを確認
            assert nested_log_file.parent.exists()


class TestResourcePath:
    """リソースパス取得のテスト"""
    
    def test_get_resource_path_development_mode(self):
        """開発環境でのリソースパス取得"""
        # 開発環境をシミュレート（sys.frozen = False）
        with patch('sys.frozen', False, create=True):
            with patch('src.utils.Path.__file__') as mock_file:
                mock_file.parent.parent = Path('/project/root')
                
                result = get_resource_path('resources/icon.png')
                
                assert isinstance(result, Path)
                assert str(result).endswith('resources/icon.png')
    
    def test_get_resource_path_frozen_mode(self):
        """実行ファイル環境でのリソースパス取得"""
        # PyInstallerでフリーズされた環境をシミュレート
        with patch('sys.frozen', True, create=True):
            with patch('sys.executable', '/app/dist/Image2PDF.exe'):
                result = get_resource_path('resources/icon.png')
                
                assert isinstance(result, Path)
                assert str(result).endswith('resources/icon.png')
    
    def test_get_resource_path_with_absolute_path(self):
        """絶対パスでのリソースパス取得"""
        result = get_resource_path('/absolute/path/to/resource.png')
        
        assert isinstance(result, Path)
        assert str(result).endswith('resource.png')


class TestImageFileDetection:
    """画像ファイル判定のテスト"""
    
    @pytest.fixture
    def temp_image_file(self):
        """一時画像ファイルを作成"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            # 最小限のJPEGヘッダーを作成
            jpeg_header = b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
            tmp.write(jpeg_header)
            tmp.flush()
            
            yield Path(tmp.name)
            
            # クリーンアップ
            Path(tmp.name).unlink(missing_ok=True)
    
    def test_is_image_file_with_valid_jpeg(self, temp_image_file):
        """有効なJPEGファイルの判定テスト"""
        with patch('mimetypes.guess_type', return_value=('image/jpeg', None)):
            assert is_image_file(temp_image_file) is True
    
    def test_is_image_file_with_valid_extensions(self):
        """有効な画像拡張子のテスト"""
        valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp']
        
        for ext in valid_extensions:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(b'fake_image_data')
                tmp.flush()
                
                try:
                    with patch('mimetypes.guess_type', return_value=(f'image/{ext[1:]}', None)):
                        assert is_image_file(tmp.name) is True
                finally:
                    Path(tmp.name).unlink(missing_ok=True)
    
    def test_is_image_file_with_invalid_file(self):
        """無効なファイルの判定テスト"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp.write(b'not an image')
            tmp.flush()
            
            try:
                with patch('mimetypes.guess_type', return_value=(None, None)):
                    assert is_image_file(tmp.name) is False
            finally:
                Path(tmp.name).unlink(missing_ok=True)
    
    def test_is_image_file_nonexistent_file(self):
        """存在しないファイルの判定テスト"""
        assert is_image_file('nonexistent_file.jpg') is False
    
    def test_get_supported_image_formats(self):
        """サポート画像形式の取得テスト"""
        formats = get_supported_image_formats()
        
        assert isinstance(formats, list)
        assert len(formats) > 0
        assert '*.jpg' in formats
        assert '*.png' in formats
        assert '*.bmp' in formats
    
    def test_get_image_filter_string(self):
        """画像フィルター文字列の取得テスト"""
        filter_string = get_image_filter_string()
        
        assert isinstance(filter_string, str)
        assert 'JPEG files' in filter_string
        assert 'PNG files' in filter_string
        assert ';;' in filter_string  # セパレータ
        assert 'すべてのファイル' in filter_string


class TestFilenameSanitization:
    """ファイル名サニタイズのテスト"""
    
    def test_sanitize_filename_removes_invalid_chars(self):
        """無効文字の削除テスト"""
        test_cases = [
            ('file<name>.txt', 'file_name_.txt'),
            ('file>name.txt', 'file_name.txt'),
            ('file:name.txt', 'file_name.txt'),
            ('file"name.txt', 'file_name.txt'),
            ('file/name.txt', 'file_name.txt'),
            ('file\\name.txt', 'file_name.txt'),
            ('file|name.txt', 'file_name.txt'),
            ('file?name.txt', 'file_name.txt'),
            ('file*name.txt', 'file_name.txt'),
        ]
        
        for original, expected in test_cases:
            result = sanitize_filename(original)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_sanitize_filename_handles_control_chars(self):
        """制御文字の処理テスト"""
        filename_with_control = 'file\x00\x01\x1fname.txt'
        result = sanitize_filename(filename_with_control)
        
        # 制御文字が削除されることを確認
        assert '\x00' not in result
        assert '\x01' not in result
        assert '\x1f' not in result
    
    def test_sanitize_filename_handles_reserved_names(self):
        """Windows予約語の処理テスト"""
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM9', 'LPT1', 'LPT9']
        
        for reserved in reserved_names:
            # 予約語のみ
            result = sanitize_filename(reserved)
            assert result == f'_{reserved}'
            
            # 拡張子付き予約語
            result = sanitize_filename(f'{reserved}.txt')
            assert result == f'_{reserved}.txt'
            
            # 小文字の場合
            result = sanitize_filename(reserved.lower())
            assert result == f'_{reserved.lower()}'
    
    def test_sanitize_filename_handles_long_names(self):
        """長いファイル名の処理テスト"""
        long_name = 'a' * 300 + '.txt'
        result = sanitize_filename(long_name)
        
        assert len(result) <= 250
        assert result.endswith('.txt')
    
    def test_validate_pdf_filename(self):
        """PDFファイル名検証のテスト"""
        test_cases = [
            ('document', 'document.pdf'),
            ('document.pdf', 'document.pdf'),
            ('document.PDF', 'document.PDF'),
            ('my<file>', 'my_file_.pdf'),
            ('', '.pdf'),
            ('test.doc', 'test.doc.pdf'),
        ]
        
        for input_name, expected in test_cases:
            result = validate_pdf_filename(input_name)
            assert result == expected, f"Input: {input_name}, Expected: {expected}, Got: {result}"


class TestFileSystemOperations:
    """ファイルシステム操作のテスト"""
    
    def test_get_temp_dir_creates_directory(self):
        """一時ディレクトリ作成のテスト"""
        with patch('src.utils.QStandardPaths.writableLocation') as mock_location:
            mock_location.return_value = str(Path.home() / 'temp')
            
            temp_dir = get_temp_dir()
            
            assert isinstance(temp_dir, Path)
            assert temp_dir.name == 'Image2PDF'
    
    def test_format_file_size(self):
        """ファイルサイズフォーマットのテスト"""
        test_cases = [
            (0, '0 B'),
            (512, '512.0 B'),
            (1024, '1.0 KB'),
            (1536, '1.5 KB'),
            (1048576, '1.0 MB'),
            (1073741824, '1.0 GB'),
            (1099511627776, '1.0 TB'),
        ]
        
        for size_bytes, expected in test_cases:
            result = format_file_size(size_bytes)
            assert result == expected, f"Size: {size_bytes}, Expected: {expected}, Got: {result}"
    
    def test_format_file_size_edge_cases(self):
        """ファイルサイズフォーマットの境界値テスト"""
        # 非常に大きなサイズ
        huge_size = 2**50  # 1 PB
        result = format_file_size(huge_size)
        assert 'TB' in result  # TB単位で表示される
        
        # 負の値（異常ケース）
        with pytest.raises((ValueError, ZeroDivisionError)):
            format_file_size(-1)


class TestImageLoading:
    """画像読み込みのテスト"""
    
    @pytest.fixture
    def mock_qpixmap(self):
        """QPixmapのモックを作成"""
        with patch('src.utils.QPixmap') as mock_pixmap_class:
            mock_pixmap = MagicMock()
            mock_pixmap.isNull.return_value = False
            mock_pixmap_class.return_value = mock_pixmap
            yield mock_pixmap
    
    def test_load_image_safely_success(self, mock_qpixmap):
        """正常な画像読み込みのテスト"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(b'fake_image_data')
            tmp.flush()
            
            try:
                with patch('src.utils.is_image_file', return_value=True):
                    result = load_image_safely(tmp.name)
                    assert result is not None
            finally:
                Path(tmp.name).unlink(missing_ok=True)
    
    def test_load_image_safely_invalid_file(self):
        """無効ファイルの読み込みテスト"""
        result = load_image_safely('nonexistent_file.jpg')
        assert result is None
    
    def test_load_image_safely_with_null_pixmap(self):
        """null QPixmapの処理テスト"""
        with patch('src.utils.QPixmap') as mock_pixmap_class:
            mock_pixmap = MagicMock()
            mock_pixmap.isNull.return_value = True  # null pixmap
            mock_pixmap_class.return_value = mock_pixmap
            
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(b'fake_image_data')
                tmp.flush()
                
                try:
                    with patch('src.utils.is_image_file', return_value=True):
                        result = load_image_safely(tmp.name)
                        assert result is None
                finally:
                    Path(tmp.name).unlink(missing_ok=True)


class TestAspectRatioCalculations:
    """アスペクト比計算のテスト"""
    
    def test_calculate_aspect_ratio_normal_cases(self):
        """通常のアスペクト比計算テスト"""
        test_cases = [
            (1920, 1080, 1920/1080),
            (1024, 768, 1024/768),
            (100, 100, 1.0),
            (800, 600, 800/600),
        ]
        
        for width, height, expected in test_cases:
            result = calculate_aspect_ratio(width, height)
            assert abs(result - expected) < 0.001, f"Width: {width}, Height: {height}"
    
    def test_calculate_aspect_ratio_zero_height(self):
        """高さがゼロの場合のテスト"""
        result = calculate_aspect_ratio(100, 0)
        assert result == 1.0  # デフォルト値
    
    def test_resize_keeping_aspect_ratio_landscape(self):
        """横長画像のアスペクト比保持リサイズテスト"""
        original = (1920, 1080)  # 16:9
        target = (800, 800)      # 正方形
        
        result = resize_keeping_aspect_ratio(original, target)
        
        # 幅が800、高さが450になるはず（16:9を維持）
        assert result[0] == 800
        assert abs(result[1] - 450) <= 1  # 丸め誤差を考慮
    
    def test_resize_keeping_aspect_ratio_portrait(self):
        """縦長画像のアスペクト比保持リサイズテスト"""
        original = (600, 800)   # 3:4
        target = (1000, 500)    # 横長ターゲット
        
        result = resize_keeping_aspect_ratio(original, target)
        
        # 高さが500、幅が375になるはず（3:4を維持）
        assert result[1] == 500
        assert abs(result[0] - 375) <= 1
    
    def test_resize_keeping_aspect_ratio_exact_fit(self):
        """完全にフィットする場合のテスト"""
        original = (400, 300)   # 4:3
        target = (800, 600)     # 4:3（同じアスペクト比）
        
        result = resize_keeping_aspect_ratio(original, target)
        
        assert result == target
    
    def test_resize_keeping_aspect_ratio_zero_original(self):
        """元サイズがゼロの場合のテスト"""
        original = (0, 0)
        target = (100, 100)
        
        result = resize_keeping_aspect_ratio(original, target)
        
        assert result == target
    
    def test_resize_keeping_aspect_ratio_edge_cases(self):
        """境界値のテスト"""
        # 非常に細い画像
        original = (10000, 1)
        target = (100, 100)
        
        result = resize_keeping_aspect_ratio(original, target)
        
        # 幅が100、高さが非常に小さい値になるはず
        assert result[0] == 100
        assert result[1] <= 1


class TestErrorHandling:
    """エラーハンドリングのテスト"""
    
    def test_setup_logging_with_permission_error(self):
        """ログファイル作成の権限エラーテスト"""
        with patch('pathlib.Path.mkdir', side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                setup_logging(Path('/root/forbidden/test.log'))
    
    def test_is_image_file_with_exception(self):
        """画像ファイル判定での例外処理テスト"""
        with patch('mimetypes.guess_type', side_effect=Exception("MIME type error")):
            # 例外が発生してもFalseを返すことを確認
            result = is_image_file('test.jpg')
            assert result is False
    
    def test_sanitize_filename_with_unicode(self):
        """Unicode文字を含むファイル名のテスト"""
        unicode_filename = 'テスト画像_2025年.jpg'
        result = sanitize_filename(unicode_filename)
        
        # Unicode文字が保持されることを確認
        assert 'テスト画像' in result
        assert '2025年' in result
        assert result.endswith('.jpg')


class TestIntegration:
    """統合テスト"""
    
    def test_image_workflow_integration(self):
        """画像処理ワークフローの統合テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 1. 一時画像ファイルを作成
            image_file = temp_path / 'test_image.jpg'
            image_file.write_bytes(b'fake_jpeg_data')
            
            # 2. 画像ファイル判定
            with patch('mimetypes.guess_type', return_value=('image/jpeg', None)):
                assert is_image_file(image_file) is True
            
            # 3. ファイル名をサニタイズ
            safe_name = sanitize_filename(image_file.name)
            assert safe_name == 'test_image.jpg'
            
            # 4. PDFファイル名を生成
            pdf_name = validate_pdf_filename('output')
            assert pdf_name == 'output.pdf'
            
            # 5. 一時ディレクトリを取得
            temp_output_dir = get_temp_dir()
            assert isinstance(temp_output_dir, Path)
    
    def test_resource_and_logging_integration(self):
        """リソース管理とログの統合テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 1. ログファイルパスを取得
            log_file = temp_path / 'integration.log'
            
            # 2. ログを設定
            setup_logging(log_file, logging.INFO)
            
            # 3. リソースパスを取得
            resource_path = get_resource_path('test_resource.png')
            
            # 4. ログに記録
            logger = logging.getLogger('integration_test')
            logger.info(f"Resource path: {resource_path}")
            
            # 5. ログファイルの内容を確認
            assert log_file.exists()
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'Resource path:' in content


# パフォーマンステスト
class TestPerformance:
    """パフォーマンステスト"""
    
    def test_large_filename_sanitization_performance(self):
        """大きなファイル名のサニタイズ性能テスト"""
        import time
        
        # 非常に長いファイル名を作成
        long_filename = 'a' * 10000 + '.txt'
        
        start_time = time.time()
        result = sanitize_filename(long_filename)
        end_time = time.time()
        
        # 処理時間が1秒未満であることを確認
        assert (end_time - start_time) < 1.0
        assert len(result) <= 250  # 適切に短縮されている
    
    def test_aspect_ratio_calculation_performance(self):
        """アスペクト比計算の性能テスト"""
        import time
        
        start_time = time.time()
        
        # 1000回計算を実行
        for i in range(1000):
            calculate_aspect_ratio(1920 + i, 1080 + i)
        
        end_time = time.time()
        
        # 1000回の計算が0.1秒未満で完了することを確認
        assert (end_time - start_time) < 0.1


# テスト実行時の設定
def pytest_configure(config):
    """pytest設定"""
    # テスト用の一時ディレクトリを設定
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
