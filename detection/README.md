# 火焰/烟尘检测 — AI边缘计算系统

基于 YOLO11-nano 的火焰/烟尘检测系统，部署于 Orange Pi 5 (RK3588S, NPU 6 TOPS)。支持视频文件检测 + 实时报警推送（火焰图片、3-5秒视频片段、位置信息）。

## 模型性能

| 指标 | 数值 | 目标 |
|------|------|------|
| mAP@50 | **89.1%** | ≥ 90% |
| Recall | 78.9% (@conf=0.25) | ≥ 90% |
| 训练集 | 524张 (188原始 + 336自标注7视频) | — |
| 验证集 | 131张 (47原始 + 84自标注) | — |
| 测试视频检出率 | 6/7 视频 **100%** 帧覆盖 (conf=0.25) | — |
| 平均推理时延 | CPU ONNX ~30ms, NPU RKNN ~5ms | ≤ 2000ms |
| 模型大小 | 5.5 MB (best.pt) / 10 MB (best.onnx) | < 10 MB |
| 推理后端 | ONNX / RKNN (NPU) / PyTorch | — |

## 快速开始

```bash
# 1. 克隆项目
git clone <仓库地址>
cd 火焰检测

# 2. 安装依赖 (Windows 开发环境)
pip install ultralytics opencv-python onnxruntime

# 3. 视频检测 (PC端)
python main.py video-test                          # 检测 test/VP47.mp4
python main.py video-test --video test/VP6.mp4     # 指定视频
python main.py video-test --save

# 4. 火焰报警检测 (含图片+视频片段+报警推送)
python main.py flame-alarm --video test/VP47.mp4 --offline
python main.py flame-alarm --video-dir test/ --offline

# 5. 边缘端视频检测 (ONNX/RKNN, 无需摄像头)
python main.py edge-video --video test/VP47.mp4 \
    --model output/yolo_train_7videos/weights/best.onnx
```

## 项目结构

```
├── main.py                     # 统一入口
├── config.py                   # 全局配置
├── train_yolo.py               # YOLO11 训练
├── evaluate_yolo.py            # 多阈值评估
├── resume_train.py             # 断点恢复训练
├── test_video.py               # 视频火焰检测 (PyTorch)
├── test_end_to_end.py          # 端到端集成测试
├── convert_rknn.py             # ONNX → RKNN 转换
├── deploy_orangepi5.sh         # Orange Pi 5 一键部署
├── edge_config.template.json   # 边缘端配置模板
│
├── edge/                       # 边缘端模块
│   ├── run.py                  #   边缘端启动入口 (摄像头模式)
│   ├── video_detect.py         #   边缘端视频检测 (ONNX/RKNN)
│   ├── flame_alarm.py          #   ** 火焰报警推送 (图片+视频+位置) **
│   ├── pipeline.py             #   主控管线
│   ├── inference_engine.py     #   推理引擎 (ONNX/RKNN/PyTorch)
│   ├── preprocessing.py        #   暗通道去雾 + CLAHE增强
│   ├── temporal_filter.py      #   时域滤波 (滑动窗口投票)
│   ├── video_stream.py         #   RTSP 视频流接入
│   ├── output_module.py        #   HTTP POST + 视频上传 → 后端
│   └── hardware_utils.py       #   NPU温度/GPIO/IP 工具
│
├── localization/               # 定位模块
│   ├── camera_calibrator.py    #   单应矩阵标定 (图像→GPS)
│   ├── ptz_parser.py           #   OCR → PTZ 参数提取
│   ├── geo_mapper.py           #   经纬度映射 + 逆地址解析
│   └── localization_pipeline.py # 定位流水线
│
├── data/
│   ├── smoke_dataset/          # 训练/验证集 (YOLO格式)
│   └── camera_calib/           # 相机标定数据
│
├── test/                       # 测试视频 (7个CCTV火焰/烟尘场景)
│   ├── VP6.mp4
│   ├── VP18.mp4
│   └── ...
│
└── output/
    ├── yolo_train_7videos/weights/  # best.pt + best.onnx (最新模型)
    ├── export/                      # smoke_detector_fp16.rknn (NPU)
    ├── alarm_clips/                 # 报警视频片段 (.mp4)
    ├── alarm_events/                # 报警事件 (.json)
    └── yolo11n.pt                   # YOLO11-nano 预训练权重
```

## 统一命令入口

```bash
python main.py                    # 查看所有命令

# AI模型
python main.py yolo-train         # 训练 YOLO11-nano
python main.py yolo-resume        # 从断点恢复训练
python main.py yolo-eval          # 多阈值评估

# 视频检测
python main.py video-test         # 视频火焰检测 (PyTorch, 带进度/FPS)
python main.py edge-video         # 边缘端视频检测 (ONNX/RKNN)

# 火焰报警 (图片 + 视频片段 + 服务端推送)
python main.py flame-alarm --video test/VP47.mp4 --offline

# 边缘部署 & 定位
python main.py e2e                # 端到端集成测试
python main.py rknn               # ONNX → RKNN 模型转换
python main.py edge-run           # 启动边缘端管线 (摄像头模式)
```

## 数据通信架构

