"""
从7个测试视频中每5帧抽取1帧，供手动标注。
输出到 detection/data/manual_label/ 目录。
"""
import cv2
import os
from pathlib import Path

TEST_DIR = Path(r'D:/flame_project/detection/test')
OUT_DIR = Path(r'D:/flame_project/detection/data/manual_label')
OUT_DIR.mkdir(parents=True, exist_ok=True)

for vp in sorted(TEST_DIR.glob('VP*.mp4')):
    cap = cv2.VideoCapture(str(vp))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    name = vp.stem  # VP6, VP18, etc.

    saved = 0
    for i in range(total):
        ret, frame = cap.read()
        if not ret:
            break
        # 每5帧抽1帧，避免太多重复
        if i % 5 == 0:
            out_path = OUT_DIR / f'{name}_frame{i:04d}.jpg'
            cv2.imwrite(str(out_path), frame)
            saved += 1

    cap.release()
    print(f'{name}.mp4: {total}帧 → 抽取{saved}帧')

total_frames = len(list(OUT_DIR.glob('*.jpg')))
print(f'\n共抽取 {total_frames} 帧，保存在 {OUT_DIR}')
print('请从中挑选 20-30 张有火焰/烟雾的帧进行标注')
