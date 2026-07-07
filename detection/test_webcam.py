"""
火焰检测 — 实时摄像头 / 图片文件测试 (OpenCV DNN + ONNX)
==========================================================
用法:
  python test_webcam.py                       摄像头实时检测
  python test_webcam.py --image test.jpg      单张图片检测
  python test_webcam.py --image data/val/     批量图片检测 (目录)
  python test_webcam.py test.jpg              可直接拖图片到命令行

按 Q 键退出摄像头模式，任意键切换下一张 (图片模式)
"""
import cv2
import numpy as np
import time
import sys
from pathlib import Path

MODEL_PATH = "output/yolo_train/weights/best.onnx"
IMG_SIZE = 416
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.5
CLASS_NAME = "火/烟"      # 模型1类合并(fire_smoke)，推理时拆分不可靠
CLASS_COLOR = (0, 165, 255)  # 橙色


# ============================================================
#  推理核心
# ============================================================

def load_model(path):
    print(f"加载 ONNX 模型: {path}")
    net = cv2.dnn.readNetFromONNX(str(path))
    print("模型已加载 (OpenCV DNN 后端)\n")
    return net


def infer(net, frame):
    """单帧推理, 返回检测框列表"""
    t0 = time.perf_counter()
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (IMG_SIZE, IMG_SIZE),
                                 (0, 0, 0), swapRB=True, crop=False)
    net.setInput(blob)
    output = net.forward()
    elapsed = (time.perf_counter() - t0) * 1000
    dets = _decode_output(output, frame.shape[1], frame.shape[0])
    return dets, elapsed


def _decode_output(output, fw, fh):
    """YOLO ONNX (1,5,3549) -> 检测框列表"""
    preds = output[0].T  # (3549, 5): [cx, cy, w, h, conf]
    mask = preds[:, 4] >= CONF_THRESHOLD
    preds = preds[mask]
    if len(preds) == 0:
        return []

    boxes, scores = [], []
    for cx, cy, w, h, conf in preds:
        x1 = (cx - w / 2) * fw / IMG_SIZE
        y1 = (cy - h / 2) * fh / IMG_SIZE
        x2 = (cx + w / 2) * fw / IMG_SIZE
        y2 = (cy + h / 2) * fh / IMG_SIZE
        boxes.append([float(x1), float(y1), float(x2 - x1), float(y2 - y1)])
        scores.append(float(conf))

    idxs = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESHOLD, IOU_THRESHOLD)
    if len(idxs) == 0:
        return []

    results = []
    for i in (idxs.flatten() if hasattr(idxs, 'flatten') else idxs):
        x, y, bw, bh = boxes[i]
        results.append({'x1': int(x), 'y1': int(y),
                        'x2': int(x + bw), 'y2': int(y + bh),
                        'conf': scores[i]})
    return results


# ============================================================
#  绘制
# ============================================================

def draw_detections(frame, dets, elapsed_ms=0):
    """在帧上绘制检测框和信息"""
    out = frame.copy()

    for d in dets:
        cv2.rectangle(out, (d['x1'], d['y1']), (d['x2'], d['y2']), CLASS_COLOR, 2)
        cv2.putText(out, f"{CLASS_NAME} {d['conf']:.2f}",
                    (d['x1'], max(d['y1'] - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, CLASS_COLOR, 2)

    # 左上角状态
    cv2.rectangle(out, (0, 0), (260, 52), (0, 0, 0), -1)
    cv2.putText(out, f"infer: {elapsed_ms:.0f}ms", (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.putText(out, f"detections: {len(dets)}", (8, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (0, 0, 255) if dets else (0, 255, 0), 1)

    # 检测到火焰, 顶部红色警告条
    if dets:
        max_conf = max(d['conf'] for d in dets)
        cv2.rectangle(out, (0, 0), (out.shape[1], 6), CLASS_COLOR, -1)
        cv2.putText(out, f"ALARM! x{len(dets)} max={max_conf:.2f}",
                    (out.shape[1] // 2 - 120, out.shape[0] - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    return out


# ============================================================
#  图片检测模式
# ============================================================

def detect_image(net, img_path):
    """检测单张图片"""
    frame = cv2.imread(str(img_path))
    if frame is None:
        print(f"无法读取图片: {img_path}")
        return

    dets, elapsed = infer(net, frame)
    annotated = draw_detections(frame, dets, elapsed)

    print(f"图片: {img_path}")
    if dets:
        for i, d in enumerate(dets):
            print(f"  [{i}] {CLASS_NAME} conf={d['conf']:.3f}  "
                  f"box=({d['x1']},{d['y1']})-({d['x2']},{d['y2']})")
    else:
        print(f"  未检测到{CLASS_NAME}")
    print(f"  推理时延: {elapsed:.0f}ms\n")

    cv2.imshow(f"Flame Detection - {Path(img_path).name}", annotated)
    cv2.waitKey(0)


def detect_images_batch(net, img_dir):
    """批量检测目录中的图片"""
    exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    files = sorted([f for f in Path(img_dir).iterdir()
                    if f.suffix.lower() in exts])
    if not files:
        print(f"目录中没有图片: {img_dir}")
        return

    print(f"批量检测 {len(files)} 张图片 (按任意键切换, Q 退出)\n")

    times = []
    for f in files:
        frame = cv2.imread(str(f))
        if frame is None:
            continue

        dets, elapsed = infer(net, frame)
        times.append(elapsed)
        annotated = draw_detections(frame, dets, elapsed)

        print(f"{f.name}: {len(dets)} 个目标, {elapsed:.0f}ms")
        cv2.imshow("Flame Detection - Image", annotated)
        key = cv2.waitKey(0) & 0xFF
        if key == ord('q'):
            break

    if times:
        print(f"\n平均推理时延: {sum(times)/len(times):.0f}ms "
              f"({1000/(sum(times)/len(times)):.1f} FPS)")
        print(f"处理: {len(times)} 张图片")


# ============================================================
#  摄像头检测模式
# ============================================================

def detect_webcam(net):
    """实时摄像头检测"""
    print("打开摄像头...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("未检测到摄像头")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"摄像头分辨率: {w}x{h}")
    print("开始检测 (按 Q 退出)\n")

    times = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        dets, elapsed = infer(net, frame)
        times.append(elapsed)
        annotated = draw_detections(frame, dets, elapsed)

        cv2.imshow("Flame Detection - Webcam", annotated)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    if times:
        avg = sum(times) / len(times)
        print(f"\n平均推理时延: {avg:.0f}ms ({1000/avg:.1f} FPS) "
              f"| 帧数: {len(times)}")


# ============================================================
#  入口
# ============================================================

def parse_args():
    # 支持 --image xxx 或直接传路径
    args = sys.argv[1:]
    image_path = None
    for i, a in enumerate(args):
        if a == '--image' and i + 1 < len(args):
            image_path = args[i + 1]
            break
        elif not a.startswith('--'):
            image_path = a
            break
    return image_path


def main():
    net = load_model(MODEL_PATH)

    image_path = parse_args()

    if image_path:
        p = Path(image_path)
        if p.is_dir():
            detect_images_batch(net, p)
        elif p.is_file():
            detect_image(net, p)
        else:
            print(f"路径不存在: {image_path}")
    else:
        detect_webcam(net)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
