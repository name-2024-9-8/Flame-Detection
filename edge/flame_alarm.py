#!/usr/bin/env python3
"""
火焰识别边缘端 — 完整报警推送
==============================
读取视频文件，实时检测火焰/烟尘，生成报警事件（含火焰图片、3-5秒视频片段、位置信息），
通过 HTTP POST 实时推送到服务端。

用法:
  # 检测单个视频
  python edge/flame_alarm.py --video test/VP47.mp4

  # 检测目录下所有视频
  python edge/flame_alarm.py --video-dir test/

  # 指定模型、服务端地址
  python edge/flame_alarm.py --video test/VP47.mp4 \\
      --model output/yolo_train_7videos/weights/best.onnx \\
      --server http://192.168.1.100:8083

  # 无服务端时，报警事件保存到本地 JSON
  python edge/flame_alarm.py --video test/VP47.mp4 --offline

报警事件数据格式 (JSON):
{
  "camera_id": 0, "device_id": 1, "area_id": 1,
  "timestamp": "2026-07-06T10:00:00+08:00",
  "longitude": 116.397, "latitude": 39.909, "location": "北京市东城区",
  "confidence": 0.95, "urgency_degree": "高",
  "picture_base64": "/9j/4AAQ...",
  "video_path": "output/alarm_clips/alarm_20260706_100000.mp4",
  "description": "检测到火焰/烟尘 (置信度: 0.95)",
  "status": "1"
}
"""
from __future__ import annotations
import sys
import os
import time
import json
import base64
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from edge.inference_engine import YOLOInferenceEngine, DetectionBox
from edge.preprocessing import ImagePreprocessor, PreprocessConfig
from edge.temporal_filter import TemporalFilter, FilterConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("FlameAlarm")

# 中国时区
TZ = timezone(timedelta(hours=8))

# 类别颜色
CLASS_COLORS = {0: (0, 0, 255), 1: (255, 165, 0)}  # fire→红色, smoke→橙色


# ============================================================
# 报警事件数据结构
# ============================================================

class AlarmEvent:
    """火焰报警事件"""
    def __init__(self, camera_id: int = 0, device_id: int = 1,
                 area_id: int = 1, timestamp: str = "",
                 longitude: float = 0.0, latitude: float = 0.0,
                 location: str = "", confidence: float = 0.0,
                 urgency_degree: str = "中", description: str = "",
                 picture_base64: str = "", video_path: str = "",
                 status: str = "1", remark: str = ""):
        self.camera_id = camera_id
        self.device_id = device_id
        self.area_id = area_id
        self.timestamp = timestamp or datetime.now(TZ).isoformat()
        self.longitude = longitude
        self.latitude = latitude
        self.location = location
        self.confidence = confidence
        self.urgency_degree = urgency_degree
        self.description = description
        self.picture_base64 = picture_base64
        self.video_path = video_path
        self.status = status
        self.remark = remark

    def to_dict(self) -> dict:
        return self.__dict__


# ============================================================
# 视频片段录制器
# ============================================================

class ClipRecorder:
    """录制报警前后的视频片段 (3-5秒)"""

    def __init__(self, fps: int = 15, pre_sec: float = 2.0,
                 post_sec: float = 3.0, output_dir: str = "output/alarm_clips"):
        self.fps = fps
        self.pre_frames = int(fps * pre_sec)
        self.post_frames = int(fps * post_sec)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.buffer: list[np.ndarray] = []
        self.max_buffer = self.pre_frames + self.post_frames + 30

    def feed(self, frame: np.ndarray):
        """喂入新帧"""
        self.buffer.append(frame.copy())
        if len(self.buffer) > self.max_buffer:
            self.buffer.pop(0)

    def save_clip(self, trigger_frame: np.ndarray = None) -> str:
        """保存报警视频片段"""
        available = len(self.buffer)
        # 最少需要1帧
        if available < 1:
            return ""

        # 缓冲不足时用全部帧
        start = max(0, available - self.pre_frames - self.post_frames)
        clip_frames = self.buffer[start:]
        total_sec = len(clip_frames) / max(self.fps, 1)

        if not clip_frames:
            return ""

        h, w = clip_frames[0].shape[:2]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = str(self.output_dir / f"alarm_{ts}.mp4")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_path, fourcc, self.fps, (w, h))
        for f in clip_frames:
            writer.write(f)
        writer.release()

        logger.info(f"视频片段已保存: {out_path} ({len(clip_frames)}帧, {total_sec:.1f}秒)")
        return out_path


