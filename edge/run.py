#!/usr/bin/env python3
"""
火焰检测边缘端 — Orange Pi 5 一键启动入口
============================================
用法:
  python edge/run.py                          # 从 edge_config.json 加载配置运行
  python edge/run.py --config my_config.json  # 指定配置文件
  python edge/run.py --simulate               # 模拟模式 (无摄像头时用测试帧)
  python edge/run.py --preview                # 显示检测画面
  python edge/run.py --camera 0               # 使用指定摄像头 (0=USB摄像头)
  python edge/run.py --once                   # 单帧测试模式

自动检测推理后端: RKNN (NPU) > ONNX (CPU) > PyTorch (CPU)
"""
from __future__ import annotations
import sys
import os
import json
import time
import signal
import logging
import argparse
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PROJECT_ROOT, DATA_DIR, OUTPUT_DIR
from edge.pipeline import EdgePipeline, EdgeConfig
from edge.video_stream import CameraConfig
from edge.hardware_utils import OrangePi5Utils

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_DIR / 'logs' / 'edge.log', encoding='utf-8'),
    ],
)
logger = logging.getLogger("EdgeRunner")

DEFAULT_CONFIG = PROJECT_ROOT / "edge_config.json"


# ============================================================
# 配置加载
# ============================================================

def load_config(config_path: str) -> dict:
    """加载边缘端配置 JSON"""
    path = Path(config_path)
    if not path.exists():
        logger.error(f"配置文件不存在: {path}")
        logger.info("可从模板创建: cp edge_config.template.json edge_config.json")
        return {}

    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    logger.info(f"配置已加载: {path} (server={cfg.get('server', {}).get('url', 'N/A')})")
    return cfg


def build_pipeline_config(cfg: dict) -> EdgeConfig:
    """从 JSON 配置构建 EdgeConfig"""
    m = cfg.get('model', {})
    v = cfg.get('video', {})
    p = cfg.get('preprocessing', {})
    t = cfg.get('temporal_filter', {})
    perf = cfg.get('performance', {})
    srv = cfg.get('server', {})

    return EdgeConfig(
        model_path=m.get('path', 'output/export/smoke_detector_fp16.rknn'),
        conf_threshold=m.get('conf_threshold', 0.25),
        iou_threshold=m.get('iou_threshold', 0.5),
        img_size=m.get('img_size', 416),
        target_fps=v.get('target_fps', 15),
        enable_dehaze=p.get('enable_dehaze', True),
        enable_clahe=p.get('enable_clahe', True),
        server_url=srv.get('url', 'http://127.0.0.1:8083'),
        api_key=srv.get('api_key', ''),
        heartbeat_interval=srv.get('heartbeat_interval_s', 30),
        clip_pre_frames=v.get('clip_pre_frames', 30),
        clip_post_frames=v.get('clip_post_frames', 45),
        clip_dir=v.get('clip_dir', 'output/clips'),
        temporal_window_size=t.get('window_size', 5),
        temporal_vote_threshold=t.get('vote_threshold', 3),
        temporal_cooldown_frames=t.get('cooldown_frames', 30),
        latency_target_ms=perf.get('latency_target_ms', 2000),
        calib_dir=cfg.get('device', {}).get('calib_dir', 'data/camera_calib'),
        enable_localization=True,
        show_preview=v.get('show_preview', False),
        save_annotated=v.get('save_annotated', True),
    )


# ============================================================
# 推理后端检测
# ============================================================

def detect_backend() -> str:
    """自动检测最佳推理后端: RKNN > ONNX > PyTorch"""
    # 1. 检查 RKNN (NPU)
    try:
        from rknnlite.api import RKNNLite
        logger.info("检测到 RKNN Toolkit Lite 2 (NPU 推理可用)")
        return "rknn"
    except ImportError:
        pass

    # 2. 检查 ONNX Runtime
    try:
        import onnxruntime
        logger.info(f"检测到 ONNX Runtime (CPU 推理): {onnxruntime.__version__}")
        return "onnx"
    except ImportError:
        pass

    # 3. 检查 PyTorch
    try:
        import torch
        logger.info(f"检测到 PyTorch (CPU 推理): {torch.__version__}")
        return "pytorch"
    except ImportError:
        pass

    logger.error("未检测到任何推理后端! 请安装 onnxruntime 或 rknn-toolkit-lite2")
    return "none"


