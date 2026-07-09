#!/usr/bin/env python3
"""
火焰检测 — 视频文件推理 + 报警推送 (演示/测试用)
用法:
  python demo_flame_detect.py --video test/VP47.mp4
  python demo_flame_detect.py --video test/VP47.mp4 --conf 0.25 --server http://127.0.0.1:8080/index.php
"""
from __future__ import annotations
import sys, os, json, base64, time, argparse, logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

import cv2
import numpy as np
import requests
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).parent))
from edge.utils import confidence_to_level

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("FlameDetect")


def push_alarm(server_url: str, annotated_frame: np.ndarray, conf: float,
               device_id: int, area_id: int, camera_id: int,
               lng: float, lat: float, location: str):
    """推送报警到服务器（完整标注帧，不含视频）"""
    tz = timezone(timedelta(hours=8))
    ts = datetime.now(tz).isoformat()

    _, buf = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    img_b64 = base64.b64encode(buf).decode()

    payload = {
        "event_type": "fire",
        "camera_id": camera_id, "device_id": device_id, "area_id": area_id,
        "timestamp": ts, "longitude": lng, "latitude": lat, "location": location,
        "confidence": round(conf, 4), "urgency_degree": confidence_to_level(conf),
        "picture_base64": img_b64, "video_path": "",
        "description": f"检测到火焰 (置信度: {conf:.2f})", "status": "1",
    }

    try:
        r = requests.post(f"{server_url}/api/detect/alarm", json=payload, timeout=10)
        if r.status_code == 200:
            logger.info(f"报警已推送: conf={conf:.2f}")
            resp_data = r.json()
            return resp_data.get('data', {}).get('id') if isinstance(resp_data, dict) else None
        else:
            logger.warning(f"推送失败: {r.status_code} {r.text[:100]}")
    except Exception as e:
        logger.error(f"推送异常: {e}")
    return None


