"""
ONNX → RKNN 模型转换与量化脚本
目标硬件: Orange Pi 5 (RK3588S, NPU: 6 TOPS)

RKNN Toolkit 2 安装 (在 Orange Pi 5 上):
  pip install rknn-toolkit2==2.3.0

量化策略:
  - FP16: 精度损失 < 0.5%, 性能 ~6 TOPS  (推荐)
  - INT8: 精度损失 < 2%, 性能 ~12 TOPS (混合精度)
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

PROJECT_ROOT = Path(__file__).parent

# 输入路径 (YOLO11 ONNX)
YOLO_ONNX = PROJECT_ROOT / "output" / "yolo_train" / "weights" / "best.onnx"
LEGACY_ONNX = PROJECT_ROOT / "output" / "export" / "smoke_detector.onnx"

# 输出路径
RKNN_FP16 = PROJECT_ROOT / "output" / "export" / "smoke_detector_fp16.rknn"
RKNN_INT8 = PROJECT_ROOT / "output" / "export" / "smoke_detector_int8.rknn"

DATASET_DIR = PROJECT_ROOT / "data" / "smoke_dataset"

# RK3588 配置
TARGET_PLATFORM = "rk3588"       # Orange Pi 5
NPU_CORES = 3                    # RK3588 NPU 有 3 个核心 (2+1 架构)
IMG_SIZE = 416
BATCH_SIZE = 1


def find_onnx_model() -> Path:
    """自动查找可用的 ONNX 模型 (YOLO11 优先)"""
    if YOLO_ONNX.exists():
        return YOLO_ONNX
    if LEGACY_ONNX.exists():
        return LEGACY_ONNX
    return None


def check_rknn2():
    """检查 RKNN Toolkit 2 是否可用"""
    try:
        from rknn.api import RKNN
        return True, RKNN
    except ImportError:
        return False, None


def get_rknn2_version():
    """获取 RKNN Toolkit 2 版本"""
    try:
        import rknn
        if hasattr(rknn, '__version__'):
            return rknn.__version__
        if hasattr(rknn, 'api'):
            return "2.x (detected)"
    except Exception:
        pass
    return "unknown"


def convert_fp16(onnx_path: Path) -> bool:
    """
    FP16 量化转换 (推荐)
    - 精度损失: < 0.5%
    - 模型大小: ~50% of FP32
    - 推理速度: 实时 (利用 6 TOPS)
    """
    available, RKNN = check_rknn2()
    if not available:
        print("[警告] RKNN Toolkit 2 未安装 (仅在 Orange Pi 5 / x86 Linux 上可用)")
        print("  安装方法:")
        print("    git clone https://github.com/airockchip/rknn-toolkit2.git")
        print("    cd rknn-toolkit2/rknn-toolkit2/packages")
        print("    pip install rknn_toolkit2-2.3.0-cp310-cp310-linux_x86_64.whl")
        print("  或使用 Orange Pi 5 官方镜像 (预装 RKNN Toolkit 2):")
        print("    Orange Pi 5 Debian/Ubuntu image from orangepi.org")
        return False

    print("=" * 60)
    print(f"ONNX → RKNN FP16 转换 (目标: Orange Pi 5 / {TARGET_PLATFORM})")
    print(f"RKNN Toolkit 2 版本: {get_rknn2_version()}")
    print("=" * 60)

    rknn = RKNN(verbose=False)

    # Step 1: 配置
    print("\n[1/5] 配置 RKNN 模型...")
    rknn.config(
        mean_values=[[0, 0, 0]],
        std_values=[[255, 255, 255]],
        target_platform=TARGET_PLATFORM,
        batch_size=BATCH_SIZE,
        quantized_dtype='asymmetric_quantized-u8',  # FP16 也用 u8 容器
        optimization_level=3,         # 最高优化级别
        custom_string="smoke_detector_v1",
    )

    # Step 2: 加载 ONNX
    print(f"[2/5] 加载 ONNX: {onnx_path.name}")
    ret = rknn.load_onnx(model=str(onnx_path))
    if ret != 0:
        print(f"  [错误] ONNX 加载失败, 错误码: {ret}")
        print("  可能原因: ONNX opset 版本不兼容 (建议 <= 17)")
        rknn.release()
        return False

    # Step 3: 构建 (FP16 = 不提供校准数据集)
    print("[3/5] 构建 RKNN 模型 (FP16 量化)...")
    print("  这可能需要 5-15 分钟 (取决于模型复杂度)...")
    ret = rknn.build(
        do_quantization=False,    # False = FP16, True = INT8 (需要 dataset)
        dataset=None,
    )
    if ret != 0:
        print(f"  [错误] 模型构建失败, 错误码: {ret}")
        rknn.release()
        return False

    # Step 4: 导出
    print(f"[4/5] 导出 RKNN: {RKNN_FP16.name}")
    ret = rknn.export_rknn(str(RKNN_FP16))
    if ret != 0:
        print(f"  [错误] 导出失败, 错误码: {ret}")
        rknn.release()
        return False

    # Step 5: 精度验证
    print("[5/5] 精度验证...")
    try:
        ret = rknn.accuracy_analysis(
            inputs=[str(DATASET_DIR / "images" / "val")],
            target=TARGET_PLATFORM,
        )
        if ret is not None:
            print(f"  精度分析完成: {ret}")
    except Exception as e:
        print(f"  精度分析跳过 (可能需要板端运行): {e}")

    rknn.release()

    size_kb = RKNN_FP16.stat().st_size / 1024
    print(f"\n✅ FP16 RKNN 模型已保存: {RKNN_FP16}")
    print(f"   模型大小: {size_kb:.1f} KB")
    print(f"   目标平台: Orange Pi 5 ({TARGET_PLATFORM})")
    return True


def convert_int8(onnx_path: Path, calib_images: list[str] = None) -> bool:
    """
    INT8 量化转换 (更高性能)
    - 精度损失: < 2%
    - 模型大小: ~25% of FP32
    - 推理速度: 更快 (利用混合精度)
    - 需要校准数据集 (50-100 张图片)
    """
    available, RKNN = check_rknn2()
    if not available:
        print("[跳过] RKNN Toolkit 2 不可用，无法进行 INT8 转换")
        return False

    print("\n" + "=" * 60)
    print(f"ONNX → RKNN INT8 转换")
    print("=" * 60)

    rknn = RKNN(verbose=False)

    # Step 1: 配置 (INT8 混合精度)
    print("[1/5] 配置 INT8 量化...")
    rknn.config(
        mean_values=[[0, 0, 0]],
        std_values=[[255, 255, 255]],
        target_platform=TARGET_PLATFORM,
        batch_size=BATCH_SIZE,
        quantized_dtype='asymmetric_quantized-u8',
        optimization_level=3,
        # RK3588 混合精度: 敏感层自动用 FP16
        quant_img_RGB2BGR=False,
    )

    # Step 2: 加载
    print(f"[2/5] 加载 ONNX: {onnx_path.name}")
    rknn.load_onnx(model=str(onnx_path))

    # Step 3: 准备校准数据
    if calib_images is None:
        calib_images = _prepare_calib_data()
    print(f"[3/5] 使用 {len(calib_images)} 张校准图像进行 INT8 量化...")

    # Step 4: 构建 (INT8 = 提供校准数据集)
    ret = rknn.build(
        do_quantization=True,
        dataset=calib_images,
    )
    if ret != 0:
        print(f"  [错误] INT8 模型构建失败, 错误码: {ret}")
        rknn.release()
        return False

    # Step 5: 导出
    print(f"[4/5] 导出 RKNN: {RKNN_INT8.name}")
    rknn.export_rknn(str(RKNN_INT8))

    rknn.release()

    size_kb = RKNN_INT8.stat().st_size / 1024
    print(f"\n✅ INT8 RKNN 模型已保存: {RKNN_INT8}")
    print(f"   模型大小: {size_kb:.1f} KB")
    return True


def _prepare_calib_data(num_samples: int = 50) -> list[str]:
    """准备 INT8 校准数据集"""
    img_dir = DATASET_DIR / "images" / "train"
    if not img_dir.exists():
        # fallback to val
        img_dir = DATASET_DIR / "images" / "val"
    return sorted([
        str(f) for f in img_dir.iterdir()
        if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp'}
    ])[:num_samples]


def verify_rknn(rknn_path: Path):
    """在 PC 上模拟验证 RKNN 模型"""
    available, RKNN = check_rknn2()
    if not available or not rknn_path.exists():
        return

    print(f"\n验证 RKNN 模型: {rknn_path.name}")

    rknn = RKNN(verbose=False)
    rknn.load_rknn(str(rknn_path))

    # 在 PC 上模拟 RK3588 推理
    ret = rknn.init_runtime(target=TARGET_PLATFORM)
    if ret != 0:
        print(f"  [跳过] 模拟器初始化失败 (P C端无法完全模拟NPU)")
        print(f"  请将 {rknn_path.name} 拷贝到 Orange Pi 5 上验证")
        rknn.release()
        return

    # 测试推理
    dummy = np.random.randn(1, 3, IMG_SIZE, IMG_SIZE).astype(np.float32)
    outputs = rknn.inference(inputs=[dummy])
    print(f"  推理成功, 输出数量: {len(outputs)}")
    for i, o in enumerate(outputs):
        print(f"  output[{i}] shape: {o.shape}")

    # 性能评估
    try:
        perf = rknn.eval_perf()
        print(f"  预估 NPU 性能: {perf}")
    except Exception:
        pass

    rknn.release()


def export_onnx_from_yolo():
    """从 YOLO11 模型导出 ONNX (如果没有的话)"""
    if YOLO_ONNX.exists():
        return True

    best_pt = PROJECT_ROOT / "output" / "yolo_train" / "weights" / "best.pt"
    if not best_pt.exists():
        print("[错误] YOLO11 best.pt 不存在, 请先训练: python train_yolo.py")
        return False

    try:
        from ultralytics import YOLO
        model = YOLO(str(best_pt))
        model.export(
            format="onnx",
            imgsz=IMG_SIZE,
            half=False,
            simplify=True,
            opset=12,  # RK3588 推荐 opset 12-17
        )
        print(f"✅ ONNX 导出完成: {YOLO_ONNX}")
        return True
    except Exception as e:
        print(f"[错误] ONNX 导出失败: {e}")
        return False


def main():
    print("=" * 60)
    print("🔥 火焰检测模型 → Orange Pi 5 (RK3588) 部署转换")
    print("=" * 60)
    print(f"  目标平台: Orange Pi 5 ({TARGET_PLATFORM})")
    print(f"  NPU 算力: 6 TOPS")
    print(f"  输入尺寸: {IMG_SIZE}×{IMG_SIZE}")
    print(f"  所需工具: RKNN Toolkit 2 (rknn-toolkit2)")
    print()

    # 找到 ONNX 模型
    onnx_path = find_onnx_model()
    if onnx_path is None:
        print("[信息] 未找到 ONNX 模型, 尝试从 YOLO11 best.pt 导出...")
        if not export_onnx_from_yolo():
            print("\n[跳过] 请先完成 YOLO11 训练:")
            print("  python train_yolo.py")
            print("  然后重新运行本脚本")
            sys.exit(0)
        onnx_path = YOLO_ONNX

    print(f"输入模型: {onnx_path}")
    if onnx_path.exists():
        print(f"文件大小: {onnx_path.stat().st_size / 1024:.1f} KB")
    print()

    # FP16 转换 (推荐)
    fp16_ok = convert_fp16(onnx_path)
    if fp16_ok:
        verify_rknn(RKNN_FP16)

    # INT8 转换 (可选, 需要校准数据)
    print("\n" + "-" * 40)
    try_int8 = input("是否进行 INT8 量化? (y/n, 默认n): ").strip().lower()
    if try_int8 == 'y':
        convert_int8(onnx_path)

    # 最终说明
    print("\n" + "=" * 60)
    print("📋 Orange Pi 5 部署步骤:")
    print("=" * 60)
    print("""
  1. 将 .rknn 文件拷贝到 Orange Pi 5:
     scp output/export/smoke_detector_fp16.rknn orangepi@<IP>:/home/orangepi/

  2. 在 Orange Pi 5 上安装 RKNN Toolkit Lite 2:
     sudo apt update
     sudo apt install python3-pip python3-opencv
     pip3 install rknn-toolkit-lite2

  3. 运行边缘端管线:
     python edge/pipeline.py

  4. 或直接使用 Python 测试 NPU 推理:
     python -c "
     from rknnlite.api import RKNNLite
     rknn = RKNNLite()
     rknn.load_rknn('smoke_detector_fp16.rknn')
     rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO)
     import numpy as np
     img = np.random.randn(1,3,416,416).astype(np.float32)
     outputs = rknn.inference([img])
     print('NPU 推理成功!', [o.shape for o in outputs])
     "
""")
    print("-" * 60)
    print("📌 注意事项:")
    print("  - RKNN Toolkit 2 在 x86 Linux 上可模拟转换，但推理需在板端运行")
    print("  - RKNN Toolkit Lite 2 仅在 Orange Pi 5 (ARM64) 上运行推理")
    print("  - 推荐使用 Orange Pi 5 官方 Debian/Ubuntu 镜像")
    print("  - NPU 驱动: sudo apt install rknpu2-driver")


if __name__ == "__main__":
    main()
