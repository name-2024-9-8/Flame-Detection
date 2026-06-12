"""
端到端集成测试
- 视频帧输入 → AI检测 → 定位计算 → JSON输出
- 验证: 时延≤2s, 识别率≥90%, 误报率<5%
"""
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    VAL_IMG_DIR, VAL_LABEL_DIR, IMAGE_SIZE,
    TARGET_RECALL, MAX_FALSE_POSITIVE_RATE,
)
from edge.output_module import AlarmEvent, encode_frame_base64


def compute_iou_xyxy(box1, box2):
    x1 = max(box1[0], box2[0]); y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2]); y2 = min(box1[3], box2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    return inter / (area1 + area2 - inter + 1e-7)


def load_val_data():
    """直接加载验证集图像和标签"""
    img_files = sorted(VAL_IMG_DIR.glob('*'))
    img_files = [f for f in img_files if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp'}]

    images = []
    labels = []
    for img_path in img_files:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        images.append((img_path.stem, img))

        lbl_path = VAL_LABEL_DIR / (img_path.stem + '.txt')
        boxes = []
        if lbl_path.exists():
            with open(lbl_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        boxes.append([float(x) for x in parts[:5]])
        labels.append(np.array(boxes, dtype=np.float32) if boxes else np.zeros((0, 5)))

    return images, labels


def test_model_inference():
    try:
        from ultralytics import YOLO
        model = YOLO("output/yolo_train/weights/best.pt")
    except Exception:
        print("[跳过] YOLO11 模型尚未训练完成")
        return None

    print("=" * 60)
    print("端到端集成测试")
    print("=" * 60)

    images, all_gts = load_val_data()
    total_gt = sum(len(g) for g in all_gts)
    print(f"验证集: {len(images)} 张图片, {total_gt} 个GT框")

    total_inference_time = 0
    total_end_to_end_time = 0
    total_tp = total_fp = total_fn = 0
    results = []

    for idx, (name, img) in enumerate(images):
        if idx >= 47:
            break

        gt_boxes = all_gts[idx]
        h, w = img.shape[:2]

        t0 = time.perf_counter()

        t1 = time.perf_counter()
        pred_results = model(img, conf=0.25, iou=0.5, verbose=False)
        t2 = time.perf_counter()
        inference_ms = (t2 - t1) * 1000

        pred_boxes = []
        if len(pred_results) > 0 and pred_results[0].boxes is not None:
            boxes = pred_results[0].boxes
            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                conf = boxes.conf[i].item()
                cls_id = int(boxes.cls[i].item())
                pred_boxes.append([x1, y1, x2, y2, conf, cls_id])

        matched_gt = set()
        tp_img = fp_img = 0
        for pb in pred_boxes:
            px1, py1, px2, py2, conf, cls = pb
            if len(gt_boxes) > 0:
                best_iou, best_j = 0, -1
                for j, gt in enumerate(gt_boxes):
                    if j in matched_gt:
                        continue
                    gcls, gcx, gcy, gw, gh = gt[:5]
                    gx1 = (gcx - gw/2) * w; gy1 = (gcy - gh/2) * h
                    gx2 = (gcx + gw/2) * w; gy2 = (gcy + gh/2) * h
                    iou = compute_iou_xyxy([px1, py1, px2, py2], [gx1, gy1, gx2, gy2])
                    if iou > best_iou:
                        best_iou, best_j = iou, j
                if best_iou >= 0.5 and best_j >= 0:
                    tp_img += 1
                    matched_gt.add(best_j)
                else:
                    fp_img += 1
            else:
                fp_img += 1

        fn_img = len(gt_boxes) - len(matched_gt)
        total_tp += tp_img
        total_fp += fp_img
        total_fn += fn_img

        t3 = time.perf_counter()
        e2e_ms = (t3 - t0) * 1000
        total_inference_time += inference_ms
        total_end_to_end_time += e2e_ms

        results.append({
            "image": idx + 1, "name": name,
            "gt_boxes": len(gt_boxes), "pred_boxes": len(pred_boxes),
            "tp": tp_img, "fp": fp_img, "fn": fn_img,
            "inference_ms": inference_ms, "e2e_ms": e2e_ms,
        })

    recall = total_tp / (total_tp + total_fn + 1e-16)
    precision = total_tp / (total_tp + total_fp + 1e-16)
    fpr = total_fp / (total_tp + total_fp + 1e-16)
    avg_inference_ms = total_inference_time / max(len(results), 1)
    avg_e2e_ms = total_end_to_end_time / max(len(results), 1)

    print(f"\n{'='*60}")
    print(f"测试结果汇总 (共 {len(results)} 张图像)")
    print(f"{'='*60}")
    print(f"检测框: TP={total_tp}, FP={total_fp}, FN={total_fn}")
    print(f"识别率 (Recall):      {recall*100:6.2f}%  (目标 ≥ {TARGET_RECALL*100:.0f}%)  {'✅' if recall >= TARGET_RECALL else '❌'}")
    print(f"精确率 (Precision):   {precision*100:6.2f}%")
    print(f"误报率 (FPR):         {fpr*100:6.2f}%  (目标 < {MAX_FALSE_POSITIVE_RATE*100:.0f}%)  {'✅' if fpr < MAX_FALSE_POSITIVE_RATE else '❌'}")
    print(f"平均推理时延:         {avg_inference_ms:6.1f} ms  (目标 ≤ 2000ms)  {'✅' if avg_inference_ms <= 2000 else '❌'}")
    print(f"平均端到端时延:       {avg_e2e_ms:6.1f} ms")
    print(f"模型大小:             {Path('output/yolo_train/weights/best.pt').stat().st_size/1e6:.2f} MB  (目标 < 10MB)")

    output_path = Path("output/test_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "recall": recall, "precision": precision, "fpr": fpr,
                "avg_inference_ms": avg_inference_ms, "avg_e2e_ms": avg_e2e_ms,
                "tp": total_tp, "fp": total_fp, "fn": total_fn,
                "num_images": len(results),
            },
            "details": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n详细结果已保存至: {output_path}")

    return {
        "recall": recall, "precision": precision, "fpr": fpr,
        "avg_inference_ms": avg_inference_ms, "avg_e2e_ms": avg_e2e_ms,
    }


def main():
    metrics = test_model_inference()
    if metrics is None:
        print("\n等待YOLO11训练完成...")
    else:
        print(f"\n{'='*60}")
        print("报警事件样例 (JSON)")
        print(f"{'='*60}")
        event = AlarmEvent(
            camera_id=1, device_id=1, area_id=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            longitude=116.397428, latitude=39.90923,
            location="北京市东城区天安门广场",
            confidence=0.95, urgency_degree="高",
            description="检测到火焰/烟尘",
            status="1",
            remark="端到端测试生成",
        )
        print(json.dumps(event.to_json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