# ============================================================
# 报警推送器
# ============================================================

class AlarmPusher:
    """HTTP 推送报警事件到服务端"""

    def __init__(self, server_url: str = "", offline: bool = False):
        self.server_url = server_url.rstrip("/") if server_url else ""
        self.offline = offline
        self.output_dir = Path("output/alarm_events")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._session = None
        if not offline and server_url:
            try:
                import requests
                self._session = requests.Session()
                self._session.headers.update({"Content-Type": "application/json"})
            except ImportError:
                logger.warning("requests 未安装, 自动切换为离线模式")
                self.offline = True

    def push(self, event: AlarmEvent) -> bool:
        """推送报警事件"""
        data = event.to_dict()

        # 离线模式/无服务端: 保存到本地 JSON
        if self.offline or not self.server_url:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            fname = self.output_dir / f"alarm_{ts}.json"
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"报警已保存到本地: {fname}")
            return True

        # 在线模式: HTTP POST
        url = f"{self.server_url}/api/detect/alarm"
        for attempt in range(3):
            try:
                resp = self._session.post(url, json=data, timeout=10)
                if resp.status_code == 200:
                    logger.info(f"报警已推送: conf={event.confidence:.2f}")
                    return True
                logger.warning(f"推送失败 [{resp.status_code}]: {resp.text[:100]}")
            except Exception as e:
                logger.warning(f"推送异常 (attempt {attempt+1}/3): {e}")
                time.sleep(2 ** attempt)

        # 重试失败，保存本地
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        fname = self.output_dir / f"alarm_failed_{ts}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.warning(f"推送全部失败，已缓存到本地: {fname}")
        return False


# ============================================================
# 视频标注器
# ============================================================

