# @File : main.py
# Author: 郭
# Software: PyCharm
# Time：2026/6/11 下午5:40
"""
火焰/烟尘检测系统 — 统一入口 (YOLO11)
========================================
用法: python main.py <命令>

AI模型:
  yolo-train     训练 YOLO11-nano
  yolo-resume    从断点恢复训练
  yolo-eval      多阈值评估

目标定位:
  calib          创建相机标定数据
  ptz            PTZ参数解析测试
  locate         定位流水线演示
  verify         定位精度验证

边缘部署:
  rknn           ONNX → RKNN 转换 (Orange Pi 5)
  edge-run       启动边缘端检测管线 (Orange Pi 5)
  edge-video     边缘端视频检测 (ONNX/RKNN, 无需摄像头)
  flame-alarm    火焰识别报警推送 (图片+视频+位置)
  e2e            端到端集成测试
  video-test     视频文件火焰检测 (test/VP47.mp4)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def cmd_yolo_train():
    from train_yolo import main
    main()


def cmd_yolo_resume():
    from resume_train import main
    main()


def cmd_yolo_eval():
    from evaluate_yolo import evaluate_at_thresholds
    evaluate_at_thresholds()


def cmd_calib():
    from config import DATA_DIR
    from localization.camera_calibrator import create_sample_calibration
    save_path = DATA_DIR / "camera_calib" / "camera_001_calib.json"
    create_sample_calibration(save_path)


def cmd_ptz():
    from localization.ptz_parser import test_parser
    test_parser()


def cmd_locate():
    from localization.localization_pipeline import demo_pipeline
    demo_pipeline()


def cmd_verify():
    from config import DATA_DIR
    from localization.camera_calibrator import CameraCalibrator
    import numpy as np

    calib = CameraCalibrator("camera_001")
    calib.load_calibration(DATA_DIR / "camera_calib" / "camera_001_calib.json")
    calib.calibrate()

    test_pts = [
        (50, 50, 116.391200, 39.907500),
        (366, 50, 116.396800, 39.907500),
        (50, 366, 116.391200, 39.903100),
        (366, 366, 116.396800, 39.903100),
    ]
    errors = []
    for img_x, img_y, exp_lng, exp_lat in test_pts:
        pred_lng, pred_lat = calib.image_to_gps(img_x, img_y)
        d_lng = (pred_lng - exp_lng) * 111320 * np.cos(np.radians(exp_lat))
        d_lat = (pred_lat - exp_lat) * 111320
        error = np.sqrt(d_lng**2 + d_lat**2)
        errors.append(error)
        print(f"  ({img_x:3d},{img_y:3d}) -> "
              f"预测({pred_lng:.6f},{pred_lat:.6f}) "
              f"真实({exp_lng:.6f},{exp_lat:.6f}) "
              f"误差={error:.1f}m")
    print(f"\n平均误差: {np.mean(errors):.1f}m")
    print(f"最大误差: {np.max(errors):.1f}m")
    print(f"达标(<=200m): {'通过' if np.max(errors) <= 200 else '不通过'}")


def cmd_rknn():
    from convert_rknn import main
    main()


def cmd_e2e():
    from test_end_to_end import main
    main()


def cmd_video_test():
    from test_video import main
    main()


def cmd_edge_video():
    from edge.video_detect import main
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    main()


def cmd_flame_alarm():
    from edge.flame_alarm import main
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    main()


def cmd_edge_run():
    from edge.run import main
    # 转发命令行参数 (去掉 'edge-run' 本身)
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    main()


COMMANDS = {
    "yolo-train":   ("训练 YOLO11-nano", cmd_yolo_train),
    "yolo-resume":  ("从断点恢复 YOLO11 训练", cmd_yolo_resume),
    "yolo-eval":    ("YOLO11 多阈值评估", cmd_yolo_eval),
    "calib":        ("创建相机标定数据", cmd_calib),
    "ptz":          ("PTZ参数解析测试", cmd_ptz),
    "locate":       ("定位流水线演示", cmd_locate),
    "verify":       ("定位精度验证", cmd_verify),
    "rknn":         ("ONNX → RKNN 转换 (Orange Pi 5)", cmd_rknn),
    "edge-run":     ("启动边缘端检测管线 (Orange Pi 5)", cmd_edge_run),
    "e2e":          ("端到端集成测试", cmd_e2e),
    "edge-video":   ("边缘端视频检测 (ONNX/RKNN)", cmd_edge_video),
    "flame-alarm":  ("火焰识别报警推送", cmd_flame_alarm),
    "video-test":   ("视频文件火焰检测", cmd_video_test),
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("可用命令:")
        max_len = max(len(k) for k in COMMANDS)
        for name, (desc, _) in COMMANDS.items():
            print(f"  {name:<{max_len}s}  {desc}")
        print(f"\n示例: python main.py yolo-train")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd in COMMANDS:
        print(f">>> {COMMANDS[cmd][0]}")
        COMMANDS[cmd][1]()
    else:
        print(f"未知命令: {cmd}")
        print(f"可用命令: {', '.join(COMMANDS.keys())}")
        sys.exit(1)
