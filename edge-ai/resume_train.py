"""恢复 YOLO11 训练 - 从 last.pt 断点继续"""
from ultralytics import YOLO
from pathlib import Path

LAST_PT = Path(__file__).parent / "output" / "yolo_train" / "weights" / "last.pt"
DATA_YAML = Path(__file__).parent / "data" / "smoke_dataset" / "data.yaml"


def main():
    if not LAST_PT.exists():
        print(f"[错误] 未找到断点文件: {LAST_PT}")
        print("如果是全新训练，请运行: python train_yolo.py")
        return

    print(f"从断点恢复训练: {LAST_PT}")
    model = YOLO(str(LAST_PT))

    model.train(
        data=str(DATA_YAML),
        resume=True,           # 关键：从 last.pt 恢复
        epochs=200,
        imgsz=416,
        batch=8,
        device="cpu",
        workers=0,
        exist_ok=True,
    )

    # 训练完成后评估
    print("\n========== 验证集评估 ==========")
    metrics = model.val()
    print(f"mAP@50:    {metrics.box.map50:.4f}")
    print(f"mAP@50-95: {metrics.box.map:.4f}")
    print(f"Recall:    {metrics.box.mr:.4f}")
    print(f"Precision: {metrics.box.mp:.4f}")


if __name__ == "__main__":
    main()