```
┌──────────────────────────────────────────────────────────────┐
│  输入方式:                                                    │
│    • 视频文件 (test/*.mp4)         python flame-alarm         │
│    • RTSP 摄像头 (海康/大华)        python edge-run           │
│    • 目录批量检测                  python flame-alarm --video-dir│
└──────────────────┬───────────────────────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │   Orange Pi 5      │
         │   (RK3588S NPU)    │
         │                    │
         │ 1. 视频读取/采集    │
         │ 2. 去雾 + CLAHE    │
         │ 3. NPU推理 (YOLO)  │
         │ 4. 时域滤波 (5帧3票)│
         │ 5. 报警判定         │
         │ 6. 图片+视频片段     │
         └─────────┬──────────┘
                   │  HTTP POST (JSON)
         ┌─────────▼──────────┐
         │   后端服务器         │
         │   (管理系统)         │
         │                    │
         │ POST /api/detect/  │
         │   alarm (报警事件)  │
         │   upload (视频上传) │
         │   heartbeat (心跳)  │
         │   error (故障上报)  │
         └────────────────────┘
```

### 报警事件数据格式

火焰报警通过 HTTP POST 发送到 `${server}/api/detect/alarm`:

```json
{
  "camera_id": 0,
  "device_id": 1,
  "area_id": 1,
  "timestamp": "2026-07-06T10:12:52+08:00",
  "longitude": 116.397,
  "latitude": 39.909,
  "location": "北京市东城区",
  "confidence": 0.95,
  "urgency_degree": "高",
  "description": "检测到火焰/烟尘 (置信度: 0.95)",
  "picture_base64": "/9j/4AAQSkZJRg...",          // JPEG base64
  "video_path": "output/alarm_clips/alarm_xxx.mp4",  // 3-5秒视频片段
  "status": "1",
  "remark": "推理时延: 30ms, 滤波: 3/5"
}
```

**离线模式**: 无服务端时，报警数据保存到 `output/alarm_events/*.json`，视频保存到 `output/alarm_clips/*.mp4`。

## Orange Pi 5 部署指南

### 1. 克隆项目

```bash
git clone <仓库地址>
cd 火焰检测
```

### 2. 一键部署

```bash
bash deploy_orangepi5.sh              # 安装系统依赖+NPU驱动+Python环境
bash deploy_orangepi5.sh --check      # 仅查看系统状态
bash deploy_orangepi5.sh --npu-only   # 仅安装NPU驱动
```

### 3. 模型转换 (板端)

```bash
# ONNX → RKNN 转换 (NPU推理)
python main.py rknn
# 生成: output/export/smoke_detector_fp16.rknn
```

### 4. 运行检测

```bash
# 方式A: 火焰报警检测 (推荐 - 视频文件输入)
python main.py flame-alarm \
    --video test/VP47.mp4 \
    --model output/export/smoke_detector_fp16.rknn \
    --server http://192.168.1.100:8083 \
    --lng 116.397 --lat 39.909 --location "北京市东城区"

# 方式B: 离线检测 (报警保存到本地)
python main.py flame-alarm --video test/VP47.mp4 --offline

# 方式C: 边缘端视频检测 (简明输出)
python main.py edge-video --video test/VP47.mp4 \
    --model output/export/smoke_detector_fp16.rknn --save

# 方式D: 摄像头模式 (需配置RTSP)
python main.py edge-run
```

### 5. 常用参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--conf` | 0.25 | 置信度阈值 |
| `--filter-window` | 5 | 时域滤波窗口(帧) |
| `--filter-votes` | 3 | 触发报警所需投票数 |
| `--clip-sec` | 5.0 | 报警视频片段长度(秒) |
| `--lng --lat --location` | — | 火焰位置(GPS) |
| `--offline` | — | 离线模式(保存本地) |
| `--no-display` | — | 不显示检测画面 |

## 训练说明

### 数据集

- 原始: CCTV Fire Smoke Emergency Detection (188 train / 47 val)
- 扩充: 7个CCTV视频自动标注 (336 train / 84 val)
- 合并后: **524 train / 131 val** (655张)

### 训练命令

```bash
python main.py yolo-train      # 从头训练 (200 epochs, CPU ~2h)
python main.py yolo-resume     # 从 last.pt 断点恢复
python main.py yolo-eval       # 多阈值评估
```

### 添加新视频训练

1. 将新视频放入 `test/` 目录
2. 修改 `build_7video_dataset.py` 或手动执行抽帧→标注→合并
3. 重新训练

## 性能验证

```bash
# PC端端到端评估
python main.py e2e

# Orange Pi 5 NPU 性能测试
python -c "
from rknnlite.api import RKNNLite
import numpy as np, time

rknn = RKNNLite()
rknn.load_rknn('output/export/smoke_detector_fp16.rknn')
rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO)

img = np.random.randn(1, 3, 416, 416).astype(np.float32)
for _ in range(10): rknn.inference([img])  # 预热

times = []
for _ in range(100):
    t0 = time.perf_counter()
    rknn.inference([img])
    times.append((time.perf_counter() - t0) * 1000)

print(f'NPU推理: avg={np.mean(times):.1f}ms, FPS={1000/np.mean(times):.1f}')
"
```

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| NPU设备不存在 | 驱动未安装 | `bash deploy_orangepi5.sh --npu-only` |
| RKNN加载失败 | opset不兼容 | 导出ONNX时指定 `opset=12` |
| 推理时延 > 2s | CPU推理 | 检查NPU驱动，确认.rknn文件 |
| 报警未触发 | 滤波窗口未满 | 减小 `--filter-votes` 或 `--conf` |
| 编码错误 (Windows) | GBK编码问题 | 使用 `--no-display` 或 Linux 部署 |
| NPU过热降频 | 散热不足 | 加装散热片+风扇 |
