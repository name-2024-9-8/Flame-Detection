# 视频AI智能识别及预警管理信息系统 — 火焰识别

## FlameDetection 1.1 (combined_system 融合版)

> 计算机视觉 · 边缘计算 · GIS 可视化 · 全链路闭环  
> YOLO11 + Orange Pi 5 + Flask + PHP + MySQL  
> 重庆理工大学 · 综合课程设计 III  

---

## 👥 项目成员

| 角色 | 姓名 | 学号 | 负责模块 |
|------|------|------|----------|
| **组长（人员A）** | 郭俊奇 | 12303070411 | AI 边缘检测 — YOLO11 训练、ONNX/RKNN 转换、Orange Pi 5 NPU 部署 |
| **组员（人员B）** | 王永林 | 12303070414 | PHP 后端 API + MySQL 数据库 — CodeIgniter 3 / php_alt_server.py |
| **组员（人员C）** | 段林川 | 12309040309 | Flask Web 前端 — GIS 大屏、管理后台、API 桥接层 |

📅 **创建时间**：2026 年 6 月 11 日  
📅 **上传时间**：2026 年 7 月 9 日  
📋 **当前分支**：`edge-deploy-full`  

---

## 🧠 项目简介

**视频AI火焰识别预警系统**是一套完整的 **"边缘 AI 检测 + Web 可视化管理"** 全链路解决方案。系统通过 Orange Pi 5（RK3588S）边缘设备运行 YOLO11-nano 模型，对 RTSP 监控摄像头视频流进行实时火焰和烟雾检测，检测到火情后自动推送报警数据（含检测截图、取证视频、GPS 坐标）至 Web 管理平台。

Web 管理平台基于 **Flask + Bootstrap 5 + 高德地图 JSAPI 2.0 + ECharts 5** 构建，提供 GIS 数据大屏、管理仪表盘、报警事件全流程管理、设备管理、用户权限管理和日志审计等完整的可视化功能。

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────┐
│              客户端 (Browser / 大屏)                │
│    Bootstrap 5 · ECharts 5 · 高德JSAPI 2.0         │
├──────────────────────────────────────────────────┤
│         Web 服务层 Flask :5000 (段林川)             │
│   auth_bp · main_bp · api_bp · detect_bp           │
│   api_bridge.py (JWT 线程安全桥接层)                │
├──────────────────────────────────────────────────┤
│      API 服务层 PHP/Python :8080 (王永林)          │
│   JWT 认证 · CRUD API · 30+ REST 端点              │
├──────────────────────────────────────────────────┤
│      数据存储 MySQL :3306 + 文件系统                │
│   15 张表 · 检测图片 · 取证视频 · 日志              │
└──────────────────────────────────────────────────┘
         ↑ HTTP POST (报警/心跳/故障)
┌──────────────────────────────────────────────────┐
│   边缘计算层 Orange Pi 5 RK3588S (郭俊奇)          │
│   YOLO11-nano · ONNX/RKNN · 6 TOPS NPU            │
│   RTSP 视频流 → 去雾+CLAHE → 推理 → 报警推送       │
└──────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| Web 框架 | Flask | 3.1.0 |
| 前端 UI | Bootstrap 5 | 5.3.x |
| 图表库 | ECharts | 5.5.x |
| 地图 API | 高德 JSAPI | 2.0 |
| 模板引擎 | Jinja2 | 3.1.x |
| API 桥接 | Python Requests + PyJWT | - |
| 后端框架 | CodeIgniter 3 / php_alt_server.py | - |
| 数据库 | MySQL | 8.0 |
| AI 模型 | YOLO11-nano | ultralytics 8.3 |
| 推理引擎 | ONNX Runtime / RKNN | - |
| 边缘硬件 | Orange Pi 5 (RK3588S NPU 6TOPS) | - |

---

## 📸 系统界面展示

### GIS 数据大屏（主页）

高德地图 3D 视图，实时标注摄像头位置和火情报警点位。点击火焰标记弹出信息窗口，展示**检测图片、取证视频、报警级别、置信度**等关键信息。

![GIS数据大屏](报告模板/截图或图片/02_GIS数据大屏.png)

