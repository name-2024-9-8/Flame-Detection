-- ============================================
-- 视频AI智能识别及预警管理系统 — 索引优化 & 定时任务
--
-- 使用说明：
--   在 001_schema.sql + 002_seed.sql 执行后运行
--   mysql -u root -p flame_detection < 003_optimization.sql
-- ============================================

USE flame_detection;

-- ============================================
-- 1. 性能索引（面向海量事件数据的快速筛选）
-- ============================================
ALTER TABLE T_DetectResult ADD INDEX idx_area_status_time (AreaId, Status, CreatTime);
ALTER TABLE T_OperateLog   ADD INDEX idx_time (CreateTime);
ALTER TABLE T_AccessLog    ADD INDEX idx_user_time (UserId, CreateTime);
ALTER TABLE T_Device       ADD INDEX idx_mac (MAC);
ALTER TABLE T_Camera       ADD INDEX idx_device (DeviceId);

-- ============================================
-- 2. 启动事件调度器 + 定时清理90天前已审核报警
-- ============================================
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

-- ============================================
-- 3. 备份与运维参考
-- ============================================
-- 创建备份专用用户（最小权限原则）：
--   CREATE USER 'backup_user'@'localhost' IDENTIFIED BY 'YourStrongPassword';
--   GRANT SELECT, LOCK TABLES, SHOW VIEW, EVENT, TRIGGER ON flame_detection.* TO 'backup_user'@'localhost';
--   FLUSH PRIVILEGES;
--
-- 全量备份（Linux/macOS）：
--   mysqldump -u backup_user -p --single-transaction --routines --triggers --events flame_detection > backup_$(date +%Y%m%d).sql
--
-- 全量备份（Windows PowerShell）：
--   $DATE = Get-Date -Format "yyyyMMdd_HHmmss"
--   mysqldump -u backup_user -p --single-transaction --routines --triggers --events flame_detection > "backup_$DATE.sql"
--
-- 恢复：
--   mysql -u root -p flame_detection < backup_20260706.sql
