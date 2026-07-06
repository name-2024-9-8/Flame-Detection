"""
火焰检测 — 视频文件测试 (YOLO11)
===================================
用法:
  python test_video.py                             检测 test/VP47.mp4
  python test_video.py --video path/to/video.mp4   指定视频
  python test_video.py --save                      保存结果到 output/
  python test_video.py --no-display                不显示窗口 (配合 --save)

按键: Q 退出 | 空格 暂停/继续
"""
import time
import sys
import argparse
from pathlib import Path

import cv2
from ultralytics import YOLO

MODEL_PATH = "output/yolo_train_7videos/weights/best.pt"
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.5
DEFAULT_VIDEO = "test/VP47.mp4"
OUTPUT_DIR = Path("output")

CLASS_NAME = "fire_smoke"
CLASS_COLOR = (0, 165, 255)


def load_model(path):
    print(f"加载模型: {path}")
    model = YOLO(path)
    print("模型已加载\n")
    return model


def draw_detections(frame, results, elapsed_ms, fps):
    out = frame.copy()
    dets = []

    if len(results) > 0 and results[0].boxes is not None:
        for box in results[0].boxes:
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            conf = float(box.conf[0].item())
            dets.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "conf": conf})
            cv2.rectangle(out, (x1, y1), (x2, y2), CLASS_COLOR, 2)
            cv2.putText(out, f"{CLASS_NAME} {conf:.2f}",
                        (x1, max(y1 - 8, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, CLASS_COLOR, 2)

    h = out.shape[0]
    cv2.rectangle(out, (0, 0), (260, 72), (0, 0, 0), -1)
    cv2.putText(out, f"FPS: {fps:.1f}", (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.putText(out, f"infer: {elapsed_ms:.0f}ms", (8, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.putText(out, f"detections: {len(dets)}", (8, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (0, 0, 255) if dets else (0, 255, 0), 1)

    if dets:
        max_conf = max(d["conf"] for d in dets)
        cv2.rectangle(out, (0, 0), (out.shape[1], 6), (0, 0, 255), -1)
        cv2.putText(out, f"ALARM! x{len(dets)} max={max_conf:.2f}",
                    (out.shape[1] // 2 - 130, h - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    return out, dets


def process_video(model, video_path, save, display):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps_video = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"视频: {video_path}")
    print(f"分辨率: {width}x{height}  FPS: {fps_video:.1f}  总帧数: {total_frames}")
    print(f"置信度: {CONF_THRESHOLD}  NMS: {IOU_THRESHOLD}")
    print("Q 退出  空格 暂停/继续\n")

    writer = None
    if save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_name = Path(video_path).stem + "_detected.mp4"
        out_path = str(OUTPUT_DIR / out_name)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_path, fourcc, fps_video, (width, height))
        print(f"输出: {out_path}\n")

    idx = 0
    paused = False
    infer_times = []
    total_det = 0
    fire_frames = 0

    while True:
        if not paused:
            ret, frame = cap.read()
            if not ret:
                break
            idx += 1

            t0 = time.perf_counter()
            results = model(frame, conf=CONF_THRESHOLD, iou=IOU_THRESHOLD, verbose=False)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            infer_times.append(elapsed_ms)

            recent = infer_times[-10:]
            fps = 1000 / (sum(recent) / len(recent))

            annotated, dets = draw_detections(frame, results, elapsed_ms, fps)

            if dets:
                fire_frames += 1
                total_det += len(dets)

            pct = idx / total_frames * 100
            bar = "=" * int(pct / 5) + ">" + " " * (20 - int(pct / 5))
            sys.stdout.write(
                f"\r[{bar}] {idx}/{total_frames} ({pct:.0f}%)  "
                f"infer: {elapsed_ms:.0f}ms  det: {len(dets)}  "
            )
            sys.stdout.flush()

            if writer:
                writer.write(annotated)

        if display:
            cv2.imshow("Flame Detection - Video", annotated)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord(" "):
                paused = not paused
                print("\n[暂停]" if paused else "\n[继续]")

    cap.release()
    if writer:
        writer.release()
    if display:
        cv2.destroyAllWindows()

    print(f"\n\n{'='*50}")
    print(f"检测完毕")
    print(f"{'='*50}")
    print(f"处理帧数:       {idx}")
    print(f"火焰帧:         {fire_frames} ({fire_frames/max(idx,1)*100:.1f}%)")
    print(f"总检测次数:     {total_det}")
    if infer_times:
        avg_ms = sum(infer_times) / len(infer_times)
        print(f"平均推理时延:   {avg_ms:.1f}ms ({1000/avg_ms:.1f} FPS)")
        print(f"最快/最慢:      {min(infer_times):.1f}ms / {max(infer_times):.1f}ms")
    if save:
        print(f"结果视频:       {out_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="火焰检测 — 视频文件测试")
    parser.add_argument("--video", type=str, default=DEFAULT_VIDEO,
                        help=f"视频路径 (默认: {DEFAULT_VIDEO})")
    parser.add_argument("--save", action="store_true",
                        help="保存检测结果视频到 output/")
    parser.add_argument("--no-display", action="store_true",
                        help="不显示窗口 (配合 --save 使用)")
    parser.add_argument("--model", type=str, default=MODEL_PATH,
                        help=f"模型路径 (默认: {MODEL_PATH})")
    parser.add_argument("--conf", type=float, default=CONF_THRESHOLD,
                        help=f"置信度阈值 (默认: {CONF_THRESHOLD})")
    return parser.parse_args()


def main():
    args = parse_args()

    global CONF_THRESHOLD
    CONF_THRESHOLD = args.conf

    if not Path(args.video).exists():
        print(f"视频文件不存在: {args.video}")
        sys.exit(1)

    model = load_model(args.model)
    process_video(model, args.video, args.save, not args.no_display)


if __name__ == "__main__":
    main()
