"""使用 YOLO11-nano 预训练权重进行火焰/烟尘检测迁移学习"""
from ultralytics import YOLO
from pathlib import Path

DATA_YAML = Path(__file__).parent / "data" / "smoke_dataset" / "data.yaml"
OUTPUT_DIR = Path(__file__).parent / "output" / "yolo_train"

def main():
    # 加载 YOLO11-nano 预训练模型 (~2.6M params, ~5.5MB)
    model = YOLO("output/yolo11n.pt")

    results = model.train(
        data=str(DATA_YAML),
        epochs=200,
        imgsz=416,           # 匹配项目配置
        batch=8,
        device="cpu",
        workers=0,
        project=str(OUTPUT_DIR.parent),
        name="yolo_train",
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
        # 验证指标
        val=True,
        save=True,
        save_period=20,
        # 早停
        patience=50,
    )

    # 评估最终模型
    print("\n========== 验证集评估 ==========")
    metrics = model.val()
    print(f"mAP@50:       {metrics.box.map50:.4f}")
    print(f"mAP@50-95:    {metrics.box.map:.4f}")
    print(f"Recall:       {metrics.box.mr:.4f}")
    print(f"Precision:    {metrics.box.mp:.4f}")

    # 导出 ONNX
    print("\n========== 导出 ONNX ==========")
    model.export(format="onnx", imgsz=416, half=False, simplify=True)

if __name__ == "__main__":
    main()
