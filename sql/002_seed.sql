-- ============================================
-- 视频AI智能识别及预警管理系统 — 初始种子数据
--
-- 使用说明：
--   先执行 001_schema.sql 建表，再执行本文件导入种子数据
--   mysql -u root -p flame_detection < 002_seed.sql
-- ============================================

USE flame_detection;

-- ============================================
-- 1. 默认角色
-- ============================================
INSERT INTO T_Role (Name, Description) VALUES ('超级管理员', '系统最高权限');
INSERT INTO T_Role (Name, Description) VALUES ('普通用户',   '查看和处理报警事件');

-- ============================================
-- 2. 默认管理员（密码 123456，bcrypt 哈希加密）
--    RoleId=1 → 超级管理员
-- ============================================
INSERT INTO T_User (Account, Name, Password) VALUES ('admin', '管理员', '$2y$10$7QnEoGsR8POwiIekEtlIIu/ZGCatuhYt8p1yfFGjMq8nfu34Szikm');
INSERT INTO T_UserRole (UserId, RoleId) VALUES (1, 1);

-- ============================================
-- 3. 系统默认配置
-- ============================================
INSERT INTO T_Site (thresh, width, height, video_times, heartBeat, exception_times)
VALUES (0.6, 640, 480, 5, 24, 10);

-- ============================================
-- 4. 数据字典
-- ============================================
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('EventType',   'fire');
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('EventType',   'smoke');
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('UrgencyDegree','紧急');
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('UrgencyDegree','重要');
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('UrgencyDegree','一般');
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('UrgencyDegree','提示');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('DeviceType',   '摄像头型号A', NULL);
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('DeviceType',   '摄像头型号B', NULL);

-- ============================================
-- 5. 区域
-- ============================================
INSERT INTO T_Area (Name, Remark) VALUES ('主厂区', '主要生产区域');
INSERT INTO T_Area (Name, Remark) VALUES ('仓库区', '仓储物流区域');

-- ============================================
-- 6. 部门
-- ============================================
INSERT INTO T_Branch (Name, ParentId, LeaderId, CreateTime, CreateBy, Remark)
VALUES ('技术部', 0, 1, NOW(), 1, '负责系统运维与技术管理');
INSERT INTO T_Branch (Name, ParentId, LeaderId, CreateTime, CreateBy, Remark)
VALUES ('安保部', 0, 1, NOW(), 1, '负责安全监控与应急响应');

-- ============================================
-- 7. 普通用户（密码 123456，与管理员同密码）
-- ============================================
INSERT INTO T_User (Account, Name, Password, Email, Phone, AreaId, BranchId, CreateTime, CreateBy, Remark)
VALUES ('chuli001', '处理员小张', '$2y$10$7QnEoGsR8POwiIekEtlIIu/ZGCatuhYt8p1yfFGjMq8nfu34Szikm',
        'chuli@firealarm.com', '13800138001', 1, 1, NOW(), 1, '技术部员工');
INSERT INTO T_User (Account, Name, Password, Email, Phone, AreaId, BranchId, CreateTime, CreateBy, Remark)
VALUES ('zhangsan', '张三', '$2y$10$7QnEoGsR8POwiIekEtlIIu/ZGCatuhYt8p1yfFGjMq8nfu34Szikm',
        'zhangsan@example.com', '13800138002', 2, 2, NOW(), 1, '安保部员工');

-- 分配角色（用户ID从2开始，因为1是admin）
INSERT INTO T_UserRole (UserId, RoleId) VALUES (2, 2);
INSERT INTO T_UserRole (UserId, RoleId) VALUES (3, 2);

-- ============================================
-- 8. 权限
-- ============================================

-- 超级管理员全权限（RoleId=1）
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'system:config');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'system:department');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'system:user');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'system:role');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'system:datadict');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'device:cloudbox');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'device:camera');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'device:view');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'alarm:event');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'alarm:review');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'alarm:camera_fault');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'alarm:cloudbox_fault');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'log:access');
INSERT INTO T_Authority (RoleId, Authority) VALUES (1, 'log:operation');

-- 普通用户权限（只读，RoleId=2）
INSERT INTO T_Authority (RoleId, Authority) VALUES (2, 'device:view');
INSERT INTO T_Authority (RoleId, Authority) VALUES (2, 'alarm:event');
INSERT INTO T_Authority (RoleId, Authority) VALUES (2, 'alarm:review');

-- ============================================
-- 9. AI分析盒设备
-- ============================================
INSERT INTO T_Device (MAC, Longitude, Latitude, Address, AreaId, ModelPerson, ModelInfo, Maintainer, CreateTime, StructuralInfo, DetailInfo)
VALUES ('AA:BB:CC:DD:EE:01', '116.397428', '39.909204', '主厂区1号监控室', 1, '王工', 'RK3399 Pro D', '王工', NOW(), 'ARM Cortex-A72 + NPU', '主厂区边缘AI分析盒');
INSERT INTO T_Device (MAC, Longitude, Latitude, Address, AreaId, ModelPerson, ModelInfo, Maintainer, CreateTime, StructuralInfo, DetailInfo)
VALUES ('AA:BB:CC:DD:EE:02', '116.398500', '39.908500', '仓库区入口', 2, '赵工', 'RK3399 Pro D', '赵工', NOW(), 'ARM Cortex-A72 + NPU', '仓库区边缘AI分析盒');

-- ============================================
-- 10. 摄像头
-- ============================================
INSERT INTO T_Camera (IP, MAC, CameraUrl, Name, Longitude, Latitude, AreaId, Type, InstallTime, Maintainer, DeviceId, Remark)
VALUES ('192.168.1.101', 'CAM:MAC:00:00:01', 'rtsp://192.168.1.101:554/stream1', '主厂区1号摄像头', '116.397428', '39.909204', 1, '摄像头型号A', NOW(), '王工', 1, '主厂区火焰监控');
INSERT INTO T_Camera (IP, MAC, CameraUrl, Name, Longitude, Latitude, AreaId, Type, InstallTime, Maintainer, DeviceId, Remark)
VALUES ('192.168.1.102', 'CAM:MAC:00:00:02', 'rtsp://192.168.1.102:554/stream1', '仓库区1号摄像头', '116.398500', '39.908500', 2, '摄像头型号B', NOW(), '赵工', 2, '仓库区烟雾监控');

-- ============================================
-- 11. 补充数据字典
-- ============================================
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('CameraType', '固定摄像头', '固定安装不可转动');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('CameraType', '云台摄像头', '支持PTZ云台控制');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('DeviceType', 'RK3399 Pro D', 'Rockchip AI处理器');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('DeviceType', 'Jetson Nano', 'NVIDIA AI处理器');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('ErrorCode', '1', '网络故障');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('ErrorCode', '2', '图像质量差');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('ErrorCode', 'HEARTBEAT_LOST', '设备心跳丢失');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('UnitCode', 'SMART_CITY_001', '智慧城市平台');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('UnitCode', 'VIDEO_MONITOR_001', '视频监控平台');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('UnitCode', 'ATMOS_MONITOR_001', '大气监测平台');
