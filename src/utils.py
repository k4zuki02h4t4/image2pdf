"""
共通ユーティリティ関数
ファイル操作、ログ設定、リソース管理などの共通機能
"""

import logging
import sys
import os
from pathlib import Path
from typing import List, Optional, Tuple, Union
import mimetypes

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QPixmap


def validate_and_prepare_output_path(output_path: Union[str, Path]) -> Tuple[bool, Path, str]:
    """
    PDF出力パスを検証・準備する
    
    Args:
        output_path: 出力パス
        
    Returns:
        (success, normalized_path, error_message)
    """
    try:
        # パスオブジェクトに変換
        path = Path(output_path)
        
        # 相対パスの場合は絶対パスに変換
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # パスを正規化
        path = path.resolve()
        
        # 拡張子をチェック・追加
        if not path.suffix.lower() == '.pdf':
            path = path.with_suffix('.pdf')
        
        # 親ディレクトリの存在確認・作成
        parent_dir = path.parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                return False, path, f"ディレクトリ作成権限がありません: {parent_dir}"
            except OSError as e:
                return False, path, f"ディレクトリ作成エラー: {e}"
        
        # 書き込み権限チェック
        if parent_dir.exists() and not os.access(parent_dir, os.W_OK):
            return False, path, f"書き込み権限がありません: {parent_dir}"
        
        # ファイル名の妥当性チェック
        filename = path.name
        if not filename or filename in ['', '.pdf']:
            return False, path, "有効なファイル名を指定してください"
        
        # Windowsでの無効な文字をチェック
        invalid_chars = '<>:"|?*'
        if any(char in filename for char in invalid_chars):
            return False, path, f"ファイル名に無効な文字が含まれています: {invalid_chars}"
        
        # パスの長さチェック（Windows）
        if len(str(path)) > 260:
            return False, path, "パスが長すぎます（260文字制限）"
        
        return True, path, ""
        
    except Exception as e:
        return False, Path(output_path), f"パス検証エラー: {e}"


def check_file_overwrite(file_path: Path) -> Tuple[bool, str]:
    """
    ファイル上書きをチェック
    
    Args:
        file_path: ファイルパス
        
    Returns:
        (should_overwrite, message)
    """
    if file_path.exists():
        file_size = format_file_size(file_path.stat().st_size)
        modified_time = file_path.stat().st_mtime
        import datetime
        modified_str = datetime.datetime.fromtimestamp(modified_time).strftime('%Y-%m-%d %H:%M:%S')
        
        message = (
            f"ファイルが既に存在します:\n"
            f"ファイル名: {file_path.name}\n"
            f"サイズ: {file_size}\n"
            f"更新日時: {modified_str}\n\n"
            f"上書きしますか？"
        )
        return True, message
    
    return False, ""


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
