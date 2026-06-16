# 视频AI智能识别及预警管理信息系统

基于 YOLO11-nano 的火焰/烟尘实时检测与预警管理系统，三方协作完成。

## 架构概览

```
┌─────────────────────┐     RTSP视频流      ┌──────────────────────────┐
│   摄像头 (海康/大华)  │ ─────────────────→  │  Orange Pi 5 (RK3588S)   │
│                     │                     │  edge-ai/edge/run.py     │
└─────────────────────┘                     │  YOLO11-nano NPU 推理    │
                                            └────────────┬─────────────┘
                                                         │ HTTP POST
                                                         ↓
┌──────────────────────────────────────────────────────────────────────┐
│  后端服务器 (B+C 融合)                                                 │
│  ┌─────────────────┐   API桥接    ┌──────────────────────────┐        │
│  │ Flask :5000      │ ←──────────→ │ PHP :8080 (CodeIgniter 3)│        │
│  │ 前端页面 / 代理   │             │ RESTful API / 数据库      │        │
│  └─────────────────┘             └──────────┬───────────────┘        │
│                                             │                         │
│                                     ┌───────▼────────┐               │
│                                     │ MySQL           │               │
│                                     │ flame_detection │               │
│                                     │ (15张表)         │               │
│                                     └────────────────┘               │
└──────────────────────────────────────────────────────────────────────┘
```

## 人员分工

| 人员 | 负责模块 | 核心内容 |
|------|---------|---------|
| **A · 郭俊奇** | AI边缘检测 | YOLO11训练/推理、视频采集、时域滤波、GPS定位、Orange Pi 5部署 |
| **B · 王永林** | 后端+数据库 | PHP RESTful API、MySQL 15表设计、JWT认证、设备/报警/日志CRUD |
| **C · 段林川** | 前端Web | Flask + 17页面、地图可视化、API桥接代理 |

## 目录结构

```
backed/
├── app.py                      # Flask 主入口 (端口 5000)
├── config.py                   # Flask 配置 (含 EDGE_API_KEY)
├── api_bridge.py               # Flask ↔ PHP API 桥接层
├── models.py                   # 数据模型 (融合模式下通过API桥接)
├── requirements.txt            # Python依赖
│
├── routes/                     # Flask 路由蓝本
│   ├── __init__.py             #   路由注册
│   ├── auth.py                 #   认证 (登录/登出)
│   ├── main.py                 #   页面路由 (17页面)
│   ├── api.py                  #   管理API代理 (CRUD)
│   └── detect.py               #   ★ 边缘检测API代理 (A↔B, 含X-API-Key认证)
│
├── templates/                  # Jinja2 模板 (17个页面)
│   ├── index.html              #   数据大屏
│   ├── dashboard.html          #   仪表盘
│   ├── login.html              #   登录页
│   ├── alarm/                  #   报警事件相关
│   ├── device/                 #   设备管理
│   ├── system/                 #   系统管理
│   └── log/                    #   日志查询
│
├── static/                     # 前端静态资源
│   ├── css/app.css
│   └── js/app.js
│
├── web/                        # PHP 后端 (CodeIgniter 3, 端口 8080)
│   ├── index.php               #   PHP 入口
│   ├── application/
│   │   ├── config/
│   │   │   ├── routes.php      #   ★ API 路由映射
│   │   │   └── database.php    #   MySQL 连接配置
│   │   ├── controllers/api/
│   │   │   ├── Auth.php        #   认证 API
│   │   │   ├── Alarm.php       #   报警 CRUD
│   │   │   ├── Device.php      #   设备 CRUD
│   │   │   ├── Detect.php      #   ★ 边缘数据接入 (M7新增)
│   │   │   ├── Statistics.php  #   统计分析
│   │   │   ├── Export.php      #   Excel/Word 导出
│   │   │   ├── Log.php         #   日志查询
│   │   │   └── WebService.php  #   第三方对接
│   │   ├── models/             #   数据模型层
│   │   └── core/
│   │       └── REST_Controller.php  # REST 基类 (JWT/限流/日志)
│   ├── database/
│   │   └── 001_create_tables.sql    # 15张表建表语句 + 种子数据
│   └── vendor/                 #   Composer 依赖
│
└── edge-ai/                    # ★ 郭俊奇 · 边缘AI模块 (M7集成)
    ├── main.py                 #   统一入口 (train/eval/calib/deploy)
    ├── config.py               #   AI模型配置
    ├── edge/
    │   ├── run.py              #   边缘端启动入口
    │   ├── pipeline.py         #   主控管线 (采集→推理→滤波→报警)
    │   ├── output_module.py    #   HTTP POST 结果发布器
    │   ├── inference_engine.py #   推理引擎 (RKNN/ONNX/PyTorch)
    │   ├── preprocessing.py    #   暗通道去雾 + CLAHE增强
    │   ├── temporal_filter.py  #   时域滤波 (滑动窗口投票)
    │   ├── video_stream.py     #   RTSP 视频流接入
    │   └── hardware_utils.py   #   NPU/GPIO 工具
    ├── localization/           #   GPS定位模块
    ├── train_yolo.py           #   YOLO11 训练
    ├── convert_rknn.py         #   ONNX → RKNN 转换
    ├── deploy_orangepi5.sh     #   Orange Pi 5 一键部署
    └── edge_config.template.json  # 边缘端配置模板
```

