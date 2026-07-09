#!/usr/bin/env python3
"""ONNX诊断 v3 — 匹配pipeline预处理 (letterbox)"""
import cv2, numpy as np, onnxruntime as ort, sys

model_path = sys.argv[1] if len(sys.argv) > 1 else "output/dfire_train/weights/best.onnx"
video_path = sys.argv[2] if len(sys.argv) > 2 else "../test/VP23.mp4"

print(f"cv2:{cv2.__version__}  ort:{ort.__version__}  np:{np.__version__}")

# 读帧
cap = cv2.VideoCapture(video_path)
ok, frame = cap.read()
cap.release()
h, w = frame.shape[:2]
print(f"帧: {w}x{h}")

# === pipeline 同款预处理: letterbox ===
target = 416
scale = min(target / w, target / h)
nw, nh = int(w * scale), int(h * scale)
resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
canvas = np.full((target, target, 3), 114, dtype=np.uint8)
dw, dh = (target - nw) // 2, (target - nh) // 2
canvas[dh:dh+nh, dw:dw+nw] = resized
print(f"letterbox: {nw}x{nh} -> 416x416  pad: left={dw} top={dh}")

img = canvas.astype(np.float32) / 255.0
tensor = np.transpose(img, (2, 0, 1))[None]

# 推理
m = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
out = m.run(None, {m.get_inputs()[0].name: tensor})
pred = out[0][0].transpose()
scores = pred[:, 4:]

print(f"\n预测: {len(pred)}个")
for i in range(2):
    col = scores[:, i]
    print(f"  类别{i} — max={col.max():.4f}  avg={col.mean():.4f}  >0.1:{int((col>0.1).sum())}  >0.2:{int((col>0.2).sum())}  >0.3:{int((col>0.3).sum())}")

# 前10个最高分
top = np.argsort(scores[:,0])[-10:][::-1]
print(f"\n类0 top10: {[f'{scores[i,0]:.4f}' for i in top]}")
