"""
Organize CCTV Fire Smoke dataset into proper train/val split.
Fixes: data.yaml nc bug, creates train/val directories.
"""
import os, shutil, random
from pathlib import Path

BASE = Path(r'D:\火焰检测\combined_system\detection\data\smoke_dataset')
RAW = Path(r'D:\火焰检测\combined_system\detection\data\raw_dataset\CCTV_Fire_Smoke_Emergency_Detection_Dataset')

# Create directory structure
for sub in ['images/train', 'images/val', 'labels/train', 'labels/val']:
    (BASE / sub).mkdir(parents=True, exist_ok=True)

# Get all images
images = sorted(RAW.glob('images/*.png'))
random.seed(42)
random.shuffle(images)

# 80/20 split
split = int(len(images) * 0.8)
train_imgs = images[:split]
val_imgs = images[split:]

print(f'Total images: {len(images)}')
print(f'Train: {len(train_imgs)}, Val: {len(val_imgs)}')

# Copy files
class_dist = {'train': {}, 'val': {}}
for split_name, img_list in [('train', train_imgs), ('val', val_imgs)]:
    for img_path in img_list:
        # Copy image
        dst_img = BASE / f'images/{split_name}' / img_path.name
        shutil.copy2(img_path, dst_img)

        # Copy label if exists
        label_name = img_path.stem + '.txt'
        label_path = RAW / 'labels' / label_name
        dst_lbl = BASE / f'labels/{split_name}' / label_name
        if label_path.exists():
            shutil.copy2(label_path, dst_lbl)
            # Count classes
            with open(label_path) as f:
                for line in f:
                    if line.strip():
                        cls_id = line.split()[0]
                        class_dist[split_name][cls_id] = class_dist[split_name].get(cls_id, 0) + 1
        else:
            # Create empty label file
            dst_lbl.touch()

print(f'\nClass distribution:')
print(f'  Train: {class_dist["train"]}')
print(f'  Val: {class_dist["val"]}')

# Write correct data.yaml
yaml_content = f"""# CCTV Fire Smoke Emergency Detection Dataset
# Organized for YOLO11 training

path: {str(BASE)}
train: images/train
val: images/val

nc: 2
names:
  0: fire
  1: smoke
"""
with open(BASE / 'data.yaml', 'w') as f:
    f.write(yaml_content)
print(f'\ndata.yaml written to {BASE / "data.yaml"}')
print('Done!')
