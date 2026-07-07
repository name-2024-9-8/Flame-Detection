"""
D-Fire 数据集一键训练 + 续训练脚本 (Cloud Studio GPU 优化)

用法:
    python train_dfire.py                    # 训练 (检测到 last.pt 自动续训练)
    python train_dfire.py --fresh            # 强制重新训练
    python train_dfire.py --epochs 300       # 自定义训练轮数
    python train_dfire.py --batch 128        # 自定义 batch size
    python train_dfire.py --imgsz 960        # 自定义输入尺寸
    python train_dfire.py --cache ram        # 缓存到 RAM (需足够内存)
    python train_dfire.py --device cpu       # 强制 CPU 训练

GPU batch size 自动选择:
    >= 24GB VRAM → 128  (A10)
    >= 16GB VRAM → 64   (V100, T4)
    <  16GB VRAM → 32

输出:
    output/dfire_train/weights/best.pt   (最佳模型)
    output/dfire_train/weights/last.pt   (断点续训)
    output/dfire_train/weights/best.onnx (ONNX 导出)
"""
import argparse
import os
import sys
from pathlib import Path

import torch

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_YAML = PROJECT_ROOT / "data" / "dfire" / "data.yaml"
OUTPUT_DIR = PROJECT_ROOT / "output" / "dfire_train"


def detect_gpu() -> dict:
    """检测 GPU 并返回设备信息"""
    info = {
        "device": "cpu",
        "gpu_name": "CPU",
        "vram_gb": 0,
        "batch_size": 8,
        "workers": 0,
    }

    if torch.cuda.is_available():
        idx = torch.cuda.current_device()
        name = torch.cuda.get_device_name(idx)
        total_mem = torch.cuda.get_device_properties(idx).total_memory
        vram_gb = total_mem / (1024 ** 3)

        info["device"] = "cuda:0"
        info["gpu_name"] = name
        info["vram_gb"] = vram_gb
        info["workers"] = min(8, os.cpu_count() or 4)

        if vram_gb >= 24:
            info["batch_size"] = 128
        elif vram_gb >= 16:
            info["batch_size"] = 64
        elif vram_gb >= 8:
            info["batch_size"] = 32
        else:
            info["batch_size"] = 16

    elif torch.backends.mps.is_available():
        info["device"] = "mps"
        info["gpu_name"] = "Apple MPS"
        info["batch_size"] = 32
        info["workers"] = min(4, os.cpu_count() or 4)
    else:
        info["gpu_name"] = "CPU (警告: 训练会很慢)"
        info["batch_size"] = 8

    return info


def check_dataset() -> bool:
    """检查数据集是否就绪"""
    if not DATA_YAML.exists():
        print(f"[!] 数据集 data.yaml 不存在: {DATA_YAML}")
        print(f"   请先运行: python download_dfire.py")
        return False
    return True


