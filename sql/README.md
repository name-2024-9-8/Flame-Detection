# 数据库初始化脚本

本目录包含"视频AI智能识别及预警管理系统"的完整数据库建表与种子数据脚本。

## 数据库信息

| 项目 | 说明 |
|------|------|
| 数据库名 | `flame_detection` |
| 字符集 | `utf8mb4` / `utf8mb4_unicode_ci` |
| 引擎 | InnoDB |
| 表数量 | 15 张 |
| 推荐版本 | MySQL 8.0+ |

## 表结构一览

| 序号 | 表名 | 说明 |
|------|------|------|
| 1 | `T_Site` | 系统配置表 |
| 2 | `T_Role` | 角色定义表 |
| 3 | `T_Authority` | 角色权限表 |
| 4 | `T_UserRole` | 用户角色关联表 |
| 5 | `T_Dictionary` | 数据字典表 |
| 6 | `T_Branch` | 部门管理表 |
| 7 | `T_Area` | 区域信息表 |
| 8 | `T_User` | 用户管理表 |
| 9 | `T_Device` | AI分析盒信息表 |
| 10 | `T_Camera` | 摄像头信息表 |
| 11 | `T_DetectResult` | 检测结果/报警事件表 |
| 12 | `T_CameraError` | 摄像头故障表 |
| 13 | `T_DeviceError` | AI分析盒故障表 |
| 14 | `T_OperateLog` | 操作日志表 |
| 15 | `T_AccessLog` | 访问日志表 |

## 快速开始

### 1. 确保 MySQL 已安装并运行

```bash
mysql --version  # 确认版本 ≥ 8.0
```

### 2. 依次执行 SQL 脚本

```bash
# 步骤1：创建数据库和表结构
mysql -u root -p < sql/001_schema.sql

# 步骤2：导入初始种子数据
mysql -u root -p < sql/002_seed.sql

# 步骤3（可选）：创建性能索引和定时清理任务
mysql -u root -p < sql/003_optimization.sql
```

### 3. 验证

```sql
USE flame_detection;
SHOW TABLES;
SELECT Id, Account, Name FROM T_User;
```

## 默认账户

| 账号 | 密码 | 角色 |
|------|------|------|
| `admin` | `123456` | 超级管理员 |
| `chuli001` | `123456` | 普通用户（处理员） |
| `zhangsan` | `123456` | 普通用户（安保部） |

> **安全提示**：生产环境请立即修改默认密码！

## 系统架构说明

本项目支持两种运行模式：

- **融合模式**（`FUSION_MODE=true`）：Flask 前端通过 PHP API 连接 MySQL 数据库
- **本地模式**（`FUSION_MODE=false`）：使用 SQLite（`fire_alarm.db`），无需 MySQL

### 端口配置

PHP API 默认连接 MySQL `127.0.0.1:3306`，如果你的 MySQL 端口不同，请修改 `web/application/config/database.php`。

### 种子数据脚本（Python）

项目还提供了 Python 脚本用于直接写入种子数据：

```bash
pip install pymysql
python seed_data.py        # 基础种子数据
python add_cameras.py      # 额外摄像头（重庆示例）
python add_faulty_cameras.py  # 故障摄像头 + 报警事件
```

## 备份与运维

详见 `003_optimization.sql` 中的备份脚本和定时清理策略。
