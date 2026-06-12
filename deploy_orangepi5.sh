#!/bin/bash
# ==============================================
# Orange Pi 5 (RK3588S) 火焰检测边缘端一键部署
# ==============================================
# 用法:
#   bash deploy_orangepi5.sh              # 完整部署
#   bash deploy_orangepi5.sh --check      # 仅检查系统状态
#   bash deploy_orangepi5.sh --npu-only   # 仅安装NPU驱动
#   bash deploy_orangepi5.sh --python-only # 仅配置Python环境
#   bash deploy_orangepi5.sh --service-only # 仅配置systemd服务
#
# 适用系统: Orange Pi 5 官方 Debian 12 / Ubuntu 22.04 / Armbian
# 需要网络连接用于下载依赖
# ==============================================
set -e

# ========== 默认配置 ==========
PROJECT_NAME="flame_detection"
PROJECT_DIR="/home/orangepi/${PROJECT_NAME}"
PYTHON_VER="python3"
RKNN_TOOLKIT_URL="https://github.com/airockchip/rknn-toolkit2.git"
RKNN_LITE_WHEEL="rknn_toolkit_lite2-2.3.0-cp311-cp311-linux_aarch64.whl"
MODE="full"

# ========== 颜色输出 ==========
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERR]${NC} $1"; }

# ========== 解析参数 ==========
for arg in "$@"; do
    case $arg in
        --check) MODE="check" ;;
        --npu-only) MODE="npu" ;;
        --python-only) MODE="python" ;;
        --service-only) MODE="service" ;;
        --project-dir) PROJECT_DIR="$2"; shift ;;
        -h|--help)
            echo "用法: bash deploy_orangepi5.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --check         仅检查系统状态"
            echo "  --npu-only      仅安装 NPU 驱动"
            echo "  --python-only   仅配置 Python 虚拟环境"
            echo "  --service-only  仅配置 systemd 服务"
            echo "  --project-dir   指定项目目录 (默认: /home/orangepi/flame_detection)"
            echo "  -h, --help      显示帮助"
            exit 0
            ;;
    esac
done


# ========== 1. 系统检查 ==========
check_system() {
    echo ""
    echo "=========================================="
    echo " Orange Pi 5 系统状态检查"
    echo "=========================================="

    echo -n "  设备型号: "
    if [ -f /proc/device-tree/model ]; then
        tr -d '\0' < /proc/device-tree/model
    else
        echo "未知 (非 Orange Pi 设备?)"
    fi

    echo -n "  架构:     "; uname -m
    echo -n "  内核:     "; uname -r
    echo -n "  内存:     "; free -h | awk '/Mem:/{print $2}'
    echo -n "  存储:     "; df -h / | awk 'NR==2{print $4 " 可用 / " $2 " 总计"}'
    echo -n "  Python:   "; $PYTHON_VER --version 2>/dev/null || echo "未安装"
    echo -n "  pip:      "; pip3 --version 2>/dev/null || echo "未安装"
    echo -n "  OpenCV:   "; $PYTHON_VER -c "import cv2; print(cv2.__version__)" 2>/dev/null || echo "未安装"
    echo -n "  NPU设备:  "
    if ls /dev/rknpu* 2>/dev/null; then
        info "检测到 NPU 设备"
    else
        warn "未检测到 /dev/rknpu* (需安装NPU驱动)"
    fi

    echo -n "  NPU驱动:  "
    if ldconfig -p 2>/dev/null | grep -q librknnrt; then
        info "librknnrt.so 已加载"
    else
        warn "librknnrt.so 未找到"
    fi

    echo -n "  NPU温度:  "
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        TEMP=$(awk '{printf "%.1f°C", $1/1000}' /sys/class/thermal/thermal_zone0/temp)
        echo "$TEMP"
    else
        echo "N/A"
    fi

    echo -n "  本机 IP:  "
    hostname -I 2>/dev/null | awk '{print $1}' || echo "N/A"

    echo ""
    echo "=========================================="
    [ "$MODE" = "check" ] && exit 0
}


# ========== 2. 系统依赖 ==========
install_system_deps() {
    echo ""
    echo "[2/6] 安装系统依赖..."

    sudo apt update -qq

    sudo apt install -y -qq \
        python3 python3-pip python3-venv python3-dev \
        git curl wget rsync \
        libopencv-dev python3-opencv \
        libjpeg-dev libpng-dev libtiff-dev \
        libavcodec-dev libavformat-dev libswscale-dev \
        libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
        i2c-tools lm-sensors \
        htop iotop net-tools \
        ntpdate vim

    sudo timedatectl set-timezone Asia/Shanghai 2>/dev/null || true

    info "系统依赖安装完成"
}


