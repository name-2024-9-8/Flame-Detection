"""
边缘端结果输出模块
- HTTP POST 发送检测结果到后端服务器
- JSON格式封装 (匹配 T_DetectResult 表结构)
- 图片/视频片段保存与上传
- 故障上报 (T_DeviceError)
- 心跳保活 (T_Device 心跳更新)
"""
from __future__ import annotations
import time
import json
import base64
import logging
import threading
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from io import BytesIO

import numpy as np
import cv2
import requests

logger = logging.getLogger(__name__)


@dataclass
class AlarmEvent:
    """报警事件 - 对应 T_DetectResult 表"""
    # 必填字段
    camera_id: int
    device_id: int
    area_id: int
    timestamp: str  # ISO 格式
    # 位置
    longitude: float
    latitude: float
    location: str  # 逆地址解析后的文字位置
    # 检测信息
    event_type: str = "fire"  # 事件类型: fire/smoke
    confidence: float = 0.0
    urgency_degree: str = "中"  # 紧急程度: 高/中/低
    description: str = ""
    # 媒体数据
    picture_base64: str = ""  # 检测帧 base64
    video_url: str = ""  # 视频片段路径
    # 状态
    status: str = "1"  # 1=未处理, 2=处理中, 3=已处理
    # 可选
    device_mac: str = ""  # 设备MAC地址（用于身份验证）
    operate_user_id: Optional[int] = None
    operate_result: str = ""
    audit_user_id: Optional[int] = None
    remark: str = ""

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class DeviceHeartbeat:
    """设备心跳"""
    device_id: int
    mac: str
    timestamp: str
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    npu_temp: float = 0.0
    status: str = "online"


@dataclass
class DeviceError:
    """设备故障上报 - 对应 T_DeviceError 表"""
    device_id: int
    mac: str
    error_code: str
    error_msg: str
    timestamp: str


class ResultPublisher:
    """
    结果发布器
    - 将检测结果发送到后端 REST API
    - 视频文件 multipart 上传
    - 支持重试和本地缓存
    """

    def __init__(self, server_url: str = "http://127.0.0.1:8083",
                 api_key: str = "", cache_dir: str = "output/edge_cache"):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if not api_key:
            raise ValueError("API密钥未配置! 请在 edge_config.json 的 server.api_key 中设置，"
                             "或通过 EDGE_API_KEY 环境变量传入")
        self._session = requests.Session()
        self._session.headers.update({'X-API-Key': api_key})
        self._lock = threading.Lock()
        self._pending_events: list[AlarmEvent] = []
        self._upload_timeout = 30

    def upload_video(self, video_path: str, camera_id: int,
                     timestamp: str) -> str:
        """
        上传视频文件到服务器，返回服务器端 URL
        使用 multipart/form-data 上传 MP4
        """
        if not video_path or not Path(video_path).exists():
            return ""

        url = f"{self.server_url}/api/detect/upload"
        try:
            with open(video_path, 'rb') as f:
                files = {
                    'file': (Path(video_path).name, f, 'video/mp4')
                }
                data = {
                    'camera_id': str(camera_id),
                    'timestamp': timestamp,
                }
                resp = requests.post(
                    url,
                    files=files,
                    data=data,
                    timeout=self._upload_timeout,
                )
                if resp.status_code in (200, 201):
                    result = resp.json()
                    video_url = result.get('url', '') or result.get('data', {}).get('url', '')
                    logger.info(f"视频已上传: {Path(video_path).name} -> {video_url}")
                    return video_url
                else:
                    logger.warning(f"视频上传失败 [{resp.status_code}]: {resp.text}")
        except Exception as e:
            logger.warning(f"视频上传异常: {e}")

        return video_path  # 上传失败时返回本地路径

    def send_alarm(self, event: AlarmEvent, retry: int = 3) -> bool:
        """发送报警事件到后端 (先上传视频，再发送JSON)"""
        # 如果有本地视频，先上传获取 URL
        if event.video_url and not event.video_url.startswith('http'):
            uploaded_url = self.upload_video(
                event.video_url,
                event.camera_id,
                event.timestamp,
            )
            if uploaded_url:
                event.video_url = uploaded_url

        url = f"{self.server_url}/api/detect/alarm"

        for attempt in range(retry):
            try:
                resp = self._session.post(
                    url,
                    json=event.to_json(),
                    timeout=10.0,
                    headers={'Content-Type': 'application/json'},
                )
                if resp.status_code in (200, 201):
                    logger.info(f"报警已发送: camera={event.camera_id}, "
                                f"conf={event.confidence:.2f}")
                    return True
                else:
                    logger.warning(f"发送报警失败 [{resp.status_code}]: {resp.text}")
            except requests.RequestException as e:
                logger.warning(f"发送报警异常 (attempt {attempt+1}/{retry}): {e}")
                time.sleep(2 ** attempt)

        # 重试失败，缓存到本地
        self._cache_event(event)
        return False

    def send_heartbeat(self, heartbeat: DeviceHeartbeat) -> bool:
        """发送设备心跳"""
        url = f"{self.server_url}/api/device/heartbeat"
        try:
            resp = self._session.post(url, json=asdict(heartbeat), timeout=3.0)
            return resp.status_code in (200, 201)
        except requests.RequestException:
            return False

    def report_device_error(self, error: DeviceError) -> bool:
        """上报设备故障"""
        url = f"{self.server_url}/api/device/error"
        try:
            resp = self._session.post(url, json=asdict(error), timeout=5.0)
            return resp.status_code in (200, 201)
        except requests.RequestException:
            return False

    def _cache_event(self, event: AlarmEvent):
        """本地缓存未成功发送的事件"""
        with self._lock:
            self._pending_events.append(event)
        cache_file = self.cache_dir / f"event_{event.timestamp.replace(':', '-')}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(event.to_json(), f, ensure_ascii=False, indent=2)

    def flush_cache(self) -> int:
        """重试发送缓存的事件"""
        sent = 0
        for f in sorted(self.cache_dir.glob("event_*.json")):
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            event = AlarmEvent(**data)
            if self.send_alarm(event):
                f.unlink()
                sent += 1
        return sent


def encode_frame_base64(frame: np.ndarray, quality: int = 80) -> str:
    """将帧编码为base64 JPEG字符串"""
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buffer).decode('utf-8')


def save_video_clip(frames: list[np.ndarray], output_path: str,
                     fps: int = 15, duration: float = 5.0) -> str:
    """
    保存报警视频片段 (3-5秒)
    返回保存路径
    """
    if not frames:
        return ""

    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    num_frames = int(fps * duration)
    for i, frame in enumerate(frames[:num_frames]):
        out.write(frame)

    # 如果帧不够，重复最后一帧
    if len(frames) < num_frames:
        last = frames[-1]
        for _ in range(num_frames - len(frames)):
            out.write(last)

    out.release()
    return output_path


def extract_clip_frames(frame_buffer: list[np.ndarray],
                         trigger_idx: int = -1,
                         pre_frames: int = 30,
                         post_frames: int = 45) -> list[np.ndarray]:
    """
    从帧缓冲区提取报警前后帧
    pre_frames: 报警前帧数 (2秒 @15fps)
    post_frames: 报警后帧数 (3秒 @15fps)
    """
    if trigger_idx < 0 or trigger_idx >= len(frame_buffer):
        trigger_idx = len(frame_buffer) - 1

    start = max(0, trigger_idx - pre_frames)
    end = min(len(frame_buffer), trigger_idx + post_frames)
    return frame_buffer[start:end]
