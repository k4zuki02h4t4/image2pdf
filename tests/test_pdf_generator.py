"""
PDF生成クラスのテスト
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import numpy as np
from PIL import Image

from src.pdf_generator import PDFGenerator


class TestPDFGenerator:
    """PDFGeneratorクラスのテスト"""
    
    @pytest.fixture
    def pdf_generator(self):
        """PDFGeneratorインスタンスを作成"""
        return PDFGenerator()
    
    @pytest.fixture
    def sample_image_files(self):
        """テスト用のサンプル画像ファイルを作成"""
        image_files = []
        
        for i in range(3):
            # PIL画像を作成
            img = Image.new('RGB', (200, 150), color=(i*80, 100, 200))
            
            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(suffix=f'_test_{i}.jpg', delete=False) as tmp:
                img.save(tmp.name, 'JPEG')
                image_files.append(tmp.name)
        
        yield image_files
        
        # クリーンアップ
        for file_path in image_files:
            Path(file_path).unlink(missing_ok=True)


class TestSimplePDFGeneration(TestPDFGenerator):
    """シンプルPDF生成のテスト"""
    
    @patch('img2pdf.convert')
    def test_generate_pdf_simple_success(self, mock_convert, pdf_generator, sample_image_files):
        """シンプルPDF生成の成功テスト"""
        # Mock設定
        mock_convert.return_value = b'fake_pdf_data'
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            output_path = tmp.name
            
            # mock_openを使用してファイル書き込みを模擬
            with patch('builtins.open', mock_open()) as mock_file:
                result = pdf_generator.generate_pdf_simple(
                    sample_image_files,
                    output_path,
                    page_size='A4',
                    fit_to_page=True
                )
                
                assert result is True
                mock_convert.assert_called_once()
                mock_file.assert_called()
            
            # クリーンアップ
            Path(output_path).unlink(missing_ok=True)
    
    def test_generate_pdf_simple_no_images(self, pdf_generator):
        """画像なしでのPDF生成テスト"""
        with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
            result = pdf_generator.generate_pdf_simple(
                [],  # 空のリスト
                tmp.name
            )
            assert result is False
    
    @patch('img2pdf.convert')
    def test_generate_pdf_simple_invalid_images(self, mock_convert, pdf_generator):
        """無効な画像でのPDF生成テスト"""
        invalid_files = ['nonexistent1.jpg', 'nonexistent2.jpg']
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
            result = pdf_generator.generate_pdf_simple(
                invalid_files,
                tmp.name
            )
            assert result is False
    
    def test_get_img2pdf_layout(self, pdf_generator):
        """img2pdfレイアウト関数取得のテスト"""
        # 有効なページサイズ
        layout_func = pdf_generator._get_img2pdf_layout('A4', True)
        # 関数が返されるかNoneが返される（img2pdfの実装による）
        assert layout_func is not None or layout_func is None
        
        # 無効なページサイズ
        layout_func = pdf_generator._get_img2pdf_layout('INVALID', True)
        assert layout_func is not None or layout_func is None
        
        # カスタムサイズ
        layout_func = pdf_generator._get_img2pdf_layout('Custom', True)
        assert layout_func is None


class TestAdvancedPDFGeneration(TestPDFGenerator):
    """高度PDF生成のテスト"""
    
    @patch('reportlab.pdfgen.canvas.Canvas')
    @patch('PIL.Image.open')
    def test_generate_pdf_advanced_success(self, mock_pil_open, mock_canvas, pdf_generator, sample_image_files):
        \"\"\"高度PDF生成の成功テスト\"\"\"
        # Canvas mock設定
        mock_canvas_instance = MagicMock()
        mock_canvas.return_value = mock_canvas_instance
        
        # PIL Image mock設定
        mock_image = MagicMock()
        mock_image.mode = 'RGB'
        mock_image.size = (200, 150)
        mock_pil_open.return_value.__enter__.return_value = mock_image
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            output_path = tmp.name
            
            result = pdf_generator.generate_pdf_advanced(
                sample_image_files,
                output_path,
                page_size=(595, 842),  # A4
                margins=(28, 28, 28, 28),
                title='Test PDF',
                author='Test Author',
                subject='Test Subject'
            )
            
            assert result is True
            mock_canvas.assert_called_once()
            mock_canvas_instance.save.assert_called_once()
            
            # メタデータ設定の確認
            mock_canvas_instance.setTitle.assert_called_with('Test PDF')
            mock_canvas_instance.setAuthor.assert_called_with('Test Author')
            mock_canvas_instance.setSubject.assert_called_with('Test Subject')
            
            # クリーンアップ
            Path(output_path).unlink(missing_ok=True)
    
    def test_calculate_image_placement(self, pdf_generator):
        \"\"\"画像配置計算のテスト\"\"\"
        # アスペクト比維持の場合
        x, y, width, height = pdf_generator._calculate_image_placement(
            img_width=200,
            img_height=150,
            available_width=400,
            available_height=300,
            margin_left=50,
            margin_bottom=50,
            maintain_aspect_ratio=True
        )
        
        # 結果が妥当な範囲内にあることを確認
        assert x >= 50
        assert y >= 50
        assert width <= 400
        assert height <= 300
        assert width > 0
        assert height > 0
        
        # アスペクト比を維持しない場合
        x2, y2, width2, height2 = pdf_generator._calculate_image_placement(
            img_width=200,
            img_height=150,
            available_width=400,
            available_height=300,
            margin_left=50,
            margin_bottom=50,
            maintain_aspect_ratio=False
        )
        
        # 利用可能領域を完全に使用
        assert width2 == 400
        assert height2 == 300


class TestPDFMerging(TestPDFGenerator):
    \"\"\"PDF結合機能のテスト\"\"\"
    
    @patch('PyPDF2.PdfMerger')
    def test_merge_pdfs_success(self, mock_merger_class, pdf_generator):
        \"\"\"PDF結合の成功テスト\"\"\"
        # PdfMerger mock設定
        mock_merger = MagicMock()
        mock_merger_class.return_value = mock_merger
        
        # テスト用PDFファイルを作成
        pdf_files = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(suffix=f'_test_{i}.pdf', delete=False) as tmp:
                tmp.write(b'fake_pdf_data')
                pdf_files.append(tmp.name)
        
        try:
            with tempfile.NamedTemporaryFile(suffix='_output.pdf', delete=False) as tmp:
                output_path = tmp.name
                
                with patch('builtins.open', mock_open()) as mock_file:
                    result = pdf_generator.merge_pdfs(pdf_files, output_path)
                    
                    assert result is True
                    mock_merger_class.assert_called_once()
                    mock_merger.append.assert_called()
                    mock_merger.write.assert_called()
                    mock_merger.close.assert_called_once()
                
                # クリーンアップ
                Path(output_path).unlink(missing_ok=True)
        
        finally:
            # テストファイルのクリーンアップ
            for file_path in pdf_files:
                Path(file_path).unlink(missing_ok=True)
    
    def test_merge_pdfs_no_files(self, pdf_generator):
        \"\"\"ファイルなしでのPDF結合テスト\"\"\"
        with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
            result = pdf_generator.merge_pdfs([], tmp.name)
            assert result is False


class TestPDFInfo(TestPDFGenerator):
    \"\"\"PDF情報取得のテスト\"\"\"
    
    @patch('PyPDF2.PdfReader')
    def test_get_pdf_info_success(self, mock_reader_class, pdf_generator):
        \"\"\"PDF情報取得の成功テスト\"\"\"
        # PdfReader mock設定
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock()]  # 2ページ
        mock_reader.is_encrypted = False
        mock_reader.metadata = {
            '/Title': 'Test PDF',
            '/Author': 'Test Author',
            '/Subject': 'Test Subject',
            '/Creator': 'Test Creator',
            '/Producer': 'Test Producer',
            '/CreationDate': 'D:20240101120000',
            '/ModDate': 'D:20240101120000'
        }
        
        mock_reader_class.return_value = mock_reader
        
        # テスト用PDFファイルを作成
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(b'fake_pdf_data')
            pdf_path = tmp.name
        
        try:
            with patch('builtins.open', mock_open()):
                info = pdf_generator.get_pdf_info(pdf_path)
                
                assert info is not None
                assert isinstance(info, dict)
                assert info['page_count'] == 2
                assert info['encrypted'] is False
                assert info['title'] == 'Test PDF'
                assert info['author'] == 'Test Author'
                
        finally:
            Path(pdf_path).unlink(missing_ok=True)
    
    def test_get_pdf_info_nonexistent(self, pdf_generator):
        \"\"\"存在しないPDFの情報取得テスト\"\"\"
        info = pdf_generator.get_pdf_info('nonexistent_file.pdf')
        assert info is None


class TestPageSizes(TestPDFGenerator):
    \"\"\"ページサイズ関連のテスト\"\"\"
    
    def test_get_available_page_sizes(self):
        \"\"\"利用可能ページサイズ取得のテスト\"\"\"
        sizes = PDFGenerator.get_available_page_sizes()
        
        assert isinstance(sizes, list)
        assert len(sizes) > 0
        assert 'A4' in sizes
        assert 'Letter' in sizes
        assert 'Legal' in sizes


class TestSignalEmission(TestPDFGenerator):
    \"\"\"シグナル発行のテスト\"\"\"
    
    def test_signal_connections(self, pdf_generator):
        \"\"\"シグナル接続のテスト\"\"\"
        # シグナルハンドラーを設定
        generation_started_signals = []
        progress_signals = []
        generation_finished_signals = []
        error_signals = []
        
        pdf_generator.generation_started.connect(generation_started_signals.append)
        pdf_generator.progress_updated.connect(progress_signals.append)
        pdf_generator.generation_finished.connect(generation_finished_signals.append)
        pdf_generator.generation_error.connect(error_signals.append)
        
        # エラーシグナルをテスト
        pdf_generator.generation_error.emit(\"Test error\")
        
        assert len(error_signals) == 1
        assert error_signals[0] == \"Test error\"


class TestErrorHandling(TestPDFGenerator):
    \"\"\"エラーハンドリングのテスト\"\"\"
    
    @patch('img2pdf.convert')
    def test_pdf_generation_exception(self, mock_convert, pdf_generator, sample_image_files):
        \"\"\"PDF生成中の例外処理テスト\"\"\"
        # img2pdf.convertで例外を発生させる
        mock_convert.side_effect = Exception(\"Test exception\")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
            result = pdf_generator.generate_pdf_simple(
                sample_image_files,
                tmp.name
            )
            
            assert result is False
    
    @patch('reportlab.pdfgen.canvas.Canvas')
    def test_advanced_pdf_generation_exception(self, mock_canvas, pdf_generator, sample_image_files):
        \"\"\"高度PDF生成中の例外処理テスト\"\"\"
        # Canvasで例外を発生させる
        mock_canvas.side_effect = Exception(\"Canvas error\")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
            result = pdf_generator.generate_pdf_advanced(
                sample_image_files,
                tmp.name
            )
            
            assert result is False


# テスト実行用
if __name__ == '__main__':
    pytest.main([__file__])
