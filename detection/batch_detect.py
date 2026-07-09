"""批量检测 — 生成带框标注视频"""
import sys
from pathlib import Path
import cv2
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).parent))

VIDEO_DIR = Path(__file__).parent / "test"
OUT_DIR = Path(__file__).parent / "output" / "detected"
OUT_DIR.mkdir(parents=True, exist_ok=True)

model = YOLO("output/dfire_train/weights/best.pt")

for vp in sorted(VIDEO_DIR.glob("VP*.mp4")):
    name = vp.stem
    print(f"{name}...", end=" ", flush=True)

    cap = cv2.VideoCapture(str(vp))
    w, h = int(cap.get(3)), int(cap.get(4))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    out = cv2.VideoWriter(str(OUT_DIR / f"{name}_detected.mp4"),
                          cv2.VideoWriter_fourcc(*"avc1"), fps, (w, h))

    for _ in range(total):
        ret, frame = cap.read()
        if not ret:
            break
        annotated = model(frame, verbose=False)[0].plot()
        out.write(annotated)

    cap.release()
    out.release()
    print(f"完成")

print(f"\n标注视频: {OUT_DIR}")