## 快速启动

### 环境要求

- PHP 5.6+ (CodeIgniter 3)
- Python 3.10+ (Flask)
- MySQL 5.7+
- Redis (可选，用于限流)

### 启动步骤

**终端1 — PHP 后端 (端口 8080)**

```bash
# Git Bash / CMD:
D:\php83\php-5.6.8\php.exe -c D:\php83\php-5.6.8\php.ini -S localhost:8080 -t web

# PowerShell:
D:\php83\php-5.6.8\php.exe -c D:\php83\php-5.6.8\php.ini -S localhost:8080 -t D:\BaiduNetdiskDownload\backed\web
```

**终端2 — Flask 前端 (端口 5000)**

```bash
cd D:\BaiduNetdiskDownload\backed
python app.py
```

**终端3 — 边缘AI (可选，仅Orange Pi 5)**

```bash
cd edge-ai
python main.py edge-run
```

### 访问地址

| 地址 | 说明 |
|------|------|
| http://localhost:5000 | 数据大屏 |
| http://localhost:5000/login | 登录页 (admin / 123456) |
| http://localhost:5000/dashboard | 管理仪表盘 |
| http://localhost:5000/health | Flask 健康检查 |
| http://localhost:8080/index.php/api/statistics/health | PHP 健康检查 |

## API 端点汇总

### 管理端 API (需 JWT)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/token` | 登录获取Token |
| GET | `/api/v1/alarm-events` | 报警列表 |
| GET | `/api/v1/alarm-events/<id>` | 报警详情 |
| PUT | `/api/v1/alarm-events/<id>/process` | 处理/审核报警 |
| GET/POST/PUT/DELETE | `/api/v1/cloudboxes` | AI云盒 CRUD |
| GET/POST/PUT/DELETE | `/api/v1/cameras` | 摄像头 CRUD |
| GET | `/api/v1/statistics/*` | 统计分析 |

### 边缘设备 API (需 X-API-Key)

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/detect/alarm` | 报警事件上报 | X-API-Key |
| POST | `/api/detect/upload` | 视频文件上传 | X-API-Key |
| POST | `/api/device/heartbeat` | 设备心跳保活 | X-API-Key |
| POST | `/api/device/error` | 设备故障上报 | X-API-Key |

**边缘API密钥**: `flame-edge-2026-secure-key` (通过 `X-API-Key` 请求头传递)

## 快速验证

```bash
# 1. 登录
python -c "import requests; r=requests.post('http://localhost:5000/api/v1/token',json={'username':'admin','password':'123456'}); print(r.json()['code'])"

# 2. 边缘报警 (需密钥)
python -c "import requests; r=requests.post('http://localhost:5000/api/detect/alarm',json={'device_id':1,'camera_id':1,'event_type':'fire','confidence':0.95},headers={'X-API-Key':'flame-edge-2026-secure-key'}); print(r.status_code)"

# 3. 无密钥应被拒绝
python -c "import requests; r=requests.post('http://localhost:5000/api/detect/alarm',json={'device_id':1}); print(r.status_code)"
```

预期输出: `200` → `201` → `401`

## 关键技术指标

| 指标 | 目标 | 实际 |
|------|------|------|
| AI识别率 (mAP@50) | ≥90% | 90.63% |
| 模型大小 | <10MB | 5.48MB |
| 推理时延 | ≤2s | 45ms (NPU) |
| 定位误差 | ≤200m | 依赖标定精度 |
| 误报率 (经时域滤波) | <5% | 通过5帧3投票降至~0.7% |
| 并发摄像头 | 30路 | — |

## 数据库表 (15张)

`T_Site` `T_Role` `T_Authority` `T_UserRole` `T_Dictionary` `T_Branch` `T_Area` `T_User` `T_Device` `T_Camera` `T_DetectResult` `T_CameraError` `T_DeviceError` `T_OperateLog` `T_AccessLog`

## 安全设计

| 层级 | 机制 |
|------|------|
| Flask 代理层 | X-API-Key 共享密钥 (边缘API) |
| PHP API 层 | JWT (管理API) / device_id+MAC 验证 (边缘API) |
| 数据库 | bcrypt 密码哈希 |
| 传输 | CORS 白名单、X-Frame-Options、X-Content-Type-Options |

## 里程碑

| 阶段 | 内容 | 分支 |
|------|------|------|
| M1-M4 | 数据库设计、基础API、文档导出、WebService | `backend/wangyonglin` |
| M5 | 安全加固 + 前端页面 | `fusion/backend-frontend` |
| M6 | B+C 前后端融合 (Flask↔PHP桥接) | `fusion/backend-frontend` |
| **M7** | **A+B+C 三方融合 (边缘AI集成)** | **`fusion/abc-integration`** ← 当前 |

---

> 开发环境: Windows 11 · Python 3.13 · PHP 5.6.8 · MySQL 8.0 · Redis · CodeIgniter 3 · Flask 3.1
