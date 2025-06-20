"""
画像処理クラス
OpenCVを使用した画像の切り抜き、歪み補正、回転などの処理
"""

import logging
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Union
import cv2
from PIL import Image, ImageOps
from PyQt6.QtCore import QObject, pyqtSignal


class ImageProcessor(QObject):
    """画像処理を行うクラス"""
    
    # シグナル定義
    processing_started = pyqtSignal(str)  # 処理開始
    processing_finished = pyqtSignal(str)  # 処理完了
    processing_error = pyqtSignal(str, str)  # エラー (operation, message)
    progress_updated = pyqtSignal(int)  # 進捗更新
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
    def load_image(self, image_path: Union[str, Path]) -> Optional[np.ndarray]:
        """
        画像を読み込み
        
        Args:
            image_path: 画像ファイルのパス
            
        Returns:
            読み込まれた画像（BGR形式）、失敗時はNone
        """
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                self.logger.error(f"画像ファイルが存在しません: {image_path}")
                return None
            
            # OpenCVで画像を読み込み（BGR形式）
            image = cv2.imread(str(image_path))
            
            if image is None:
                # OpenCVで読み込めない場合はPILで試行
                try:
                    pil_image = Image.open(image_path)
                    # RGBA → RGB変換
                    if pil_image.mode == 'RGBA':
                        pil_image = pil_image.convert('RGB')
                    # PIL → OpenCV変換
                    image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                except Exception as e:
                    self.logger.error(f"PIL画像読み込みエラー: {e}")
                    return None
            
            self.logger.info(f"画像読み込み完了: {image_path}")
            return image
            
        except Exception as e:
            self.logger.error(f"画像読み込みエラー: {image_path} - {e}")
            self.processing_error.emit("load_image", str(e))
            return None
    
    def save_image(self, image: np.ndarray, output_path: Union[str, Path]) -> bool:
        """
        画像を保存
        
        Args:
            image: 保存する画像
            output_path: 出力パス
            
        Returns:
            保存が成功した場合True
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # OpenCVで保存
            success = cv2.imwrite(str(output_path), image)
            
            if success:
                self.logger.info(f"画像保存完了: {output_path}")
                return True
            else:
                self.logger.error(f"画像保存失敗: {output_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"画像保存エラー: {output_path} - {e}")
            self.processing_error.emit("save_image", str(e))
            return False
    
    def crop_image_with_four_points(
        self, 
        image: np.ndarray, 
        points: List[Tuple[int, int]]
    ) -> Optional[np.ndarray]:
        """
        4つの点で指定された範囲を切り抜き（透視変換による歪み補正付き）
        
        Args:
            image: 元画像
            points: 4つの点の座標 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
                   時計回りまたは反時計回りの順序
                   
        Returns:
            切り抜かれた画像、失敗時はNone
        """
        try:
            if len(points) != 4:
                raise ValueError("4つの点が必要です")
            
            self.processing_started.emit("crop_with_perspective")
            
            # 点を numpy array に変換
            src_points = np.array(points, dtype=np.float32)
            
            # 点の順序を修正（左上、右上、右下、左下の順に並び替え）
            src_points = self._order_points(src_points)
            
            # 出力サイズを計算
            width, height = self._calculate_output_dimensions(src_points)
            
            # 変換先の点を定義（長方形）
            dst_points = np.array([
                [0, 0],
                [width - 1, 0],
                [width - 1, height - 1],
                [0, height - 1]
            ], dtype=np.float32)
            
            # 透視変換行列を計算
            perspective_matrix = cv2.getPerspectiveTransform(src_points, dst_points)
            
            # 透視変換を適用
            warped_image = cv2.warpPerspective(
                image, 
                perspective_matrix, 
                (width, height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255)
            )
            
            self.processing_finished.emit("crop_with_perspective")
            self.logger.info("4点切り抜き完了")
            
            return warped_image
            
        except Exception as e:
            self.logger.error(f"4点切り抜きエラー: {e}")
            self.processing_error.emit("crop_with_perspective", str(e))
            return None
    
    def _order_points(self, points: np.ndarray) -> np.ndarray:
        """
        4つの点を左上、右上、右下、左下の順序に並び替え
        
        Args:
            points: 4つの点の配列
            
        Returns:
            並び替えられた点の配列
        """
        # 各点の座標の合計と差を計算
        sums = points.sum(axis=1)
        diffs = np.diff(points, axis=1)
        
        # 左上: 合計が最小
        # 右下: 合計が最大
        # 右上: 差（x-y）が最小
        # 左下: 差（x-y）が最大
        ordered_points = np.zeros((4, 2), dtype=np.float32)
        ordered_points[0] = points[np.argmin(sums)]  # 左上
        ordered_points[2] = points[np.argmax(sums)]  # 右下
        ordered_points[1] = points[np.argmin(diffs)]  # 右上
        ordered_points[3] = points[np.argmax(diffs)]  # 左下
        
        return ordered_points
    
    def _calculate_output_dimensions(self, points: np.ndarray) -> Tuple[int, int]:
        """
        切り抜き後の出力サイズを計算
        
        Args:
            points: 並び替えられた4つの点
            
        Returns:
            (width, height)
        """
        # 各辺の長さを計算
        width_a = np.linalg.norm(points[0] - points[1])  # 上辺
        width_b = np.linalg.norm(points[2] - points[3])  # 下辺
        max_width = max(int(width_a), int(width_b))
        
        height_a = np.linalg.norm(points[1] - points[2])  # 右辺
        height_b = np.linalg.norm(points[3] - points[0])  # 左辺
        max_height = max(int(height_a), int(height_b))
        
        return max_width, max_height
    
    def rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """
        画像を回転
        
        Args:
            image: 元画像
            angle: 回転角度（度）、時計回り正
            
        Returns:
            回転後の画像
        """
        try:
            self.processing_started.emit("rotate")
            
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            
            # 回転行列を計算
            rotation_matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
            
            # 新しい画像サイズを計算（90度単位の場合は最適化）
            if abs(angle) % 90 == 0:
                if abs(angle) % 180 == 90:
                    new_width, new_height = height, width
                else:
                    new_width, new_height = width, height
                
                # 中心を調整
                rotation_matrix[0, 2] += (new_width - width) / 2
                rotation_matrix[1, 2] += (new_height - height) / 2
            else:
                # 任意角度の場合は元サイズを維持
                new_width, new_height = width, height
            
            # 回転を適用
            rotated_image = cv2.warpAffine(
                image, 
                rotation_matrix, 
                (new_width, new_height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255)
            )
            
            self.processing_finished.emit("rotate")
            self.logger.info(f"画像回転完了: {angle}度")
            
            return rotated_image
            
        except Exception as e:
            self.logger.error(f"画像回転エラー: {e}")
            self.processing_error.emit("rotate", str(e))
            return image  # エラー時は元画像を返す
    
    def enhance_image(self, image: np.ndarray) -> np.ndarray:
        """
        画像の品質向上（コントラスト調整、ノイズ除去など）
        
        Args:
            image: 元画像
            
        Returns:
            品質向上後の画像
        """
        try:
            self.processing_started.emit("enhance")
            
            enhanced = image.copy()
            
            # ガウシアンノイズ除去
            enhanced = cv2.GaussianBlur(enhanced, (1, 1), 0)
            
            # CLAHE（適応的ヒストグラム均等化）でコントラスト改善
            if len(enhanced.shape) == 3:
                # カラー画像の場合はLAB色空間で処理
                lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                lab[:, :, 0] = clahe.apply(lab[:, :, 0])
                enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            else:
                # グレースケール画像の場合
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(enhanced)
            
            self.processing_finished.emit("enhance")
            self.logger.info("画像品質向上完了")
            
            return enhanced
            
        except Exception as e:
            self.logger.error(f"画像品質向上エラー: {e}")
            self.processing_error.emit("enhance", str(e))
            return image
    
    def resize_image(
        self, 
        image: np.ndarray, 
        target_size: Tuple[int, int], 
        keep_aspect_ratio: bool = True
    ) -> np.ndarray:
        """
        画像のリサイズ
        
        Args:
            image: 元画像
            target_size: 目標サイズ (width, height)
            keep_aspect_ratio: アスペクト比を保持するか
            
        Returns:
            リサイズ後の画像
        """
        try:
            target_width, target_height = target_size
            height, width = image.shape[:2]
            
            if keep_aspect_ratio:
                # アスペクト比を保持してリサイズ
                aspect_ratio = width / height
                
                if target_width / target_height > aspect_ratio:
                    # 高さを基準にリサイズ
                    new_height = target_height
                    new_width = int(target_height * aspect_ratio)
                else:
                    # 幅を基準にリサイズ
                    new_width = target_width
                    new_height = int(target_width / aspect_ratio)
                
                resized = cv2.resize(
                    image, 
                    (new_width, new_height), 
                    interpolation=cv2.INTER_AREA
                )
                
                # 余白を追加して目標サイズに調整
                if new_width < target_width or new_height < target_height:
                    result = np.full(
                        (target_height, target_width, image.shape[2] if len(image.shape) == 3 else 1),
                        255, dtype=image.dtype
                    )
                    
                    # 中央に配置
                    y_offset = (target_height - new_height) // 2
                    x_offset = (target_width - new_width) // 2
                    
                    if len(image.shape) == 3:
                        result[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = resized
                    else:
                        result[y_offset:y_offset+new_height, x_offset:x_offset+new_width, 0] = resized
                    
                    return result
                else:
                    return resized
            else:
                # アスペクト比を無視してリサイズ
                return cv2.resize(
                    image, 
                    target_size, 
                    interpolation=cv2.INTER_AREA
                )
                
        except Exception as e:
            self.logger.error(f"画像リサイズエラー: {e}")
            return image
    
    def get_image_info(self, image_path: Union[str, Path]) -> Optional[dict]:
        """
        画像の情報を取得
        
        Args:
            image_path: 画像ファイルのパス
            
        Returns:
            画像情報の辞書、失敗時はNone
        """
        try:
            image_path = Path(image_path)
            
            # ファイル情報
            file_stat = image_path.stat()
            
            # 画像を読み込んで情報取得
            image = self.load_image(image_path)
            if image is None:
                return None
            
            height, width = image.shape[:2]
            channels = image.shape[2] if len(image.shape) == 3 else 1
            
            return {
                'filename': image_path.name,
                'filepath': str(image_path),
                'width': width,
                'height': height,
                'channels': channels,
                'file_size': file_stat.st_size,
                'modified_time': file_stat.st_mtime
            }
            
        except Exception as e:
            self.logger.error(f"画像情報取得エラー: {image_path} - {e}")
            return None
