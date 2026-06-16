-- ============================================
-- 视频AI智能识别及预警管理系统 — 数据库建表
-- 基于数据库设计文档修正版本（15张表）
--
-- @author    王永林
-- @studentId 12303070414
-- @created   2026-06-11
-- @modified  2026-06-11
-- @task      王永林 — 阶段1 数据库整体设计/建表/索引优化
-- ============================================
--
-- 修正说明：
-- 1. T_User 新增 Email, Phone 字段（支撑邮件/短信/微信通知）
-- 2. T_DetectResult 新增 EventType, Confidence 字段（支撑AI模型输出）
-- 3. 新增 T_AccessLog 访问日志表（与操作日志分离）
-- 4. T_Branch 补全 LeaderId 字段（原设计缺失）
-- 5. T_CameraError MAC 改为 CameraIP（修正字段名与含义不一致）
-- 6. T_DeviceError 表名修正（原设计文档误写为 T_DevicesError）
-- ============================================

CREATE DATABASE IF NOT EXISTS flame_detection
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE flame_detection;

-- ============================================
-- 1. 站点/系统配置表 T_Site
-- ============================================
CREATE TABLE T_Site (
    Id              INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '系统ID',
    thresh          FLOAT           NULL                     COMMENT '烟雾检测的conf阈值',
    width           FLOAT           NULL                     COMMENT '返回的图片和视频的长',
    height          FLOAT           NULL                     COMMENT '返回的图片和视频的宽',
    video_times     FLOAT           NULL                     COMMENT '返回视频的秒数',
    heartBeat       FLOAT           NULL                     COMMENT '板子连接心跳时间（小时）',
    exception_times FLOAT           NULL                     COMMENT '网络异常误差（分钟）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置表';


-- ============================================
-- 2. 角色表 T_Role
-- ============================================
CREATE TABLE T_Role (
    Id          INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '角色ID',
    Name        VARCHAR(20)    NULL                     COMMENT '角色名',
    Description VARCHAR(100)   NULL                     COMMENT '角色描述',
    IsDelete    BIT             NULL DEFAULT 0           COMMENT '删除标记'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色定义表';


-- ============================================
-- 3. 角色权限表 T_Authority
-- ============================================
CREATE TABLE T_Authority (
    Id        INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '权限ID',
    RoleId    INT             NOT NULL                 COMMENT '角色ID',
    Authority VARCHAR(50)    NULL                     COMMENT '权限值',
    CONSTRAINT FK_Authority_Role FOREIGN KEY (RoleId) REFERENCES T_Role(Id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色权限表';


-- ============================================
-- 4. 用户角色关联表 T_UserRole
-- ============================================
CREATE TABLE T_UserRole (
    Id      INT     NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '关联ID',
    UserId  INT     NOT NULL                 COMMENT '用户ID',
    RoleId  INT     NOT NULL                 COMMENT '角色ID',
    CONSTRAINT FK_UserRole_Role FOREIGN KEY (RoleId) REFERENCES T_Role(Id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户角色对应表';


-- ============================================
-- 5. 数据字典表 T_Dictionary
-- ============================================
CREATE TABLE T_Dictionary (
    Id      BIGINT          NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '字典ID',
    `Key`   VARCHAR(20)    NULL                     COMMENT '选项名（设备类型、性别等），用英文',
    `Value` VARCHAR(20)    NULL                     COMMENT '可选项',
    Remark  TEXT            NULL                     COMMENT '备注'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据字典表';


-- ============================================
-- 6. 部门表 T_Branch
-- ============================================
CREATE TABLE T_Branch (
    Id          INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '部门ID',
    Name        VARCHAR(50)    NULL                     COMMENT '部门名称',
    ParentId    INT             NULL DEFAULT 0           COMMENT '父节点ID',
    LeaderId    INT             NULL                     COMMENT '部门负责人ID',
    CreateTime  DATETIME        NULL                     COMMENT '创建时间',
    CreateBy    INT             NULL                     COMMENT '创建人',
    Remark      TEXT   NULL                     COMMENT '备注'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门管理表';


-- ============================================
-- 7. 区域表 T_Area
-- ============================================
CREATE TABLE T_Area (
    Id      INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '区域ID',
    Name    VARCHAR(50)    NULL                     COMMENT '区域名称',
    Remark  TEXT   NULL                     COMMENT '备注'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='区域信息表';


-- ============================================
-- 8. 用户表 T_User
-- ============================================
CREATE TABLE T_User (
    Id          INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '用户ID',
    Account     VARCHAR(50)    NOT NULL                 COMMENT '账号',
    Name        VARCHAR(50)    NULL                     COMMENT '姓名',
    Password    VARCHAR(255)   NOT NULL                 COMMENT '密码（加密存储）',
    Email       VARCHAR(100)   NULL                     COMMENT '邮箱（邮件通知）',
    Phone       VARCHAR(20)    NULL                     COMMENT '手机号（短信/微信通知）',
    AreaId      INT             NULL                     COMMENT '地区ID',
    BranchId    INT             NULL                     COMMENT '所属部门ID',
    CreateTime  DATETIME        NULL                     COMMENT '创建时间',
    CreateBy    INT             NULL                     COMMENT '创建人',
    IsDelete    BIT             NULL DEFAULT 0           COMMENT '删除标记',
    Remark      TEXT   NULL                     COMMENT '备注',
    CONSTRAINT FK_User_Branch  FOREIGN KEY (BranchId) REFERENCES T_Branch(Id),
    CONSTRAINT FK_User_Area    FOREIGN KEY (AreaId)   REFERENCES T_Area(Id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户管理表';

-- 补充外键（延迟添加，因为建表时 T_User 还不存在）
ALTER TABLE T_UserRole ADD CONSTRAINT FK_UserRole_User FOREIGN KEY (UserId) REFERENCES T_User(Id);
ALTER TABLE T_Branch   ADD CONSTRAINT FK_Branch_Leader  FOREIGN KEY (LeaderId) REFERENCES T_User(Id);


-- ============================================
-- 9. AI分析盒设备表 T_Device
-- ============================================
CREATE TABLE T_Device (
    Id                  INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '设备ID',
    MAC                 VARCHAR(50)    NULL                     COMMENT 'MAC地址',
    Longitude           VARCHAR(50)    NULL                     COMMENT '经度',
    Latitude            VARCHAR(50)    NULL                     COMMENT '纬度',
    Address             VARCHAR(200)   NULL                     COMMENT '置放地点',
    AreaId              INT             NULL                     COMMENT '所在区域',
    ModelPerson         VARCHAR(50)    NULL                     COMMENT '模型上板人',
    ModelInfo           VARCHAR(50)    NULL                     COMMENT '上板模型信息',
    Maintainer          VARCHAR(50)    NULL                     COMMENT '上板维护人',
    CreateTime          DATETIME        NULL                     COMMENT '上板时间',
    StructuralInfo      VARCHAR(200)   NULL                     COMMENT '架构信息',
    DetailInfo          VARCHAR(200)   NULL                     COMMENT '设备详细信息',
    LastConnectTime     DATETIME        NULL                     COMMENT '最后一次通信时间',
    AutoGenerateError   VARCHAR(50)    NULL                     COMMENT '是否已自动产生故障信息',
    Remark              TEXT   NULL                     COMMENT '备注',
    CONSTRAINT FK_Device_Area FOREIGN KEY (AreaId) REFERENCES T_Area(Id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI分析盒信息表';


-- ============================================
-- 10. 摄像头表 T_Camera
-- ============================================
CREATE TABLE T_Camera (
    Id          INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '摄像头ID',
    IP          VARCHAR(50)    NULL                     COMMENT 'IP地址',
    MAC         VARCHAR(50)    NULL                     COMMENT 'MAC地址',
    CameraUrl   VARCHAR(500)   NULL                     COMMENT '摄像头RTSP地址',
    Name        VARCHAR(50)    NULL                     COMMENT '摄像头名称',
    Longitude   VARCHAR(50)    NULL                     COMMENT '经度',
    Latitude    VARCHAR(50)    NULL                     COMMENT '纬度',
    AreaId      INT             NULL                     COMMENT '所在区域',
    Type        VARCHAR(50)    NULL                     COMMENT '设备型号',
    InstallTime DATETIME        NULL                     COMMENT '安装时间',
    BandWidth   FLOAT           NULL                     COMMENT '带宽信息',
    Maintainer  VARCHAR(50)    NULL                     COMMENT '设备维护人',
    DeviceId    INT             NULL                     COMMENT '绑定的AI分析盒ID',
    Remark      TEXT   NULL                     COMMENT '备注',
    CONSTRAINT FK_Camera_Area   FOREIGN KEY (AreaId)   REFERENCES T_Area(Id),
    CONSTRAINT FK_Camera_Device FOREIGN KEY (DeviceId) REFERENCES T_Device(Id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='摄像头信息表';


-- ============================================
-- 11. 检测结果/报警事件表 T_DetectResult
-- ============================================
CREATE TABLE T_DetectResult (
    Id              INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '事件ID',
    EventType       VARCHAR(50)    NULL                     COMMENT '事件类型（fire火焰/smoke烟雾）',
    Confidence      FLOAT           NULL                     COMMENT 'AI识别置信度（0~1）',
    Longitude       VARCHAR(50)    NULL                     COMMENT '经度',
    Latitude        VARCHAR(50)    NULL                     COMMENT '纬度',
    Location        VARCHAR(200)   NULL                     COMMENT '报警地点（逆地址解析）',
    Picture         VARCHAR(200)   NULL                     COMMENT '取证图片地址',
    VideoUrl        VARCHAR(200)   NULL                     COMMENT '取证视频地址',
    AreaId          INT             NULL                     COMMENT '所在区域',
    CreatTime       DATETIME        NULL                     COMMENT '报警时间',
    CameraId        INT             NULL                     COMMENT '对应摄像头ID',
    DeviceId        INT             NULL                     COMMENT '对应边缘设备ID',
    Status          VARCHAR(50)    NULL DEFAULT '1'         COMMENT '状态：1报警、2待审核、3已审核',
    OperateUserId   INT             NULL                     COMMENT '处理人',
    OperateTime     DATETIME        NULL                     COMMENT '处理时间',
    UrgencyDegree   VARCHAR(50)    NULL                     COMMENT '事件紧急程度',
    OperateResult   VARCHAR(50)    NULL                     COMMENT '处理结果',
    Description     VARCHAR(200)   NULL                     COMMENT '事件描述',
    AuditUserId     INT             NULL                     COMMENT '审核人',
    AuditTime       DATETIME        NULL                     COMMENT '审核时间',
    IsRead          BIT             NULL DEFAULT 0           COMMENT '是否已在前端展示（1展示过/0新事件）',
    Remark          TEXT   NULL                     COMMENT '备注',
    CONSTRAINT FK_Detect_Area   FOREIGN KEY (AreaId)   REFERENCES T_Area(Id),
    CONSTRAINT FK_Detect_Camera FOREIGN KEY (CameraId) REFERENCES T_Camera(Id),
    CONSTRAINT FK_Detect_Device FOREIGN KEY (DeviceId) REFERENCES T_Device(Id),
    CONSTRAINT FK_Detect_Oper   FOREIGN KEY (OperateUserId) REFERENCES T_User(Id),
    CONSTRAINT FK_Detect_Audit  FOREIGN KEY (AuditUserId)  REFERENCES T_User(Id),
    INDEX idx_detect_status (Status),
    INDEX idx_detect_time   (CreatTime),
    INDEX idx_detect_area   (AreaId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='检测结果/报警事件表';


-- ============================================
-- 12. 摄像头故障表 T_CameraError
-- ============================================
CREATE TABLE T_CameraError (
    Id          INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '故障ID',
    CameraId    INT             NOT NULL                 COMMENT '摄像头ID',
    CameraIP    VARCHAR(50)    NULL                     COMMENT '摄像头IP地址',
    CreateTime  DATETIME        NULL                     COMMENT '故障时间',
    ErrorCode   VARCHAR(50)    NULL                     COMMENT '错误标识码（1网络故障/2图像质量差）',
    ErrorMsg    VARCHAR(200)   NULL                     COMMENT '设备故障详细信息',
    Remark      TEXT   NULL                     COMMENT '备注',
    CONSTRAINT FK_CamErr_Camera FOREIGN KEY (CameraId) REFERENCES T_Camera(Id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='摄像头故障表';


-- ============================================
-- 13. AI分析盒故障表 T_DeviceError
-- ============================================
CREATE TABLE T_DeviceError (
    Id          INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '故障ID',
    DeviceId    INT             NOT NULL                 COMMENT '设备ID',
    MAC         VARCHAR(50)    NULL                     COMMENT '边缘设备MAC地址',
    CreateTime  DATETIME        NULL                     COMMENT '故障时间',
    ErrorCode   VARCHAR(50)    NULL                     COMMENT '错误标识码',
    ErrorMsg    VARCHAR(200)   NULL                     COMMENT '设备故障详细信息',
    Remark      TEXT   NULL                     COMMENT '备注',
    CONSTRAINT FK_DevErr_Device FOREIGN KEY (DeviceId) REFERENCES T_Device(Id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI分析盒故障表';


-- ============================================
-- 14. 操作日志表 T_OperateLog
-- ============================================
CREATE TABLE T_OperateLog (
    Id          INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '日志ID',
    MenuName    VARCHAR(50)    NULL                     COMMENT '功能菜单',
    Type        VARCHAR(50)    NULL                     COMMENT '操作类型（增加/修改/删除/处理/审核）',
    ContentNew  TEXT   NULL                     COMMENT '操作后内容',
    ContentOld  TEXT   NULL                     COMMENT '操作前内容',
    CreateTime  DATETIME        NULL                     COMMENT '操作时间',
    UserId      INT             NULL                     COMMENT '操作人',
    Remark      TEXT   NULL                     COMMENT '备注',
    CONSTRAINT FK_OpLog_User FOREIGN KEY (UserId) REFERENCES T_User(Id),
    INDEX idx_oplog_time (CreateTime)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='操作日志表';


-- ============================================
-- 15. 访问日志表 T_AccessLog（新增）
-- ============================================
CREATE TABLE T_AccessLog (
    Id          INT             NOT NULL AUTO_INCREMENT  PRIMARY KEY  COMMENT '日志ID',
    UserId      INT             NULL                     COMMENT '用户ID（未登录时为NULL）',
    Url         VARCHAR(500)   NULL                     COMMENT '访问URL',
    Method      VARCHAR(10)    NULL                     COMMENT '请求方法（GET/POST/PUT/DELETE）',
    IP          VARCHAR(50)    NULL                     COMMENT '客户端IP',
    UserAgent   VARCHAR(500)   NULL                     COMMENT '浏览器UserAgent',
    CreateTime  DATETIME        NULL                     COMMENT '访问时间',
    Remark      TEXT   NULL                     COMMENT '备注',
    INDEX idx_alog_time (CreateTime),
    INDEX idx_alog_user (UserId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='访问日志表';


-- ============================================
-- 初始化数据：默认角色
-- ============================================
INSERT INTO T_Role (Name, Description) VALUES ('超级管理员', '系统最高权限');
INSERT INTO T_Role (Name, Description) VALUES ('普通用户',   '查看和处理报警事件');

-- 初始化数据：默认管理员（密码 123456，bcrypt 哈希加密）
INSERT INTO T_User (Account, Name, Password) VALUES ('admin', '管理员', '$2y$10$7QnEoGsR8POwiIekEtlIIu/ZGCatuhYt8p1yfFGjMq8nfu34Szikm');
INSERT INTO T_UserRole (UserId, RoleId) VALUES (1, 1);

-- 初始化数据：系统默认配置
INSERT INTO T_Site (thresh, width, height, video_times, heartBeat, exception_times)
VALUES (0.6, 640, 480, 5, 24, 10);

-- 初始化数据：数据字典
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('EventType',   'fire');
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('EventType',   'smoke');
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('UrgencyDegree','紧急');
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('UrgencyDegree','一般');
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('UrgencyDegree','低');
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('DeviceType',   '摄像头型号A', NULL);
INSERT INTO T_Dictionary (`Key`, `Value`, `Remark`) VALUES ('DeviceType',   '摄像头型号B', NULL);

-- ============================================
-- M7融合修复：种子数据补充（区域/部门/用户/权限/设备/故障/字典）
-- ============================================

-- 区域
INSERT INTO T_Area (Name, Remark) VALUES ('主厂区', '主要生产区域');
INSERT INTO T_Area (Name, Remark) VALUES ('仓库区', '仓储物流区域');

-- 部门
INSERT INTO T_Branch (Name, ParentId, LeaderId, CreateTime, CreateBy, Remark)
VALUES ('技术部', 0, 1, NOW(), 1, '负责系统运维与技术管理');
INSERT INTO T_Branch (Name, ParentId, LeaderId, CreateTime, CreateBy, Remark)
VALUES ('安保部', 0, 1, NOW(), 1, '负责安全监控与应急响应');

-- 普通用户（密码 123456，与管理员同密码）
INSERT INTO T_User (Account, Name, Password, Email, Phone, AreaId, BranchId, CreateTime, CreateBy, Remark)
VALUES ('chuli001', '处理员小张', '$2y$10$7QnEoGsR8POwiIekEtlIIu/ZGCatuhYt8p1yfFGjMq8nfu34Szikm',
        'chuli@firealarm.com', '13800138001', 1, 1, NOW(), 1, '技术部员工');
INSERT INTO T_User (Account, Name, Password, Email, Phone, AreaId, BranchId, CreateTime, CreateBy, Remark)
VALUES ('zhangsan', '张三', '$2y$10$7QnEoGsR8POwiIekEtlIIu/ZGCatuhYt8p1yfFGjMq8nfu34Szikm',
        'zhangsan@example.com', '13800138002', 2, 2, NOW(), 1, '安保部员工');

-- 分配角色（用户ID从2开始，因为1是admin）
INSERT INTO T_UserRole (UserId, RoleId) VALUES (2, 2);
INSERT INTO T_UserRole (UserId, RoleId) VALUES (3, 2);

-- 权限（超级管理员全权限）
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

-- 普通用户权限（只读）
INSERT INTO T_Authority (RoleId, Authority) VALUES (2, 'device:view');
INSERT INTO T_Authority (RoleId, Authority) VALUES (2, 'alarm:event');
INSERT INTO T_Authority (RoleId, Authority) VALUES (2, 'alarm:review');

-- AI分析盒设备
INSERT INTO T_Device (MAC, Longitude, Latitude, Address, AreaId, ModelPerson, ModelInfo, Maintainer, CreateTime, StructuralInfo, DetailInfo)
VALUES ('AA:BB:CC:DD:EE:01', '116.397428', '39.909204', '主厂区1号监控室', 1, '王工', 'RK3399 Pro D', '王工', NOW(), 'ARM Cortex-A72 + NPU', '主厂区边缘AI分析盒');
INSERT INTO T_Device (MAC, Longitude, Latitude, Address, AreaId, ModelPerson, ModelInfo, Maintainer, CreateTime, StructuralInfo, DetailInfo)
VALUES ('AA:BB:CC:DD:EE:02', '116.398500', '39.908500', '仓库区入口', 2, '赵工', 'RK3399 Pro D', '赵工', NOW(), 'ARM Cortex-A72 + NPU', '仓库区边缘AI分析盒');

-- 摄像头
INSERT INTO T_Camera (IP, MAC, CameraUrl, Name, Longitude, Latitude, AreaId, Type, InstallTime, Maintainer, DeviceId, Remark)
VALUES ('192.168.1.101', 'CAM:MAC:00:00:01', 'rtsp://192.168.1.101:554/stream1', '主厂区1号摄像头', '116.397428', '39.909204', 1, '摄像头型号A', NOW(), '王工', 1, '主厂区火焰监控');
INSERT INTO T_Camera (IP, MAC, CameraUrl, Name, Longitude, Latitude, AreaId, Type, InstallTime, Maintainer, DeviceId, Remark)
VALUES ('192.168.1.102', 'CAM:MAC:00:00:02', 'rtsp://192.168.1.102:554/stream1', '仓库区1号摄像头', '116.398500', '39.908500', 2, '摄像头型号B', NOW(), '赵工', 2, '仓库区烟雾监控');

-- 故障记录
INSERT INTO T_CameraError (CameraId, CameraIP, CreateTime, ErrorCode, ErrorMsg, Remark)
VALUES (1, '192.168.1.101', NOW(), '1', '网络连接超时，摄像头视频流中断', '需检查交换机端口');
INSERT INTO T_CameraError (CameraId, CameraIP, CreateTime, ErrorCode, ErrorMsg, Remark)
VALUES (2, '192.168.1.102', NOW(), '2', '图像质量下降，镜头存在遮挡物', '需现场清理镜头');
INSERT INTO T_DeviceError (DeviceId, MAC, CreateTime, ErrorCode, ErrorMsg, Remark)
VALUES (1, 'AA:BB:CC:DD:EE:01', NOW(), 'HEARTBEAT_LOST', '设备心跳超时，已超过30分钟无响应', '需检查设备供电');

-- 补充数据字典
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
