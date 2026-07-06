-- ============================================
-- FlameDetection_1.1 — 补充取证视频URL和历史报警数据
-- 视频文件通过 /static/videos/VP*.mp4 访问（Flask静态文件服务）
-- ============================================

USE flame_detection;

-- ============================================
-- 1. 为现有报警事件填充取证视频URL
-- ============================================
UPDATE T_DetectResult SET Picture = '/static/videos/VP18.mp4', VideoUrl = '/static/videos/VP18.mp4' WHERE Id = 1;
UPDATE T_DetectResult SET Picture = '/static/videos/VP23.mp4', VideoUrl = '/static/videos/VP23.mp4' WHERE Id = 2;
UPDATE T_DetectResult SET Picture = '/static/videos/VP32.mp4', VideoUrl = '/static/videos/VP32.mp4' WHERE Id = 3;
UPDATE T_DetectResult SET Picture = '/static/videos/VP45.mp4', VideoUrl = '/static/videos/VP45.mp4' WHERE Id = 4;
UPDATE T_DetectResult SET Picture = '/static/videos/VP47.mp4', VideoUrl = '/static/videos/VP47.mp4' WHERE Id = 5;
UPDATE T_DetectResult SET Picture = '/static/videos/VP6.mp4',  VideoUrl = '/static/videos/VP6.mp4'  WHERE Id = 6;
UPDATE T_DetectResult SET Picture = '/static/videos/VP25.mp4', VideoUrl = '/static/videos/VP25.mp4' WHERE Id = 7;
UPDATE T_DetectResult SET Picture = '/static/videos/VP23.mp4', VideoUrl = '/static/videos/VP23.mp4' WHERE Id = 8;
UPDATE T_DetectResult SET Picture = '/static/videos/VP32.mp4', VideoUrl = '/static/videos/VP32.mp4' WHERE Id = 9;
UPDATE T_DetectResult SET Picture = '/static/videos/VP45.mp4', VideoUrl = '/static/videos/VP45.mp4' WHERE Id = 10;

-- ============================================
-- 2. 为已有报警的摄像头补充历史报警数据
--    (使摄像头标记弹窗能展示历史报警列表)
-- ============================================

-- Camera 1 (主厂区) — 新增历史报警（已处理，status=3）
INSERT INTO T_DetectResult (EventType, Confidence, Longitude, Latitude, Location, Picture, VideoUrl, CameraId, DeviceId, AreaId, Status, CreatTime, UrgencyDegree, Description)
VALUES ('fire', 0.88, '116.397428', '39.909204', '重庆市江北区解放碑商圈主街',
        '/static/videos/VP6.mp4', '/static/videos/VP6.mp4',
        1, 1, 1, '3', DATE_SUB(NOW(), INTERVAL 3 DAY), '重要',
        '火情已由消防队扑灭，AI识别火源为装修材料燃烧');

-- Camera 3 (江北嘴) — 新增历史报警（已处理，status=3）
INSERT INTO T_DetectResult (EventType, Confidence, Longitude, Latitude, Location, Picture, VideoUrl, CameraId, DeviceId, AreaId, Status, CreatTime, UrgencyDegree, Description)
VALUES ('smoke', 0.72, '106.5720', '29.5750', '重庆市江北嘴金融城B区',
        '/static/videos/VP18.mp4', '/static/videos/VP18.mp4',
        3, 1, 1, '3', DATE_SUB(NOW(), INTERVAL 5 DAY), '一般',
        '施工区域扬尘误报，经审核确认非火情，已关闭');

-- Camera 2 (仓库区) — 新增历史报警（已处理，status=3）
INSERT INTO T_DetectResult (EventType, Confidence, Longitude, Latitude, Location, Picture, VideoUrl, CameraId, DeviceId, AreaId, Status, CreatTime, UrgencyDegree, Description)
VALUES ('fire', 0.91, '116.398500', '39.908500', '重庆市渝中区仓库区通风口',
        '/static/videos/VP25.mp4', '/static/videos/VP25.mp4',
        2, 2, 2, '3', DATE_SUB(NOW(), INTERVAL 7 DAY), '紧急',
        '仓库通风口检测到明火，消防喷淋系统已启动，火情已控制');

-- Camera 4 (南滨路) — 新增历史报警（处理中，status=2）
INSERT INTO T_DetectResult (EventType, Confidence, Longitude, Latitude, Location, Picture, VideoUrl, CameraId, DeviceId, AreaId, Status, CreatTime, UrgencyDegree, Description)
VALUES ('smoke', 0.75, '106.5900', '29.5450', '重庆市南滨路观景平台',
        '/static/videos/VP47.mp4', '/static/videos/VP47.mp4',
        4, 2, 2, '2', DATE_SUB(NOW(), INTERVAL 2 DAY), '一般',
        '观景平台烧烤摊烟雾触发报警，安保人员已到场处理');

-- ============================================
-- 3. 为历史报警补充处理信息
-- ============================================
-- Check for IDs assigned by last INSERT
UPDATE T_DetectResult SET Status = '3', OperateUserId = 2, OperateTime = NOW(), OperateResult = '火情已解除，系统恢复正常', AuditUserId = 1, AuditTime = NOW() WHERE Id >= 11 AND CameraId = 1 LIMIT 1;
UPDATE T_DetectResult SET Status = '3', OperateUserId = 2, OperateTime = NOW(), OperateResult = '施工扬尘误报，关闭事件', AuditUserId = 1, AuditTime = NOW() WHERE Id >= 12 AND CameraId = 3 LIMIT 1;
UPDATE T_DetectResult SET Status = '3', OperateUserId = 2, OperateTime = NOW(), OperateResult = '消防已灭火，现场安全', AuditUserId = 1, AuditTime = NOW() WHERE Id >= 13 AND CameraId = 2 LIMIT 1;
