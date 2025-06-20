"""
Image2PDF テストパッケージ
テスト用の共通設定とユーティリティ
"""

import sys
import os
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

# テスト実行時にsrcディレクトリをPythonパスに追加
test_dir = Path(__file__).parent
project_root = test_dir.parent
src_dir = project_root / "src"

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# テスト用の共通設定
TEST_DATA_DIR = test_dir / "test_data"
TEMP_DIR = None


def setup_module():
    """モジュール開始時の設定"""
    global TEMP_DIR
    TEMP_DIR = Path(tempfile.mkdtemp(prefix="image2pdf_test_"))
    
    # テストデータディレクトリを作成
    TEST_DATA_DIR.mkdir(exist_ok=True)
    
    print(f"テスト用一時ディレクトリ: {TEMP_DIR}")


def teardown_module():
    """モジュール終了時のクリーンアップ"""
    global TEMP_DIR
    if TEMP_DIR and TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        print(f"テスト用一時ディレクトリを削除: {TEMP_DIR}")


# テスト用のフィクスチャー
@pytest.fixture(scope="session")
def temp_dir():
    """セッション全体で使用する一時ディレクトリ"""
    return TEMP_DIR


@pytest.fixture
def temp_file():
    """一時ファイルを作成するフィクスチャー"""
    def _create_temp_file(content=b"test_content", suffix=".tmp"):
        temp_file = TEMP_DIR / f"temp_{len(os.listdir(TEMP_DIR))}{suffix}"
        temp_file.write_bytes(content)
        return temp_file
    return _create_temp_file


@pytest.fixture
def mock_qapplication():
    """QApplicationのモックを作成"""
    mock_app = MagicMock()
    
    # QApplication.instanceが存在することをシミュレート
    with pytest.MonkeyPatch().context() as m:
        m.setattr("PyQt6.QtWidgets.QApplication.instance", lambda: mock_app)
        yield mock_app


# テスト用のサンプル画像生成関数
def create_test_image(width=100, height=100, color=(255, 0, 0)):
    """
    テスト用のサンプル画像を作成
    
    Args:
        width: 画像の幅
        height: 画像の高さ  
        color: RGB色 (R, G, B)
        
    Returns:
        PIL.Image: 作成された画像
    """
    try:
        from PIL import Image
        return Image.new('RGB', (width, height), color)
    except ImportError:
        # PILが利用できない場合はNone
        return None


def create_test_image_file(width=100, height=100, color=(255, 0, 0), format='JPEG'):
    """
    テスト用のサンプル画像ファイルを作成
    
    Args:
        width: 画像の幅
        height: 画像の高さ
        color: RGB色 (R, G, B)
        format: 画像フォーマット
        
    Returns:
        Path: 作成された画像ファイルのパス
    """
    try:
        from PIL import Image
        
        img = Image.new('RGB', (width, height), color)
        
        # ファイル拡張子を決定
        ext_map = {
            'JPEG': '.jpg',
            'PNG': '.png', 
            'BMP': '.bmp',
            'TIFF': '.tif'
        }
        ext = ext_map.get(format, '.jpg')
        
        # 一時ファイルに保存
        file_path = TEMP_DIR / f"test_image_{width}x{height}{ext}"
        img.save(file_path, format)
        
        return file_path
        
    except ImportError:
        # PILが利用できない場合は空ファイルを作成
        file_path = TEMP_DIR / f"test_image_{width}x{height}.jpg"
        file_path.write_bytes(b"fake_image_data")
        return file_path


def create_test_pdf_file(content=None):
    """
    テスト用のサンプルPDFファイルを作成
    
    Args:
        content: PDFの内容（省略時はダミーデータ）
        
    Returns:
        Path: 作成されたPDFファイルのパス
    """
    if content is None:
        content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    
    file_path = TEMP_DIR / "test_document.pdf"
    file_path.write_bytes(content)
    
    return file_path


# テスト用のカスタムアサーション
def assert_image_dimensions(image_path, expected_width, expected_height):
    """
    画像ファイルのサイズをアサート
    
    Args:
        image_path: 画像ファイルのパス
        expected_width: 期待される幅
        expected_height: 期待される高さ
    """
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            assert img.size == (expected_width, expected_height), \
                f"画像サイズが期待値と異なります: 期待値{(expected_width, expected_height)}, 実際{img.size}"
    except ImportError:
        # PILが利用できない場合はファイルの存在のみチェック
        assert Path(image_path).exists(), f"画像ファイルが存在しません: {image_path}"


def assert_file_exists(file_path):
    """
    ファイルの存在をアサート
    
    Args:
        file_path: ファイルパス
    """
    path = Path(file_path)
    assert path.exists(), f"ファイルが存在しません: {file_path}"
    assert path.is_file(), f"指定されたパスはファイルではありません: {file_path}"


def assert_file_size_greater_than(file_path, min_size):
    """
    ファイルサイズが指定値より大きいことをアサート
    
    Args:
        file_path: ファイルパス
        min_size: 最小サイズ（バイト）
    """
    path = Path(file_path)
    assert_file_exists(path)
    
    actual_size = path.stat().st_size
    assert actual_size > min_size, \
        f"ファイルサイズが小さすぎます: 期待値>{min_size}, 実際{actual_size}"


# テスト用のQt環境設定
def setup_qt_test_environment():
    """
    Qt テスト環境をセットアップ
    """
    import os
    
    # Qt関連の環境変数設定
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'  # ヘッドレス実行
    os.environ['QT_LOGGING_RULES'] = '*.debug=false'  # デバッグログを無効化
    
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        
        # QApplicationが存在しない場合は作成
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
            app.setAttribute(Qt.ApplicationAttribute.AA_DisableWindowContextHelpButton)
        
        return app
        
    except ImportError:
        print("Warning: PyQt6が利用できません。GUI関連のテストはスキップされます。")
        return None


# テスト実行時のセットアップ
if __name__ == "__main__":
    # テスト環境のセットアップ
    setup_module()
    
    # Qt環境のセットアップ
    app = setup_qt_test_environment()
    
    print("テスト環境セットアップ完了")
    print(f"一時ディレクトリ: {TEMP_DIR}")
    print(f"Qt Application: {app is not None}")
    
    # モジュール終了時のクリーンアップ
    import atexit
    atexit.register(teardown_module)
