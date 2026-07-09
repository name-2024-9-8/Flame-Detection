#!/usr/bin/env python3
"""
香橙派边缘端 — 火焰检测报警推送
================================
读取视频文件，检测火焰/烟雾，推送报警到服务端。
每条报警包含：检测图片(base64)、3-5秒视频片段、摄像头位置信息。

用法:
  python push_alarm.py --video test/VP47.mp4
  python push_alarm.py --video test/VP47.mp4 --server http://192.168.1.100:8080/index.php
  python push_alarm.py --video test/VP47.mp4 --save  # 同时保存本地标注视频

摄像头: 重庆理工大学-花溪校区摄像头 (camera_id=10, lng=106.528, lat=29.453)
"""
from __future__ import annotations
import sys, os, json, base64, time, argparse, logging, uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

import cv2
import numpy as np
import requests
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import confidence_to_level, encode_frame_base64

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("EdgeAlarm")

TZ = timezone(timedelta(hours=8))

# ── 默认摄像头: 重庆理工大学-花溪校区 ──
DEFAULT_CAMERA_ID = 10
DEFAULT_LNG = 106.528
DEFAULT_LAT = 29.453
DEFAULT_LOCATION = "重庆理工大学-花溪校区摄像头"
DEFAULT_SERVER = "http://127.0.0.1:8080/index.php"


class ClipRecorder:
    """录制报警前后 3-5 秒视频片段"""

    def __init__(self, fps: float = 15.0, pre_sec: float = 2.0, post_sec: float = 3.0,
                 output_dir: str = "output/clips"):
        self.fps = max(fps, 1.0)
        self.pre_frames = int(self.fps * pre_sec)
        self.post_frames = int(self.fps * post_sec)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.buffer: list[np.ndarray] = []
        self.max_buffer = self.pre_frames + self.post_frames + 30
        self._recording = False
        self._post_counter = 0

    def feed(self, frame: np.ndarray):
        self.buffer.append(frame.copy())
        if len(self.buffer) > self.max_buffer:
            self.buffer.pop(0)
        if self._recording:
            self._post_counter -= 1
            if self._post_counter <= 0:
                self._recording = False

    def trigger(self):
        self._recording = True
        self._post_counter = self.post_frames

    def save_clip(self) -> str:
        available = len(self.buffer)
        if available < 1:
            return ""
        start = max(0, available - self.pre_frames - self.post_frames)
        clip_frames = self.buffer[start:]
        if not clip_frames:
            return ""

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:17]
        out_path = str(self.output_dir / f"clip_{ts}.mp4")
        h, w = clip_frames[0].shape[:2]
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (w, h))
        for f in clip_frames:
            writer.write(f)
        writer.release()
        return out_path


