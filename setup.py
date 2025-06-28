#!/usr/bin/env python3
"""
Image2PDF アプリケーション インストール設定
複数の画像から PDF を生成するツール
"""

from setuptools import setup, find_packages
import pathlib

# プロジェクトルートディレクトリ
HERE = pathlib.Path(__file__).parent

# README.mdの内容を読み込み
README = (HERE / "README.md").read_text(encoding="utf-8")

# requirements.txtから依存関係を読み込み
def get_requirements():
    """requirements.txtから依存関係を取得"""
    requirements = []
    with open(HERE / "requirements.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                requirements.append(line)
    return requirements

setup(
    name="image2pdf",
    version="1.0.0",
    description="複数の画像から PDF を生成するツール",
    long_description=README,
    long_description_content_type="text/markdown",
    author="K4zuki T.",
    author_email="",
    url="https://github.com/k4zuki02h4t4/image2pdf",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows :: Windows 11",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Graphics :: Graphics Conversion",
        "Topic :: Office/Business",
        "Topic :: Utilities",
    ],
    keywords="pdf image converter gui windows opencv pyqt",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=get_requirements(),
    include_package_data=True,
    package_data={
        "": ["resources/icons/*.png", "resources/styles/*.qss"],
    },
    entry_points={
        "console_scripts": [
            "image2pdf=main:main",
        ],
        "gui_scripts": [
            "image2pdf-gui=main:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/k4zuki02h4t4/image2pdf/issues",
        "Source": "https://github.com/k4zuki02h4t4/image2pdf",
        "Documentation": "https://github.com/k4zuki02h4t4/image2pdf/wiki",
    },
    zip_safe=False,
)
