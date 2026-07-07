"""
Re-encode all annotated videos from mp4v (browser-incompatible) to WebM/VP8 (browser-native).
Browser support: Chrome, Firefox, Edge all support WebM VP8 natively.
"""
import cv2
import os
import glob
import shutil

VIDEO_DIR = r'D:\火焰检测\combined_system\static\videos'
ANNOTATED_DIR = os.path.join(VIDEO_DIR, 'annotated')
WEBM_DIR = os.path.join(VIDEO_DIR, 'webm')

os.makedirs(WEBM_DIR, exist_ok=True)

mp4_files = sorted(glob.glob(os.path.join(ANNOTATED_DIR, 'VP*.mp4')))
print(f'Found {len(mp4_files)} videos to re-encode\n')

for mp4_path in mp4_files:
    basename = os.path.splitext(os.path.basename(mp4_path))[0]  # e.g., VP18
    webm_path = os.path.join(WEBM_DIR, basename + '.webm')

    # Skip if already re-encoded and newer
    if os.path.exists(webm_path) and os.path.getmtime(webm_path) > os.path.getmtime(mp4_path):
        print(f'{basename}.webm: already exists (newer), skipping')
        continue

    cap = cv2.VideoCapture(mp4_path)
    if not cap.isOpened():
        print(f'{basename}: cannot open source')
        continue

    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*'VP80')
    writer = cv2.VideoWriter(webm_path, fourcc, fps, (w, h))

    if not writer.isOpened():
        print(f'{basename}: cannot create WebM writer')
        cap.release()
        continue

    frames_written = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        writer.write(frame)
        frames_written += 1

    cap.release()
    writer.release()

    orig_size = os.path.getsize(mp4_path)
    new_size = os.path.getsize(webm_path)
    print(f'{basename}: {total}frames {w}x{h} → {basename}.webm '
          f'({orig_size//1024}KB → {new_size//1024}KB)')

print(f'\nDone! {len(mp4_files)} videos re-encoded to WebM/VP8')
print(f'Output directory: {WEBM_DIR}')
