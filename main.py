#!/usr/bin/env python3
"""
Image2PDF - 複数の画像から PDF を生成するツール
モダンなUIデザインのデスクトップアプリケーション
ナビゲーション削除版：単一画面で全機能を統合

Author: K4zuki T.
License: MIT
"""

import sys
import os
import logging
from pathlib import Path

# PyQt6とqfluentwidgetsのインポート
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
    from qfluentwidgets import setTheme, Theme, setThemeColor
    
    # アプリケーション内部モジュール
    from src import (
        __appname__, __version__, __author__, __license__, __description__
    )
    from src.main_window import MainWindow
    from src.utils import setup_logging, get_resource_path

except ImportError as e:
    print(f"必要なライブラリがインストールされていません: {e}")
    print("pip install -r requirements.txt を実行してください")
    sys.exit(1)


class Image2PDFApplication:
    """Image2PDF アプリケーションクラス"""
    
    def __init__(self):
        """アプリケーションの初期化"""
        self.app = None
        self.main_window = None
        
    def setup_application(self):
        """QApplicationの設定"""
        # QApplication作成
        self.app = QApplication(sys.argv)
        self.app.setApplicationName(f"{__appname__}")
        self.app.setApplicationVersion(f"{__version__}")
        self.app.setOrganizationName(f"{__author__}")
        self.app.setApplicationDisplayName(f"{__appname__} - {__description__}")
        
        # アプリケーションアイコン設定
        icon_path = get_resource_path("resources/icons/app_icon.png")
        if icon_path.exists():
            self.app.setWindowIcon(QIcon(str(icon_path)))
        
        # Windows 11の高DPI対応
        if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
            self.app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
            self.app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
        # テーマ設定（qfluentwidgetsの基本テーマのみ）
        try:
            setTheme(Theme.AUTO)  # システムテーマに自動追従
            setThemeColor('#3498db')  # モダンブルーをアクセントカラーに
        except Exception as e:
            logging.warning(f"テーマ設定でエラーが発生しました: {e}")
        
    def setup_directories(self):
        """必要なディレクトリの作成"""
        app_data_dir = Path.home() / "AppData" / "Local" / f"{__appname__}"
        app_data_dir.mkdir(parents=True, exist_ok=True)
        
        # ログディレクトリ
        log_dir = app_data_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # 設定ディレクトリ
        config_dir = app_data_dir / "config"
        config_dir.mkdir(exist_ok=True)
        
        return app_data_dir
        
    def run(self):
        """アプリケーションの実行"""
        try:
            # ログ設定
            app_data_dir = self.setup_directories()
            setup_logging(app_data_dir / "logs" / "step.log")
            
            logging.info(f"{__appname__} アプリケーション開始")
            
            # QApplication設定
            self.setup_application()
            
            # メインウィンドウ作成
            self.main_window = MainWindow()
            self.main_window.show()
            
            # アプリケーション実行
            return self.app.exec()
            
        except Exception as e:
            logging.error(f"アプリケーション実行エラー: {e}")
            
            # エラーダイアログ表示
            if hasattr(self, 'app') and self.app:
                from PyQt6.QtWidgets import QMessageBox
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Icon.Critical)
                msg_box.setWindowTitle("エラー")
                msg_box.setText("アプリケーションでエラーが発生しました")
                msg_box.setDetailedText(str(e))
                msg_box.exec()
            else:
                print(f"アプリケーション起動エラー: {e}")
            
            return 1


def main():
    """メイン関数"""
    # Windows 11でのフォント設定
    if sys.platform == "win32":
        os.environ["QT_FONT_DPI"] = "96"
    
    # アプリケーション実行
    app_instance = Image2PDFApplication()
    exit_code = app_instance.run()
    
    logging.info(f"{__appname__} アプリケーション終了 (exit code: {exit_code})")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
