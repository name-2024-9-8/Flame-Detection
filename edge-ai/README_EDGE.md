# 火焰/烟尘检测 — AI边缘计算系统

基于 YOLO11-nano 的火焰/烟尘实时检测系统，部署于 Orange Pi 5 (RK3588S, NPU 6 TOPS)。

## 模型性能

| 指标 | 数值 | 目标 |
|------|------|------|
| mAP@50 | **90.63%** | ≥ 90% |
| Recall | 94.12% (@conf=0.05) | ≥ 90% |
| 模型大小 | **5.48 MB** | < 10 MB |
| 数据集 | CCTV Fire Smoke Emergency Detection | 235张 (188/47) |
| 推理后端 | ONNX / RKNN (NPU) / PyTorch | — |

## 项目结构

```
├── main.py                    # 统一入口
├── config.py                  # 全局配置
├── train_yolo.py              # YOLO11 训练
├── evaluate_yolo.py           # 多阈值评估
├── resume_train.py            # 断点恢复训练
├── convert_rknn.py            # ONNX → RKNN 转换
├── test_end_to_end.py         # 端到端集成测试
├── deploy_orangepi5.sh        # Orange Pi 5 一键部署
├── edge_config.template.json  # 边缘端配置模板
│
├── edge/                      # 边缘端模块
│   ├── run.py                 #   ** 边缘端启动入口 **
│   ├── pipeline.py            #   主控管线
│   ├── inference_engine.py    #   推理引擎 (ONNX/RKNN/PyTorch)
│   ├── preprocessing.py       #   暗通道去雾 + CLAHE增强
│   ├── temporal_filter.py     #   时域滤波 (滑动窗口投票)
│   ├── video_stream.py        #   RTSP 视频流接入
│   ├── output_module.py       #   HTTP POST + 视频上传 → 后端
│   └── hardware_utils.py      #   NPU温度/GPIO/IP 工具
│
├── localization/              # 定位模块
│   ├── camera_calibrator.py   #   单应矩阵标定 (图像→GPS)
│   ├── ptz_parser.py          #   OCR → PTZ 参数提取
│   ├── geo_mapper.py          #   经纬度映射 + 逆地址解析
│   └── localization_pipeline.py # 定位流水线
│
├── data/
│   ├── smoke_dataset/         # 训练/验证集 (YOLO格式)
│   └── camera_calib/          # 相机标定数据
│
└── output/
    ├── yolo_train/weights/    # best.pt + best.onnx
    ├── export/                # smoke_detector_fp16.rknn
    └── yolo11n.pt             # YOLO11-nano 预训练权重
```

## 数据通信架构

```
┌──────────────┐    RTSP      ┌─────────────────┐    HTTP POST     ┌──────────────┐
│  摄像头       │ ──────────→  │  Orange Pi 5    │ ──────────────→  │  后端服务器    │
│  (海康/大华)   │   视频流     │  (RK3588S NPU)  │  JSON + 视频     │  (管理系统)    │
└──────────────┘              │                 │                  │              │
                              │ 1. 视频采集      │                  │ API:         │
                              │ 2. 去雾+CLAHE    │                  │ /api/detect/ │
                              │ 3. NPU推理(YOLO) │                  │   alarm      │
                              │ 4. 时域滤波       │                  │   upload     │
                              │ 5. GPS定位       │                  │   heartbeat  │
                              │ 6. 报警输出       │                  │   error      │
                              └─────────────────┘                  └──────────────┘

报警事件数据包 (JSON):
  {
    camera_id, device_id, area_id, timestamp,
    longitude, latitude, location,      ← 火焰位置
    picture_base64,                     ← 检测帧 JPEG (base64)
    video_url,                          ← 3-5秒 MP4 视频片段
    confidence, urgency_degree, status
  }
```

## 使用方法

```bash
python main.py                    # 查看所有命令

# AI模型训练
python main.py yolo-train         # 训练 YOLO11-nano
python main.py yolo-resume        # 从断点恢复训练
python main.py yolo-eval          # 多阈值评估

# 目标定位
python main.py calib              # 创建相机标定数据
python main.py ptz                # PTZ 参数解析测试
python main.py locate             # 定位流水线演示
python main.py verify             # 定位精度验证

# 边缘部署
python main.py rknn               # ONNX → RKNN 模型转换
python main.py edge-run           # 启动边缘端检测管线
python main.py e2e                # 端到端集成测试
```

## Orange Pi 5 完整部署指南

### 一、烧录系统镜像到 Orange Pi 5

#### 1.1 准备工作

| 物品 | 说明 |
|------|------|
| Orange Pi 5 主板 | RK3588S, 推荐 8GB 内存版本 |
| MicroSD 卡 | ≥ 32GB, Class 10 / UHS-I (推荐 SanDisk/Samsung) |
| 读卡器 | USB 3.0 读卡器 |
| 电源适配器 | 5V/4A Type-C (带 PD 协议) |
| 网线 | 千兆以太网线 |
| HDMI 线 + 显示器 | 首次配置使用 |
| USB 键盘鼠标 | 首次配置使用 |
| 散热片 + 风扇 | **必需**，NPU 满负载时发热较大 |