def auto_select_model(cfg: dict, backend: str) -> str:
    """根据后端自动选择模型文件"""
    model_path = cfg.get('model', {}).get('path', '')

    if backend == 'rknn':
        rknn_path = PROJECT_ROOT / "output" / "export" / "smoke_detector_fp16.rknn"
        if rknn_path.exists():
            return str(rknn_path)

    if backend in ('onnx', 'pytorch'):
        onnx_path = PROJECT_ROOT / "output" / "yolo_train_7videos" / "weights" / "best.onnx"
        if onnx_path.exists():
            return str(onnx_path)

        pt_path = PROJECT_ROOT / "output" / "yolo_train_7videos" / "weights" / "best.pt"
        if pt_path.exists() and backend == 'pytorch':
            return str(pt_path)

    if model_path and Path(model_path).exists():
        return model_path

    logger.warning("未找到合适的模型文件，将尝试自动查找")
    return model_path


# ============================================================
# 摄像头初始化
# ============================================================

def create_camera_from_config(cam_cfg: dict) -> CameraConfig:
    """从配置创建摄像头配置"""
    return CameraConfig(
        camera_id=cam_cfg.get('camera_id', 0),
        name=cam_cfg.get('name', ''),
        rtsp_url=cam_cfg.get('rtsp_url', ''),
        ip=cam_cfg.get('ip', ''),
        port=cam_cfg.get('port', 554),
        username=cam_cfg.get('username', 'admin'),
        password=cam_cfg.get('password', 'admin'),
        width=cam_cfg.get('width', 1920),
        height=cam_cfg.get('height', 1080),
        fps=cam_cfg.get('fps', 25),
        longitude=cam_cfg.get('longitude', 0.0),
        latitude=cam_cfg.get('latitude', 0.0),
        area_id=cam_cfg.get('area_id', 0),
        device_id=cam_cfg.get('device_id', 0),
    )


def create_local_camera(device_id: int) -> Optional[CameraConfig]:
    """使用本地 USB 摄像头 (OpenCV VideoCapture)"""
    for cam_id in range(2):
        cap = cv2.VideoCapture(cam_id)
        if cap.isOpened():
            cap.release()
            return CameraConfig(
                camera_id=cam_id,
                name=f"USB摄像头-{cam_id}",
                device_id=device_id,
            )
    return None


# ============================================================
# 系统信息
# ============================================================

def print_system_info(cfg: dict, backend: str):
    """打印系统信息"""
    dev = cfg.get('device', {})
    on_pi = OrangePi5Utils.check_npu_ready() if backend == 'rknn' else False

    print("=" * 60)
    print(" 火焰检测边缘端 — Orange Pi 5 (RK3588S)")
    print("=" * 60)
    print(f"  设备 ID:     {dev.get('device_id', 'N/A')}")
    print(f"  设备名称:    {dev.get('name', 'N/A')}")
    print(f"  推理后端:    {backend.upper()}")
    print(f"  NPU 状态:    {'可用' if on_pi else '不可用 (PC/模拟)'}")
    print(f"  服务器:      {cfg.get('server', {}).get('url', 'N/A')}")
    print(f"  摄像头数:    {len(cfg.get('cameras', []))}")
    print(f"  检测阈值:    {cfg.get('model', {}).get('conf_threshold', 0.25)}")
    ip = OrangePi5Utils.get_ip_address()
    print(f"  本机 IP:     {ip}")
    print("=" * 60)


# ============================================================
# 命令行参数
# ============================================================

