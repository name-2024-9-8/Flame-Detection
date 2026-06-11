-- ============================================
-- 数据库备份与运维策略
--
-- @author    王永林
-- @studentId 12303070414
-- @created   2026-06-11
-- @modified  2026-06-11
-- @task      人员B — 阶段5 服务器部署与运维：云数据库主备切换与灾难恢复
-- ============================================

-- ── 1. 创建备份专用用户（最小权限原则）──
-- CREATE USER 'backup_user'@'localhost' IDENTIFIED BY 'Backup@Pass2026';
-- GRANT SELECT, LOCK TABLES, SHOW VIEW, EVENT, TRIGGER ON flame_detection.* TO 'backup_user'@'localhost';
-- FLUSH PRIVILEGES;

-- ── 2. 备份脚本（Windows PowerShell）──
-- # daily_backup.ps1
-- $DATE = Get-Date -Format "yyyyMMdd_HHmmss"
-- $BACKUP_DIR = "D:\backups\mysql"
-- New-Item -ItemType Directory -Force -Path $BACKUP_DIR
-- Set-Location "D:\MySQL\MySQL Server 8.0\bin"
-- .\mysqldump.exe -u backup_user -pBackup@Pass2026 --single-transaction --routines --triggers --events flame_detection > "$BACKUP_DIR\flame_detection_$DATE.sql"
-- # 保留最近7天，删除过期备份
-- Get-ChildItem $BACKUP_DIR -Filter "*.sql" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item

-- ── 3. 主备切换（MySQL 8.0 InnoDB Cluster）──
-- 开发环境为单机模式，生产部署时启用：
-- ALTER INSTANCE ADD MEMBER 'slave_node_ip:3306';
-- SELECT * FROM performance_schema.replication_group_members;

-- ── 4. 启动事件调度器 + 定时清理90天前已审核报警 ──
SET GLOBAL event_scheduler = ON;

DROP EVENT IF EXISTS evt_clean_old_alarms;
CREATE EVENT evt_clean_old_alarms
ON SCHEDULE EVERY 7 DAY
DO
    UPDATE T_DetectResult
    SET Remark = CONCAT(IFNULL(Remark,''), ' [ARCHIVED ', NOW(), ']'),
        IsRead = 1
    WHERE Status = '3'
      AND CreatTime < DATE_SUB(NOW(), INTERVAL 90 DAY)
      AND Remark NOT LIKE '%ARCHIVED%';

-- ── 5. 索引优化（面向海量事件数据的快速筛选）──
ALTER TABLE T_DetectResult ADD INDEX idx_area_status_time (AreaId, Status, CreatTime);
ALTER TABLE T_OperateLog ADD INDEX idx_time (CreateTime);
ALTER TABLE T_AccessLog ADD INDEX idx_user_time (UserId, CreateTime);
ALTER TABLE T_Device ADD INDEX idx_mac (MAC);
ALTER TABLE T_Camera ADD INDEX idx_device (DeviceId);

-- ── 6. 防火墙规则（参考，由运维配置）──
-- 仅开放 80/443（Web）, 3306 仅允许内网访问, 6379 仅允许本机访问
-- Windows: netsh advfirewall firewall add rule name="Allow HTTP" dir=in action=allow protocol=TCP localport=80,443
