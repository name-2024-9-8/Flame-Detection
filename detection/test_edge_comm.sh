#!/bin/bash
# ============================================================
# 火焰检测边缘端 — 一键通信测试脚本
# ============================================================
# 功能: 下载模型 → 处理测试视频 → 生成标注视频 → 推送报警到服务器
#
# 用法:
#   bash test_edge_comm.sh                          # 交互式
#   bash test_edge_comm.sh --server 192.168.1.100   # 指定服务器
#   bash test_edge_comm.sh --all                     # 处理所有测试视频
# ============================================================
set -e

# ========== 默认配置 ==========
SERVER_IP=""
SERVER_PORT="8080"
MODEL_URL="https://github.com/name-2024-9-8/Flame-Detection/releases/download/model/best.onnx"
TEST_VIDEOS=("test/VP18.mp4" "test/VP23.mp4" "test/VP25.mp4" "test/VP45.mp4")
DEVICE_ID=3
AREA_ID=1
LNG=106.528
LAT=29.453
LOCATION="重庆理工大学花溪校区"
OUTPUT_DIR="output"
PROCESS_ALL=false

# ========== 颜色 ==========
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERR]${NC} $1"; }

# ========== 解析参数 ==========
VIDEO_ARG=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --server)   SERVER_IP="$2"; shift ;;
        --port)     SERVER_PORT="$2"; shift ;;
        --device)   DEVICE_ID="$2"; shift ;;
        --video)    VIDEO_ARG="$2"; shift ;;
        --all)      PROCESS_ALL=true ;;
        -h|--help)
            echo "用法: bash test_edge_comm.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --server IP    服务器IP地址 (必需)"
            echo "  --port PORT    服务器端口 (默认: 8080)"
            echo "  --device ID    边缘设备ID (默认: 3)"
            echo "  --video PATH   指定单个测试视频"
            echo "  --all          处理所有测试视频"
            echo "  -h, --help     显示帮助"
            echo ""
            echo "示例:"
            echo "  bash test_edge_comm.sh --server 192.168.1.100"
            echo "  bash test_edge_comm.sh --server 192.168.1.100 --all"
            echo "  bash test_edge_comm.sh --server 192.168.1.100 --video test/VP18.mp4"
            exit 0
            ;;
        *) err "未知参数: $1"; exit 1 ;;
    esac
    shift
done

# ========== 交互式输入 ==========
if [ -z "$SERVER_IP" ]; then
    echo "============================================"
    echo " 火焰检测边缘端 — 通信测试"
    echo "============================================"
    echo ""
    read -p "请输入服务器IP地址: " SERVER_IP
    if [ -z "$SERVER_IP" ]; then
        err "服务器IP不能为空"
        exit 1
    fi
fi

SERVER_URL="http://${SERVER_IP}:${SERVER_PORT}"

# ========== 1. 环境检查 ==========
echo ""
echo "[1/5] 检查环境..."

# Python
if ! command -v python3 &>/dev/null; then
    err "未找到 python3，请先安装: sudo apt install python3 python3-pip"
    exit 1
fi
info "Python: $(python3 --version)"

# pip
if ! python3 -m pip --version &>/dev/null; then
    err "未找到 pip，请先安装: sudo apt install python3-pip"
    exit 1
fi
info "pip: OK"

# 检查依赖
echo "  检查 Python 依赖..."
MISSING=""
for pkg in opencv-python-headless onnxruntime numpy requests; do
    pkg_name=$(echo $pkg | sed 's/-/_/g')
    if ! python3 -c "import ${pkg_name}" 2>/dev/null; then
        MISSING="$MISSING $pkg"
    fi
done

if [ -n "$MISSING" ]; then
    warn "缺少依赖:$MISSING"
    echo "  安装中..."
    python3 -m pip install $MISSING -q
    info "依赖安装完成"
else
    info "依赖齐全"
fi

# 检查项目文件
if [ ! -f "edge/flame_alarm.py" ]; then
    err "未找到 edge/flame_alarm.py，请在项目 detection/ 目录下运行"
    exit 1
fi
info "项目文件: OK"

# ========== 2. 检查模型 ==========
echo ""
echo "[2/5] 检查模型文件..."

