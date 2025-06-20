"""
メインウィンドウ
Image2PDF アプリケーションのメインGUIウィンドウ
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QListWidget, QListWidgetItem, QGroupBox,
    QFileDialog, QMessageBox, QProgressBar, QStatusBar,
    QMenuBar, QMenu, QToolBar
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QThread, QTimer, QSettings, 
    QStandardPaths, QMimeData, QUrl
)
from PyQt6.QtGui import (
    QAction, QIcon, QPixmap, QDragEnterEvent, 
    QDropEvent, QCloseEvent, QKeySequence
)

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon,
    PushButton, ToolButton, CommandBar, Action,
    InfoBar, InfoBarPosition, MessageBox, Dialog,
    BodyLabel, StrongBodyLabel, ComboBox, SpinBox,
    CheckBox, LineEdit, FilledPushButton, TransparentPushButton,
    CardWidget, HeaderCardWidget, ElevatedCardWidget,
    ProgressRing, StateToolTip, TeachingTip, TeachingTipTailPosition
)

from .utils import (
    is_image_file, get_image_filter_string, 
    validate_pdf_filename, format_file_size, get_temp_dir
)
from .image_processor import ImageProcessor
from .pdf_generator import PDFGenerator  
from .crop_widget import CropWidget


class ImageListWidget(QListWidget):
    """画像リスト表示・並び替え可能ウィジェット"""
    
    # シグナル定義
    images_reordered = pyqtSignal(list)  # 画像順序変更
    image_selected = pyqtSignal(str)  # 画像選択
    image_removed = pyqtSignal(str)  # 画像削除
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        # ドラッグ&ドロップ設定
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        # 選択設定
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        
        # スタイル設定
        self.setAlternatingRowColors(True)
        self.setMinimumHeight(200)
        
        # シグナル接続
        self.itemClicked.connect(self._on_item_clicked)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        """ドラッグ開始イベント"""
        if event.mimeData().hasUrls():
            # 外部ファイルのドラッグ
            urls = event.mimeData().urls()
            if any(is_image_file(url.toLocalFile()) for url in urls):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            # 内部アイテムの並び替え
            super().dragEnterEvent(event)
    
    def dragMoveEvent(self, event):
        """ドラッグ移動イベント"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)
    
    def dropEvent(self, event: QDropEvent):
        """ドロップイベント"""
        if event.mimeData().hasUrls():
            # 外部ファイルのドロップ
            urls = event.mimeData().urls()
            image_files = [url.toLocalFile() for url in urls if is_image_file(url.toLocalFile())]
            
            if image_files:
                # メインウィンドウに画像追加を依頼
                main_window = self.window()
                if hasattr(main_window, 'add_images'):
                    main_window.add_images(image_files)
            
            event.acceptProposedAction()
        else:
            # 内部アイテムの並び替え
            super().dropEvent(event)
            # 順序変更を通知
            self._emit_reorder_signal()
    
    def _emit_reorder_signal(self):
        """順序変更シグナルを発行"""
        image_paths = []
        for i in range(self.count()):
            item = self.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole):
                image_paths.append(item.data(Qt.ItemDataRole.UserRole))
        
        self.images_reordered.emit(image_paths)
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """アイテムクリック時の処理"""
        if item and item.data(Qt.ItemDataRole.UserRole):
            image_path = item.data(Qt.ItemDataRole.UserRole)
            self.image_selected.emit(image_path)
    
    def _on_selection_changed(self):
        """選択変更時の処理"""
        current_item = self.currentItem()
        if current_item and current_item.data(Qt.ItemDataRole.UserRole):
            image_path = current_item.data(Qt.ItemDataRole.UserRole)
            self.image_selected.emit(image_path)
    
    def add_image(self, image_path: str, thumbnail: Optional[QPixmap] = None):
        """画像をリストに追加"""
        try:
            path = Path(image_path)
            if not path.exists():
                return
            
            # アイテム作成
            item = QListWidgetItem()
            item.setText(f"{path.name}\n{format_file_size(path.stat().st_size)}")
            item.setData(Qt.ItemDataRole.UserRole, image_path)
            
            # サムネイル設定
            if thumbnail:
                # サムネイルサイズを調整
                scaled_thumbnail = thumbnail.scaled(
                    64, 64, 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                item.setIcon(QIcon(scaled_thumbnail))
            
            # ツールチップ設定
            item.setToolTip(f"ファイル: {path.name}\nパス: {image_path}")
            
            self.addItem(item)
            self.logger.info(f"画像をリストに追加: {path.name}")
            
        except Exception as e:
            self.logger.error(f"画像リスト追加エラー: {image_path} - {e}")
    
    def remove_current_image(self):
        """現在選択中の画像を削除"""
        current_item = self.currentItem()
        if current_item:
            image_path = current_item.data(Qt.ItemDataRole.UserRole)
            row = self.row(current_item)
            self.takeItem(row)
            
            if image_path:
                self.image_removed.emit(image_path)
                self.logger.info(f"画像をリストから削除: {Path(image_path).name}")
    
    def clear_all_images(self):
        """すべての画像をクリア"""
        self.clear()
        self.logger.info("画像リストをクリア")
    
    def get_all_image_paths(self) -> List[str]:
        """すべての画像パスを取得"""
        image_paths = []
        for i in range(self.count()):
            item = self.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole):
                image_paths.append(item.data(Qt.ItemDataRole.UserRole))
        return image_paths