def annotate_frame(frame: np.ndarray, detections: list[DetectionBox],
                   elapsed_ms: float = 0, fps: float = 0) -> np.ndarray:
    """在帧上绘制检测框和状态信息"""
    out = frame.copy()

    for det in detections:
        color = CLASS_COLORS.get(det.class_id, (0, 0, 255))
        cv2.rectangle(out,
                      (int(det.x1), int(det.y1)),
                      (int(det.x2), int(det.y2)), color, 2)
        label = f"{det.class_name} {det.confidence:.2f}"
        cv2.putText(out, label, (int(det.x1), max(int(det.y1) - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # 状态栏
    h = out.shape[0]
    cv2.rectangle(out, (0, 0), (280, 72), (0, 0, 0), -1)
    cv2.putText(out, f"FPS: {fps:.1f}", (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.putText(out, f"infer: {elapsed_ms:.0f}ms", (8, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.putText(out, f"det: {len(detections)}", (8, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (0, 0, 255) if detections else (0, 255, 0), 1)

    if detections:
        max_c = max(d.confidence for d in detections)
        cv2.rectangle(out, (0, 0), (out.shape[1], 6), (0, 0, 255), -1)
        cv2.putText(out, f"FIRE ALARM! x{len(detections)} max_conf={max_c:.2f}",
                    (out.shape[1] // 2 - 150, h - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    return out


def encode_frame_jpeg(frame: np.ndarray, quality: int = 80) -> str:
    """编码帧为 base64 JPEG"""
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf).decode("utf-8")


# ============================================================
# 火焰识别检测器
# ============================================================

class FlameAlarmDetector:
    """
    火焰识别 + 报警推送 一体化检测器
    """

    def __init__(self, model_path: str, conf: float = 0.25,
                 iou: float = 0.5, img_size: int = 416,
                 server_url: str = "", offline: bool = True,
                 device_id: int = 1, area_id: int = 1,
                 longitude: float = 0.0, latitude: float = 0.0,
                 location: str = "", clip_sec: float = 5.0,
                 filter_window: int = 5, filter_votes: int = 3,
                 cooldown_frames: int = 30):
        self.conf = conf
        self.device_id = device_id
        self.area_id = area_id
        self.longitude = longitude
        self.latitude = latitude
        self.location = location

        # 推理引擎
        logger.info(f"加载模型: {model_path}")
        self.engine = YOLOInferenceEngine(
            model_path=model_path,
            conf_threshold=conf,
            iou_threshold=iou,
            img_size=img_size,
        )
        logger.info(f"推理后端: {self.engine._backend.upper()}")

        # 预处理
        self.preprocessor = ImagePreprocessor(PreprocessConfig(
            target_size=(img_size, img_size),
            enable_dehaze=False, enable_clahe=False,
        ))

        # 时域滤波器 (消除偶发误报)
        self.temporal_filter = TemporalFilter(FilterConfig(
            window_size=filter_window,
            vote_threshold=filter_votes,
            cooldown_frames=cooldown_frames,
        ))

        # 视频片段录制
        self.clip_recorder = ClipRecorder(
            fps=15, pre_sec=2.0, post_sec=clip_sec - 2.0,
        )

        # 报警推送
        self.pusher = AlarmPusher(server_url=server_url, offline=offline)

        # 统计
        self.frame_count = 0
        self.fire_frames = 0
        self.alarm_count = 0

    def process_frame(self, frame: np.ndarray,
                      camera_id: int = 0) -> tuple[np.ndarray, list, Optional[AlarmEvent]]:
        """处理单帧，返回 (annotated_frame, detections, alarm_event_or_none)"""
        t0 = time.perf_counter()

        # 预处理 + 推理
        input_tensor = self.preprocessor.process(frame)
        outputs = self.engine.infer(input_tensor)
        detections = self.engine.postprocess_onnx(outputs, frame.shape[:2])

        elapsed = (time.perf_counter() - t0) * 1000

        # 标注
        annotated = annotate_frame(frame, detections, elapsed,
                                   1000 / max(elapsed, 1))

        # 喂入录制缓冲区
        self.clip_recorder.feed(annotated)

        alarm = None
        has_fire = len(detections) > 0
        best_conf = max((d.confidence for d in detections), default=0)

        if has_fire:
            self.fire_frames += 1

        # 时域滤波
        fire_event = self.temporal_filter.update(
            has_fire=has_fire,
            confidence=best_conf,
            camera_id=camera_id,
        )

        if fire_event is not None:
            # 触发报警!
            clip_path = self.clip_recorder.save_clip()
            picture_b64 = encode_frame_jpeg(annotated)

            urgency = "高" if best_conf > 0.8 else ("中" if best_conf > 0.5 else "低")

            alarm = AlarmEvent(
                camera_id=camera_id,
                device_id=self.device_id,
                area_id=self.area_id,
                longitude=self.longitude,
                latitude=self.latitude,
                location=self.location,
                confidence=best_conf,
                urgency_degree=urgency,
                description=f"检测到火焰/烟尘 (置信度: {best_conf:.2f})",
                picture_base64=picture_b64,
                video_path=clip_path,
                remark=f"推理时延: {elapsed:.0f}ms, "
                        f"滤波: {self.temporal_filter.vote_count}/{self.temporal_filter.cfg.window_size}",
            )

            logger.info(f"[FIRE] 报警触发! conf={best_conf:.2f}, "
                        f"投票={self.temporal_filter.vote_count}/{self.temporal_filter.cfg.window_size}")

            self.pusher.push(alarm)
            self.alarm_count += 1

        self.frame_count += 1
        return annotated, detections, alarm

    def process_video(self, video_path: str, display: bool = False) -> dict:
        """处理整个视频文件"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"无法打开视频: {video_path}")
            return {}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_src = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        logger.info(f"开始检测: {Path(video_path).name} ({w}x{h}, {total_frames}帧)")

        name = Path(video_path).stem
        idx = 0
        paused = False

        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    break
                idx += 1

                annotated, dets, alarm = self.process_frame(frame)

                # 进度
                pct = idx / total_frames * 100 if total_frames else 0
                bar = "=" * int(pct / 5) + ">" + " " * max(0, 20 - int(pct / 5))
                status = f"[{bar}] {name} {idx}/{total_frames} det:{len(dets)}"
                if alarm:
                    status += " [ALARM]"
                sys.stdout.write(f"\r{status}  ")
                sys.stdout.flush()

            if display:
                cv2.imshow("Flame Detection", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord(" "):
                    paused = not paused

        cap.release()
        if display:
            cv2.destroyAllWindows()

        return {
            "video": video_path,
            "frames": idx,
            "fire_frames": self.fire_frames,
            "alarms": self.alarm_count,
        }


# ============================================================
# 测试服务端 (用于验证数据流, 不需要真实后端)
# ============================================================

class MockServer:
    """简易测试服务端，接收并展示报警事件"""

    def __init__(self, port: int = 8083):
        self.port = port
        self.received_events: list[dict] = []

    def start(self):
        """启动测试服务端 (阻塞)"""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        events = self.received_events

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len)
                try:
                    data = json.loads(body)
                    # 去掉 base64 图片减少日志
                    log_data = {k: v for k, v in data.items() if k != "picture_base64"}
                    events.append(log_data)
                    print(f"\n📨 收到报警 #{len(events)}:")
                    print(f"   时间: {data.get('timestamp', 'N/A')}")
                    print(f"   置信度: {data.get('confidence', 0):.2f}")
                    print(f"   紧急程度: {data.get('urgency_degree', 'N/A')}")
                    print(f"   位置: {data.get('location', 'N/A')}")
                    print(f"   视频: {data.get('video_path', 'N/A')}")
                    print(f"   图片: {'有' if data.get('picture_base64') else '无'} "
                          f"({len(data.get('picture_base64', ''))} chars)")
                    print(f"   描述: {data.get('description', 'N/A')}")
                except Exception as e:
                    print(f"解析失败: {e}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')

            def do_GET(self):
                if self.path == "/":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    html = _mock_server_html(events)
                    self.wfile.write(html.encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()

        print(f"\n{'='*50}")
        print(f" 测试服务端已启动: http://localhost:{self.port}")
        print(f" 浏览器打开查看报警事件面板")
        print(f"{'='*50}\n")

        server = HTTPServer(("0.0.0.0", self.port), Handler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()


def _mock_server_html(events: list) -> str:
    items = ""
    for e in reversed(events[-20:]):
        items += f"""
        <div class="alarm">
            <span class="time">{e.get('timestamp','')[:19]}</span>
            <span class="conf">{e.get('confidence',0):.2f}</span>
            <span class="urgency">{e.get('urgency_degree','')}</span>
            <span class="loc">{e.get('location','未知')}</span>
            <span class="desc">{e.get('description','')}</span>
        </div>"""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>火焰报警监控</title>
<style>
body{{font-family:monospace;background:#1a1a2e;color:#eee;margin:20px}}
h1{{color:#e94560;text-align:center}}
.alarm{{background:#16213e;margin:8px 0;padding:10px;border-left:4px solid #e94560}}
.time{{color:#888;margin-right:15px}}
.conf{{color:#e94560;font-weight:bold;margin-right:10px}}
.urgency{{background:#e94560;color:#fff;padding:2px 6px;border-radius:3px;margin-right:10px}}
.loc{{color:#0f3460;margin-right:10px}}
.desc{{color:#ccc}}
.summary{{text-align:center;margin:15px;font-size:18px;color:#f5c518}}
</style></head><body>
<h1>🔥 火焰报警监控面板</h1>
<p class="summary">共收到 {len(events)} 条报警</p>
{items}
</body></html>"""


# ============================================================
# 命令行入口
# ============================================================

def parse_args():
    p = argparse.ArgumentParser(description="火焰识别边缘端 — 报警推送")
    p.add_argument("--video", type=str, help="视频文件路径")
    p.add_argument("--video-dir", type=str, help="视频目录 (检测所有 .mp4)")
    p.add_argument("--model", type=str,
                   default="output/yolo_train_7videos/weights/best.onnx",
                   help="模型路径 (默认: ONNX)")
    p.add_argument("--server", type=str, default="",
                   help="服务端地址 (如 http://192.168.1.100:8083)")
    p.add_argument("--offline", action="store_true",
                   help="离线模式 (报警保存到本地 JSON)")
    p.add_argument("--device-id", type=int, default=1, help="设备ID")
    p.add_argument("--area-id", type=int, default=1, help="区域ID")
    p.add_argument("--lng", type=float, default=0.0, help="经度")
    p.add_argument("--lat", type=float, default=0.0, help="纬度")
    p.add_argument("--location", type=str, default="", help="位置描述")
    p.add_argument("--conf", type=float, default=0.25, help="置信度阈值")
    p.add_argument("--img-size", type=int, default=416, help="输入尺寸")
    p.add_argument("--no-display", action="store_true", help="不显示窗口")
    p.add_argument("--clip-sec", type=float, default=5.0, help="报警视频片段长度(秒)")
    p.add_argument("--filter-window", type=int, default=5, help="时域滤波窗口")
    p.add_argument("--filter-votes", type=int, default=3, help="报警所需投票数")
    p.add_argument("--mock-server", action="store_true",
                   help="启动测试服务端 (默认端口8083)")
    p.add_argument("--server-port", type=int, default=8083, help="测试服务端端口")
    return p.parse_args()


def main():
    args = parse_args()

    # 启动测试服务端 (在另一个线程)
    if args.mock_server:
        import threading
        mock = MockServer(args.server_port)
        t = threading.Thread(target=mock.start, daemon=True)
        t.start()
        time.sleep(1)
        # 同时设为指向本地测试服务器
        if not args.server:
            args.server = f"http://localhost:{args.server_port}"
            args.offline = False

    # 收集视频列表
    videos = []
    if args.video:
        videos.append(args.video)
    if args.video_dir:
        vdir = Path(args.video_dir)
        videos.extend(sorted(str(p) for p in vdir.glob("VP*.mp4")))
        videos.extend(sorted(str(p) for p in vdir.glob("*.mp4")))

    if not videos:
        print("请指定 --video 或 --video-dir")
        sys.exit(1)

    # 离线模式
    offline = args.offline or not args.server

    print("=" * 55)
    print(" 火焰识别边缘端")
    print("=" * 55)
    print(f" 模型: {args.model}")
    print(f" 服务端: {args.server if not offline else '离线 (保存到本地)'}")
    print(f" 置信度: {args.conf}")
    print(f" 时域滤波: {args.filter_votes}/{args.filter_window} 投票")
    print(f" 报警视频: {args.clip_sec}秒")
    print(f" 位置: ({args.lng}, {args.lat}) {args.location}")
    print()

    detector = FlameAlarmDetector(
        model_path=args.model,
        conf=args.conf,
        img_size=args.img_size,
        server_url=args.server,
        offline=offline,
        device_id=args.device_id,
        area_id=args.area_id,
        longitude=args.lng,
        latitude=args.lat,
        location=args.location,
        clip_sec=args.clip_sec,
        filter_window=args.filter_window,
        filter_votes=args.filter_votes,
    )

    all_results = []
    for vpath in videos:
        if not Path(vpath).exists():
            logger.warning(f"视频不存在: {vpath}")
            continue
        result = detector.process_video(vpath, display=not args.no_display)
        all_results.append(result)
        print(f"\n  {Path(vpath).name}: {result.get('frames',0)}帧, "
              f"火焰{result.get('fire_frames',0)}帧, "
              f"报警{result.get('alarms',0)}次")

    # 汇总
    total_alarms = sum(r.get("alarms", 0) for r in all_results)
    total_frames = sum(r.get("frames", 0) for r in all_results)
    total_fire = sum(r.get("fire_frames", 0) for r in all_results)
    print(f"\n{'='*55}")
    print(f" 检测完毕: {len(all_results)}个视频, {total_frames}帧")
    print(f" 火焰帧: {total_fire}, 报警事件: {total_alarms}")
    print(f" 报警数据: output/alarm_clips/ + output/alarm_events/")

    if args.mock_server:
        print(f"\n 浏览 http://localhost:{args.server_port} 查看报警面板")
        print(" 按 Ctrl+C 退出")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
