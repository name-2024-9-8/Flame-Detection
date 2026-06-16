"""
=============================================================================
视频AI智能识别及预警管理信息系统 - 火焰识别
数据模型
作者：段林川（前端开发与质量保障工程师）
创建时间：2026-06-11
功能描述：系统全部数据库模型定义（SQLAlchemy ORM）
=============================================================================
"""
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import json

db = SQLAlchemy()


# =========================================================================
# 用户与权限模型
# =========================================================================

class Department(db.Model):
    """部门表"""
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True, comment='部门名称')
    code = db.Column(db.String(50), unique=True, comment='部门编码')
    parent_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True,
                          comment='上级部门ID')
    sort_order = db.Column(db.Integer, default=0, comment='排序号')
    status = db.Column(db.SmallInteger, default=1, comment='状态：1启用 0禁用')
    remark = db.Column(db.String(500), comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now,
                           comment='更新时间')

    # 自引用关系
    children = db.relationship('Department', backref=db.backref('parent', remote_side=[id]),
                               lazy='dynamic')
    users = db.relationship('User', backref='department', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'parent_id': self.parent_id,
            'sort_order': self.sort_order,
            'status': self.status,
            'remark': self.remark,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


class Role(db.Model):
    """角色表"""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True, comment='角色名称')
    code = db.Column(db.String(50), unique=True, comment='角色编码')
    description = db.Column(db.String(500), comment='角色描述')
    permissions = db.Column(db.Text, comment='权限JSON字符串')
    status = db.Column(db.SmallInteger, default=1, comment='状态：1启用 0禁用')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now,
                           comment='更新时间')

    users = db.relationship('User', backref='role', lazy='dynamic')

    def get_permissions(self):
        """获取权限列表"""
        if self.permissions:
            try:
                return json.loads(self.permissions)
            except json.JSONDecodeError:
                return []
        return []

    def set_permissions(self, perms):
        """设置权限列表"""
        self.permissions = json.dumps(perms, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'permissions': self.get_permissions(),
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


class User(db.Model):
    """用户表"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False, unique=True, comment='用户名')
    password_hash = db.Column(db.String(256), nullable=False, comment='密码哈希')
    real_name = db.Column(db.String(100), comment='真实姓名')
    email = db.Column(db.String(200), comment='邮箱')
    phone = db.Column(db.String(20), comment='手机号')
    avatar_url = db.Column(db.String(500), comment='头像URL')
    user_type = db.Column(db.SmallInteger, default=2, comment='用户类型：1超级用户 2普通用户')
    status = db.Column(db.SmallInteger, default=1, comment='状态：1启用 0禁用')
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True,
                              comment='所属部门ID')
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True,
                        comment='所属角色ID')
    last_login_at = db.Column(db.DateTime, comment='最后登录时间')
    last_login_ip = db.Column(db.String(50), comment='最后登录IP')
    login_count = db.Column(db.Integer, default=0, comment='登录次数')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now,
                           comment='更新时间')

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def generate_token(self, secret_key, expires_hours=24):
        """生成JWT Token"""
        payload = {
            'user_id': self.id,
            'username': self.username,
            'user_type': self.user_type,
            'exp': datetime.utcnow() + timedelta(hours=expires_hours),
            'iat': datetime.utcnow(),
        }
        return jwt.encode(payload, secret_key, algorithm='HS256')

    @staticmethod
    def verify_token(token, secret_key):
        """验证JWT Token"""
        try:
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None  # Token过期
        except jwt.InvalidTokenError:
            return None  # Token无效

    def is_admin(self):
        """是否为超级用户"""
        return self.user_type == 1

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'real_name': self.real_name,
            'email': self.email,
            'phone': self.phone,
            'avatar_url': self.avatar_url,
            'user_type': self.user_type,
            'user_type_name': '超级用户' if self.user_type == 1 else '普通用户',
            'status': self.status,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else '',
            'role_id': self.role_id,
            'role_name': self.role.name if self.role else '',
            'last_login_at': self.last_login_at.strftime('%Y-%m-%d %H:%M:%S') if self.last_login_at else None,
            'login_count': self.login_count,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


# =========================================================================
# 设备模型
# =========================================================================

class AICloudBox(db.Model):
    """AI智能云盒表（边缘计算设备 RK3399 Pro D）"""
    __tablename__ = 'ai_cloud_boxes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_code = db.Column(db.String(100), nullable=False, unique=True, comment='设备编码')
    device_name = db.Column(db.String(200), nullable=False, comment='设备名称')
    device_model = db.Column(db.String(100), default='RK3399 Pro D', comment='设备型号')
    ip_address = db.Column(db.String(50), comment='IP地址')
    mac_address = db.Column(db.String(50), comment='MAC地址')
    firmware_version = db.Column(db.String(50), comment='固件版本')
    cpu_usage = db.Column(db.Float, default=0.0, comment='CPU使用率(%)')
    memory_usage = db.Column(db.Float, default=0.0, comment='内存使用率(%)')
    storage_usage = db.Column(db.Float, default=0.0, comment='存储使用率(%)')
    npu_temperature = db.Column(db.Float, comment='NPU温度(°C)')
    status = db.Column(db.SmallInteger, default=1,
                       comment='状态：1在线 2离线 3故障 4维护中')
    last_heartbeat = db.Column(db.DateTime, comment='最后心跳时间')
    location = db.Column(db.String(500), comment='部署位置描述')
    longitude = db.Column(db.Float, comment='经度')
    latitude = db.Column(db.Float, comment='纬度')
    remark = db.Column(db.String(500), comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now,
                           comment='更新时间')

    cameras = db.relationship('Camera', backref='cloud_box', lazy='dynamic')
    faults = db.relationship('CloudBoxFault', backref='cloud_box', lazy='dynamic')

    @property
    def status_name(self):
        status_map = {1: '在线', 2: '离线', 3: '故障', 4: '维护中'}
        return status_map.get(self.status, '未知')

    @property
    def is_online(self):
        """判断是否在线（心跳超时视为离线）"""
        if self.status != 1 or not self.last_heartbeat:
            return False
        from config import Config
        threshold = Config.NETWORK_ABNORMAL_THRESHOLD
        return (datetime.now() - self.last_heartbeat).total_seconds() < threshold

    def to_dict(self):
        return {
            'id': self.id,
            'device_code': self.device_code,
            'device_name': self.device_name,
            'device_model': self.device_model,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'firmware_version': self.firmware_version,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'storage_usage': self.storage_usage,
            'npu_temperature': self.npu_temperature,
            'status': self.status,
            'status_name': self.status_name,
            'is_online': self.is_online,
            'last_heartbeat': self.last_heartbeat.strftime('%Y-%m-%d %H:%M:%S') if self.last_heartbeat else None,
            'location': self.location,
            'longitude': self.longitude,
            'latitude': self.latitude,
            'remark': self.remark,
            'camera_count': self.cameras.count(),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


class Camera(db.Model):
    """摄像头表"""
    __tablename__ = 'cameras'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_code = db.Column(db.String(100), nullable=False, unique=True, comment='设备编码')
    device_name = db.Column(db.String(200), nullable=False, comment='设备名称')
    device_model = db.Column(db.String(100), comment='设备型号')
    camera_type = db.Column(db.String(50), default='固定摄像头', comment='摄像头类型')
    rtsp_url = db.Column(db.String(500), comment='RTSP视频流地址')
    ip_address = db.Column(db.String(50), comment='IP地址')
    port = db.Column(db.Integer, default=554, comment='端口号')
    resolution = db.Column(db.String(50), default='1920x1080', comment='分辨率')
    frame_rate = db.Column(db.Integer, default=25, comment='帧率(fps)')
    ptz_support = db.Column(db.Boolean, default=False, comment='是否支持PTZ云台')
    ptz_pan = db.Column(db.Float, comment='当前水平角度(Pan)')
    ptz_tilt = db.Column(db.Float, comment='当前垂直角度(Tilt)')
    ptz_zoom = db.Column(db.Float, comment='当前变焦倍数(Zoom)')
    monitor_substance = db.Column(db.String(200), default='火焰/烟雾', comment='监测物质')
    location = db.Column(db.String(500), comment='安装位置描述')
    longitude = db.Column(db.Float, nullable=False, comment='经度')
    latitude = db.Column(db.Float, nullable=False, comment='纬度')
    altitude = db.Column(db.Float, default=0.0, comment='海拔高度(米)')
    view_range = db.Column(db.Float, default=500.0, comment='视野范围(米)')
    image_url = db.Column(db.String(500), comment='现场照片URL')
    status = db.Column(db.SmallInteger, default=1,
                       comment='状态：1正常 2离线 3故障 4维护中')
    cloud_box_id = db.Column(db.Integer, db.ForeignKey('ai_cloud_boxes.id'), nullable=True,
                             comment='关联AI云盒ID')
    last_online_at = db.Column(db.DateTime, comment='最后在线时间')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now,
                           comment='更新时间')

    alarm_events = db.relationship('AlarmEvent', backref='camera', lazy='dynamic')
    faults = db.relationship('CameraFault', backref='camera', lazy='dynamic')

    @property
    def status_name(self):
        status_map = {1: '正常', 2: '离线', 3: '故障', 4: '维护中'}
        return status_map.get(self.status, '未知')

    def to_dict(self):
        return {
            'id': self.id,
            'device_code': self.device_code,
            'device_name': self.device_name,
            'device_model': self.device_model,
            'camera_type': self.camera_type,
            'rtsp_url': self.rtsp_url,
            'ip_address': self.ip_address,
            'port': self.port,
            'resolution': self.resolution,
            'frame_rate': self.frame_rate,
            'ptz_support': self.ptz_support,
            'ptz_pan': self.ptz_pan,
            'ptz_tilt': self.ptz_tilt,
            'ptz_zoom': self.ptz_zoom,
            'monitor_substance': self.monitor_substance,
            'location': self.location,
            'longitude': self.longitude,
            'latitude': self.latitude,
            'altitude': self.altitude,
            'view_range': self.view_range,
            'image_url': self.image_url,
            'status': self.status,
            'status_name': self.status_name,
            'cloud_box_id': self.cloud_box_id,
            'cloud_box_name': self.cloud_box.device_name if self.cloud_box else '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


# =========================================================================
# 报警事件模型
# =========================================================================

class AlarmEvent(db.Model):
    """火焰报警事件表"""
    __tablename__ = 'alarm_events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_code = db.Column(db.String(100), nullable=False, unique=True, comment='事件编号')
    event_type = db.Column(db.SmallInteger, default=1,
                           comment='事件类型：1火焰报警 2烟雾报警 3设备异常')
    alarm_level = db.Column(db.SmallInteger, default=2,
                            comment='报警级别：1紧急 2重要 3一般 4提示')
    detection_confidence = db.Column(db.Float, comment='检测置信度')
    fire_area_ratio = db.Column(db.Float, comment='火焰区域占比(%)')
    bbox_x = db.Column(db.Integer, comment='检测框左上角X坐标')
    bbox_y = db.Column(db.Integer, comment='检测框左上角Y坐标')
    bbox_w = db.Column(db.Integer, comment='检测框宽度')
    bbox_h = db.Column(db.Integer, comment='检测框高度')
    longitude = db.Column(db.Float, comment='火焰发生位置经度')
    latitude = db.Column(db.Float, comment='火焰发生位置纬度')
    location_description = db.Column(db.String(500), comment='逆地址解析位置描述')
    image_url = db.Column(db.String(500), comment='取证图片URL')
    video_url = db.Column(db.String(500), comment='取证视频URL（3-5秒）')
    camera_id = db.Column(db.Integer, db.ForeignKey('cameras.id'), nullable=True,
                          comment='关联摄像头ID')
    cloud_box_id = db.Column(db.Integer, db.ForeignKey('ai_cloud_boxes.id'), nullable=True,
                             comment='关联AI云盒ID')
    process_status = db.Column(db.SmallInteger, default=1,
                               comment='处理状态：1待处理 2处理中 3已处理 4已驳回 5已关闭')
    handler_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True,
                           comment='处理人ID')
    handler_remark = db.Column(db.Text, comment='处理备注')
    handled_at = db.Column(db.DateTime, comment='处理时间')
    detected_at = db.Column(db.DateTime, default=datetime.now, comment='检测时间')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    handler = db.relationship('User', foreign_keys=[handler_id], backref='handled_events')

    @property
    def event_type_name(self):
        type_map = {1: '火焰报警', 2: '烟雾报警', 3: '设备异常'}
        return type_map.get(self.event_type, '未知')

    @property
    def alarm_level_name(self):
        level_map = {1: '紧急', 2: '重要', 3: '一般', 4: '提示'}
        return level_map.get(self.alarm_level, '未知')

    @property
    def process_status_name(self):
        status_map = {1: '待处理', 2: '处理中', 3: '已处理', 4: '已驳回', 5: '已关闭'}
        return status_map.get(self.process_status, '未知')

    def to_dict(self):
        return {
            'id': self.id,
            'event_code': self.event_code,
            'event_type': self.event_type,
            'event_type_name': self.event_type_name,
            'alarm_level': self.alarm_level,
            'alarm_level_name': self.alarm_level_name,
            'detection_confidence': self.detection_confidence,
            'fire_area_ratio': self.fire_area_ratio,
            'longitude': self.longitude,
            'latitude': self.latitude,
            'location_description': self.location_description,
            'image_url': self.image_url,
            'video_url': self.video_url,
            'camera_id': self.camera_id,
            'camera_name': self.camera.device_name if self.camera else '',
            'cloud_box_id': self.cloud_box_id,
            'cloud_box_name': self.cloud_box.device_name if self.cloud_box else '',
            'process_status': self.process_status,
            'process_status_name': self.process_status_name,
            'handler_remark': self.handler_remark,
            'detected_at': self.detected_at.strftime('%Y-%m-%d %H:%M:%S') if self.detected_at else None,
            'handled_at': self.handled_at.strftime('%Y-%m-%d %H:%M:%S') if self.handled_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


class CameraFault(db.Model):
    """摄像头故障表"""
    __tablename__ = 'camera_faults'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fault_code = db.Column(db.String(100), nullable=False, unique=True, comment='故障编号')
    camera_id = db.Column(db.Integer, db.ForeignKey('cameras.id'), nullable=False,
                          comment='摄像头ID')
    fault_type = db.Column(db.SmallInteger, comment='故障类型：1离线 2画面异常 3云台故障 4网络异常 5硬件故障 6其他')
    fault_description = db.Column(db.Text, comment='故障描述')
    fault_level = db.Column(db.SmallInteger, default=2,
                            comment='故障级别：1严重 2一般 3轻微')
    process_status = db.Column(db.SmallInteger, default=1,
                               comment='处理状态：1待处理 2处理中 3已修复 4已关闭')
    repair_description = db.Column(db.Text, comment='修复描述')
    repair_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True,
                               comment='修复人ID')
    occurred_at = db.Column(db.DateTime, default=datetime.now, comment='故障发生时间')
    repaired_at = db.Column(db.DateTime, comment='修复时间')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    repair_user = db.relationship('User', foreign_keys=[repair_user_id])

    @property
    def fault_type_name(self):
        type_map = {1: '离线', 2: '画面异常', 3: '云台故障', 4: '网络异常', 5: '硬件故障', 6: '其他'}
        return type_map.get(self.fault_type, '未知')

    def to_dict(self):
        return {
            'id': self.id,
            'fault_code': self.fault_code,
            'camera_id': self.camera_id,
            'camera_name': self.camera.device_name if self.camera else '',
            'fault_type': self.fault_type,
            'fault_type_name': self.fault_type_name,
            'fault_description': self.fault_description,
            'fault_level': self.fault_level,
            'process_status': self.process_status,
            'repair_description': self.repair_description,
            'occurred_at': self.occurred_at.strftime('%Y-%m-%d %H:%M:%S') if self.occurred_at else None,
            'repaired_at': self.repaired_at.strftime('%Y-%m-%d %H:%M:%S') if self.repaired_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


class CloudBoxFault(db.Model):
    """AI云盒故障表"""
    __tablename__ = 'cloud_box_faults'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fault_code = db.Column(db.String(100), nullable=False, unique=True, comment='故障编号')
    cloud_box_id = db.Column(db.Integer, db.ForeignKey('ai_cloud_boxes.id'), nullable=False,
                             comment='AI云盒ID')
    fault_type = db.Column(db.SmallInteger, comment='故障类型：1离线 2NPU异常 3CPU过载 4内存不足 5存储异常 6温度过高 7网络异常 8其他')
    fault_description = db.Column(db.Text, comment='故障描述')
    fault_level = db.Column(db.SmallInteger, default=2,
                            comment='故障级别：1严重 2一般 3轻微')
    process_status = db.Column(db.SmallInteger, default=1,
                               comment='处理状态：1待处理 2处理中 3已修复 4已关闭')
    repair_description = db.Column(db.Text, comment='修复描述')
    repair_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True,
                               comment='修复人ID')
    occurred_at = db.Column(db.DateTime, default=datetime.now, comment='故障发生时间')
    repaired_at = db.Column(db.DateTime, comment='修复时间')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    repair_user = db.relationship('User', foreign_keys=[repair_user_id])

    @property
    def fault_type_name(self):
        type_map = {1: '离线', 2: 'NPU异常', 3: 'CPU过载', 4: '内存不足',
                    5: '存储异常', 6: '温度过高', 7: '网络异常', 8: '其他'}
        return type_map.get(self.fault_type, '未知')

    def to_dict(self):
        return {
            'id': self.id,
            'fault_code': self.fault_code,
            'cloud_box_id': self.cloud_box_id,
            'cloud_box_name': self.cloud_box.device_name if self.cloud_box else '',
            'fault_type': self.fault_type,
            'fault_type_name': self.fault_type_name,
            'fault_description': self.fault_description,
            'fault_level': self.fault_level,
            'process_status': self.process_status,
            'repair_description': self.repair_description,
            'occurred_at': self.occurred_at.strftime('%Y-%m-%d %H:%M:%S') if self.occurred_at else None,
            'repaired_at': self.repaired_at.strftime('%Y-%m-%d %H:%M:%S') if self.repaired_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


# =========================================================================
# 日志模型
# =========================================================================

class AccessLog(db.Model):
    """访问日志表"""
    __tablename__ = 'access_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment='用户ID')
    username = db.Column(db.String(100), comment='用户名')
    ip_address = db.Column(db.String(50), comment='访问IP')
    request_method = db.Column(db.String(10), comment='请求方法')
    request_url = db.Column(db.String(500), comment='请求URL')
    request_params = db.Column(db.Text, comment='请求参数')
    response_code = db.Column(db.Integer, comment='响应状态码')
    user_agent = db.Column(db.String(500), comment='浏览器UA')
    duration_ms = db.Column(db.Integer, comment='请求耗时(毫秒)')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='访问时间')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'ip_address': self.ip_address,
            'request_method': self.request_method,
            'request_url': self.request_url,
            'request_params': self.request_params,
            'response_code': self.response_code,
            'user_agent': self.user_agent,
            'duration_ms': self.duration_ms,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


class OperationLog(db.Model):
    """操作日志表"""
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment='用户ID')
    username = db.Column(db.String(100), comment='用户名')
    operation_type = db.Column(db.String(50), comment='操作类型：CREATE/UPDATE/DELETE/LOGIN/LOGOUT/EXPORT')
    operation_module = db.Column(db.String(100), comment='操作模块')
    operation_desc = db.Column(db.Text, comment='操作描述')
    target_table = db.Column(db.String(100), comment='目标数据表')
    target_id = db.Column(db.Integer, comment='目标记录ID')
    old_data = db.Column(db.Text, comment='操作前数据JSON')
    new_data = db.Column(db.Text, comment='操作后数据JSON')
    ip_address = db.Column(db.String(50), comment='操作IP')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='操作时间')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'operation_type': self.operation_type,
            'operation_module': self.operation_module,
            'operation_desc': self.operation_desc,
            'target_table': self.target_table,
            'target_id': self.target_id,
            'ip_address': self.ip_address,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }


# =========================================================================
# 数据字典模型
# =========================================================================

class DataDict(db.Model):
    """数据字典表"""
    __tablename__ = 'data_dicts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dict_type = db.Column(db.String(100), nullable=False, comment='字典类型')
    dict_label = db.Column(db.String(200), nullable=False, comment='字典标签')
    dict_value = db.Column(db.String(100), nullable=False, comment='字典值')
    sort_order = db.Column(db.Integer, default=0, comment='排序号')
    status = db.Column(db.SmallInteger, default=1, comment='状态：1启用 0禁用')
    remark = db.Column(db.String(500), comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now,
                           comment='更新时间')

    def to_dict(self):
        return {
            'id': self.id,
            'dict_type': self.dict_type,
            'dict_label': self.dict_label,
            'dict_value': self.dict_value,
            'sort_order': self.sort_order,
            'status': self.status,
            'remark': self.remark,
        }


# =========================================================================
# 系统配置模型
# =========================================================================

class SystemConfig(db.Model):
    """系统配置表"""
    __tablename__ = 'system_configs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_key = db.Column(db.String(100), nullable=False, unique=True, comment='配置键')
    config_value = db.Column(db.Text, comment='配置值')
    config_type = db.Column(db.String(50), default='string', comment='配置类型：string/int/float/bool/json')
    description = db.Column(db.String(500), comment='配置说明')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now,
                           comment='更新时间')

    def to_dict(self):
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'config_type': self.config_type,
            'description': self.description,
        }
