# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller設定ファイル
Image2PDF Windows 11アプリケーション用
"""

import sys
import os
from pathlib import Path

from src import (
    __appname__, __version__, __author__, __license__, __description__
)

# プロジェクトのルートディレクトリ
project_root = Path('.').resolve()
src_dir = project_root / 'src'
resources_dir = project_root / 'resources'

# アプリケーション情報
app_name = __appname__
app_version = __version__
app_author = __author__
app_description = __description__

# 分析対象のスクリプト
a = Analysis(
    ['main.py'],
    pathex=[str(project_root), str(src_dir)],
    binaries=[],
    datas=[
        # リソースファイルを含める
        (str(resources_dir / 'icons'), 'resources/icons'),
        (str(resources_dir / 'styles'), 'resources/styles'),
        # ライセンスファイル
        ('LICENSE', '.'),
        ('README.md', '.'),
    ],
    hiddenimports=[
        # PyQt6関連
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        
        # qfluentwidgets関連
        'qfluentwidgets',
        'qfluentwidgets.components',
        'qfluentwidgets.common',
        'qfluentwidgets.window',
        
        # OpenCV関連
        'cv2',
        'numpy',
        
        # PIL関連
        'PIL',
        'PIL.Image',
        'PIL.ImageOps',
        
        # PDF生成関連
        'img2pdf',
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.units',
        
        # その他
        'pathlib',
        'logging',
        'json',
        'tempfile',
        'mimetypes',
        
        # アプリケーション内部モジュール
        'src',
        'src.main_window',
        'src.image_processor', 
        'src.pdf_generator',
        'src.crop_widget',
        'src.utils',
    ],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 不要なモジュールを除外
        'tkinter',
        'unittest',
        'test',
        'tests',
        'pytest',
        'setuptools',
        'distutils',
        'email',
        'http',
        'urllib',
        'xml',
        'multiprocessing',
        'concurrent.futures',
        'asyncio',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# PYZ（Python Zip Archive）作成
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 実行ファイル作成
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # UPX圧縮を有効
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # コンソールウィンドウを非表示
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows固有設定
    icon=str(resources_dir / 'icons' / 'app_icon.ico') if (resources_dir / 'icons' / 'app_icon.ico').exists() else None,
    version_file='version_info.txt',  # バージョン情報ファイル
)

# Windows用のバージョン情報ファイル内容
version_info_content = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({app_version.replace('.', ', ')}, 0),
    prodvers=({app_version.replace('.', ', ')}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'041104B0',
          [
            StringStruct(u'CompanyName', u'{app_author}'),
            StringStruct(u'FileDescription', u'{app_description}'),
            StringStruct(u'FileVersion', u'{app_version}'),
            StringStruct(u'InternalName', u'{app_name}'),
            StringStruct(u'LegalCopyright', u'Copyright (c) 2025 {app_author}. All rights reserved.'),
            StringStruct(u'OriginalFilename', u'{app_name}.exe'),
            StringStruct(u'ProductName', u'{app_name}'),
            StringStruct(u'ProductVersion', u'{app_version}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1041, 1200])])
  ]
)
'''

# バージョン情報ファイルを作成
with open('version_info.txt', 'w', encoding='utf-8') as f:
    f.write(version_info_content)

print(f"PyInstaller設定完了: {app_name} v{app_version}")
print(f"アイコン: {resources_dir / 'icons' / 'app_icon.ico'}")
print(f"出力ディレクトリ: dist/{app_name}.exe")
