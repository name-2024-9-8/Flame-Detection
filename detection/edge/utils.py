"""
边缘端共享工具函数
- 置信度→报警级别映射
- 帧编码 (base64 JPEG)
- 视频片段保存
"""
import base64
import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("EdgeUtils")


def confidence_to_level(conf: float) -> str:
    """置信度 → 报警级别"""
    if conf >= 0.8:
        return "紧急"
    elif conf >= 0.5:
        return "重要"
    elif conf >= 0.3:
        return "一般"
    return "提示"


def encode_frame_base64(frame: np.ndarray, quality: int = 80) -> str:
    """编码帧为 base64 JPEG 字符串"""
    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf).decode('utf-8')


def save_video_clip(frames: list[np.ndarray], output_path: str,
                    fps: int = 15, duration: float = 5.0) -> str:
    """
    保存报警视频片段 (3-5秒)
    返回保存路径，帧不够时重复最后一帧补齐
    """
    if not frames:
        return ""

    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    num_frames = int(fps * duration)
    for frame in frames[:num_frames]:
        out.write(frame)

    if len(frames) < num_frames:
        last = frames[-1]
        for _ in range(num_frames - len(frames)):
            out.write(last)

    out.release()
    return output_path
