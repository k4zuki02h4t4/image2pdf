"""
PDF生成クラス
img2pdfとReportLabを使用した高品質なPDF生成機能
"""

import logging
import tempfile
from pathlib import Path
from typing import List, Union, Optional, Tuple
import io

import img2pdf
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4, legal
from reportlab.lib.units import inch, cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from PyQt6.QtCore import QObject, pyqtSignal

from .utils import get_temp_dir, sanitize_filename, format_file_size


class PDFGenerator(QObject):
    """PDF生成を行うクラス"""
    
    # シグナル定義
    generation_started = pyqtSignal(int)  # 生成開始 (総ページ数)
    page_processed = pyqtSignal(int)  # ページ処理完了 (現在のページ)
    generation_finished = pyqtSignal(str)  # 生成完了 (出力ファイルパス)
    generation_error = pyqtSignal(str)  # エラー
    progress_updated = pyqtSignal(int, str)  # 進捗更新 (パーセント, メッセージ)
    
    # ページサイズ定義
    PAGE_SIZES = {
        'A4': A4,
        'Letter': letter,
        'Legal': legal,
        'A3': (842, 1191),
        'A5': (420, 595),
        'Custom': None
    }
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.temp_dir = get_temp_dir()
        
    def generate_pdf_simple(
        self,
        image_paths: List[Union[str, Path]],
        output_path: Union[str, Path],
        page_size: str = 'A4',
        fit_to_page: bool = True
    ) -> bool:
        """
        シンプルなPDF生成（img2pdfを使用）
        
        Args:
            image_paths: 画像ファイルのパスリスト
            output_path: 出力PDFファイルのパス
            page_size: ページサイズ
            fit_to_page: ページに合わせて画像をフィット
            
        Returns:
            生成が成功した場合True
        """
        try:
            if not image_paths:
                raise ValueError("画像ファイルが指定されていません")
            
            self.generation_started.emit(len(image_paths))
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 有効な画像ファイルのみフィルタリング
            valid_images = []
            for i, image_path in enumerate(image_paths):
                self.progress_updated.emit(
                    int((i / len(image_paths)) * 30), 
                    f"画像を確認中: {Path(image_path).name}"
                )
                
                image_path = Path(image_path)
                if image_path.exists():
                    try:
                        # 画像の有効性を確認
                        with Image.open(image_path) as img:
                            img.verify()
                        valid_images.append(str(image_path))
                    except Exception as e:
                        self.logger.warning(f"無効な画像ファイルをスキップ: {image_path} - {e}")
                else:
                    self.logger.warning(f"存在しない画像ファイルをスキップ: {image_path}")
            
            if not valid_images:
                raise ValueError("有効な画像ファイルが見つかりません")
            
            # ページサイズ設定
            layout_func = self._get_img2pdf_layout(page_size, fit_to_page)
            
            self.progress_updated.emit(50, "PDFを生成中...")\n            \n            # img2pdfでPDF生成\n            with open(output_path, \"wb\") as pdf_file:\n                if layout_func:\n                    pdf_bytes = img2pdf.convert(valid_images, layout_fun=layout_func)\n                else:\n                    pdf_bytes = img2pdf.convert(valid_images)\n                pdf_file.write(pdf_bytes)\n            \n            self.progress_updated.emit(100, \"完了\")\n            self.generation_finished.emit(str(output_path))\n            \n            # ファイルサイズをログに記録\n            file_size = output_path.stat().st_size\n            self.logger.info(\n                f\"PDF生成完了: {output_path} \"\n                f\"({len(valid_images)}ページ, {format_file_size(file_size)})\"\n            )\n            \n            return True\n            \n        except Exception as e:\n            self.logger.error(f\"PDF生成エラー: {e}\")\n            self.generation_error.emit(str(e))\n            return False\n    \n    def generate_pdf_advanced(\n        self,\n        image_paths: List[Union[str, Path]],\n        output_path: Union[str, Path],\n        page_size: Tuple[float, float] = A4,\n        margins: Tuple[float, float, float, float] = (1*cm, 1*cm, 1*cm, 1*cm),\n        title: str = \"\",\n        author: str = \"\",\n        subject: str = \"\",\n        fit_to_page: bool = True,\n        maintain_aspect_ratio: bool = True\n    ) -> bool:\n        \"\"\"\n        高度なPDF生成（ReportLabを使用）\n        \n        Args:\n            image_paths: 画像ファイルのパスリスト\n            output_path: 出力PDFファイルのパス\n            page_size: ページサイズ (width, height) in points\n            margins: マージン (top, right, bottom, left) in points\n            title: PDFタイトル\n            author: 作成者\n            subject: 件名\n            fit_to_page: ページに合わせて画像をフィット\n            maintain_aspect_ratio: アスペクト比を維持\n            \n        Returns:\n            生成が成功した場合True\n        \"\"\"\n        try:\n            if not image_paths:\n                raise ValueError(\"画像ファイルが指定されていません\")\n            \n            self.generation_started.emit(len(image_paths))\n            output_path = Path(output_path)\n            output_path.parent.mkdir(parents=True, exist_ok=True)\n            \n            # PDFキャンバス作成\n            pdf_canvas = canvas.Canvas(str(output_path), pagesize=page_size)\n            \n            # メタデータ設定\n            if title:\n                pdf_canvas.setTitle(title)\n            if author:\n                pdf_canvas.setAuthor(author)\n            if subject:\n                pdf_canvas.setSubject(subject)\n            \n            pdf_canvas.setCreator(\"Image2PDF v1.0\")\n            \n            # ページサイズとマージンを取得\n            page_width, page_height = page_size\n            margin_top, margin_right, margin_bottom, margin_left = margins\n            \n            # 画像配置可能領域を計算\n            available_width = page_width - margin_left - margin_right\n            available_height = page_height - margin_top - margin_bottom\n            \n            # 各画像を処理\n            for i, image_path in enumerate(image_paths):\n                self.progress_updated.emit(\n                    int((i / len(image_paths)) * 90),\n                    f\"ページ {i+1}/{len(image_paths)} を処理中\"\n                )\n                \n                try:\n                    # 画像を読み込み\n                    image_path = Path(image_path)\n                    if not image_path.exists():\n                        self.logger.warning(f\"画像ファイルが存在しません: {image_path}\")\n                        continue\n                    \n                    with Image.open(image_path) as img:\n                        # RGBA画像をRGBに変換\n                        if img.mode in ('RGBA', 'LA', 'P'):\n                            rgb_img = Image.new('RGB', img.size, (255, 255, 255))\n                            if img.mode == 'P':\n                                img = img.convert('RGBA')\n                            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)\n                            img = rgb_img\n                        \n                        # 画像サイズを取得\n                        img_width, img_height = img.size\n                        \n                        # 配置位置とサイズを計算\n                        if fit_to_page:\n                            x, y, width, height = self._calculate_image_placement(\n                                img_width, img_height,\n                                available_width, available_height,\n                                margin_left, margin_bottom,\n                                maintain_aspect_ratio\n                            )\n                        else:\n                            # 元サイズで配置（中央寄せ）\n                            width = min(img_width * 72 / 300, available_width)  # 300dpi想定\n                            height = min(img_height * 72 / 300, available_height)\n                            x = margin_left + (available_width - width) / 2\n                            y = margin_bottom + (available_height - height) / 2\n                        \n                        # 一時ファイルに画像を保存\n                        temp_image_path = self.temp_dir / f\"temp_img_{i}.jpg\"\n                        img.save(temp_image_path, \"JPEG\", quality=95)\n                        \n                        # PDFに画像を描画\n                        pdf_canvas.drawImage(\n                            str(temp_image_path),\n                            x, y, width, height,\n                            preserveAspectRatio=maintain_aspect_ratio\n                        )\n                        \n                        # 一時ファイルを削除\n                        if temp_image_path.exists():\n                            temp_image_path.unlink()\n                    \n                    # ページを完了\n                    if i < len(image_paths) - 1:  # 最後のページでない場合\n                        pdf_canvas.showPage()\n                    \n                    self.page_processed.emit(i + 1)\n                    \n                except Exception as e:\n                    self.logger.error(f\"ページ {i+1} 処理エラー: {image_path} - {e}\")\n                    continue\n            \n            # PDFを保存\n            self.progress_updated.emit(95, \"PDFファイルを保存中...\")\n            pdf_canvas.save()\n            \n            self.progress_updated.emit(100, \"完了\")\n            self.generation_finished.emit(str(output_path))\n            \n            # ファイルサイズをログに記録\n            file_size = output_path.stat().st_size\n            self.logger.info(\n                f\"高度PDF生成完了: {output_path} \"\n                f\"({len(image_paths)}ページ, {format_file_size(file_size)})\"\n            )\n            \n            return True\n            \n        except Exception as e:\n            self.logger.error(f\"高度PDF生成エラー: {e}\")\n            self.generation_error.emit(str(e))\n            return False\n    \n    def _get_img2pdf_layout(self, page_size: str, fit_to_page: bool):\n        \"\"\"\n        img2pdf用のレイアウト関数を取得\n        \n        Args:\n            page_size: ページサイズ名\n            fit_to_page: ページにフィットさせるか\n            \n        Returns:\n            img2pdfのレイアウト関数\n        \"\"\"\n        try:\n            if page_size not in self.PAGE_SIZES:\n                page_size = 'A4'\n            \n            if page_size == 'Custom':\n                return None\n            \n            size = self.PAGE_SIZES[page_size]\n            if fit_to_page:\n                return img2pdf.get_layout_fun(\n                    img2pdf.get_fixed_dpi_layout_fun(300),\n                    img2pdf.get_default_layout_fun(),\n                    pagesize=size\n                )\n            else:\n                return img2pdf.get_layout_fun(pagesize=size)\n                \n        except Exception as e:\n            self.logger.warning(f\"レイアウト関数取得エラー: {e}\")\n            return None\n    \n    def _calculate_image_placement(\n        self, \n        img_width: int, \n        img_height: int,\n        available_width: float, \n        available_height: float,\n        margin_left: float, \n        margin_bottom: float,\n        maintain_aspect_ratio: bool = True\n    ) -> Tuple[float, float, float, float]:\n        \"\"\"\n        画像の配置位置とサイズを計算\n        \n        Args:\n            img_width: 元画像の幅\n            img_height: 元画像の高さ\n            available_width: 利用可能な幅\n            available_height: 利用可能な高さ\n            margin_left: 左マージン\n            margin_bottom: 下マージン\n            maintain_aspect_ratio: アスペクト比を維持するか\n            \n        Returns:\n            (x, y, width, height) の配置情報\n        \"\"\"\n        if maintain_aspect_ratio:\n            # アスペクト比を維持してサイズを計算\n            scale_x = available_width / img_width\n            scale_y = available_height / img_height\n            scale = min(scale_x, scale_y)\n            \n            width = img_width * scale\n            height = img_height * scale\n        else:\n            # アスペクト比を無視して利用可能領域に合わせる\n            width = available_width\n            height = available_height\n        \n        # 中央に配置\n        x = margin_left + (available_width - width) / 2\n        y = margin_bottom + (available_height - height) / 2\n        \n        return x, y, width, height\n    \n    def merge_pdfs(self, pdf_paths: List[Union[str, Path]], output_path: Union[str, Path]) -> bool:\n        \"\"\"\n        複数のPDFファイルを結合\n        \n        Args:\n            pdf_paths: 結合するPDFファイルのパスリスト\n            output_path: 出力PDFファイルのパス\n            \n        Returns:\n            結合が成功した場合True\n        \"\"\"\n        try:\n            from PyPDF2 import PdfMerger\n            \n            if not pdf_paths:\n                raise ValueError(\"PDFファイルが指定されていません\")\n            \n            self.progress_updated.emit(0, \"PDF結合を開始中...\")\n            \n            merger = PdfMerger()\n            \n            for i, pdf_path in enumerate(pdf_paths):\n                pdf_path = Path(pdf_path)\n                if pdf_path.exists():\n                    merger.append(str(pdf_path))\n                    self.progress_updated.emit(\n                        int((i + 1) / len(pdf_paths) * 90),\n                        f\"結合中: {pdf_path.name}\"\n                    )\n                else:\n                    self.logger.warning(f\"PDFファイルが存在しません: {pdf_path}\")\n            \n            # 結合したPDFを保存\n            output_path = Path(output_path)\n            output_path.parent.mkdir(parents=True, exist_ok=True)\n            \n            with open(output_path, 'wb') as output_file:\n                merger.write(output_file)\n            \n            merger.close()\n            \n            self.progress_updated.emit(100, \"PDF結合完了\")\n            self.generation_finished.emit(str(output_path))\n            \n            self.logger.info(f\"PDF結合完了: {output_path}\")\n            return True\n            \n        except Exception as e:\n            self.logger.error(f\"PDF結合エラー: {e}\")\n            self.generation_error.emit(str(e))\n            return False\n    \n    def get_pdf_info(self, pdf_path: Union[str, Path]) -> Optional[dict]:\n        \"\"\"\n        PDFファイルの情報を取得\n        \n        Args:\n            pdf_path: PDFファイルのパス\n            \n        Returns:\n            PDF情報の辞書、失敗時はNone\n        \"\"\"\n        try:\n            from PyPDF2 import PdfReader\n            \n            pdf_path = Path(pdf_path)\n            if not pdf_path.exists():\n                return None\n            \n            with open(pdf_path, 'rb') as pdf_file:\n                reader = PdfReader(pdf_file)\n                \n                info = {\n                    'filename': pdf_path.name,\n                    'filepath': str(pdf_path),\n                    'page_count': len(reader.pages),\n                    'file_size': pdf_path.stat().st_size,\n                    'encrypted': reader.is_encrypted\n                }\n                \n                # メタデータを取得\n                if reader.metadata:\n                    info.update({\n                        'title': reader.metadata.get('/Title', ''),\n                        'author': reader.metadata.get('/Author', ''),\n                        'subject': reader.metadata.get('/Subject', ''),\n                        'creator': reader.metadata.get('/Creator', ''),\n                        'producer': reader.metadata.get('/Producer', ''),\n                        'creation_date': reader.metadata.get('/CreationDate', ''),\n                        'modification_date': reader.metadata.get('/ModDate', '')\n                    })\n                \n                return info\n                \n        except Exception as e:\n            self.logger.error(f\"PDF情報取得エラー: {pdf_path} - {e}\")\n            return None\n    \n    @staticmethod\n    def get_available_page_sizes() -> List[str]:\n        \"\"\"\n        利用可能なページサイズのリストを取得\n        \n        Returns:\n            ページサイズ名のリスト\n        \"\"\"\n        return list(PDFGenerator.PAGE_SIZES.keys())"