class PDFGenerationThread(QThread):
    """PDF生成用ワーカースレッド"""
    
    # シグナル定義
    progress_updated = pyqtSignal(int, str)  # 進捗更新
    generation_finished = pyqtSignal(bool, str)  # 生成完了 (成功/失敗, メッセージ)
    
    def __init__(self, image_paths: List[str], output_path: str, settings: Dict[str, Any]):
        super().__init__()
        self.image_paths = image_paths
        self.output_path = output_path
        self.settings = settings
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """PDF生成実行"""
        try:
            self.progress_updated.emit(0, "PDF生成を開始...")
            
            # PDF生成器を作成
            generator = PDFGenerator()
            generator.progress_updated.connect(self.progress_updated)
            
            # 設定に応じて生成方法を選択
            if self.settings.get('advanced_mode', False):
                success = generator.generate_pdf_advanced(
                    self.image_paths,
                    self.output_path,
                    page_size=self.settings.get('page_size', (595, 842)),  # A4
                    margins=self.settings.get('margins', (28, 28, 28, 28)),  # 1cm
                    title=self.settings.get('title', ''),
                    author=self.settings.get('author', ''),
                    subject=self.settings.get('subject', ''),
                    fit_to_page=self.settings.get('fit_to_page', True),
                    maintain_aspect_ratio=self.settings.get('maintain_aspect_ratio', True)
                )
            else:
                success = generator.generate_pdf_simple(
                    self.image_paths,
                    self.output_path,
                    page_size=self.settings.get('page_size_name', 'A4'),
                    fit_to_page=self.settings.get('fit_to_page', True)
                )
            
            if success:
                self.generation_finished.emit(True, f"PDFが正常に生成されました: {self.output_path}")
            else:
                self.generation_finished.emit(False, "PDF生成に失敗しました")
                
        except Exception as e:
            self.logger.error(f"PDF生成スレッドエラー: {e}")
            self.generation_finished.emit(False, f"エラーが発生しました: {e}")


