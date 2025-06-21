"""
PDF設定管理クラス
PDF関連の設定値を管理し、検証を行う
"""

import logging
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from .utils import (
    PDF_PAGE_SIZES, PDF_MARGIN_PRESETS, PDF_GENERATION_MODES, PDF_DEFAULTS,
    get_pdf_page_size_list, get_pdf_margin_preset_list
)


@dataclass
class PDFSettings:
    """PDF設定を格納するデータクラス"""
    
    # ページ設定
    page_size_name: str = PDF_DEFAULTS['page_size']
    margin_preset: str = PDF_DEFAULTS['margin_preset']
    custom_margins: Tuple[float, float, float, float] = field(default_factory=lambda: (28, 28, 28, 28))
    
    # 生成設定
    generation_mode: str = PDF_DEFAULTS['generation_mode']
    fit_to_page: bool = PDF_DEFAULTS['fit_to_page']
    maintain_aspect_ratio: bool = PDF_DEFAULTS['maintain_aspect_ratio']
    
    # メタデータ
    title: str = PDF_DEFAULTS['title']
    author: str = PDF_DEFAULTS['author']
    subject: str = PDF_DEFAULTS['subject']
    creator: str = PDF_DEFAULTS['creator']
    
    def __post_init__(self):
        """初期化後の検証"""
        self.validate()
    
    def validate(self) -> bool:
        """設定値の検証"""
        try:
            # ページサイズの検証
            if self.page_size_name not in get_pdf_page_size_list():
                self.page_size_name = PDF_DEFAULTS['page_size']
                logging.warning(f"無効なページサイズを修正: {self.page_size_name}")
            
            # マージンプリセットの検証
            if self.margin_preset not in get_pdf_margin_preset_list():
                self.margin_preset = PDF_DEFAULTS['margin_preset']
                logging.warning(f"無効なマージンプリセットを修正: {self.margin_preset}")
            
            # 生成モードの検証
            if self.generation_mode not in PDF_GENERATION_MODES:
                self.generation_mode = PDF_DEFAULTS['generation_mode']
                logging.warning(f"無効な生成モードを修正: {self.generation_mode}")
            
            # カスタムマージンの検証
            if len(self.custom_margins) != 4:
                self.custom_margins = (28, 28, 28, 28)
                logging.warning("無効なカスタムマージンを修正")
            
            # マージン値の範囲チェック
            validated_margins = []
            for margin in self.custom_margins:
                if not isinstance(margin, (int, float)) or margin < 0 or margin > 200:
                    validated_margins.append(28)  # デフォルト値
                else:
                    validated_margins.append(float(margin))
            self.custom_margins = tuple(validated_margins)
            
            return True
            
        except Exception as e:
            logging.error(f"PDF設定検証エラー: {e}")
            return False
    
    def get_page_size(self) -> Tuple[float, float]:
        """ページサイズを取得"""
        return PDF_PAGE_SIZES.get(self.page_size_name, PDF_PAGE_SIZES[PDF_DEFAULTS['page_size']])
    
    def get_margins(self) -> Tuple[float, float, float, float]:
        """マージンを取得"""
        if self.margin_preset == 'カスタム':
            return self.custom_margins
        else:
            return PDF_MARGIN_PRESETS.get(self.margin_preset, PDF_MARGIN_PRESETS[PDF_DEFAULTS['margin_preset']])
    
    def is_advanced_mode(self) -> bool:
        """高度モードかどうかを判定"""
        return PDF_GENERATION_MODES.get(self.generation_mode, 'simple') == 'advanced'
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'page_size_name': self.page_size_name,
            'page_size': self.get_page_size(),
            'margins': self.get_margins(),
            'fit_to_page': self.fit_to_page,
            'maintain_aspect_ratio': self.maintain_aspect_ratio,
            'advanced_mode': self.is_advanced_mode(),
            'title': self.title,
            'author': self.author,
            'subject': self.subject,
            'creator': self.creator
        }
    
    @classmethod
    def from_ui_values(
        cls,
        page_size_name: str,
        margin_preset: str,
        custom_margins: Tuple[float, float, float, float],
        generation_mode: str,
        fit_to_page: bool,
        maintain_aspect_ratio: bool,
        title: str = "",
        author: str = "",
        subject: str = ""
    ) -> "PDFSettings":
        """UI値からPDFSettingsを作成"""
        return cls(
            page_size_name=page_size_name,
            margin_preset=margin_preset,
            custom_margins=custom_margins,
            generation_mode=generation_mode,
            fit_to_page=fit_to_page,
            maintain_aspect_ratio=maintain_aspect_ratio,
            title=title.strip(),
            author=author.strip(),
            subject=subject.strip()
        )


class PDFConfigManager:
    """PDF設定管理クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._current_settings = PDFSettings()
    
    @property
    def current_settings(self) -> PDFSettings:
        """現在の設定を取得"""
        return self._current_settings
    
    def update_settings(self, new_settings: PDFSettings) -> bool:
        """設定を更新"""
        try:
            if new_settings.validate():
                self._current_settings = new_settings
                self.logger.info("PDF設定を更新しました")
                return True
            else:
                self.logger.error("PDF設定の更新に失敗しました")
                return False
        except Exception as e:
            self.logger.error(f"PDF設定更新エラー: {e}")
            return False
    
    def get_generation_settings(self) -> Dict[str, Any]:
        """PDF生成用の設定辞書を取得"""
        return self._current_settings.to_dict()
    
    def reset_to_defaults(self):
        """設定をデフォルト値にリセット"""
        self._current_settings = PDFSettings()
        self.logger.info("PDF設定をデフォルト値にリセットしました")
    
    def get_ui_values(self) -> Dict[str, Any]:
        """UI表示用の値を取得"""
        settings = self._current_settings
        return {
            'page_size_name': settings.page_size_name,
            'margin_preset': settings.margin_preset,
            'custom_margins': settings.custom_margins,
            'generation_mode': settings.generation_mode,
            'fit_to_page': settings.fit_to_page,
            'maintain_aspect_ratio': settings.maintain_aspect_ratio,
            'title': settings.title,
            'author': settings.author,
            'subject': settings.subject
        }


# グローバルな設定管理インスタンス
pdf_config_manager = PDFConfigManager()


def get_pdf_config_manager() -> PDFConfigManager:
    """PDF設定管理インスタンスを取得"""
    return pdf_config_manager