# ========== 3. NPU 驱动 ==========
install_npu_driver() {
    echo ""
    echo "[3/6] 安装 RK3588 NPU 驱动..."

    # 检查是否已安装
    if ldconfig -p 2>/dev/null | grep -q librknnrt; then
        info "NPU 驱动已安装, 跳过"
        return
    fi

    # 方式1: apt 安装 (Orange Pi 官方源)
    if apt-cache show rknpu2 2>/dev/null; then
        sudo apt install -y rknpu2
        info "NPU 驱动已通过 apt 安装"
        return
    fi

    # 方式2: 从 GitHub 下载
    local tmpdir=$(mktemp -d)
    cd "$tmpdir"
    git clone --depth 1 https://github.com/airockchip/rknn-toolkit2.git 2>/dev/null && {
        local so_path="rknn-toolkit2/rknpu2/runtime/RK3588/Linux/librknn_api/aarch64/librknnrt.so"
        if [ -f "$so_path" ]; then
            sudo cp "$so_path" /usr/lib/
            sudo ldconfig
            info "NPU 驱动已安装 (from GitHub)"
        fi
    } || {
        warn "无法自动安装 NPU 驱动"
        warn "请手动操作:"
        warn "  1. 下载: git clone https://github.com/airockchip/rknn-toolkit2.git"
        warn "  2. 复制: sudo cp rknn-toolkit2/rknpu2/runtime/RK3588/Linux/librknn_api/aarch64/librknnrt.so /usr/lib/"
        warn "  3. 加载: sudo ldconfig"
    }
    rm -rf "$tmpdir"

    # 验证
    if ldconfig -p 2>/dev/null | grep -q librknnrt; then
        info "NPU 驱动验证通过"
    fi

    [ "$MODE" = "npu" ] && exit 0
}