def push_alarm(server_url: str, picture_b64: str, video_b64: str,
               confidence: float, event_type: str = "fire"):
    """推送一条报警到服务端"""
    payload = {
        "event_type": event_type,
        "camera_id": DEFAULT_CAMERA_ID,
        "device_id": 1,
        "area_id": 1,
        "timestamp": datetime.now(TZ).isoformat(),
        "longitude": str(DEFAULT_LNG),
        "latitude": str(DEFAULT_LAT),
        "location": DEFAULT_LOCATION,
        "confidence": round(confidence, 4),
        "urgency_degree": confidence_to_level(confidence),
        "picture_base64": picture_b64,
        "video_base64": video_b64,
        "description": f"边缘端检测到火焰 (置信度: {confidence:.2f})",
        "status": "1",
    }
    try:
        r = requests.post(f"{server_url}/api/detect/alarm", json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get("data", {}).get("id")
        else:
            logger.warning(f"推送失败: {r.status_code}")
    except Exception as e:
        logger.error(f"推送异常: {e}")
    return None


def process_video(video_path: str, model_path: str, conf_threshold: float,
                  server_url: str, save_video: bool = False, no_push: bool = False):
    """处理视频文件，检测火焰并推送报警"""
    model = YOLO(model_path)
    logger.info(f"模型已加载: {model_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"无法打开视频: {video_path}")
        return

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps_video = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info(f"视频: {Path(video_path).name} ({w}x{h}, {total}帧, {fps_video:.1f}fps)")

    name = Path(video_path).stem
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 视频录制器
    recorder = ClipRecorder(fps=fps_video, pre_sec=2.0, post_sec=3.0)

    # 标注视频输出
    writer = None
    if save_video:
        out_path = str(out_dir / f"{name}_detected.mp4")
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps_video, (w, h))

    alarm_count = 0
    alarm_ids = []
    cooldown = 0  # 防止同一事件重复推送
    COOLDOWN_FRAMES = int(fps_video * 2)  # 2秒冷却

    for idx in range(total):
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, conf=conf_threshold, verbose=False)
        boxes = results[0].boxes
        annotated = frame.copy()

        has_detection = boxes is not None and len(boxes) > 0
        best_conf = 0.0

        if has_detection:
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                best_conf = max(best_conf, conf)
                xyxy = box.xyxy[0].tolist()
                x1, y1, x2, y2 = map(int, xyxy)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(annotated, f"FIRE {conf:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

            # 触发报警 (带冷却)
            if cooldown <= 0 and not no_push:
                recorder.trigger()
                clip_path = recorder.save_clip()

                # 编码视频片段
                video_b64 = ""
                if clip_path and os.path.exists(clip_path):
                    with open(clip_path, "rb") as f:
                        video_b64 = base64.b64encode(f.read()).decode()

                picture_b64 = encode_frame_base64(annotated)
                alarm_id = push_alarm(server_url, picture_b64, video_b64, best_conf)
                if alarm_id:
                    alarm_ids.append(alarm_id)
                    alarm_count += 1
                    logger.info(f"[ALARM #{alarm_count}] conf={best_conf:.2f}, "
                                f"pic={'有' if picture_b64 else '无'}, "
                                f"video={'有' if video_b64 else '无'}")

                cooldown = COOLDOWN_FRAMES

        if cooldown > 0:
            cooldown -= 1

        recorder.feed(annotated)

        if writer:
            writer.write(annotated)

        # 进度
        pct = (idx + 1) / total * 100
        bar = "=" * int(pct / 5) + ">" + " " * max(0, 20 - int(pct / 5))
        sys.stdout.write(f"\r[{bar}] {idx+1}/{total} ({pct:.0f}%)  alarms: {alarm_count}")
        sys.stdout.flush()

    cap.release()
    if writer:
        writer.release()
        logger.info(f"标注视频已保存: {out_path}")

    print(f"\n\n{'='*50}")
    print(" 检测完毕")
    print(f"{'='*50}")
    print(f" 视频: {video_path}")
    print(f" 摄像头: {DEFAULT_LOCATION} (ID={DEFAULT_CAMERA_ID})")
    print(f" 坐标: ({DEFAULT_LNG}, {DEFAULT_LAT})")
    print(f" 报警推送: {alarm_count} 条")
    print(f" 服务端: {server_url}")
    if save_video:
        print(f" 标注视频: {out_path}")
    print(f" 视频片段: {recorder.output_dir}/")


def main():
    p = argparse.ArgumentParser(description="香橙派边缘端 — 火焰检测报警推送")
    p.add_argument("--video", required=True, help="视频文件路径")
    p.add_argument("--model", default="output/dfire_train/weights/best.pt", help="模型路径")
    p.add_argument("--conf", type=float, default=0.25, help="置信度阈值")
    p.add_argument("--server", type=str, default=DEFAULT_SERVER, help="服务端地址")
    p.add_argument("--save", action="store_true", help="保存完整标注视频到本地")
    p.add_argument("--no-push", action="store_true", help="只检测不推送 (离线测试)")
    args = p.parse_args()

    if not Path(args.video).exists():
        print(f"视频文件不存在: {args.video}")
        sys.exit(1)

    print("=" * 50)
    print(" 香橙派边缘端 — 火焰检测报警推送")
    print("=" * 50)
    print(f" 摄像头: {DEFAULT_LOCATION}")
    print(f" 坐标: ({DEFAULT_LNG}, {DEFAULT_LAT})")
    print(f" 服务端: {args.server}")
    print(f" 置信度: {args.conf}")
    print()

    process_video(args.video, args.model, args.conf, args.server, args.save, args.no_push)


if __name__ == "__main__":
    main()
