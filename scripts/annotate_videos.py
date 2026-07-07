"""
批量视频检测 + 画框 + 提取关键帧
用已训练好的 YOLO11 模型对 static/videos/ 下的所有视频进行推理，
画出火焰/烟雾边界框，并提取检测帧作为预览图片。

输出:
  static/videos/annotated/VP*.mp4    — 带检测框的标注视频
  static/videos/frames/VP*.jpg       — 检测关键帧截图
"""
import sys
import cv2
import numpy as np
from pathlib import Path

# ── 路径 ──
MODEL_PATH = "D:/火焰检测/combined_system/detection/output/yolo_train_7videos/weights/best.pt"
VIDEO_DIR = Path("D:/火焰检测/combined_system/static/videos")
ANNOTATED_DIR = VIDEO_DIR / "annotated"
FRAMES_DIR = VIDEO_DIR / "frames"

ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.5

# 火焰/烟雾检测框颜色 (橙黄色)
BOX_COLOR = (0, 165, 255)       # BGR
TEXT_COLOR = (255, 255, 255)
ALARM_BAR_COLOR = (0, 0, 255)   # 红色警示条

# ── 加载模型 ──
print("加载 YOLO11 模型...")
from ultralytics import YOLO
model = YOLO(MODEL_PATH)
print("模型加载完成\n")


def annotate_frame(frame, results):
    """在帧上绘制检测框和信息"""
    annotated = frame.copy()
    dets = []
    h, w = annotated.shape[:2]

    if len(results) > 0 and results[0].boxes is not None:
        for box in results[0].boxes:
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            conf = float(box.conf[0].item())
            cls_id = int(box.cls[0].item()) if box.cls is not None else 0
            dets.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "conf": conf, "cls": cls_id})

            # 边界框
            cv2.rectangle(annotated, (x1, y1), (x2, y2), BOX_COLOR, 3)
            label = f"fire_smoke {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 6, y1), BOX_COLOR, -1)
            cv2.putText(annotated, label, (x1 + 3, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 2)

    # ── 顶部状态栏 ──
    overlay = annotated.copy()
    cv2.rectangle(overlay, (0, 0), (w, 44), (0, 0, 0), -1)
    annotated = cv2.addWeighted(overlay, 0.6, annotated, 0.4, 0)

    status_text = f"AI火焰识别预警  |  检测: {len(dets)} 处"
    cv2.putText(annotated, status_text, (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    # 如有检测 — 红色警示条
    if dets:
        max_conf = max(d["conf"] for d in dets)
        cv2.rectangle(annotated, (0, 0), (w, 5), ALARM_BAR_COLOR, -1)
        alarm_text = f"!!! 火情预警  (最高置信度: {max_conf:.0%}) !!!"
        (aw, ah), _ = cv2.getTextSize(alarm_text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        tx = (w - aw) // 2
        cv2.putText(annotated, alarm_text, (tx, h - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, ALARM_BAR_COLOR, 2)

    return annotated, dets


def process_video(video_path):
    """处理单个视频：检测画框 + 输出 + 提取关键帧"""
    name = video_path.stem
    print(f"\n{'='*55}")
    print(f"  处理: {video_path.name}")
    print(f"{'='*55}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  [错误] 无法打开视频")
        return None, None

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"  分辨率: {width}x{height}  帧率: {fps:.1f}  总帧: {total}")

    # VideoWriter
    out_path = str(ANNOTATED_DIR / video_path.name)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    best_frame = None
    best_conf = 0
    idx = 0
    fire_frames = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        idx += 1

        results = model(frame, conf=CONF_THRESHOLD, iou=IOU_THRESHOLD, verbose=False)
        annotated, dets = annotate_frame(frame, results)
        writer.write(annotated)

        if dets:
            fire_frames += 1
            max_conf = max(d["conf"] for d in dets)
            if max_conf > best_conf:
                best_conf = max_conf
                # 保存检测帧（带框）
                best_frame = annotated.copy()

        # 进度
        pct = idx / total * 100
        bar = "█" * int(pct / 5) + "▒" * (20 - int(pct / 5))
        sys.stdout.write(f"\r  [{bar}] {idx}/{total} ({pct:.0f}%)  检测: {len(dets)}")
        sys.stdout.flush()

    cap.release()
    writer.release()

    print(f"\n  火焰帧: {fire_frames}/{idx} ({fire_frames/max(idx,1)*100:.1f}%)")
    print(f"  最高置信度: {best_conf:.2%}")
    print(f"  输出: {out_path}")

    # 提取关键帧
    frame_path = None
    if best_frame is not None:
        frame_path = str(FRAMES_DIR / f"{name}.jpg")
        cv2.imwrite(frame_path, best_frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"  关键帧: {frame_path}")
    else:
        # 没有检测到 — 取中间帧
        print(f"  [提示] 未检测到目标，截取中间帧作为占位")
        cap2 = cv2.VideoCapture(str(video_path))
        mid_frame_num = total // 2
        cap2.set(cv2.CAP_PROP_POS_FRAMES, mid_frame_num)
        ret, placeholder = cap2.read()
        cap2.release()
        if ret:
            frame_path = str(FRAMES_DIR / f"{name}.jpg")
            cv2.imwrite(frame_path, placeholder, [cv2.IMWRITE_JPEG_QUALITY, 85])
            print(f"  占位帧: {frame_path}")

    return out_path, frame_path


def main():
    videos = sorted(VIDEO_DIR.glob("VP*.mp4"))
    if not videos:
        print("未找到 VP*.mp4 视频文件")
        return

    print(f"找到 {len(videos)} 个视频，开始批量检测...\n")

    for vp in videos:
        if vp.name.startswith("."):
            continue
        process_video(vp)

    print(f"\n{'='*55}")
    print(f"  全部处理完成!")
    print(f"  标注视频: {ANNOTATED_DIR}")
    print(f"  关键帧:   {FRAMES_DIR}")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