MODEL_PATH="output/best.onnx"
if [ ! -f "$MODEL_PATH" ]; then
    warn "模型文件不存在: $MODEL_PATH"
    warn "请将 ONNX 模型复制到 output/best.onnx"
    echo ""
    echo "  从PC传输模型:"
    echo "    scp detection/output/yolo_train/weights/best.onnx orangepi@<IP>:~/Flame-Detection/detection/output/best.onnx"
    echo ""
    read -p "模型已就绪？按回车继续 (Ctrl+C 取消) "
    if [ ! -f "$MODEL_PATH" ]; then
        err "模型文件仍未找到，退出"
        exit 1
    fi
fi
MODEL_SIZE=$(du -h "$MODEL_PATH" | awk '{print $1}')
info "模型: $MODEL_PATH ($MODEL_SIZE)"

# ========== 3. 检查视频 ==========
echo ""
echo "[3/5] 检查测试视频..."

if [ -n "$VIDEO_ARG" ]; then
    if [ -f "$VIDEO_ARG" ]; then
        TEST_VIDEOS=("$VIDEO_ARG")
        info "测试视频: $VIDEO_ARG"
    else
        err "视频不存在: $VIDEO_ARG"
        exit 1
    fi
elif [ "$PROCESS_ALL" = true ]; then
    info "处理所有测试视频: ${#TEST_VIDEOS[@]} 个"
else
    # 默认用第一个存在的视频
    for v in "${TEST_VIDEOS[@]}"; do
        if [ -f "$v" ]; then
            TEST_VIDEOS=("$v")
            info "测试视频: $v"
            break
        fi
    done
    if [ ! -f "${TEST_VIDEOS[0]}" ]; then
        warn "未找到测试视频，请从PC传输:"
        echo "  scp detection/test/VP*.mp4 orangepi@<IP>:~/Flame-Detection/detection/test/"
        read -p "按回车继续 (Ctrl+C 取消) "
    fi
fi

# ========== 4. 测试服务器连接 ==========
echo ""
echo "[4/5] 测试服务器连接..."

if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "${SERVER_URL}/index.php/api/statistics/health" 2>/dev/null | grep -q "200"; then
    info "服务器可达: $SERVER_URL"
else
    warn "无法连接服务器 $SERVER_URL"
    warn "请检查:"
    warn "  1. PC端服务是否运行: curl http://127.0.0.1:8080/index.php/api/statistics/health"
    warn "  2. 防火墙是否开放8080端口"
    warn "  3. 网络是否互通: ping $SERVER_IP"
    echo ""
    read -p "忽略并继续测试？(y/N) " IGNORE
    if [ "$IGNORE" != "y" ] && [ "$IGNORE" != "Y" ]; then
        err "用户取消"
        exit 1
    fi
fi

# ========== 5. 运行检测 ==========
echo ""
echo "[5/5] 开始火焰检测..."
echo "============================================"
echo " 服务器:  $SERVER_URL"
echo " 设备ID:  $DEVICE_ID"
echo " 位置:    $LOCATION ($LNG, $LAT)"
echo "============================================"
echo ""

TOTAL_ALARMS=0
TOTAL_FRAMES=0

for v in "${TEST_VIDEOS[@]}"; do
    if [ ! -f "$v" ]; then
        warn "跳过不存在的视频: $v"
        continue
    fi

    echo ">>> 处理: $(basename $v)"

    python3 edge/flame_alarm.py \
        --video "$v" \
        --model "$MODEL_PATH" \
        --server "$SERVER_URL" \
        --device-id "$DEVICE_ID" \
        --area-id "$AREA_ID" \
        --lng "$LNG" \
        --lat "$LAT" \
        --location "$LOCATION" \
        --save-video \
        --push-video \
        --output-dir "$OUTPUT_DIR" \
        --no-display \
        --filter-window 3 \
        --filter-votes 2

    echo ""
done

# ========== 汇总 ==========
echo ""
echo "============================================"
echo " 检测完成!"
echo "============================================"
echo ""
echo "生成的文件:"
ls -lh ${OUTPUT_DIR}/*_detected.mp4 2>/dev/null && echo "" || true
ls -lh ${OUTPUT_DIR}/alarm_clips/ 2>/dev/null || true

echo ""
echo "验证服务器端数据:"
echo "  python3 -c \""
echo "import pymysql"
echo "c = pymysql.connect(host='${SERVER_IP}', port=3306, user='root', password='', database='flame_detection')"
echo "cur = c.cursor()"
echo "cur.execute('SELECT COUNT(*) FROM T_DetectResult')"
echo "print(f'火情总数: {cur.fetchone()[0]}')\""
echo ""
echo "浏览器查看大屏: http://${SERVER_IP}:5000"
