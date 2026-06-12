"""
边缘端视频流接入模块
- RTSP协议获取摄像头视频流
- ONVIF协议摄像头发现与控制
- 支持多路视频并发接入
"""
from __future__ import annotations
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Callable, Generator
from dataclasses import dataclass, field

import numpy as np
import cv2

logger = logging.getLogger(__name__)


@dataclass
class CameraConfig:
    """摄像头配置"""
    camera_id: int
    name: str = ""
    rtsp_url: str = ""
    ip: str = ""
    port: int = 554
    username: str = "admin"
    password: str = "admin"
    onvif_port: int = 80
    # 视频参数
    width: int = 1920
    height: int = 1080
    fps: int = 25
    # 位置信息
    longitude: float = 0.0
    latitude: float = 0.0
    area_id: int = 0
    device_id: int = 0


class RTSPStreamReader:
    """RTSP视频流读取器"""

    def __init__(self, camera: CameraConfig, reconnect_interval: float = 5.0):
        self.camera = camera
        self.reconnect_interval = reconnect_interval
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def rtsp_url(self) -> str:
        """构建RTSP URL"""
        if self.camera.rtsp_url:
            return self.camera.rtsp_url
        u, p = self.camera.username, self.camera.password
        ip, port = self.camera.ip, self.camera.port
        return f"rtsp://{u}:{p}@{ip}:{port}/Streaming/Channels/101"

    def connect(self) -> bool:
        """建立RTSP连接"""
        with self._lock:
            if self._cap is not None:
                self._cap.release()

            self._cap = cv2.VideoCapture(self.rtsp_url)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))

            if not self._cap.isOpened():
                logger.error(f"无法连接摄像头 {self.camera.camera_id}: {self.rtsp_url}")
                return False

            logger.info(f"已连接摄像头 {self.camera.camera_id} ({self.camera.name})")
            self._running = True
            return True

    def read_frame(self) -> Optional[np.ndarray]:
        """读取一帧图像"""
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                if not self.connect():
                    return None

            ret, frame = self._cap.read()
            if not ret:
                logger.warning(f"摄像头 {self.camera.camera_id} 读取帧失败，尝试重连...")
                time.sleep(self.reconnect_interval)
                self.connect()
                return None

            return frame

    def stream_generator(self, max_fps: Optional[int] = None) -> Generator[np.ndarray, None, None]:
        """帧生成器，支持FPS限制"""
        frame_interval = 1.0 / max_fps if max_fps else 0
        last_frame_time = 0

        while self._running:
            current_time = time.time()
            if current_time - last_frame_time < frame_interval:
                time.sleep(0.001)
                continue

            frame = self.read_frame()
            if frame is not None:
                last_frame_time = current_time
                yield frame

    def close(self):
        """关闭连接"""
        self._running = False
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
        logger.info(f"已断开摄像头 {self.camera.camera_id}")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()


class MultiCameraManager:
    """多路摄像头管理器 - 支持30路并发"""

    def __init__(self):
        self._streams: dict[int, RTSPStreamReader] = {}
        self._frames: dict[int, np.ndarray] = {}
        self._lock = threading.Lock()
        self._running = False
        self._threads: list[threading.Thread] = []

    def add_camera(self, camera: CameraConfig) -> bool:
        """添加摄像头"""
        stream = RTSPStreamReader(camera)
        if stream.connect():
            self._streams[camera.camera_id] = stream
            return True
        return False

    def start_capture(self, fps: int = 15):
        """启动多路采集线程"""
        self._running = True

        def _capture_loop(cam_id: int, stream: RTSPStreamReader):
            interval = 1.0 / fps
            while self._running:
                frame = stream.read_frame()
                if frame is not None:
                    with self._lock:
                        self._frames[cam_id] = frame
                time.sleep(interval)

        for cam_id, stream in self._streams.items():
            t = threading.Thread(target=_capture_loop, args=(cam_id, stream), daemon=True)
            t.start()
            self._threads.append(t)

        logger.info(f"已启动 {len(self._threads)} 路视频采集 (fps={fps})")

    def get_latest_frame(self, camera_id: int) -> Optional[np.ndarray]:
        """获取最新帧"""
        with self._lock:
            return self._frames.get(camera_id)

    def get_all_frames(self) -> dict[int, np.ndarray]:
        """获取所有摄像头的最新帧"""
        with self._lock:
            return dict(self._frames)

    def stop(self):
        """停止所有采集"""
        self._running = False
        for t in self._threads:
            t.join(timeout=3.0)
        for stream in self._streams.values():
            stream.close()
        self._threads.clear()
        self._streams.clear()
        self._frames.clear()


# ---------- 模拟摄像头 (用于开发测试, 无真实摄像头时使用) ----------

class SimulatedCamera:
    """模拟摄像头 - 从本地视频文件或图片目录读取"""

    def __init__(self, source: str = "video", video_path: str = "", image_dir: str = ""):
        self.source = source
        self.video_path = video_path
        self.image_dir = image_dir
        self._image_files: list[Path] = []
        self._img_idx = 0

        if source == "image" and image_dir:
            img_dir = Path(image_dir)
            self._image_files = sorted([
                f for f in img_dir.iterdir()
                if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp'}
            ])

    def get_frame(self) -> Optional[np.ndarray]:
        """获取模拟帧"""
        if self.source == "image" and self._image_files:
            frame = cv2.imread(str(self._image_files[self._img_idx]))
            self._img_idx = (self._img_idx + 1) % len(self._image_files)
            return frame

        elif self.source == "video" and self.video_path:
            # 每次调用重新读取(简单实现)
            cap = cv2.VideoCapture(self.video_path)
            ret, frame = cap.read()
            cap.release()
            return frame if ret else None

        else:
            # 生成随机测试图像
            return np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
