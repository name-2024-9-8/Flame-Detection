#!/usr/bin/env python3
"""
香橙派报警上传 — 只传视频
==========================
把检测到的火焰视频片段推送到服务端。

用法:
  python upload_alarm.py --video clip.mp4
  python upload_alarm.py --video clip.mp4 --conf 0.72 --server http://10.170.13.127:8080/index.php

依赖: pip install requests
"""
import sys, os, base64, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import confidence_to_level

try:
    import requests
except ImportError:
    print("请先安装: pip install requests")
    sys.exit(1)

DEFAULT_CAMERA_ID = 10
DEFAULT_LNG = 106.528
DEFAULT_LAT = 29.453
DEFAULT_LOCATION = "重庆理工大学-花溪校区摄像头"
DEFAULT_SERVER = "http://127.0.0.1:8080/index.php"


def upload(video_path, confidence, server_url):
    with open(video_path, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "event_type": "fire",
        "camera_id": DEFAULT_CAMERA_ID,
        "device_id": 1,
        "area_id": 1,
        "longitude": str(DEFAULT_LNG),
        "latitude": str(DEFAULT_LAT),
        "location": DEFAULT_LOCATION,
        "confidence": round(confidence, 4),
        "urgency_degree": confidence_to_level(confidence),
        "video_base64": video_b64,
        "description": f"边缘端检测到火焰 (置信度: {confidence:.2f})",
        "status": "1",
    }

    url = f"{server_url}/api/detect/alarm"
    print(f"推送: {url}")
    print(f"视频: {video_path} ({os.path.getsize(video_path)//1024}KB)")
    print(f"置信度: {confidence:.0%} → {confidence_to_level(confidence)}")

    r = requests.post(url, json=payload, timeout=120)
    if r.status_code == 200:
        print("推送成功!")
        return True
    print(f"失败: HTTP {r.status_code}")
    return False


def main():
    p = argparse.ArgumentParser(description="香橙派报警上传")
    p.add_argument("--video", required=True, help="火焰视频片段路径")
    p.add_argument("--conf", type=float, default=0.8, help="置信度 (0-1)")
    p.add_argument("--server", default=DEFAULT_SERVER, help="服务端地址")
    args = p.parse_args()

    if not os.path.exists(args.video):
        print(f"文件不存在: {args.video}")
        sys.exit(1)

    upload(args.video, args.conf, args.server)


if __name__ == "__main__":
    main()
