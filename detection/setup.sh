#!/bin/bash
# ==============================================
# 火焰检测 — 香橙派一键部署脚本
# ==============================================
# 用法:
#   bash setup.sh              # 完整部署
#   bash setup.sh --check      # 仅检查系统状态
#   bash setup.sh --service    # 额外配置开机自启
# ==============================================
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERR]${NC} $1"; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="flame-edge"
SETUP_SERVICE=false

for arg in "$@"; do
    case $arg in
        --check) MODE="check" ;;
        --service) SETUP_SERVICE=true ;;
        -h|--help)
            echo "用法: bash setup.sh [--check] [--service]"
            exit 0 ;;
    esac
done

echo ""
echo "=========================================="
echo " 火焰检测 — 香橙派一键部署"
echo " 项目目录: $PROJECT_DIR"
echo "=========================================="

# ========== 1. 系统检查 ==========
echo ""
echo "[1/5] 检查系统状态..."

echo -n "  设备型号: "; tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo "未知"
echo -n "  架构:     "; uname -m
echo -n "  内存:     "; free -h | awk '/Mem:/{print $2}'
echo -n "  存储:     "; df -h / | awk 'NR==2{print $4 " 可用 / " $2 " 总计"}'
echo -n "  Python:   "; python3 --version 2>/dev/null || { err "请先安装 python3"; exit 1; }
echo -n "  pip:      "; pip3 --version 2>/dev/null || info "将通过 apt 安装"

[ "$MODE" = "check" ] && exit 0

# ========== 2. 系统依赖 ==========
echo ""
echo "[2/5] 安装系统依赖..."

sudo apt update -qq

sudo apt install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    git curl rsync \
    libopencv-dev python3-opencv \
    libjpeg-dev libpng-dev \
    libavcodec-dev libavformat-dev libswscale-dev \
    net-tools vim 2>&1 | tail -1

sudo timedatectl set-timezone Asia/Shanghai 2>/dev/null || true
info "系统依赖完成"

# ========== 3. Python 环境 ==========
echo ""
echo "[3/5] 配置 Python 虚拟环境..."

if [ ! -d "$PROJECT_DIR/.venv" ]; then
    python3 -m venv "$PROJECT_DIR/.venv"
    info "虚拟环境已创建"
else
    info "虚拟环境已存在"
fi

source "$PROJECT_DIR/.venv/bin/activate"
pip install --upgrade pip setuptools wheel -q

pip install -q \
    numpy opencv-python-headless pillow requests onnxruntime tqdm

info "Python 依赖安装完成"
deactivate

# ========== 4. 配置文件 ==========
echo ""
echo "[4/5] 检查配置文件..."

if [ ! -f "$PROJECT_DIR/edge_config.json" ]; then
    if [ -f "$PROJECT_DIR/edge_config.template.json" ]; then
        cp "$PROJECT_DIR/edge_config.template.json" "$PROJECT_DIR/edge_config.json"
        info "已从模板创建 edge_config.json"
    else
        warn "未找到 edge_config.template.json，请手动创建 edge_config.json"
    fi
else
    info "edge_config.json 已存在"
fi

# 创建必要目录
mkdir -p "$PROJECT_DIR"/{output/{clips,export,logs},data/camera_calib}

# ========== 5. 测试运行 ==========
echo ""
echo "[5/5] 测试运行..."

source "$PROJECT_DIR/.venv/bin/activate"

# 检查模型
MODEL_PATH=""
for m in "$PROJECT_DIR/output/export/smoke_detector_fp16.rknn" \
         "$PROJECT_DIR/output/yolo_train_7videos/weights/best.onnx" \
         "$PROJECT_DIR/output/best.onnx"; do
    if [ -f "$m" ]; then
        MODEL_PATH="$m"
        break
    fi
done

if [ -z "$MODEL_PATH" ]; then
    warn "未找到模型文件，请将 .onnx 或 .rknn 模型放入 output/ 目录"
else
    info "模型: $(basename $MODEL_PATH)"
fi

# 快速验证
python3 -c "
import cv2, numpy as np
print('OpenCV:', cv2.__version__)
try:
    import onnxruntime
    print('ONNX Runtime:', onnxruntime.__version__)
except: print('ONNX Runtime: 未安装')
print('环境验证通过')
"

deactivate

# ========== systemd 服务 ==========
if [ "$SETUP_SERVICE" = true ]; then
    echo ""
    echo "配置 systemd 自启动服务..."

    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Flame Detection Edge Pipeline
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${PROJECT_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=${PROJECT_DIR}/.venv/bin/python edge/run.py
Restart=always
RestartSec=10
StandardOutput=append:${PROJECT_DIR}/logs/edge.log
StandardError=append:${PROJECT_DIR}/logs/edge_error.log

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    info "服务已创建"
    echo ""
    echo "  启动服务: sudo systemctl enable --now ${SERVICE_NAME}"
    echo "  查看状态: sudo systemctl status ${SERVICE_NAME}"
    echo "  查看日志: tail -f ${PROJECT_DIR}/logs/edge.log"
fi

# ========== 完成 ==========
echo ""
echo "=========================================="
echo " 部署完成!"
echo "=========================================="
echo ""
echo "后续步骤:"
echo ""
echo "  1. 编辑配置:  vim $PROJECT_DIR/edge_config.json"
echo "  2. 放入模型:  scp best.onnx orangepi@<IP>:$PROJECT_DIR/output/"
echo ""
echo "  3. 视频检测:"
echo "     cd $PROJECT_DIR && source .venv/bin/activate"
echo "     python edge/flame_alarm.py --video test/VP47.mp4 --model output/best.onnx --save"
echo ""
echo "  4. 视频检测 + 推送:"
echo "     python edge/flame_alarm.py --video test/VP47.mp4 --model output/best.onnx --server http://服务器IP:8080"
echo ""
