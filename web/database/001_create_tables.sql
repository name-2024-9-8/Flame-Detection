-- ============================================
-- 视频AI智能识别及预警管理系统 — 数据库建表
-- 基于数据库设计文档修正版本（15张表）
--
-- @author    王永林
-- @studentId 12303070414
-- @created   2026-06-11
-- @modified  2026-06-11
-- @task      人员B — 阶段1 数据库整体设计/建表/索引优化
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
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('DeviceType',   '摄像头型号A');
INSERT INTO T_Dictionary (`Key`, `Value`) VALUES ('DeviceType',   '摄像头型号B');
