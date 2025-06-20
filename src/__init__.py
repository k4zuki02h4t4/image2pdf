"""
Image2PDF Package
Windows 11対応の画像からPDF変換ツール

Author: K4zuki T.
License: MIT
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "K4zuki T."
__license__ = "MIT"
__description__ = "Windows 11対応のモダンな画像からPDF変換ツール"

# メインクラスのインポート
from .main_window import MainWindow
from .image_processor import ImageProcessor
from .pdf_generator import PDFGenerator
from .crop_widget import CropWidget, InteractiveImageWidget
from .utils import (
    is_image_file,
    get_supported_image_formats,
    get_image_filter_string,
    sanitize_filename,
    validate_pdf_filename,
    format_file_size,
    load_image_safely,
    get_resource_path,
    get_temp_dir,
    setup_logging
)

# パブリックAPI
__all__ = [
    # メインクラス
    'MainWindow',
    'ImageProcessor', 
    'PDFGenerator',
    'CropWidget',
    'InteractiveImageWidget',
    
    # ユーティリティ関数
    'is_image_file',
    'get_supported_image_formats', 
    'get_image_filter_string',
    'sanitize_filename',
    'validate_pdf_filename',
    'format_file_size',
    'load_image_safely',
    'get_resource_path',
    'get_temp_dir',
    'setup_logging',
    
    # メタデータ
    '__version__',
    '__author__',
    '__license__',
    '__description__'
]

# ログ設定（パッケージレベル）
import logging

# パッケージレベルのロガー設定
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # デフォルトではログを出力しない

# バージョン情報表示用の関数
def get_version_info():
    """
    バージョン情報を取得
    
    Returns:
        dict: バージョン情報の辞書
    """
    return {
        'version': __version__,
        'author': __author__,
        'license': __license__,
        'description': __description__
    }

def print_version_info():
    """バージョン情報を表示"""
    info = get_version_info()
    print(f"Image2PDF {info['version']}")
    print(f"Author: {info['author']}")
    print(f"License: {info['license']}")
    print(f"Description: {info['description']}")

# パッケージレベルの初期化
logger.info(f"Image2PDF package initialized (version {__version__})")