def main():
    p = argparse.ArgumentParser(description="火焰检测 — 视频推理 + 报警推送")
    p.add_argument("--video", required=True, help="视频文件路径")
    p.add_argument("--model", default="output/dfire_train/weights/best.pt", help="模型路径")
    p.add_argument("--conf", type=float, default=0.25, help="置信度阈值")
    p.add_argument("--save", action="store_true", help="保存标注视频")
    p.add_argument("--server", type=str, default="", help="服务器地址 (如 http://127.0.0.1:8080/index.php)")
    p.add_argument("--camera-id", type=int, default=10, help="摄像头ID")
    p.add_argument("--area-id", type=int, default=1, help="区域ID")
    p.add_argument("--lng", type=float, default=0.0, help="经度")
    p.add_argument("--lat", type=float, default=0.0, help="纬度")
    p.add_argument("--location", type=str, default="", help="位置描述")
    p.add_argument("--output-dir", type=str, default="output", help="输出目录")
    args = p.parse_args()

    print("=" * 50)
    print(" 火焰检测 — 视频推理")
    print("=" * 50)
    print(f" 视频: {args.video}")
    print(f" 模型: {args.model}")
    print(f" 阈值: {args.conf}")
    print(f" 服务端: {args.server if args.server else '离线'}")
    print()

    # 加载模型
    model = YOLO(args.model)
    logger.info(f"模型已加载: {args.model}")

    # 打开视频
    cap = cv2.VideoCapture(args.video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info(f"视频: {args.video} ({w}x{h}, {total}帧, {fps:.1f}fps)")

    # 输出视频
    writer = None
    out_name = Path(args.video).stem + "_detected.mp4"
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    if args.save:
        out_path = str(Path(args.output_dir) / out_name)
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        logger.info(f"输出: {out_path}")

    alarm_ids = []  # 收集报警ID，检测完成后回填视频
    alarm_count = 0
    detect_frames = 0
    times = []

    for idx in range(total):
        ret, frame = cap.read()
        if not ret:
            break

        t0 = time.perf_counter()
        results = model(frame, conf=args.conf, verbose=False)
        elapsed = (time.perf_counter() - t0) * 1000
        times.append(elapsed)

        annotated = frame.copy()
        boxes = results[0].boxes

        if boxes is not None and len(boxes) > 0:
            detect_frames += 1
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].tolist()

                # 标注
                color = (0, 0, 255)
                x1, y1, x2, y2 = map(int, xyxy)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                label = f"fire {conf:.2f}"
                cv2.putText(annotated, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                # 报警推送 (发送标注后的完整帧)
                if args.server:
                    alarm_id = push_alarm(args.server, annotated, conf,
                               args.device_id, args.area_id, args.camera_id,
                               args.lng, args.lat, args.location)
                    if alarm_id:
                        alarm_ids.append(alarm_id)
                    alarm_count += 1

        # 进度条
        pct = (idx + 1) / total * 100
        bar = "=" * int(pct / 5) + ">" + " " * (20 - int(pct / 5))
        avg_ms = sum(times[-30:]) / len(times[-30:])
        sys.stdout.write(f"\r[{bar}] {idx+1}/{total} ({pct:.0f}%)  "
                         f"infer: {avg_ms:.0f}ms  fire: {detect_frames}")
        sys.stdout.flush()

        if writer:
            writer.write(annotated)

    cap.release()
    if writer:
        writer.release()

    # 检测完成后，将标注视频转码为浏览器可播的 H.264 并关联报警
    if args.server and args.save and alarm_ids:
        import shutil, uuid, subprocess
        alarm_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 'static', 'uploads', 'alarms')
        os.makedirs(alarm_dir, exist_ok=True)

        # 用 imageio-ffmpeg 把 mp4v 转成 H.264 (浏览器必需)
        video_name_h264 = 'alarm_%s_h264.mp4' % uuid.uuid4().hex[:16]
        video_dst = os.path.join(alarm_dir, video_name_h264)
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
            result = subprocess.run([
                ffmpeg, '-y', '-i', out_path,
                '-c:v', 'libx264', '-preset', 'ultrafast',
                '-pix_fmt', 'yuv420p', '-an',
                video_dst
            ], capture_output=True, timeout=60)
            if os.path.exists(video_dst) and os.path.getsize(video_dst) > 0:
                video_url = '/static/uploads/alarms/' + video_name_h264
                # 删除原始 mp4v 临时文件
                os.unlink(out_path)
                logger.info(f"视频已转码 H.264: {video_url}")
            else:
                # 转码失败，回退复制原始文件
                logger.warning(f"ffmpeg 转码失败: {result.stderr[:200]}")
                shutil.copy2(out_path, video_dst)
                video_url = '/static/uploads/alarms/' + video_name_h264
        except Exception as e:
            logger.warning(f"转码异常: {e}，回退复制原始文件")
            shutil.copy2(out_path, video_dst)
            video_url = '/static/uploads/alarms/' + video_name_h264

        # 批量回填 VideoUrl
        try:
            r = requests.post(f"{args.server}/api/detect/alarm/batch-video",
                              json={"alarm_ids": alarm_ids, "video_url": video_url}, timeout=30)
            if r.status_code == 200:
                logger.info(f"已为 {len(alarm_ids)} 条报警关联视频")
            else:
                logger.warning(f"批量关联视频失败: {r.status_code}")
        except Exception as e:
            logger.warning(f"批量关联异常: {e}")

    print(f"\n\n{'=' * 50}")
    print(" 检测完毕")
    print("=" * 50)
    print(f" 帧数: {total}  火焰帧: {detect_frames}  报警推送: {alarm_count}")
    if times:
        print(f" 推理速度: avg={sum(times)/len(times):.0f}ms, FPS={1000/(sum(times)/len(times)):.1f}")


if __name__ == "__main__":
    main()
