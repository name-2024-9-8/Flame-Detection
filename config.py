"""全局配置 - 火焰/烟尘检测 (YOLO11)"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
DATASET_DIR = DATA_DIR / "smoke_dataset"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_DIR = OUTPUT_DIR / "logs"

for d in [DATA_DIR, OUTPUT_DIR, LOG_DIR, DATASET_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ========== 数据配置 ==========
IMAGE_SIZE = 416
BATCH_SIZE = 8
NUM_WORKERS = 0

TRAIN_IMG_DIR = DATASET_DIR / "images/train"
VAL_IMG_DIR = DATASET_DIR / "images/val"
TRAIN_LABEL_DIR = DATASET_DIR / "labels/train"
VAL_LABEL_DIR = DATASET_DIR / "labels/val"

# ========== 模型配置 ==========
NUM_CLASSES = 1               # fire_smoke 单类, 与 data/smoke_dataset/data.yaml 一致

# ========== YOLO11 ==========
YOLO_MODEL_DIR = OUTPUT_DIR / "yolo_train" / "weights"
YOLO_BEST_PT = YOLO_MODEL_DIR / "best.pt"
YOLO_PRETRAINED_PT = OUTPUT_DIR / "yolo11n.pt"

# ========== 评估目标 ==========
TARGET_RECALL = 0.90
MAX_FALSE_POSITIVE_RATE = 0.05
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.5