# ========== 4. Python 虚拟环境 ==========
setup_python() {
    echo ""
    echo "[4/6] 配置 Python 虚拟环境..."

    mkdir -p "$PROJECT_DIR"

    if [ ! -d "$PROJECT_DIR/.venv" ]; then
        $PYTHON_VER -m venv "$PROJECT_DIR/.venv"
        info "虚拟环境已创建"
    fi

    source "$PROJECT_DIR/.venv/bin/activate"
    pip install --upgrade pip setuptools wheel -q

    # 基础依赖
    pip install -q \
        numpy opencv-python-headless \
        pillow requests \
        onnxruntime \
        tqdm

    # RKNN Toolkit Lite 2 (板端 NPU 推理)
    echo "  安装 RKNN Toolkit Lite 2..."
    if pip install rknn-toolkit-lite2 -q 2>/dev/null; then
        info "rknn-toolkit-lite2 安装成功"
    else
        warn "pip 安装 rknn-toolkit-lite2 失败, 尝试从 GitHub 安装..."
        local tmpdir=$(mktemp -d)
        cd "$tmpdir"
        if git clone --depth 1 https://github.com/airockchip/rknn-toolkit2.git 2>/dev/null; then
            local wheel_dir="rknn-toolkit2/rknn-toolkit-lite2/packages"
            if [ -d "$wheel_dir" ]; then
                pip install "$wheel_dir"/*.whl 2>/dev/null || \
                    warn "未能从本地 wheel 安装, 请手动安装"
                info "RKNN Toolkit Lite 2 安装成功"
            fi
        fi
        rm -rf "$tmpdir"
    fi

    deactivate
    info "Python 环境配置完成"

    [ "$MODE" = "python" ] && exit 0
}


# ========== 5. 项目部署 ==========
deploy_project() {
    echo ""
    echo "[5/6] 部署项目文件..."

    mkdir -p "$PROJECT_DIR"/{output/{clips,export,edge_cache,logs},data/camera_calib,edge,localization}

    # 从当前目录复制 (排除不需要的文件)
    if [ -f "main.py" ]; then
        echo "  从 $(pwd) 复制项目文件..."
        rsync -av --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' \
              --exclude '.git' --exclude '.idea' --exclude 'data/smoke_dataset' \
              --exclude '*.pt' --exclude '*.pth' --exclude '*.rknn' \
              --exclude 'runs' --exclude 'output/yolo_train' \
              --exclude 'edge_config.json' \
              ./ "$PROJECT_DIR/" 2>/dev/null || \
        cp -r ./* "$PROJECT_DIR/" 2>/dev/null || true
    fi

    # 创建默认配置 (如果不存在)
    if [ ! -f "$PROJECT_DIR/edge_config.json" ] && [ -f "$PROJECT_DIR/edge_config.template.json" ]; then
        cp "$PROJECT_DIR/edge_config.template.json" "$PROJECT_DIR/edge_config.json"
        info "已从模板创建 edge_config.json (请修改服务器地址等配置)"
    fi

    # 确保日志目录存在
    mkdir -p "$PROJECT_DIR/logs"

    info "项目文件已部署到: $PROJECT_DIR"
    echo ""
    echo "  ⚠️  重要: 请编辑 edge_config.json 修改服务器地址和摄像头配置:"
    echo "     vim $PROJECT_DIR/edge_config.json"
}


# ========== 6. systemd 服务 ==========
setup_service() {
    echo ""
    echo "[6/6] 配置 systemd 自启动服务..."

    local SERVICE_NAME="flame-edge"
    local SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

    sudo tee "$SERVICE_FILE" > /dev/null << SERVICE_EOF
[Unit]
Description=Flame Detection Edge Pipeline (Orange Pi 5 RK3588)
Documentation=https://github.com/your-org/flame-detection
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

# 安全加固
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=${PROJECT_DIR}/output ${PROJECT_DIR}/logs ${PROJECT_DIR}/data
ReadOnlyPaths=${PROJECT_DIR}

[Install]
WantedBy=multi-user.target
SERVICE_EOF

    sudo systemctl daemon-reload
    info "服务文件已创建: $SERVICE_FILE"
    echo ""
    echo "  📋 服务管理命令:"
    echo "     sudo systemctl enable --now ${SERVICE_NAME}   # 启用并立即启动"
    echo "     sudo systemctl start ${SERVICE_NAME}          # 启动"
    echo "     sudo systemctl stop ${SERVICE_NAME}           # 停止"
    echo "     sudo systemctl status ${SERVICE_NAME}         # 查看状态"
    echo "     sudo journalctl -u ${SERVICE_NAME} -f         # 实时日志"
    echo "     tail -f ${PROJECT_DIR}/logs/edge.log          # 应用日志"

    [ "$MODE" = "service" ] && exit 0
}


# ========== 主流程 ==========
main() {
    echo ""
    echo "=========================================="
    echo " 火焰检测 — Orange Pi 5 一键部署"
    echo " 目标目录: $PROJECT_DIR"
    echo "=========================================="

    check_system
    [ "$MODE" = "check" ] && exit 0

    install_system_deps
    [ "$MODE" = "full" ] && install_npu_driver
    [ "$MODE" = "npu" ] && install_npu_driver
    [ "$MODE" = "full" ] && setup_python
    [ "$MODE" = "python" ] && setup_python
    [ "$MODE" = "full" ] && deploy_project
    [ "$MODE" = "full" ] && setup_service
    [ "$MODE" = "service" ] && setup_service

    echo ""
    echo "=========================================="
    echo " 部署完成!"
    echo "=========================================="
    echo ""
    echo "后续步骤:"
    echo ""
    echo "  1. 编辑配置文件:"
    echo "     vim $PROJECT_DIR/edge_config.json"
    echo ""
    echo "  2. 复制 RKNN 模型:"
    echo "     scp smoke_detector_fp16.rknn orangepi@<IP>:$PROJECT_DIR/output/export/"
    echo ""
    echo "  3. 复制标定文件:"
    echo "     scp data/camera_calib/*.json orangepi@<IP>:$PROJECT_DIR/data/camera_calib/"
    echo ""
    echo "  4. 测试运行 (模拟模式):"
    echo "     cd $PROJECT_DIR && source .venv/bin/activate"
    echo "     python edge/run.py --simulate --once"
    echo ""
    echo "  5. 启动服务:"
    echo "     sudo systemctl enable --now flame-edge"
    echo ""
    echo "  6. 查看运行日志:"
    echo "     tail -f $PROJECT_DIR/logs/edge.log"
    echo ""
}

main
