#!/usr/bin/env python3
"""
边缘端视频文件火焰检测
=======================
专为 Orange Pi 5 设计，不依赖摄像头，直接对视频文件逐帧检测。

用法:
  # 板端 NPU 推理 (推荐)
  python edge/video_detect.py --video test/VP47.mp4 --model output/export/smoke_detector_fp16.rknn

  # CPU ONNX 推理
  python edge/video_detect.py --video test/VP47.mp4 --model output/yolo_train_7videos/weights/best.onnx

  # PyTorch CPU 推理
  python edge/video_detect.py --video test/VP47.mp4 --model output/yolo_train_7videos/weights/best.pt

  # 保存结果 + 不显示窗口
  python edge/video_detect.py --video test/VP47.mp4 --save --no-display

后端自动检测: .rknn → NPU | .onnx → ONNX Runtime | .pt → PyTorch
按键: Q 退出 | 空格 暂停/继续
"""
from __future__ import annotations
import sys
import time
import argparse
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from edge.inference_engine import YOLOInferenceEngine
from edge.preprocessing import ImagePreprocessor, PreprocessConfig


class VideoDetector:
    """离线视频检测器"""

    def __init__(self, model_path: str, conf: float = 0.25,
                 iou: float = 0.5, img_size: int = 416):
        self.model_path = model_path
        self.conf = conf
        self.iou = iou
        self.img_size = img_size

        print(f"加载模型: {model_path}")
        self.engine = YOLOInferenceEngine(
            model_path=model_path,
            conf_threshold=conf,
            iou_threshold=iou,
            img_size=img_size,
        )
        backend = self.engine._backend
        print(f"推理后端: {backend.upper()}")

        self.preprocessor = ImagePreprocessor(PreprocessConfig(
            target_size=(img_size, img_size),
            enable_dehaze=False,
            enable_clahe=False,
        ))

    def detect(self, video_path: str, save: bool = False,
               display: bool = True, out_dir: str = "output"):
        """检测视频中的所有帧"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"无法打开视频: {video_path}")
            return

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_src = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"视频: {video_path}")
        print(f"分辨率: {w}x{h}  FPS: {fps_src:.1f}  帧数: {total}")
        print(f"阈值: conf={self.conf}  iou={self.iou}")
        print("Q 退出  空格 暂停\n")

        writer = None
        if save:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            out_name = Path(video_path).stem + "_edge_detected.mp4"
            out_path = str(Path(out_dir) / out_name)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(out_path, fourcc, fps_src, (w, h))
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

                # 预处理
                pp_frame = self.preprocessor.process(frame)

                # 推理
                t0 = time.perf_counter()
                outputs = self.engine.infer(pp_frame)
                detections = self.engine.postprocess_onnx(outputs, frame.shape[:2])
                elapsed_ms = (time.perf_counter() - t0) * 1000
                infer_times.append(elapsed_ms)

                # 计算瞬时 FPS
                recent = infer_times[-10:]
                fps = 1000 / (sum(recent) / max(len(recent), 1))

                # 标注
                annotated = self.engine.annotate_frame(frame, detections) if detections else frame.copy()

                # 叠加状态栏
                h_frame = annotated.shape[0]
                cv2.rectangle(annotated, (0, 0), (280, 72), (0, 0, 0), -1)
                cv2.putText(annotated, f"FPS: {fps:.1f}", (8, 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                cv2.putText(annotated, f"infer: {elapsed_ms:.0f}ms", (8, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                cv2.putText(annotated, f"det: {len(detections)}", (8, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (0, 0, 255) if detections else (0, 255, 0), 1)

                if detections:
                    fire_frames += 1
                    total_det += len(detections)
                    max_c = max(d.confidence for d in detections)
                    cv2.rectangle(annotated, (0, 0), (annotated.shape[1], 6), (0, 0, 255), -1)
                    cv2.putText(annotated, f"ALARM! x{len(detections)} max={max_c:.2f}",
                                (annotated.shape[1] // 2 - 130, h_frame - 16),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # 进度条
                pct = idx / total * 100
                bar = "=" * int(pct / 5) + ">" + " " * (20 - int(pct / 5))
                sys.stdout.write(
                    f"\r[{bar}] {idx}/{total} ({pct:.0f}%)  "
                    f"infer: {elapsed_ms:.0f}ms  det: {len(detections)}  "
                )
                sys.stdout.flush()

                if writer:
                    writer.write(annotated)

            if display:
                cv2.imshow("Edge Video Detect", annotated)
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

        # 汇总
        print(f"\n\n{'='*50}")
        print("检测完毕")
        print(f"{'='*50}")
        print(f"推理后端:       {self.engine._backend.upper()}")
        print(f"处理帧数:       {idx}")
        print(f"火焰帧:         {fire_frames} ({fire_frames/max(idx,1)*100:.1f}%)")
        print(f"总检测次数:     {total_det}")
        if infer_times:
            avg_ms = sum(infer_times) / len(infer_times)
            print(f"平均推理时延:   {avg_ms:.1f}ms ({1000/avg_ms:.1f} FPS)")
            print(f"最快/最慢:      {min(infer_times):.1f}ms / {max(infer_times):.1f}ms")
        if save:
            print(f"结果视频:       {out_path}")


def detect_backend(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".rknn":
        return "RKNN (NPU)"
    elif ext == ".onnx":
        return "ONNX Runtime (CPU)"
    elif ext == ".pt":
        return "PyTorch (CPU)"
    return f"Unknown ({ext})"


def parse_args():
    p = argparse.ArgumentParser(description="边缘端视频火焰检测")
    p.add_argument("--video", type=str, required=True, help="视频文件路径")
    p.add_argument("--model", type=str, required=True, help="模型路径 (.rknn / .onnx / .pt)")
    p.add_argument("--save", action="store_true", help="保存检测结果视频到 output/")
    p.add_argument("--no-display", action="store_true", help="不显示窗口")
    p.add_argument("--conf", type=float, default=0.25, help="置信度阈值 (默认0.25)")
    p.add_argument("--iou", type=float, default=0.5, help="NMS阈值 (默认0.5)")
    p.add_argument("--img-size", type=int, default=416, help="模型输入尺寸 (默认416)")
    p.add_argument("--out-dir", type=str, default="output", help="输出目录 (默认output)")
    return p.parse_args()


def main():
    args = parse_args()

    if not Path(args.video).exists():
        print(f"视频不存在: {args.video}")
        sys.exit(1)
    if not Path(args.model).exists():
        print(f"模型不存在: {args.model}")
        sys.exit(1)

    print("=" * 50)
    print(" 边缘端视频火焰检测")
    print("=" * 50)
    print(f" 目标后端: {detect_backend(args.model)}")
    print(f" 输入尺寸: {args.img_size}x{args.img_size}")
    print()

    detector = VideoDetector(
        model_path=args.model,
        conf=args.conf,
        iou=args.iou,
        img_size=args.img_size,
    )

    detector.detect(
        video_path=args.video,
        save=args.save,
        display=not args.no_display,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()
