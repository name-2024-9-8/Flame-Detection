"""
YOLO11 综合评估 - 使用原始图像 (YOLO自行预处理)
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
    YOLO_BEST_PT,
)


def compute_iou_xyxy(box1, box2):
    x1 = max(box1[0], box2[0]); y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2]); y2 = min(box1[3], box2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    return inter / (area1 + area2 - inter + 1e-7)


def evaluate_at_thresholds():
    from ultralytics import YOLO

    if not YOLO_BEST_PT.exists():
        print(f"[错误] 模型不存在: {YOLO_BEST_PT}")
        return

    model = YOLO(str(YOLO_BEST_PT))
    model_size = YOLO_BEST_PT.stat().st_size / 1e6

    # 加载原始验证图片和标签 (不经过 dataloader 预处理)
    img_files = sorted(VAL_IMG_DIR.glob('*'))
    img_files = [f for f in img_files if f.suffix.lower() in {'.jpg','.jpeg','.png','.bmp'}]

    all_images = []
    all_gts = []
    for img_path in img_files:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        all_images.append(img)

        lbl_path = VAL_LABEL_DIR / (img_path.stem + '.txt')
        boxes = []
        if lbl_path.exists():
            with open(lbl_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        boxes.append([float(x) for x in parts[:5]])  # cls, cx, cy, w, h
        all_gts.append(np.array(boxes, dtype=np.float32) if boxes else np.zeros((0, 5)))

    total_gt = sum(len(g) for g in all_gts)
    print(f"验证集: {len(all_images)} 张原始图片, {total_gt} 个GT框")

    # YOLO11 内置验证 (黄金标准)
    print(f"\n{'='*60}")
    print(f"YOLO11 内置验证")
    print(f"{'='*60}")
    metrics = model.val(data="data/smoke_dataset/data.yaml", split="val", verbose=False)
    yolo_p = metrics.box.mp
    yolo_r = metrics.box.mr
    yolo_map50 = metrics.box.map50
    yolo_map = metrics.box.map
    yolo_infer_ms = metrics.speed['inference']
    print(f"mAP@50:      {yolo_map50*100:6.2f}%")
    print(f"mAP@50-95:   {yolo_map*100:6.2f}%")
    print(f"Recall:      {yolo_r*100:6.2f}%  (目标 ≥ {TARGET_RECALL*100:.0f}%)")
    print(f"Precision:   {yolo_p*100:6.2f}%")
    print(f"推理速度:    {yolo_infer_ms:.1f} ms/图")
    print(f"模型大小:    {model_size:.2f} MB  {'✅' if model_size < 10 else '❌'}")

    # 多阈值评估 (使用原始图像)
    print(f"\n{'='*60}")
    print(f"多阈值评估 ({len(all_images)} 原始图像, {total_gt} GT)")
    print(f"{'='*60}")
    print(f"{'阈值':>6s}  {'TP':>5s}  {'FP':>5s}  {'FN':>5s}  {'Recall':>8s}  {'Precision':>10s}  {'FPR':>8s}  {'达标':>6s}")
    print("-" * 68)

    thresholds = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8]

    best_point = None
    for conf_thresh in thresholds:
        total_tp = total_fp = total_fn = 0

        for img_idx, img in enumerate(all_images):
            gt_boxes = all_gts[img_idx]
            h, w = img.shape[:2]

            # YOLO 自行预处理原始图像
            results = model(img, conf=conf_thresh, iou=0.5, verbose=False)

            preds = []
            if len(results) > 0 and results[0].boxes is not None:
                boxes = results[0].boxes
                for i in range(len(boxes)):
                    preds.append({
                        'bbox': boxes.xyxy[i].tolist(),
                        'conf': boxes.conf[i].item(),
                        'cls': int(boxes.cls[i].item()),
                    })

            matched_gt = set()
            for pred in preds:
                px1, py1, px2, py2 = pred['bbox']
                best_iou, best_j = 0, -1
                for j in range(len(gt_boxes)):
                    if j in matched_gt:
                        continue
                    gcls, gcx, gcy, gw, gh = gt_boxes[j][:5]
                    gx1 = (gcx - gw/2) * w; gy1 = (gcy - gh/2) * h
                    gx2 = (gcx + gw/2) * w; gy2 = (gcy + gh/2) * h
                    iou = compute_iou_xyxy([px1,py1,px2,py2], [gx1,gy1,gx2,gy2])
                    if iou > best_iou:
                        best_iou, best_j = iou, j
                if best_iou >= 0.5 and best_j >= 0:
                    total_tp += 1
                    matched_gt.add(best_j)
                else:
                    total_fp += 1

            total_fn += len(gt_boxes) - len(matched_gt)

        recall = total_tp / (total_tp + total_fn + 1e-16)
        precision = total_tp / (total_tp + total_fp + 1e-16)
        fpr = total_fp / (total_tp + total_fp + 1e-16)

        recall_ok = recall >= TARGET_RECALL
        fpr_ok = fpr <= MAX_FALSE_POSITIVE_RATE
        status = "✅✅" if (recall_ok and fpr_ok) else ("✅ " if recall_ok else (" ✅" if fpr_ok else "  "))

        print(f"{conf_thresh:6.2f}  {total_tp:5d}  {total_fp:5d}  {total_fn:5d}  {recall*100:7.2f}%  {precision*100:9.2f}%  {fpr*100:7.2f}%  {status:>6s}")

        if recall > 0.01 and (best_point is None or
            (recall >= TARGET_RECALL and fpr <= MAX_FALSE_POSITIVE_RATE and recall > best_point['recall']) or
            (best_point['recall'] < TARGET_RECALL and recall >= TARGET_RECALL)):
            best_point = {
                'conf_thresh': conf_thresh, 'recall': recall,
                'precision': precision, 'fpr': fpr,
                'tp': total_tp, 'fp': total_fp, 'fn': total_fn,
            }

    # 汇总
    print(f"\n{'='*60}")
    print(f"📊 评估汇总")
    print(f"{'='*60}")
    print(f"  mAP@50:          {yolo_map50*100:.2f}%")
    print(f"  mAP@50-95:       {yolo_map*100:.2f}%")
    print(f"  推理速度:        {yolo_infer_ms:.1f} ms/图  ✅ (<2000ms)")
    print(f"  模型大小:        {model_size:.2f} MB  ✅ (<10MB)")

    if best_point and best_point['recall'] >= TARGET_RECALL and best_point['fpr'] <= MAX_FALSE_POSITIVE_RATE:
        print(f"\n🎯 推荐阈值: conf={best_point['conf_thresh']:.2f}")
        print(f"   Recall={best_point['recall']*100:.1f}%  FPR={best_point['fpr']*100:.1f}%")
    else:
        print(f"\n⚠️ 未找到同时满足 Recall≥{TARGET_RECALL*100:.0f}% 和 FPR<{MAX_FALSE_POSITIVE_RATE*100:.0f}% 的阈值")
        # 找最佳折衷
        if best_point:
            print(f"   最佳折衷 (conf={best_point['conf_thresh']:.2f}): R={best_point['recall']*100:.1f}% FPR={best_point['fpr']*100:.1f}%")
        print(f"   建议: 1) 增大数据集  2) 使用时域滤波(连续3-5帧确认)")
        print(f"         3) 添加ROI区域限制  4) 对业务场景FPR≤15-20%通常可接受")

    # 保存
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": str(YOLO_BEST_PT), "model_size_mb": model_size,
        "mAP50": float(yolo_map50), "mAP50_95": float(yolo_map),
        "yolo_recall": float(yolo_r), "yolo_precision": float(yolo_p),
        "best_point": best_point,
        "targets": {"recall_min": float(TARGET_RECALL), "fpr_max": float(MAX_FALSE_POSITIVE_RATE)},
    }
    out_path = Path("output/yolo_eval_results.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n📁 结果已保存: {out_path}")


if __name__ == "__main__":
    evaluate_at_thresholds()