class MainWindow(FluentWindow):
    """メインウィンドウクラス"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # データ
        self.image_processor = ImageProcessor()
        self.pdf_generator = PDFGenerator()
        self.current_images: List[str] = []
        self.settings = QSettings('Image2PDF', 'Image2PDF')
        
        # UI コンポーネント
        self.image_list_widget: Optional[ImageListWidget] = None
        self.crop_widget: Optional[CropWidget] = None
        self.progress_bar: Optional[QProgressBar] = None
        self.status_label: Optional[BodyLabel] = None
        
        # PDF生成スレッド
        self.pdf_thread: Optional[PDFGenerationThread] = None
        
        # 初期化
        self._setup_ui()
        self._setup_navigation()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        self._load_settings()
        
        # ウィンドウ設定
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        self.setWindowTitle("Image2PDF - 画像からPDF変換ツール")
        
        # 最初のページを表示
        self.stackedWidget.setCurrentIndex(0)
        
        self.logger.info("メインウィンドウ初期化完了")
    
    def _setup_ui(self):
        """UI初期化"""
        # メインページの作成
        self._create_main_page()
        self._create_crop_page()
        self._create_settings_page()
    
    def _create_main_page(self):
        """メインページ作成"""
        main_page = QWidget()
        layout = QHBoxLayout(main_page)
        
        # 左側パネル（画像リスト）
        left_panel = self._create_left_panel()
        
        # 右側パネル（プレビュー・設定）
        right_panel = self._create_right_panel()
        
        # スプリッター
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])
        
        layout.addWidget(splitter)
        
        # ナビゲーションに追加
        self.addSubInterface(main_page, FluentIcon.HOME, "メイン", NavigationItemPosition.TOP)
    
    def _create_left_panel(self) -> QWidget:
        """左側パネル（画像リスト）作成"""
        panel = CardWidget()
        layout = QVBoxLayout(panel)
        
        # タイトル
        title_label = StrongBodyLabel("画像ファイル")
        layout.addWidget(title_label)
        
        # ボタン群
        button_layout = QHBoxLayout()
        
        self.add_files_btn = PushButton("ファイル追加")
        self.add_files_btn.setIcon(FluentIcon.ADD)
        
        self.remove_file_btn = PushButton("削除")
        self.remove_file_btn.setIcon(FluentIcon.DELETE)
        self.remove_file_btn.setEnabled(False)
        
        self.clear_all_btn = TransparentPushButton("すべてクリア")
        self.clear_all_btn.setIcon(FluentIcon.CLEAR_SELECTION)
        
        button_layout.addWidget(self.add_files_btn)
        button_layout.addWidget(self.remove_file_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.clear_all_btn)
        
        layout.addLayout(button_layout)
        
        # 画像リスト
        self.image_list_widget = ImageListWidget()
        layout.addWidget(self.image_list_widget)
        
        # 統計情報
        self.stats_label = BodyLabel("画像: 0 個")
        layout.addWidget(self.stats_label)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """右側パネル（プレビュー・設定）作成"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # プレビューエリア
        preview_card = HeaderCardWidget()
        preview_card.setTitle("画像プレビュー")
        preview_layout = QVBoxLayout()
        
        self.preview_label = BodyLabel("画像を選択してください")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setStyleSheet("border: 2px dashed #ccc; border-radius: 8px;")
        
        preview_layout.addWidget(self.preview_label)
        preview_card.addWidget(QWidget())  # プレースホルダー
        preview_card.layout().addLayout(preview_layout)
        
        layout.addWidget(preview_card)
        
        # PDF生成設定
        settings_card = self._create_pdf_settings_card()
        layout.addWidget(settings_card)
        
        # 生成ボタン
        self.generate_pdf_btn = FilledPushButton("PDF生成")
        self.generate_pdf_btn.setIcon(FluentIcon.SAVE)
        self.generate_pdf_btn.setEnabled(False)
        layout.addWidget(self.generate_pdf_btn)
        
        return panel
    
    def _create_pdf_settings_card(self) -> CardWidget:
        """PDF生成設定カード作成"""
        card = HeaderCardWidget()
        card.setTitle("PDF設定")
        
        layout = QVBoxLayout()
        
        # ページサイズ
        page_size_layout = QHBoxLayout()
        page_size_layout.addWidget(BodyLabel("ページサイズ:"))
        
        self.page_size_combo = ComboBox()
        self.page_size_combo.addItems(["A4", "Letter", "Legal", "A3", "A5"])
        self.page_size_combo.setCurrentText("A4")
        
        page_size_layout.addWidget(self.page_size_combo)
        page_size_layout.addStretch()
        layout.addLayout(page_size_layout)
        
        # オプション
        self.fit_to_page_cb = CheckBox("ページに合わせる")
        self.fit_to_page_cb.setChecked(True)
        
        self.maintain_aspect_cb = CheckBox("アスペクト比を維持")
        self.maintain_aspect_cb.setChecked(True)
        
        layout.addWidget(self.fit_to_page_cb)
        layout.addWidget(self.maintain_aspect_cb)
        
        # ファイル名設定
        filename_layout = QHBoxLayout()
        filename_layout.addWidget(BodyLabel("ファイル名:"))
        
        self.filename_edit = LineEdit()
        self.filename_edit.setPlaceholderText("出力ファイル名を入力")
        
        self.browse_btn = ToolButton()
        self.browse_btn.setIcon(FluentIcon.FOLDER)
        self.browse_btn.setToolTip("保存場所を選択")
        
        filename_layout.addWidget(self.filename_edit)
        filename_layout.addWidget(self.browse_btn)
        layout.addLayout(filename_layout)
        
        # カードにレイアウトを追加
        content_widget = QWidget()
        content_widget.setLayout(layout)
        card.addWidget(content_widget)
        
        return card
    
    def _create_crop_page(self):
        """切り抜きページ作成"""
        self.crop_widget = CropWidget()
        self.addSubInterface(self.crop_widget, FluentIcon.CUT, "画像切り抜き", NavigationItemPosition.TOP)
    
    def _create_settings_page(self):
        """設定ページ作成"""
        settings_page = QWidget()
        layout = QVBoxLayout(settings_page)
        
        # 設定項目を追加（今後の拡張用）
        title_label = StrongBodyLabel("アプリケーション設定")
        layout.addWidget(title_label)
        
        # 自動保存設定
        autosave_cb = CheckBox("自動保存を有効にする")
        layout.addWidget(autosave_cb)
        
        # テーマ設定
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(BodyLabel("テーマ:"))
        
        theme_combo = ComboBox()
        theme_combo.addItems(["自動", "ライト", "ダーク"])
        theme_layout.addWidget(theme_combo)
        theme_layout.addStretch()
        
        layout.addLayout(theme_layout)
        layout.addStretch()
        
        self.addSubInterface(settings_page, FluentIcon.SETTING, "設定", NavigationItemPosition.BOTTOM)
    
    def _setup_navigation(self):
        """ナビゲーション設定"""
        # アバター（オプション）
        # self.navigationInterface.addWidget(
        #     routeKey='avatar',
        #     widget=AvatarWidget(),
        #     position=NavigationItemPosition.BOTTOM
        # )
        pass
    
    def _setup_toolbar(self):
        """ツールバー設定"""
        # 将来的にコマンドバーを追加する場合
        pass
    
    def _setup_statusbar(self):
        """ステータスバー設定"""
        # FluentWindowはQMainWindowを継承していないので、
        # カスタムステータス表示を実装
        pass
    
    def _connect_signals(self):
        """シグナル接続"""
        # 画像リスト
        if self.image_list_widget:
            self.image_list_widget.images_reordered.connect(self._on_images_reordered)
            self.image_list_widget.image_selected.connect(self._on_image_selected)
            self.image_list_widget.image_removed.connect(self._on_image_removed)
        
        # ボタン
        self.add_files_btn.clicked.connect(self._add_files_dialog)
        self.remove_file_btn.clicked.connect(self._remove_current_image)
        self.clear_all_btn.clicked.connect(self._clear_all_images)
        self.generate_pdf_btn.clicked.connect(self._generate_pdf_dialog)
        self.browse_btn.clicked.connect(self._browse_output_location)
        
        # 切り抜きウィジェット
        if self.crop_widget:
            self.crop_widget.crop_completed.connect(self._on_crop_completed)
            self.crop_widget.image_rotated.connect(self._on_image_rotated)
        
        # 画像処理器
        self.image_processor.processing_error.connect(self._on_processing_error)
        
        # PDF生成器
        self.pdf_generator.generation_error.connect(self._on_pdf_generation_error)
    
    def _load_settings(self):
        """設定を読み込み"""
        try:
            # ウィンドウ位置・サイズ
            geometry = self.settings.value('geometry')
            if geometry:
                self.restoreGeometry(geometry)
            
            # PDF設定
            page_size = self.settings.value('pdf/page_size', 'A4')
            self.page_size_combo.setCurrentText(page_size)
            
            fit_to_page = self.settings.value('pdf/fit_to_page', True, type=bool)
            self.fit_to_page_cb.setChecked(fit_to_page)
            
            maintain_aspect = self.settings.value('pdf/maintain_aspect', True, type=bool)
            self.maintain_aspect_cb.setChecked(maintain_aspect)
            
            # 最後の出力ディレクトリ
            last_output_dir = self.settings.value('output/last_directory', '')
            if last_output_dir:
                self.last_output_directory = Path(last_output_dir)
            else:
                self.last_output_directory = Path.home() / "Documents"
            
            self.logger.info("設定読み込み完了")
            
        except Exception as e:
            self.logger.error(f"設定読み込みエラー: {e}")
    
    def _save_settings(self):
        """設定を保存"""
        try:
            # ウィンドウ位置・サイズ
            self.settings.setValue('geometry', self.saveGeometry())
            
            # PDF設定
            self.settings.setValue('pdf/page_size', self.page_size_combo.currentText())
            self.settings.setValue('pdf/fit_to_page', self.fit_to_page_cb.isChecked())
            self.settings.setValue('pdf/maintain_aspect', self.maintain_aspect_cb.isChecked())
            
            # 最後の出力ディレクトリ
            if hasattr(self, 'last_output_directory'):
                self.settings.setValue('output/last_directory', str(self.last_output_directory))
            
            self.logger.info("設定保存完了")
            
        except Exception as e:
            self.logger.error(f"設定保存エラー: {e}")
    
    def closeEvent(self, event: QCloseEvent):
        """ウィンドウ閉じるイベント"""
        # 進行中のタスクがある場合は確認
        if self.pdf_thread and self.pdf_thread.isRunning():
            reply = MessageBox(
                "確認", 
                "PDF生成が進行中です。アプリケーションを終了しますか？",
                self
            ).exec()
            
            if reply != MessageBox.StandardButton.Yes:
                event.ignore()
                return
            
            # スレッドを終了
            self.pdf_thread.terminate()
            self.pdf_thread.wait(3000)  # 3秒待機
        
        # 設定を保存
        self._save_settings()
        
        event.accept()
        self.logger.info("アプリケーション終了")
    
    def add_images(self, image_paths: List[str]):
        """画像を追加"""
        try:
            added_count = 0
            
            for image_path in image_paths:
                if is_image_file(image_path) and image_path not in self.current_images:
                    # サムネイル生成
                    thumbnail = self._generate_thumbnail(image_path)
                    
                    # リストに追加
                    self.image_list_widget.add_image(image_path, thumbnail)
                    self.current_images.append(image_path)
                    added_count += 1
            
            if added_count > 0:
                self._update_ui_state()
                InfoBar.success(
                    title="画像追加完了",
                    content=f"{added_count} 個の画像を追加しました",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )
            
            self.logger.info(f"画像追加: {added_count} 個")
            
        except Exception as e:
            self.logger.error(f"画像追加エラー: {e}")
            InfoBar.error(
                title="エラー",
                content=f"画像追加でエラーが発生しました: {e}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )
    
    def _generate_thumbnail(self, image_path: str) -> Optional[QPixmap]:
        """サムネイル生成"""
        try:
            from .utils import load_image_safely
            
            pixmap = load_image_safely(image_path)
            if pixmap:
                return pixmap.scaled(
                    64, 64, 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            return None
            
        except Exception as e:
            self.logger.error(f"サムネイル生成エラー: {image_path} - {e}")
            return None
    
    def _update_ui_state(self):
        """UI状態を更新"""
        has_images = len(self.current_images) > 0
        has_selection = self.image_list_widget.currentItem() is not None
        
        # ボタン状態
        self.remove_file_btn.setEnabled(has_selection)
        self.clear_all_btn.setEnabled(has_images)
        self.generate_pdf_btn.setEnabled(has_images)
        
        # 統計情報
        self.stats_label.setText(f"画像: {len(self.current_images)} 個")
        
        # デフォルトファイル名設定
        if has_images and not self.filename_edit.text():
            self.filename_edit.setText("output.pdf")
    
    # イベントハンドラー
    def _add_files_dialog(self):
        """ファイル追加ダイアログ"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "画像ファイルを選択",
            str(self.last_output_directory),
            get_image_filter_string()
        )
        
        if files:
            self.add_images(files)
    
    def _remove_current_image(self):
        """現在選択中の画像を削除"""
        self.image_list_widget.remove_current_image()
    
    def _clear_all_images(self):
        """すべての画像をクリア"""
        reply = MessageBox(
            "確認",
            "すべての画像をクリアします。よろしいですか？",
            self
        ).exec()
        
        if reply == MessageBox.StandardButton.Yes:
            self.image_list_widget.clear_all_images()
            self.current_images.clear()
            self._update_ui_state()
    
    def _browse_output_location(self):
        """出力場所選択"""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "PDFファイル保存場所を選択",
            str(self.last_output_directory / "output.pdf"),
            "PDF files (*.pdf);;All files (*.*)"
        )
        
        if filename:
            self.filename_edit.setText(filename)
            self.last_output_directory = Path(filename).parent
    
    def _generate_pdf_dialog(self):
        """PDF生成実行"""
        try:
            if not self.current_images:
                InfoBar.warning(
                    title="警告",
                    content="画像が選択されていません",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )
                return
            
            # 出力ファイル名を取得・検証
            output_path = self.filename_edit.text().strip()
            if not output_path:
                InfoBar.warning(
                    title="警告", 
                    content="出力ファイル名を入力してください",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )
                return
            
            output_path = validate_pdf_filename(output_path)
            
            # PDF生成設定を収集
            pdf_settings = {
                'page_size_name': self.page_size_combo.currentText(),
                'fit_to_page': self.fit_to_page_cb.isChecked(),
                'maintain_aspect_ratio': self.maintain_aspect_cb.isChecked(),
                'advanced_mode': False  # シンプルモード
            }
            
            # PDF生成スレッドを開始
            self._start_pdf_generation(output_path, pdf_settings)
            
        except Exception as e:
            self.logger.error(f"PDF生成開始エラー: {e}")
            InfoBar.error(
                title="エラー",
                content=f"PDF生成でエラーが発生しました: {e}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )
    
    def _start_pdf_generation(self, output_path: str, settings: Dict[str, Any]):
        """PDF生成開始"""
        try:
            # プログレス表示
            self.progress_ring = ProgressRing()
            self.state_tooltip = StateToolTip("PDF生成中", "しばらくお待ちください...", self)
            self.state_tooltip.show()
            
            # UI無効化
            self.generate_pdf_btn.setEnabled(False)
            
            # PDF生成スレッド作成・開始
            self.pdf_thread = PDFGenerationThread(
                self.current_images.copy(),
                output_path,
                settings
            )
            
            self.pdf_thread.progress_updated.connect(self._on_pdf_progress)
            self.pdf_thread.generation_finished.connect(self._on_pdf_generation_finished)
            self.pdf_thread.start()
            
            self.logger.info(f"PDF生成開始: {output_path}")
            
        except Exception as e:
            self.logger.error(f"PDF生成スレッド開始エラー: {e}")
            self._cleanup_pdf_generation()
            raise
    
    def _on_pdf_progress(self, progress: int, message: str):
        """PDF生成進捗更新"""
        if hasattr(self, 'state_tooltip'):
            self.state_tooltip.setContent(f"{message} ({progress}%)")
    
    def _on_pdf_generation_finished(self, success: bool, message: str):
        """PDF生成完了"""
        self._cleanup_pdf_generation()
        
        if success:
            InfoBar.success(
                title="PDF生成完了",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )
            
            # ファイルを開くか確認
            reply = MessageBox(
                "PDF生成完了",
                f"{message}\n\nファイルを開きますか？",
                self
            ).exec()
            
            if reply == MessageBox.StandardButton.Yes:
                os.startfile(Path(message.split(": ")[1]))  # Windows
        else:
            InfoBar.error(
                title="PDF生成失敗",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
                parent=self
            )
    
    def _cleanup_pdf_generation(self):
        """PDF生成関連のクリーンアップ"""
        if hasattr(self, 'state_tooltip'):
            self.state_tooltip.setState(True)
            delattr(self, 'state_tooltip')
        
        if hasattr(self, 'progress_ring'):
            delattr(self, 'progress_ring')
        
        self.generate_pdf_btn.setEnabled(True)
        
        if self.pdf_thread:
            self.pdf_thread = None
    
    # その他のイベントハンドラー
    def _on_images_reordered(self, image_paths: List[str]):
        """画像順序変更時の処理"""
        self.current_images = image_paths
        self.logger.info("画像順序を変更")
    
    def _on_image_selected(self, image_path: str):
        """画像選択時の処理"""
        try:
            # プレビュー更新
            thumbnail = self._generate_thumbnail(image_path)
            if thumbnail:
                # プレビューサイズに調整
                preview_pixmap = thumbnail.scaled(
                    400, 300,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.preview_label.setPixmap(preview_pixmap)
                self.preview_label.setText("")
            
            # 切り抜きウィジェットに画像を設定
            if self.crop_widget:
                self.crop_widget.set_image(image_path)
            
            self._update_ui_state()
            
        except Exception as e:
            self.logger.error(f"画像選択処理エラー: {image_path} - {e}")
    
    def _on_image_removed(self, image_path: str):
        """画像削除時の処理"""
        if image_path in self.current_images:
            self.current_images.remove(image_path)
        
        # プレビューをクリア
        self.preview_label.clear()
        self.preview_label.setText("画像を選択してください")
        
        self._update_ui_state()
    
    def _on_crop_completed(self, cropped_image):
        """切り抜き完了時の処理"""
        try:
            # 切り抜かれた画像を一時ファイルとして保存
            temp_dir = get_temp_dir()
            temp_path = temp_dir / f"cropped_image_{len(self.current_images)}.jpg"
            
            # OpenCV画像をファイルに保存
            import cv2
            cv2.imwrite(str(temp_path), cropped_image)
            
            # 画像リストに追加
            self.add_images([str(temp_path)])
            
            InfoBar.success(
                title="切り抜き完了",
                content="切り抜かれた画像をリストに追加しました",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
            
        except Exception as e:
            self.logger.error(f"切り抜き完了処理エラー: {e}")
    
    def _on_image_rotated(self, angle: float):
        """画像回転完了時の処理"""
        self.logger.info(f"画像を {angle}度 回転しました")
    
    def _on_processing_error(self, operation: str, error_message: str):
        """画像処理エラー時の処理"""
        InfoBar.error(
            title="画像処理エラー",
            content=f"{operation}: {error_message}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self
        )
    
    def _on_pdf_generation_error(self, error_message: str):
        """PDF生成エラー時の処理"""
        self._cleanup_pdf_generation()
        InfoBar.error(
            title="PDF生成エラー",
            content=error_message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self
        )