### 管理仪表盘

ECharts 图表展示 30 天报警趋势、区域分布、设备状态，提供系统运行一站式数据概览。

![管理仪表盘](报告模板/截图或图片/03_管理仪表盘.png)

### 报警详情页 — 火焰检测图片与取证视频

每条报警事件包含完整的 **AI 火焰检测截图 + 3-5 秒取证视频 + GPS 定位信息**，支持从 GIS 大屏一键跳转查看。

![报警详情页](报告模板/截图或图片/05_报警详情页.png)

### 报警事件管理

多条件筛选（事件类型/报警级别/处理状态）、分页列表、详情弹窗（含检测图片和视频播放）、审核处理全流程。

![报警事件管理](报告模板/截图或图片/04_报警事件管理.png)

### 更多页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 登录页 | `/login` | JWT + Session 双认证 |
| 报警审核 | `/alarm/review` | 待处理事件集中审核 |
| 摄像头管理 | `/device/camera` | 摄像头 CRUD，RTSP 地址配置 |
| 云盒管理 | `/device/cloudbox` | AI 分析盒 CRUD，心跳监控 |
| 用户管理 | `/system/user` | 用户 CRUD，角色分配 |
| 角色管理 | `/system/role` | 角色定义，权限配置 |
| 部门管理 | `/system/department` | 部门树形结构 |
| 系统配置 | `/system/config` | 检测阈值，视频参数 |
| 数据字典 | `/system/datadict` | 枚举值动态维护 |
| 访问日志 | `/log/access` | HTTP 请求全记录 |
| 操作日志 | `/log/operation` | 业务操作留痕，变更前后对比 |

<details>
<summary>📸 点击展开更多界面截图</summary>

### 登录页面
![登录页面](报告模板/截图或图片/01_登录页面.png)

### 报警审核页
![报警审核页](报告模板/截图或图片/08_报警审核页.png)

### 摄像头管理
![摄像头管理](报告模板/截图或图片/06_摄像头管理.png)

### 云盒设备管理
![云盒设备管理](报告模板/截图或图片/07_云盒设备管理.png)

### 系统配置
![系统配置](报告模板/截图或图片/09_系统配置页.png)

### 用户管理
![用户管理](报告模板/截图或图片/10_用户管理页.png)

### 故障管理
![摄像头故障](报告模板/截图或图片/11_故障摄像头.png)
![云盒故障](报告模板/截图或图片/17_故障云盒.png)

### 日志审计
![访问日志](报告模板/截图或图片/14_访问日志.png)
![操作日志](报告模板/截图或图片/13_操作日志.png)

</details>

---

## 🔥 报警事件全流程闭环

```
摄像头 RTSP 视频流
    │
    ▼
YOLO11-nano ONNX/NPU 推理 (Orange Pi 5)
    │
    ▼
火焰/烟雾检测触发 (Confidence > 0.85)
    │
    ▼
边缘设备数据打包 (Base64 图片 + 视频 + GPS)
    │
    ▼
HTTP POST → Flask /api/detect/alarm
    │
    ▼
PHP API → MySQL T_DetectResult 表
    │
    ▼
GIS 大屏实时展示 + 报警列表更新
    │
    ▼
管理员审核处理 (确认/驳回/关闭) + 操作留痕
```

---

## 🗄️ 数据库设计

系统含 **15 张 MySQL 数据表**，覆盖设备、用户、报警、故障、日志等全方位业务需求。

![数据库ER图](报告模板/截图或图片/diagram_数据库ER图.png)

核心表：`T_User`（用户）· `T_Role`（角色）· `T_UserRole`（用户角色）· `T_Camera`（摄像头）· `T_Device`（AI 分析盒）· `T_DetectResult`（检测结果）· `T_CameraError`· `T_DeviceError`· `T_OperateLog`· `T_AccessLog`· `T_Branch`（部门）· `T_Area`（区域）· `T_Site`（系统配置）· `T_Dictionary`（字典）· `T_Authority`（权限）

---

## 🚀 快速启动

### 环境要求

- Python 3.10+
- MySQL 8.0+

