"""
共通ユーティリティ関数
ファイル操作、ログ設定、リソース管理などの共通機能
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union
import mimetypes

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QPixmap


def setup_logging(log_file_path: Path, level: int = logging.INFO) -> None:
    """
    ログ設定を初期化
    
    Args:
        log_file_path: ログファイルのパス
        level: ログレベル
    """
    # ログファイルのディレクトリを作成
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # ログフォーマット
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 既存のハンドラーをクリア
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # ファイルハンドラー
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # コンソールハンドラー（デバッグ時のみ）
    if '--debug' in sys.argv:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)


def get_resource_path(relative_path: str) -> Path:
    """
    リソースファイルの絶対パスを取得
    
    Args:
        relative_path: リソースファイルの相対パス
        
    Returns:
        リソースファイルの絶対パス
    """
    # 実行ファイルのディレクトリを基準とする
    if getattr(sys, 'frozen', False):
        # PyInstallerでビルドされた場合
        base_path = Path(sys.executable).parent
    else:
        # 開発環境の場合
        base_path = Path(__file__).parent.parent
    
    return base_path / relative_path


def is_image_file(file_path: Union[str, Path]) -> bool:
    """
    ファイルが画像ファイルかどうかを判定
    
    Args:
        file_path: ファイルパス
        
    Returns:
        画像ファイルの場合True
    """
    file_path = Path(file_path)
    
    # ファイルが存在しない場合はFalse
    if not file_path.exists():
        return False
    
    # MIMEタイプから判定
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type and mime_type.startswith('image/'):
        return True
    
    # 拡張子から判定
    image_extensions = {
        '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', 
        '.gif', '.webp', '.ico', '.svg'
    }
    return file_path.suffix.lower() in image_extensions


def get_supported_image_formats() -> List[str]:
    """
    サポートされている画像形式の拡張子リストを取得
    
    Returns:
        サポートされている画像形式の拡張子リスト
    """
    return ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.tif', '*.gif', '*.webp']


def get_image_filter_string() -> str:
    """
    ファイルダイアログ用の画像フィルター文字列を取得
    
    Returns:
        ファイルダイアログ用フィルター文字列
    """
    formats = get_supported_image_formats()
    all_formats = ' '.join(formats)
    
    filter_parts = [
        f"画像ファイル ({all_formats})",
        "JPEG files (*.jpg *.jpeg)",
        "PNG files (*.png)",
        "BMP files (*.bmp)",
        "TIFF files (*.tiff *.tif)",
        "GIF files (*.gif)",
        "WebP files (*.webp)",
        "すべてのファイル (*.*)"
    ]
    
    return ';;'.join(filter_parts)


def sanitize_filename(filename: str) -> str:
    """
    ファイル名をサニタイズ（Windows対応）
    
    Args:
        filename: 元のファイル名
        
    Returns:
        サニタイズされたファイル名
    """
    # Windows で使用できない文字を削除
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # 制御文字を削除
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # 予約語の回避
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    if filename.upper() in reserved_names:
        filename = f"_{filename}"
    
    # 長すぎるファイル名を短縮
    if len(filename) > 250:
        name, ext = Path(filename).stem, Path(filename).suffix
        max_name_length = 250 - len(ext)
        filename = name[:max_name_length] + ext
    
    return filename


def get_temp_dir() -> Path:
    """
    一時ディレクトリのパスを取得
    
    Returns:
        一時ディレクトリのパス
    """
    temp_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation))
    app_temp_dir = temp_dir / "Image2PDF"
    app_temp_dir.mkdir(exist_ok=True)
    return app_temp_dir


def format_file_size(size_bytes: int) -> str:
    """
    ファイルサイズを人間が読みやすい形式にフォーマット
    
    Args:
        size_bytes: バイト数
        
    Returns:
        フォーマットされたファイルサイズ文字列
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def validate_pdf_filename(filename: str) -> str:
    """
    PDFファイル名を検証・修正
    
    Args:
        filename: ファイル名
        
    Returns:
        検証済みのファイル名
    """
    filename = sanitize_filename(filename)
    
    # .pdf拡張子を確認・追加
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'
    
    return filename


def load_image_safely(image_path: Union[str, Path]) -> Optional[QPixmap]:
    """
    画像を安全に読み込み
    
    Args:
        image_path: 画像ファイルのパス
        
    Returns:
        読み込まれたQPixmap、失敗時はNone
    """
    try:
        image_path = Path(image_path)
        if not image_path.exists() or not is_image_file(image_path):
            return None
        
        pixmap = QPixmap(str(image_path))
        return pixmap if not pixmap.isNull() else None
        
    except Exception as e:
        logging.error(f"画像読み込みエラー: {image_path} - {e}")
        return None


def calculate_aspect_ratio(width: int, height: int) -> float:
    """
    アスペクト比を計算
    
    Args:
        width: 幅
        height: 高さ
        
    Returns:
        アスペクト比（幅/高さ）
    """
    if height == 0:
        return 1.0
    return width / height


def resize_keeping_aspect_ratio(
    original_size: Tuple[int, int], 
    target_size: Tuple[int, int]
) -> Tuple[int, int]:
    """
    アスペクト比を保持してサイズを調整
    
    Args:
        original_size: 元のサイズ (width, height)
        target_size: 目標サイズ (width, height)
        
    Returns:
        調整後のサイズ (width, height)
    """
    orig_w, orig_h = original_size
    target_w, target_h = target_size
    
    if orig_w == 0 or orig_h == 0:
        return target_size
    
    # アスペクト比を計算
    aspect_ratio = orig_w / orig_h
    
    # 目標サイズに合わせて調整
    if target_w / target_h > aspect_ratio:
        # 高さを基準に調整
        new_h = target_h
        new_w = int(target_h * aspect_ratio)
    else:
        # 幅を基準に調整
        new_w = target_w
        new_h = int(target_w / aspect_ratio)
    
    return new_w, new_h
