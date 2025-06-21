"""
PDF設定管理のテスト
"""

import pytest
from src.pdf_config import PDFSettings, PDFConfigManager
from src.utils import PDF_DEFAULTS, PDF_PAGE_SIZES, PDF_MARGIN_PRESETS


class TestPDFSettings:
    """PDFSettingsクラスのテスト"""
    
    def test_default_initialization(self):
        """デフォルト初期化のテスト"""
        settings = PDFSettings()
        
        assert settings.page_size_name == PDF_DEFAULTS['page_size']
        assert settings.margin_preset == PDF_DEFAULTS['margin_preset']
        assert settings.generation_mode == PDF_DEFAULTS['generation_mode']
        assert settings.fit_to_page == PDF_DEFAULTS['fit_to_page']
        assert settings.maintain_aspect_ratio == PDF_DEFAULTS['maintain_aspect_ratio']
        assert settings.title == PDF_DEFAULTS['title']
        assert settings.author == PDF_DEFAULTS['author']
        assert settings.subject == PDF_DEFAULTS['subject']
        assert settings.creator == PDF_DEFAULTS['creator']
    
    def test_custom_initialization(self):
        """カスタム初期化のテスト"""
        settings = PDFSettings(
            page_size_name='Letter',
            margin_preset='広い',
            generation_mode='高度',
            fit_to_page=False,
            maintain_aspect_ratio=False,
            title='テストPDF',
            author='テスト作成者',
            subject='テスト件名'
        )
        
        assert settings.page_size_name == 'Letter'
        assert settings.margin_preset == '広い'
        assert settings.generation_mode == '高度'
        assert settings.fit_to_page == False
        assert settings.maintain_aspect_ratio == False
        assert settings.title == 'テストPDF'
        assert settings.author == 'テスト作成者'
        assert settings.subject == 'テスト件名'
    
    def test_validation_invalid_page_size(self):
        """無効なページサイズの検証テスト"""
        settings = PDFSettings(page_size_name='INVALID')
        
        # 自動的にデフォルト値に修正される
        assert settings.page_size_name == PDF_DEFAULTS['page_size']
    
    def test_validation_invalid_margin_preset(self):
        """無効なマージンプリセットの検証テスト"""
        settings = PDFSettings(margin_preset='INVALID')
        
        # 自動的にデフォルト値に修正される
        assert settings.margin_preset == PDF_DEFAULTS['margin_preset']
    
    def test_validation_invalid_generation_mode(self):
        """無効な生成モードの検証テスト"""
        settings = PDFSettings(generation_mode='INVALID')
        
        # 自動的にデフォルト値に修正される
        assert settings.generation_mode == PDF_DEFAULTS['generation_mode']
    
    def test_validation_invalid_margins(self):
        """無効なカスタムマージンの検証テスト"""
        # 長さが不正
        settings = PDFSettings(custom_margins=(10, 20))
        assert len(settings.custom_margins) == 4
        
        # 負の値
        settings = PDFSettings(custom_margins=(-10, 20, 30, 40))
        assert all(margin >= 0 for margin in settings.custom_margins)
        
        # 範囲外の値
        settings = PDFSettings(custom_margins=(10, 20, 30, 250))
        assert all(margin <= 200 for margin in settings.custom_margins)
    
    def test_get_page_size(self):
        """ページサイズ取得のテスト"""
        settings = PDFSettings(page_size_name='A4')
        page_size = settings.get_page_size()
        
        assert page_size == PDF_PAGE_SIZES['A4']
        assert isinstance(page_size, tuple)
        assert len(page_size) == 2
    
    def test_get_margins_preset(self):
        """マージン取得（プリセット）のテスト"""
        settings = PDFSettings(margin_preset='広い')
        margins = settings.get_margins()
        
        assert margins == PDF_MARGIN_PRESETS['広い']
        assert isinstance(margins, tuple)
        assert len(margins) == 4
    
    def test_get_margins_custom(self):
        """マージン取得（カスタム）のテスト"""
        custom_margins = (10, 20, 30, 40)
        settings = PDFSettings(
            margin_preset='カスタム',
            custom_margins=custom_margins
        )
        margins = settings.get_margins()
        
        assert margins == custom_margins
    
    def test_is_advanced_mode(self):
        """高度モード判定のテスト"""
        # シンプルモード
        settings = PDFSettings(generation_mode='シンプル')
        assert settings.is_advanced_mode() == False
        
        # 高度モード
        settings = PDFSettings(generation_mode='高度')
        assert settings.is_advanced_mode() == True
    
    def test_to_dict(self):
        """辞書変換のテスト"""
        settings = PDFSettings(
            page_size_name='Letter',
            title='テストPDF'
        )
        
        result = settings.to_dict()
        
        assert isinstance(result, dict)
        assert result['page_size_name'] == 'Letter'
        assert result['title'] == 'テストPDF'
        assert 'page_size' in result
        assert 'margins' in result
        assert 'advanced_mode' in result
    
    def test_from_ui_values(self):
        """UI値からの作成テスト"""
        settings = PDFSettings.from_ui_values(
            page_size_name='A3',
            margin_preset='狭い',
            custom_margins=(5, 5, 5, 5),
            generation_mode='高度',
            fit_to_page=False,
            maintain_aspect_ratio=False,
            title='  テストタイトル  ',  # 前後の空白
            author='テスト作成者',
            subject='テスト件名'
        )
        
        assert settings.page_size_name == 'A3'
        assert settings.margin_preset == '狭い'
        assert settings.custom_margins == (5, 5, 5, 5)
        assert settings.generation_mode == '高度'
        assert settings.fit_to_page == False
        assert settings.maintain_aspect_ratio == False
        assert settings.title == 'テストタイトル'  # 空白が除去される
        assert settings.author == 'テスト作成者'
        assert settings.subject == 'テスト件名'