#### 1.2 下载镜像

从 Orange Pi 官网下载系统镜像:

- **推荐: Orange Pi 5 Debian 12 (Bookworm)**
  - 下载地址: http://www.orangepi.org/html/softWare/orangePi5.html
  - 选择: `Orangepi5_Debian_bookworm_linux6.1.43.img.xz`
- 备选: Orange Pi 5 Ubuntu 22.04 (Jammy)
- 备选: Armbian for Orange Pi 5

#### 1.3 烧录镜像到 SD 卡

**Windows 平台 (推荐 balenaEtcher):**

1. 下载并安装 balenaEtcher: https://www.balena.io/etcher/
2. 插入 SD 卡读卡器
3. 打开 balenaEtcher
4. 选择下载的 `.img.xz` 镜像文件 (无需解压)
5. 选择目标 SD 卡
6. 点击 "Flash!" 开始烧录
7. 烧录完成后，Windows 可能提示格式化 — **不要格式化**

**Windows 平台 (Win32DiskImager):**

```powershell
# 1. 先用 7-Zip 解压 .img.xz 得到 .img 文件
# 2. 打开 Win32DiskImager, 选择 .img 文件和 SD 卡盘符
# 3. 点击 Write
```

**Linux/Mac 平台 (dd 命令):**

```bash
# 找到 SD 卡设备 (通常是 /dev/sdb 或 /dev/mmcblk0)
lsblk

# 解压镜像
xz -d Orangepi5_Debian_bookworm_linux6.1.43.img.xz

# 烧录 (⚠️ 确认设备路径, 错误操作会破坏数据!)
sudo dd if=Orangepi5_Debian_bookworm_linux6.1.43.img \
        of=/dev/sdX bs=4M status=progress conv=fsync

# 刷新缓存
sync
```

#### 1.4 首次启动

1. 将烧录好的 SD 卡插入 Orange Pi 5
2. 连接 HDMI 显示器、键盘鼠标、网线
3. **最后**连接 Type-C 电源
4. 系统自动启动，默认登录凭据:
   - 用户名: `orangepi`
   - 密码: `orangepi`
   - root 密码: `orangepi`

### 二、系统初始配置

```bash
# 1. 更新系统
sudo apt update && sudo apt upgrade -y

# 2. 设置时区
sudo timedatectl set-timezone Asia/Shanghai

# 3. 设置静态 IP (可选, 生产环境推荐)
sudo nmtui
# 或编辑 /etc/netplan/ 下的配置文件

# 4. 启用 SSH (方便远程管理)
sudo systemctl enable --now ssh

# 5. 查看本机 IP
ip addr show | grep inet
# 或
hostname -I

# 6. (可选) 从 PC SSH 登录, 方便后续操作
# ssh orangepi@<Orange Pi 5 IP地址>
```

### 三、一键部署火焰检测系统

```bash
# 1. 将项目代码拷贝到 Orange Pi 5 (在 PC 上执行)
scp -r pythonProject/ orangepi@<IP>:/home/orangepi/flame_detection/

# 2. SSH 登录 Orange Pi 5
ssh orangepi@<IP>

# 3. 进入项目目录并执行一键部署
cd /home/orangepi/flame_detection
bash deploy_orangepi5.sh

# 部署脚本会依次完成:
#   ✓ 系统依赖安装 (Python, OpenCV, GStreamer 等)
#   ✓ NPU 驱动安装 (librknnrt.so)
#   ✓ Python 虚拟环境 + RKNN Toolkit Lite 2
#   ✓ 项目文件部署
#   ✓ systemd 自启动服务配置
```

**部署脚本高级选项:**

```bash
bash deploy_orangepi5.sh --check        # 仅查看系统状态
bash deploy_orangepi5.sh --npu-only     # 仅安装NPU驱动
bash deploy_orangepi5.sh --python-only  # 仅配置Python环境
bash deploy_orangepi5.sh --service-only # 仅配置systemd服务
bash deploy_orangepi5.sh --project-dir /opt/flame  # 自定义目录
```

### 四、模型转换与部署

```bash
# --- 在 PC (x86) 上执行 ONNX → RKNN 转换 ---
# (需要先安装 RKNN Toolkit 2)
python main.py rknn
# 生成: output/export/smoke_detector_fp16.rknn
# 生成: output/export/smoke_detector_int8.rknn (可选)

# --- 复制 RKNN 模型到 Orange Pi 5 ---
scp output/export/smoke_detector_fp16.rknn \
    orangepi@<IP>:/home/orangepi/flame_detection/output/export/
```

### 五、配置边缘端

```bash
# 在 Orange Pi 5 上
cd /home/orangepi/flame_detection

# 从模板创建配置文件
cp edge_config.template.json edge_config.json

# 编辑配置
vim edge_config.json
```