### 1. 克隆仓库

```bash
git clone git@github.com:duanlinchuan/combined_system.git
cd combined_system
```

### 2. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
# .venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
export MYSQL_PASSWORD=your_password    # 设置MySQL密码环境变量
mysql -u root -p < sql/001_schema.sql  # 建表
mysql -u root -p < sql/002_seed.sql    # 种子数据
```

### 4. 启动后端 API 服务

```bash
python php_alt_server.py    # 端口 8080
```

### 5. 启动 Web 前端

```bash
python run.py web            # 端口 5000
```

### 6. 访问系统

浏览器打开 **http://127.0.0.1:5000**

| 账号 | 密码 | 角色 |
|------|------|------|
| `admin` | `123456` | 超级管理员（全部权限） |
| `chuli001` | `123456` | 普通操作员（查看+处理报警） |

---

## 📁 项目结构

```
combined_system/
├── app.py                  # Flask 应用工厂入口
├── run.py                  # 统一启动入口 (web/detection)
├── config.py               # 系统配置（三套环境）
├── api_bridge.py           # ★ API 桥接层（JWT 线程安全）
├── php_alt_server.py       # Python 版 PHP API 替代服务器
├── mock_api_server.py      # Mock API 服务器（无 MySQL 演示用）
├── requirements.txt        # Python 依赖
├── yolo11n.pt              # YOLO11-nano 模型权重 (5.6MB)
│
├── routes/                 # Flask Blueprint 路由
│   ├── auth.py             # 认证路由
│   ├── main.py             # 页面路由
│   ├── api.py              # RESTful API 路由
│   └── detect.py           # 边缘设备通信路由
│
├── templates/              # Jinja2 模板
│   ├── base.html           # 基模板
│   ├── index.html          # GIS 数据大屏
│   ├── login.html          # 登录页
│   ├── alarm/              # 报警管理模板
│   ├── device/             # 设备管理模板
│   └── system/             # 系统管理模板
│
├── static/                 # 静态资源
│   ├── lib/                # Bootstrap/ECharts/LayUI
│   ├── uploads/alarms/     # 检测图片与视频存储
│   └── videos/             # 测试视频
│
├── detection/              # AI 检测模块（郭俊奇）
│   ├── main.py             # 检测命令入口
│   └── edge/               # 边缘端推理管线
│
├── sql/                    # 数据库脚本（15张表）
│
├── 报告模板/               # 课程设计报告
│   ├── 课程设计报告.doc     # Word 格式
│   ├── 课程设计报告.pdf     # PDF 格式
│   └── 截图或图片/          # 28 张截图与设计图
│
└── screenshots/            # 项目演示截图
```

---

## 📊 性能指标

| 指标 | 目标 | 实测 |
|------|------|------|
| 火焰识别率 | ≥ 90% | **95%+** |
| 烟雾识别率 | ≥ 85% | **88%+** |
| 误报率 | < 5% | **< 3%** (时序滤波后) |
| 单帧推理速度 (NPU) | < 100ms | **≈18ms** |
| 报警推送延迟 | ≤ 2秒 | **< 1.5秒** |
| Web 首屏加载 | < 3秒 | **< 2秒** |

---

## 🔑 关键设计

### API 桥接层 (api_bridge.py)

- **线程安全**：`threading.Lock` 保护 JWT Token 读写
- **统一代理**：`_get()` / `_post()` 封装所有 PHP API 调用
- **数据映射**：自动转换 PHP PascalCase → 前端 camelCase
- **融合模式**：`FUSION_MODE` 环境变量切换 PHP API / 本地降级

### 边缘设备通信

- **报警推送**：HTTP POST `/api/detect/alarm`（Base64 图片 + 视频 + GPS）
- **心跳机制**：30 秒间隔，监控设备在线状态
- **故障上报**：网络断开、图像质量差等故障自动检测上报

---

## 🙏 致谢

- YOLO11: [Ultralytics](https://github.com/ultralytics/ultralytics)
- 高德地图 JSAPI: [高德开放平台](https://lbs.amap.com/)
- Orange Pi 5: [Orange Pi](http://www.orangepi.org/)
