"""
边缘端视频预处理模块
- 图像去雾 (Dark Channel Prior)
- 图像增强 (CLAHE直方图均衡)
- 帧缩放与归一化
- 预处理管线
"""
from __future__ import annotations
import numpy as np
import cv2
from dataclasses import dataclass
from typing import Optional


@dataclass
class PreprocessConfig:
    """预处理配置"""
    target_size: tuple = (416, 416)
    enable_dehaze: bool = True
    enable_clahe: bool = True
    enable_denoise: bool = False
    # 去雾参数
    dehaze_omega: float = 0.95
    dehaze_t0: float = 0.1
    dehaze_window: int = 15
    # CLAHE参数
    clahe_clip_limit: float = 2.0
    clahe_grid_size: tuple = (8, 8)
    # 归一化参数
    mean: tuple = (0.485, 0.456, 0.406)
    std: tuple = (0.229, 0.224, 0.225)


class ImagePreprocessor:
    """图像预处理器 - 去雾、增强、缩放、归一化"""

    def __init__(self, config: PreprocessConfig = PreprocessConfig()):
        self.cfg = config
        self.clahe = (cv2.createCLAHE(
            clipLimit=config.clahe_clip_limit,
            tileGridSize=config.clahe_grid_size
        ) if config.enable_clahe else None)

    # ========== 暗通道先验去雾 ==========

    @staticmethod
    def _dark_channel(image: np.ndarray, window_size: int = 15) -> np.ndarray:
        """计算暗通道"""
        min_channel = np.min(image, axis=2)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (window_size, window_size))
        return cv2.erode(min_channel, kernel)

    @staticmethod
    def _estimate_atmospheric_light(image: np.ndarray, dark_channel: np.ndarray,
                                     top_percent: float = 0.001) -> np.ndarray:
        """估计大气光值"""
        h, w = dark_channel.shape
        num_pixels = int(h * w * top_percent)
        flat_dc = dark_channel.ravel()
        indices = np.argpartition(flat_dc, -num_pixels)[-num_pixels:]
        brightest = image.reshape(-1, 3)[indices]
        return np.max(brightest, axis=0)

    def dehaze(self, image: np.ndarray) -> np.ndarray:
        """
        暗通道先验去雾 (He et al., CVPR 2009)
        输入: BGR uint8 [0, 255]
        输出: BGR uint8 [0, 255]
        """
        img_float = image.astype(np.float32) / 255.0
        dark = self._dark_channel(img_float, self.cfg.dehaze_window)
        A = self._estimate_atmospheric_light(img_float, dark)

        # 归一化透射率估计
        dark_norm = self._dark_channel(img_float / A.max(), self.cfg.dehaze_window)
        transmission = 1 - self.cfg.dehaze_omega * dark_norm
        transmission = np.maximum(transmission, self.cfg.dehaze_t0)

        # 恢复无雾图像
        transmission_3d = np.expand_dims(transmission, axis=2)
        result = (img_float - A.reshape(1, 1, 3)) / transmission_3d + A.reshape(1, 1, 3)
        result = np.clip(result, 0, 1)
        return (result * 255).astype(np.uint8)

    # ========== CLAHE增强 ==========

    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """CLAHE对比度增强 (在LAB色彩空间L通道)"""
        if self.clahe is None:
            return image
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # ========== 缩放与归一化 ==========

    def resize_letterbox(self, image: np.ndarray) -> np.ndarray:
        """等比例缩放 + 填充到正方形"""
        h, w = image.shape[:2]
        target_w, target_h = self.cfg.target_size

        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)

        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Letterbox填充 (灰色114)
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        dw, dh = (target_w - new_w) // 2, (target_h - new_h) // 2
        canvas[dh:dh + new_h, dw:dw + new_w] = resized
        return canvas

    def normalize(self, image: np.ndarray) -> np.ndarray:
        """归一化: (H, W, C) uint8 -> (C, H, W) float32 [0, 1]"""
        img = image.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        return img.astype(np.float32)

    # ========== 完整预处理管线 ==========

    def process(self, frame: np.ndarray) -> np.ndarray:
        """
        完整预处理管线
        输入: BGR uint8 原始帧
        输出: (1, 3, H, W) float32 归一化张量 (可直接输入模型)
        """
        img = frame.copy()

        if self.cfg.enable_dehaze:
            img = self.dehaze(img)

        if self.cfg.enable_clahe:
            img = self.enhance_contrast(img)

        img = self.resize_letterbox(img)
        img = self.normalize(img)
        return np.expand_dims(img, axis=0)

    def process_batch(self, frames: list[np.ndarray]) -> np.ndarray:
        """批量预处理"""
        batch = [self.normalize(self.resize_letterbox(
            self.enhance_contrast(
                self.dehaze(f) if self.cfg.enable_dehaze else f
            )
        )) for f in frames]
        return np.stack(batch, axis=0)