**关键配置项:**

```json
{
  "device": {
    "device_id": 1,           // 设备唯一ID (与数据库 T_Device 一致)
    "mac": "AA:BB:CC:DD:EE:FF" // 设备MAC地址
  },
  "server": {
    "url": "http://192.168.1.100:8083"  // 后端服务器地址
  },
  "model": {
    "path": "output/export/smoke_detector_fp16.rknn",
    "conf_threshold": 0.25
  },
  "cameras": [
    {
      "camera_id": 1,
      "rtsp_url": "rtsp://admin:password@192.168.1.64:554/Streaming/Channels/101",
      "longitude": 116.394000,
      "latitude": 39.905300
    }
  ]
}
```

### 六、相机标定 (GPS定位)

```bash
# 1. 创建标定数据
python main.py calib
# 在 data/camera_calib/camera_001_calib.json 中填写真实标志点

# 2. 验证定位精度
python main.py verify

# 3. 配置离线区域 (用于逆地址解析)
# 编辑 data/camera_calib/regions.json
```

### 七、启动与运行

```bash
# 测试模式 (单帧, 无需摄像头)
cd /home/orangepi/flame_detection
source .venv/bin/activate
python edge/run.py --simulate --once

# 模拟模式 (持续运行, 使用随机测试帧)
python edge/run.py --simulate

# 使用 RTSP 摄像头正式运行
python edge/run.py

# 显示检测画面 (需连接显示器)
python edge/run.py --preview

# 使用 USB 摄像头
python edge/run.py --camera 0

# 指定运行时长 (测试用)
python edge/run.py --duration 60

# systemd 服务管理 (生产环境)
sudo systemctl enable --now flame-edge   # 开机自启 + 立即启动
sudo systemctl status flame-edge         # 查看状态
sudo journalctl -u flame-edge -f         # 实时日志
tail -f logs/edge.log                    # 应用日志
```

### 八、报警事件数据格式

边缘端检测到火焰后，通过 HTTP POST 发送到 `${server}/api/detect/alarm`:

```json
{
  "camera_id": 1,
  "device_id": 1,
  "area_id": 1,
  "timestamp": "2026-06-12T10:30:00+08:00",
  "longitude": 116.394000,
  "latitude": 39.905300,
  "location": "北京市东城区工业园区A",
  "confidence": 0.92,
  "urgency_degree": "高",
  "description": "检测到火焰/烟尘 (置信度: 0.92)",
  "picture_base64": "/9j/4AAQSkZJRg...",   // JPEG base64 编码
  "video_url": "http://192.168.1.100:8083/uploads/alarm_1_20260612_103000.mp4",
  "status": "1",
  "remark": "推理时延: 45ms, 滤波窗口: 3/5"
}
```

**视频片段**: 报警前2秒 + 报警后3秒 = 共5秒 MP4 (15fps)，通过 `/api/detect/upload` 上传。

### 九、性能验证

```bash
# 端到端评估 (PC)
python main.py e2e

# Orange Pi 5 板端性能测试
python -c "
from rknnlite.api import RKNNLite
import numpy as np, time

rknn = RKNNLite()
rknn.load_rknn('output/export/smoke_detector_fp16.rknn')
rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO)

img = np.random.randn(1, 3, 416, 416).astype(np.float32)

# 预热
for _ in range(10):
    rknn.inference([img])

# 计时
times = []
for _ in range(100):
    t0 = time.perf_counter()
    rknn.inference([img])
    times.append((time.perf_counter() - t0) * 1000)

print(f'NPU 推理时延: avg={np.mean(times):.1f}ms, min={np.min(times):.1f}ms')
print(f'FPS: {1000/np.mean(times):.1f}')
"
```

### 十、故障排查

| 现象 | 可能原因 | 解决方法 |
|------|---------|---------|
| NPU 设备不存在 | 驱动未安装 | `sudo apt install rknpu2` 或运行 `bash deploy_orangepi5.sh --npu-only` |
| RKNN 模型加载失败 | opset 不兼容 | 导出 ONNX 时指定 `opset=12` |
| 推理时延 > 2s | 使用了 CPU 推理 | 检查 NPU 驱动，确认 `.rknn` 文件被正确加载 |
| 视频上传失败 | 服务器不可达 | 检查网络，确认 `edge_config.json` 中 `server.url` 正确 |
| 摄像头断连 | RTSP 超时 | pipeline 内置自动重连机制，检查摄像头 IP |
| SD 卡寿命 | 频繁写入日志/视频 | 使用外接 SSD 存储视频片段，日志使用 tmpfs |
| NPU 过热降频 | 散热不足 | 加装散热片+风扇，监控 `/sys/class/thermal/thermal_zone0/temp` |

### 十一、参考系统

- 项目参考: http://124.223.48.218:8083 (数据处理端 + 管理系统)
- 管理员: admin / 123456
- 处理员: chuli001 / 123456
