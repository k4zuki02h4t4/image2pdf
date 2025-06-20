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
            
            self.progress_updated.emit(50, "PDFを生成中...")
            
            # img2pdfでPDF生成
            with open(output_path, "wb") as pdf_file:
                if layout_func:
                    pdf_bytes = img2pdf.convert(valid_images, layout_fun=layout_func)
                else:
                    pdf_bytes = img2pdf.convert(valid_images)
                pdf_file.write(pdf_bytes)
            
            self.progress_updated.emit(100, "完了")
            self.generation_finished.emit(str(output_path))
            
            # ファイルサイズをログに記録
            file_size = output_path.stat().st_size
            self.logger.info(
                f"PDF生成完了: {output_path} "
                f"({len(valid_images)}ページ, {format_file_size(file_size)})"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"PDF生成エラー: {e}")
            self.generation_error.emit(str(e))
            return False
    
    def generate_pdf_advanced(
        self,
        image_paths: List[Union[str, Path]],
        output_path: Union[str, Path],
        page_size: Tuple[float, float] = A4,
        margins: Tuple[float, float, float, float] = (1*cm, 1*cm, 1*cm, 1*cm),
        title: str = "",
        author: str = "",
        subject: str = "",
        fit_to_page: bool = True,
        maintain_aspect_ratio: bool = True
    ) -> bool:
        """
        高度なPDF生成（ReportLabを使用）
        
        Args:
            image_paths: 画像ファイルのパスリスト
            output_path: 出力PDFファイルのパス
            page_size: ページサイズ (width, height) in points
            margins: マージン (top, right, bottom, left) in points
            title: PDFタイトル
            author: 作成者
            subject: 件名
            fit_to_page: ページに合わせて画像をフィット
            maintain_aspect_ratio: アスペクト比を維持
            
        Returns:
            生成が成功した場合True
        """
        try:
            if not image_paths:
                raise ValueError("画像ファイルが指定されていません")
            
            self.generation_started.emit(len(image_paths))
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # PDFキャンバス作成
            pdf_canvas = canvas.Canvas(str(output_path), pagesize=page_size)
            
            # メタデータ設定
            if title:
                pdf_canvas.setTitle(title)
            if author:
                pdf_canvas.setAuthor(author)
            if subject:
                pdf_canvas.setSubject(subject)
            
            pdf_canvas.setCreator("Image2PDF v1.0")
            
            # ページサイズとマージンを取得
            page_width, page_height = page_size
            margin_top, margin_right, margin_bottom, margin_left = margins
            
            # 画像配置可能領域を計算
            available_width = page_width - margin_left - margin_right
            available_height = page_height - margin_top - margin_bottom
            
            # 各画像を処理
            for i, image_path in enumerate(image_paths):
                self.progress_updated.emit(
                    int((i / len(image_paths)) * 90),
                    f"ページ {i+1}/{len(image_paths)} を処理中"
                )
                
                try:
                    # 画像を読み込み
                    image_path = Path(image_path)
                    if not image_path.exists():
                        self.logger.warning(f"画像ファイルが存在しません: {image_path}")
                        continue
                    
                    with Image.open(image_path) as img:
                        # RGBA画像をRGBに変換
                        if img.mode in ('RGBA', 'LA', 'P'):
                            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                            img = rgb_img
                        
                        # 画像サイズを取得
                        img_width, img_height = img.size
                        
                        # 配置位置とサイズを計算
                        if fit_to_page:
                            x, y, width, height = self._calculate_image_placement(
                                img_width, img_height,
                                available_width, available_height,
                                margin_left, margin_bottom,
                                maintain_aspect_ratio
                            )
                        else:
                            # 元サイズで配置（中央寄せ）
                            width = min(img_width * 72 / 300, available_width)  # 300dpi想定
                            height = min(img_height * 72 / 300, available_height)
                            x = margin_left + (available_width - width) / 2
                            y = margin_bottom + (available_height - height) / 2
                        
                        # 一時ファイルに画像を保存
                        temp_image_path = self.temp_dir / f"temp_img_{i}.jpg"
                        img.save(temp_image_path, "JPEG", quality=95)
                        
                        # PDFに画像を描画
                        pdf_canvas.drawImage(
                            str(temp_image_path),
                            x, y, width, height,
                            preserveAspectRatio=maintain_aspect_ratio
                        )
                        
                        # 一時ファイルを削除
                        if temp_image_path.exists():
                            temp_image_path.unlink()
                    
                    # ページを完了
                    if i < len(image_paths) - 1:  # 最後のページでない場合
                        pdf_canvas.showPage()
                    
                    self.page_processed.emit(i + 1)
                    
                except Exception as e:
                    self.logger.error(f"ページ {i+1} 処理エラー: {image_path} - {e}")
                    continue
            
            # PDFを保存
            self.progress_updated.emit(95, "PDFファイルを保存中...")
            pdf_canvas.save()
            
            self.progress_updated.emit(100, "完了")
            self.generation_finished.emit(str(output_path))
            
            # ファイルサイズをログに記録
            file_size = output_path.stat().st_size
            self.logger.info(
                f"高度PDF生成完了: {output_path} "
                f"({len(image_paths)}ページ, {format_file_size(file_size)})"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"高度PDF生成エラー: {e}")
            self.generation_error.emit(str(e))
            return False
    
    def _get_img2pdf_layout(self, page_size: str, fit_to_page: bool):
        """
        img2pdf用のレイアウト関数を取得
        
        Args:
            page_size: ページサイズ名
            fit_to_page: ページにフィットさせるか
            
        Returns:
            img2pdfのレイアウト関数
        """
        try:
            if page_size not in self.PAGE_SIZES:
                page_size = 'A4'
            
            if page_size == 'Custom':
                return None
            
            size = self.PAGE_SIZES[page_size]
            if fit_to_page:
                return img2pdf.get_layout_fun(
                    img2pdf.get_fixed_dpi_layout_fun(300),
                    img2pdf.get_default_layout_fun(),
                    pagesize=size
                )
            else:
                return img2pdf.get_layout_fun(pagesize=size)
                
        except Exception as e:
            self.logger.warning(f"レイアウト関数取得エラー: {e}")
            return None
    
    def _calculate_image_placement(
        self, 
        img_width: int, 
        img_height: int,
        available_width: float, 
        available_height: float,
        margin_left: float, 
        margin_bottom: float,
        maintain_aspect_ratio: bool = True
    ) -> Tuple[float, float, float, float]:
        """
        画像の配置位置とサイズを計算
        
        Args:
            img_width: 元画像の幅
            img_height: 元画像の高さ
            available_width: 利用可能な幅
            available_height: 利用可能な高さ
            margin_left: 左マージン
            margin_bottom: 下マージン
            maintain_aspect_ratio: アスペクト比を維持するか
            
        Returns:
            (x, y, width, height) の配置情報
        """
        if maintain_aspect_ratio:
            # アスペクト比を維持してサイズを計算
            scale_x = available_width / img_width
            scale_y = available_height / img_height
            scale = min(scale_x, scale_y)
            
            width = img_width * scale
            height = img_height * scale
        else:
            # アスペクト比を無視して利用可能領域に合わせる
            width = available_width
            height = available_height
        
        # 中央に配置
        x = margin_left + (available_width - width) / 2
        y = margin_bottom + (available_height - height) / 2
        
        return x, y, width, height
    
    def merge_pdfs(self, pdf_paths: List[Union[str, Path]], output_path: Union[str, Path]) -> bool:
        """
        複数のPDFファイルを結合
        
        Args:
            pdf_paths: 結合するPDFファイルのパスリスト
            output_path: 出力PDFファイルのパス
            
        Returns:
            結合が成功した場合True
        """
        try:
            from PyPDF2 import PdfMerger
            
            if not pdf_paths:
                raise ValueError("PDFファイルが指定されていません")
            
            self.progress_updated.emit(0, "PDF結合を開始中...")
            
            merger = PdfMerger()
            
            for i, pdf_path in enumerate(pdf_paths):
                pdf_path = Path(pdf_path)
                if pdf_path.exists():
                    merger.append(str(pdf_path))
                    self.progress_updated.emit(
                        int((i + 1) / len(pdf_paths) * 90),
                        f"結合中: {pdf_path.name}"
                    )
                else:
                    self.logger.warning(f"PDFファイルが存在しません: {pdf_path}")
            
            # 結合したPDFを保存
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as output_file:
                merger.write(output_file)
            
            merger.close()
            
            self.progress_updated.emit(100, "PDF結合完了")
            self.generation_finished.emit(str(output_path))
            
            self.logger.info(f"PDF結合完了: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"PDF結合エラー: {e}")
            self.generation_error.emit(str(e))
            return False
    
    def get_pdf_info(self, pdf_path: Union[str, Path]) -> Optional[dict]:
        """
        PDFファイルの情報を取得
        
        Args:
            pdf_path: PDFファイルのパス
            
        Returns:
            PDF情報の辞書、失敗時はNone
        """
        try:
            from PyPDF2 import PdfReader
            
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                return None
            
            with open(pdf_path, 'rb') as pdf_file:
                reader = PdfReader(pdf_file)
                
                info = {
                    'filename': pdf_path.name,
                    'filepath': str(pdf_path),
                    'page_count': len(reader.pages),
                    'file_size': pdf_path.stat().st_size,
                    'encrypted': reader.is_encrypted
                }
                
                # メタデータを取得
                if reader.metadata:
                    info.update({
                        'title': reader.metadata.get('/Title', ''),
                        'author': reader.metadata.get('/Author', ''),
                        'subject': reader.metadata.get('/Subject', ''),
                        'creator': reader.metadata.get('/Creator', ''),
                        'producer': reader.metadata.get('/Producer', ''),
                        'creation_date': reader.metadata.get('/CreationDate', ''),
                        'modification_date': reader.metadata.get('/ModDate', '')
                    })
                
                return info
                
        except Exception as e:
            self.logger.error(f"PDF情報取得エラー: {pdf_path} - {e}")
            return None
    
    @staticmethod
    def get_available_page_sizes() -> List[str]:
        """
        利用可能なページサイズのリストを取得
        
        Returns:
            ページサイズ名のリスト
        """
        return list(PDFGenerator.PAGE_SIZES.keys())