def parse_args():
    p = argparse.ArgumentParser(
        description='火焰检测边缘端 — Orange Pi 5 启动入口',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument('--config', '-c', default=str(DEFAULT_CONFIG),
                   help=f'配置文件路径 (默认: {DEFAULT_CONFIG})')
    p.add_argument('--simulate', '-s', action='store_true',
                   help='模拟模式 (使用随机测试帧, 无需摄像头)')
    p.add_argument('--camera', type=int, default=None,
                   help='使用指定编号的 USB 摄像头 (0, 1, ...)')
    p.add_argument('--preview', '-p', action='store_true',
                   help='显示检测画面窗口')
    p.add_argument('--once', action='store_true',
                   help='单帧测试模式 (处理一帧后退出)')
    p.add_argument('--duration', '-d', type=float, default=0,
                   help='运行时长 (秒, 0=无限)')
    p.add_argument('--no-dehaze', action='store_true',
                   help='关闭去雾预处理')
    p.add_argument('--no-clahe', action='store_true',
                   help='关闭 CLAHE 增强')
    return p.parse_args()


# ============================================================
# 主入口
# ============================================================

def main():
    args = parse_args()

    # 加载配置
    cfg = load_config(args.config)
    if not cfg:
        # 无配置文件时使用默认值
        cfg = {
            "device": {"device_id": 0, "area_id": 0},
            "server": {"url": "http://127.0.0.1:8083"},
            "model": {},
            "video": {"target_fps": 15},
            "preprocessing": {},
            "temporal_filter": {},
            "performance": {},
        }

    # 检测后端
    backend = detect_backend()
    if backend == 'none':
        logger.error("无法启动: 未找到可用的推理后端")
        sys.exit(1)

    # 自动选择模型
    model_path = auto_select_model(cfg, backend)
    if model_path:
        cfg.setdefault('model', {})['path'] = model_path
    logger.info(f"模型文件: {model_path}")

    # 构建管线配置
    edge_cfg = build_pipeline_config(cfg)

    # 命令行覆盖
    if args.no_dehaze:
        edge_cfg.enable_dehaze = False
    if args.no_clahe:
        edge_cfg.enable_clahe = False
    if args.preview:
        edge_cfg.show_preview = True

    # 创建摄像头
    cameras = cfg.get('cameras', [])
    first_cam = None

    if args.simulate:
        logger.info("模拟模式: 使用测试帧")
        first_cam = None  # pipeline会使用随机帧
    elif args.camera is not None:
        first_cam = create_local_camera(cfg.get('device', {}).get('device_id', 0))
        if first_cam is None:
            logger.error(f"无法打开摄像头 #{args.camera}")
            sys.exit(1)
        logger.info(f"USB 摄像头已就绪: #{args.camera}")
    elif cameras:
        # 使用配置中的第一个 RTSP 摄像头
        first_cam = create_camera_from_config(cameras[0])
        logger.info(f"RTSP 摄像头: {first_cam.name} ({first_cam.rtsp_url})")
    else:
        logger.warning("未配置摄像头，使用模拟模式")
        first_cam = None

    edge_cfg.camera = first_cam

    # 打印系统信息
    print_system_info(cfg, backend)

    # 创建设备信息
    dev = cfg.get('device', {})
    device_info = {
        'device_id': dev.get('device_id', 0),
        'area_id': dev.get('area_id', 0),
        'longitude': dev.get('longitude', 0.0),
        'latitude': dev.get('latitude', 0.0),
        'location': dev.get('location', ''),
    }

    # 创建管线
    pipeline = EdgePipeline(edge_cfg)

    # 优雅关闭
    def shutdown(signum=None, frame=None):
        logger.info("收到关闭信号，正在停止管线...")
        pipeline.stop()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # 单帧测试
    if args.once:
        logger.info("单帧测试模式")
        if not pipeline.start():
            logger.error("管线启动失败")
            sys.exit(1)

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        if first_cam is not None:
            from edge.video_stream import RTSPStreamReader
            reader = RTSPStreamReader(first_cam)
            if reader.connect():
                frame = reader.read_frame()
                reader.close()

        if frame is None:
            logger.error("无法获取测试帧")
            sys.exit(1)

        result = pipeline.process_frame(
            frame,
            camera_id=first_cam.camera_id if first_cam else 0,
            device_id=device_info['device_id'],
            area_id=device_info['area_id'],
            longitude=device_info['longitude'],
            latitude=device_info['latitude'],
            location_text=device_info['location'],
        )
        if result:
            print(f"\n检测结果: {len(result.detections)} 个目标")
            for d in result.detections:
                print(f"  {d.class_name}: conf={d.confidence:.2f}, "
                      f"pos=({d.x1:.0f},{d.y1:.0f})-({d.x2:.0f},{d.y2:.0f})")
            print(f"推理时延: {result.inference_time_ms:.1f}ms")

        pipeline.stop()
        return

    # 正常运行
    logger.info("启动边缘端管线...")
    if not pipeline.start():
        logger.error("管线启动失败")
        sys.exit(1)

    try:
        pipeline.run(
            duration=args.duration,
            camera_configs=cameras,
            device_info=device_info,
        )
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.stop()

    # 打印统计
    stats = pipeline.get_stats()
    print(f"\n运行统计:")
    print(f"  处理帧数: {stats['frames_processed']}")
    print(f"  检测帧数: {stats['detections']}")
    print(f"  平均时延: {stats['latency'].get('avg_ms', 0):.1f}ms")
    logger.info("边缘端已安全退出")


if __name__ == "__main__":
    main()