class TestPDFConfigManager:
    """PDFConfigManagerクラスのテスト"""
    
    @pytest.fixture
    def config_manager(self):
        """テスト用設定管理インスタンス"""
        return PDFConfigManager()
    
    def test_initialization(self, config_manager):
        """初期化のテスト"""
        assert isinstance(config_manager.current_settings, PDFSettings)
        assert config_manager.current_settings.page_size_name == PDF_DEFAULTS['page_size']
    
    def test_update_settings_valid(self, config_manager):
        """有効な設定更新のテスト"""
        new_settings = PDFSettings(
            page_size_name='Letter',
            title='新しいタイトル'
        )
        
        result = config_manager.update_settings(new_settings)
        
        assert result == True
        assert config_manager.current_settings.page_size_name == 'Letter'
        assert config_manager.current_settings.title == '新しいタイトル'
    
    def test_update_settings_invalid(self, config_manager):
        """無効な設定更新のテスト"""
        # 無効な設定でも検証により修正される
        new_settings = PDFSettings(page_size_name='INVALID')
        
        result = config_manager.update_settings(new_settings)
        
        assert result == True  # 検証により修正されるため成功
        assert config_manager.current_settings.page_size_name == PDF_DEFAULTS['page_size']
    
    def test_get_generation_settings(self, config_manager):
        """生成設定取得のテスト"""
        settings_dict = config_manager.get_generation_settings()
        
        assert isinstance(settings_dict, dict)
        assert 'page_size_name' in settings_dict
        assert 'page_size' in settings_dict
        assert 'margins' in settings_dict
        assert 'advanced_mode' in settings_dict
    
    def test_reset_to_defaults(self, config_manager):
        """デフォルト値リセットのテスト"""
        # 設定を変更
        new_settings = PDFSettings(page_size_name='Letter', title='変更されたタイトル')
        config_manager.update_settings(new_settings)
        
        # リセット
        config_manager.reset_to_defaults()
        
        # デフォルト値に戻っていることを確認
        assert config_manager.current_settings.page_size_name == PDF_DEFAULTS['page_size']
        assert config_manager.current_settings.title == PDF_DEFAULTS['title']
    
    def test_get_ui_values(self, config_manager):
        """UI値取得のテスト"""
        ui_values = config_manager.get_ui_values()
        
        assert isinstance(ui_values, dict)
        assert 'page_size_name' in ui_values
        assert 'margin_preset' in ui_values
        assert 'custom_margins' in ui_values
        assert 'generation_mode' in ui_values
        assert 'fit_to_page' in ui_values
        assert 'maintain_aspect_ratio' in ui_values
        assert 'title' in ui_values
        assert 'author' in ui_values
        assert 'subject' in ui_values


class TestIntegration:
    """統合テスト"""
    
    def test_settings_workflow(self):
        """設定ワークフローの統合テスト"""
        # 1. UI値からPDFSettings作成
        settings = PDFSettings.from_ui_values(
            page_size_name='A3',
            margin_preset='カスタム',
            custom_margins=(15, 15, 15, 15),
            generation_mode='高度',
            fit_to_page=False,
            maintain_aspect_ratio=True,
            title='統合テストPDF',
            author='テスト実行者',
            subject='統合テスト'
        )
        
        # 2. 設定管理に適用
        config_manager = PDFConfigManager()
        success = config_manager.update_settings(settings)
        assert success == True
        
        # 3. 生成設定を取得
        generation_settings = config_manager.get_generation_settings()
        
        # 4. 設定値の確認
        assert generation_settings['page_size_name'] == 'A3'
        assert generation_settings['margins'] == (15, 15, 15, 15)
        assert generation_settings['advanced_mode'] == True
        assert generation_settings['fit_to_page'] == False
        assert generation_settings['maintain_aspect_ratio'] == True
        assert generation_settings['title'] == '統合テストPDF'
        assert generation_settings['author'] == 'テスト実行者'
        assert generation_settings['subject'] == '統合テスト'
        
        # 5. UI値の取得
        ui_values = config_manager.get_ui_values()
        assert ui_values['page_size_name'] == 'A3'
        assert ui_values['margin_preset'] == 'カスタム'
        assert ui_values['custom_margins'] == (15, 15, 15, 15)


# テスト実行用
if __name__ == '__main__':
    pytest.main([__file__, '-v'])