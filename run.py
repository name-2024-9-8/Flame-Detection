"""
=============================================================================
视频AI智能识别及预警管理信息系统 — 统一启动入口
=============================================================================
融合: Flask Web管理平台 (段林川/王永林) + YOLO11边缘检测 (郭俊奇)

用法:
  python run.py web             启动 Web 管理平台 (Flask)
  python run.py detection <cmd>  运行检测命令 (YOLO11)

Web 管理:
  run.py web          → http://127.0.0.1:5000

检测命令 (delegated to detection/main.py):
  run.py detection yolo-train     训练 YOLO11-nano
  run.py detection yolo-resume    从断点恢复训练
  run.py detection yolo-eval      多阈值评估
  run.py detection calib          创建相机标定数据
  run.py detection ptz            PTZ参数解析测试
  run.py detection locate         定位流水线演示
  run.py detection verify         定位精度验证
  run.py detection rknn           ONNX → RKNN 转换
  run.py detection edge-run       启动边缘端检测管线
  run.py detection edge-video     边缘端视频检测
  run.py detection flame-alarm    火焰识别报警推送
  run.py detection e2e            端到端集成测试
  run.py detection video-test     视频文件火焰检测
  run.py detection --help         查看所有检测命令

提示:
  也可直接 cd detection && python main.py <命令>
  或直接 python app.py (启动 Web)
=============================================================================
"""
import sys
import os
from pathlib import Path


def cmd_web():
    """启动 Flask Web 管理平台"""
    sys.path.insert(0, str(Path(__file__).parent))
    from app import app
    print("=" * 60)
    print("  [Fire] 视频AI智能识别及预警管理信息系统")
    print("  火焰识别 - Web管理平台")
    print("=" * 60)
    print("  访问地址: http://127.0.0.1:5000")
    print("  管理后台: http://127.0.0.1:5000/dashboard")
    print("  数据大屏: http://127.0.0.1:5000/")
    print("  登录页面: http://127.0.0.1:5000/login")
    print("  管理员账号: admin / 123456")
    print("  健康检查: http://127.0.0.1:5000/health")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)


def cmd_detection():
    """运行检测命令 (转发到 detection/main.py)"""
    detection_dir = Path(__file__).parent / "detection"
    sys.path.insert(0, str(detection_dir))

    # 切换到 detection 目录执行
    os.chdir(str(detection_dir))

    # 转发剩余参数给 detection/main.py
    from detection.main import COMMANDS

    if len(sys.argv) < 3:
        print("检测命令用法: python run.py detection <命令>")
        print("\n可用命令:")
        max_len = max(len(k) for k in COMMANDS)
        for name, (desc, _) in COMMANDS.items():
            print(f"  {name:<{max_len}s}  {desc}")
        print("\n示例: python run.py detection video-test")
        sys.exit(0)

    cmd = sys.argv[2]
    if cmd in COMMANDS:
        print(f">>> {COMMANDS[cmd][0]}")
        # 保留 sys.argv[0] 和后续参数，去掉 'detection' 索引位
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        COMMANDS[cmd][1]()
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    mode = sys.argv[1]
    if mode == "web":
        cmd_web()
    elif mode == "detection":
        cmd_detection()
    else:
        print(f"未知模式: {mode}")
        print("用法: python run.py web|detection")
        sys.exit(1)