def train(args, gpu_info: dict) -> None:
    """执行训练"""
    from ultralytics import YOLO

    last_pt = OUTPUT_DIR / "weights" / "last.pt"

    # 判断是续训练还是全新训练
    if last_pt.exists() and not args.fresh:
        print(f"\n{'='*60}")
        print(f"检测到断点文件: {last_pt}")
        print(f"将从断点继续训练...")
        print(f"{'='*60}")
        model = YOLO(str(last_pt))
        resume = True
    elif last_pt.exists() and args.fresh:
        print(f"\n[--fresh] 强制全新训练，忽略已有断点")
        resume = False
        pretrained = PROJECT_ROOT / "output" / "yolo11n.pt"
        if pretrained.exists():
            model = YOLO(str(pretrained))
            print(f"  使用本地预训练权重: {pretrained}")
        else:
            model = YOLO("yolo11n.pt")
            print("  自动下载 yolo11n.pt 预训练权重...")
    else:
        print(f"\n{'='*60}")
        print(f"全新训练")
        print(f"{'='*60}")
        resume = False
        pretrained = PROJECT_ROOT / "output" / "yolo11n.pt"
        if pretrained.exists():
            model = YOLO(str(pretrained))
            print(f"  使用本地预训练权重: {pretrained}")
        else:
            model = YOLO("yolo11n.pt")
            print("  自动下载 yolo11n.pt 预训练权重...")

    batch = args.batch or gpu_info["batch_size"]
    imgsz = args.imgsz or 640
    epochs = args.epochs or 200
    device = args.device or gpu_info["device"]
    workers = gpu_info["workers"]
    cache = args.cache or "disk"

    # 打印训练配置
    print(f"\n训练配置:")
    print(f"  GPU:        {gpu_info['gpu_name']} ({gpu_info['vram_gb']:.1f} GB)")
    print(f"  设备:       {device}")
    print(f"  数据集:     {DATA_YAML}")
    print(f"  epochs:     {epochs}")
    print(f"  imgsz:      {imgsz}")
    print(f"  batch:      {batch}")
    print(f"  workers:    {workers}")
    print(f"  cache:      {cache}")
    print(f"  输出目录:   {OUTPUT_DIR}")
    print(f"  续训练:     {'是' if resume else '否'}")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if resume:
        results = model.train(
            data=str(DATA_YAML),
            resume=True,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device=device,
            workers=workers,
            exist_ok=True,
        )
    else:
        results = model.train(
            data=str(DATA_YAML),
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device=device,
            workers=workers,
            project=str(OUTPUT_DIR.parent),
            name="dfire_train",
            exist_ok=True,
            pretrained=True,
            optimizer="AdamW",
            lr0=0.001,
            lrf=0.01,
            momentum=0.937,
            weight_decay=5e-4,
            warmup_epochs=3,
            cos_lr=True,
            close_mosaic=15,
            cache=cache,
            # 数据增强
            augment=True,
            hsv_h=0.015,
            hsv_s=0.7,
            hsv_v=0.4,
            degrees=10.0,
            translate=0.1,
            scale=0.5,
            shear=2.0,
            perspective=0.0,
            flipud=0.0,
            fliplr=0.5,
            mosaic=1.0,
            mixup=0.1,
            copy_paste=0.1,
            # 验证与保存
            val=True,
            save=True,
            save_period=10,
            # 早停
            patience=50,
        )

    # 训练后评估
    print(f"\n{'='*60}")
    print(f"验证集评估")
    print(f"{'='*60}")
    metrics = model.val()
    print(f"mAP@50:       {metrics.box.map50:.4f}")
    print(f"mAP@50-95:    {metrics.box.map:.4f}")
    print(f"Recall:       {metrics.box.mr:.4f}")
    print(f"Precision:    {metrics.box.mp:.4f}")

    # 导出 ONNX
    print(f"\n{'='*60}")
    print(f"导出 ONNX")
    print(f"{'='*60}")
    onnx_path = model.export(format="onnx", imgsz=imgsz, half=False, simplify=True)
    print(f"ONNX 模型: {onnx_path}")

    # 汇总输出
    print(f"\n{'='*60}")
    print(f"训练完成!")
    print(f"{'='*60}")
    print(f"最佳模型:  {OUTPUT_DIR / 'weights' / 'best.pt'}")
    print(f"断点文件:  {OUTPUT_DIR / 'weights' / 'last.pt'}")
    print(f"ONNX 模型: {OUTPUT_DIR / 'weights' / 'best.onnx'}")
    print(f"\n可用该模型替换当前模型进行检测:")
    print(f"  python edge/video_detect.py --model {OUTPUT_DIR / 'weights' / 'best.pt'}")


def main():
    parser = argparse.ArgumentParser(
        description="D-Fire 数据集 YOLO11 训练 (GPU 优化)"
    )
    parser.add_argument("--fresh", action="store_true",
                        help="强制全新训练 (忽略已有断点)")
    parser.add_argument("--epochs", type=int, default=None,
                        help="训练轮数 (默认: 200)")
    parser.add_argument("--batch", type=int, default=None,
                        help="batch size (默认: 自动检测)")
    parser.add_argument("--imgsz", type=int, default=None,
                        help="输入尺寸 (默认: 640)")
    parser.add_argument("--device", type=str, default=None,
                        help="设备 (默认: 自动检测, 可指定 cpu/cuda:0/mps)")
    parser.add_argument("--cache", type=str, default=None,
                        choices=["ram", "disk"],
                        help="缓存模式 (默认: disk)")

    args = parser.parse_args()

    print("=" * 60)
    print("D-Fire YOLO11 训练脚本")
    print("=" * 60)

    # 1. 检查数据集
    if not check_dataset():
        sys.exit(1)

    # 2. 检测 GPU
    gpu_info = detect_gpu()
    print(f"\n检测到设备: {gpu_info['gpu_name']}")
    if gpu_info["vram_gb"] > 0:
        print(f"显存: {gpu_info['vram_gb']:.1f} GB")
    print(f"自动选择 batch_size = {gpu_info['batch_size']}")

    # 3. 训练
    train(args, gpu_info)


if __name__ == "__main__":
    main()
