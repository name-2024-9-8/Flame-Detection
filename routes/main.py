"""
=============================================================================
视频AI智能识别及预警管理信息系统 - 火焰识别
主页面路由：所有前端页面入口
作者：人员C（前端开发与质量保障工程师）
创建时间：2026-06-11
功能描述：负责所有前端页面的路由分发，包括GIS大屏首页、系统设置、
          设备管理、报警事件管理、日志管理等全部功能模块页面
=============================================================================
"""
from flask import Blueprint, render_template, request, session, redirect, url_for
from models import db, User, Department, Role, DataDict, SystemConfig
from models import Camera, AICloudBox, AlarmEvent, CameraFault, CloudBoxFault
from models import AccessLog, OperationLog
from routes.auth import login_required, admin_required, get_current_user
from sqlalchemy import func, extract
from datetime import datetime, timedelta
import json

main_bp = Blueprint('main', __name__)


# =========================================================================
# 上下文处理器 - 注入全局变量到模板
# =========================================================================

@main_bp.context_processor
def inject_globals():
    """注入全局变量到所有模板"""
    user = get_current_user()
    return {
        'current_user': user,
        'site_name': '视频AI智能识别及预警管理信息系统',
        'logo_text': 'AI火焰识别预警',
        'current_year': datetime.now().year,
    }


# =========================================================================
# 首页 - GIS数据大屏
# =========================================================================

@main_bp.route('/')
@login_required
def index():
    """首页 - GIS地图数据大屏"""
    user = get_current_user()

    # 统计数据
    total_cameras = Camera.query.count()
    online_cameras = Camera.query.filter_by(status=1).count()
    fault_cameras = Camera.query.filter(Camera.status.in_([2, 3])).count()

    total_cloud_boxes = AICloudBox.query.count()
    online_cloud_boxes = AICloudBox.query.filter_by(status=1).count()

    total_alarms = AlarmEvent.query.count()
    pending_alarms = AlarmEvent.query.filter_by(process_status=1).count()
    today_alarms = AlarmEvent.query.filter(
        func.date(AlarmEvent.detected_at) == datetime.now().date()
    ).count()

    # 摄像头列表（用于地图标注）
    cameras = Camera.query.all()
    camera_list = [c.to_dict() for c in cameras]

    # 报警事件列表（用于地图弹窗）
    recent_alarms = AlarmEvent.query.order_by(
        AlarmEvent.detected_at.desc()
    ).limit(50).all()
    alarm_list = [a.to_dict() for a in recent_alarms]

    # 故障摄像头列表
    fault_camera_list = Camera.query.filter(
        Camera.status.in_([2, 3])
    ).all()
    fault_camera_data = [c.to_dict() for c in fault_camera_list]

    # 按时间统计报警（最近7天）
    alarm_by_date = []
    for i in range(6, -1, -1):
        date = datetime.now().date() - timedelta(days=i)
        count = AlarmEvent.query.filter(
            func.date(AlarmEvent.detected_at) == date
        ).count()
        alarm_by_date.append({'date': date.strftime('%m-%d'), 'count': count})

    # 按区域统计报警
    alarm_by_region = db.session.query(
        Camera.location, func.count(AlarmEvent.id)
    ).join(AlarmEvent, AlarmEvent.camera_id == Camera.id).group_by(
        Camera.location
    ).all()
    region_data = [{'name': r[0] or '未知区域', 'value': r[1]} for r in alarm_by_region]

    return render_template(
        'index.html',
        total_cameras=total_cameras,
        online_cameras=online_cameras,
        fault_cameras=fault_cameras,
        total_cloud_boxes=total_cloud_boxes,
        online_cloud_boxes=online_cloud_boxes,
        total_alarms=total_alarms,
        pending_alarms=pending_alarms,
        today_alarms=today_alarms,
        camera_list_json=json.dumps(camera_list, ensure_ascii=False),
        alarm_list_json=json.dumps(alarm_list, ensure_ascii=False),
        fault_camera_json=json.dumps(fault_camera_data, ensure_ascii=False),
        alarm_by_date_json=json.dumps(alarm_by_date, ensure_ascii=False),
        region_data_json=json.dumps(region_data, ensure_ascii=False),
        user=user,
    )


# =========================================================================
# 管理后台仪表盘
# =========================================================================

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """管理后台仪表盘"""
    user = get_current_user()

    # 核心统计数据
    total_cameras = Camera.query.count()
    online_cameras = Camera.query.filter_by(status=1).count()
    total_cloud_boxes = AICloudBox.query.count()
    total_alarms = AlarmEvent.query.count()
    pending_alarms = AlarmEvent.query.filter_by(process_status=1).count()

    # 本周报警趋势
    week_alarms = []
    for i in range(6, -1, -1):
        date = datetime.now().date() - timedelta(days=i)
        count = AlarmEvent.query.filter(
            func.date(AlarmEvent.detected_at) == date
        ).count()
        week_alarms.append({'date': date.strftime('%m-%d'), 'count': count})

    # 本月报警趋势
    month_alarms = []
    today = datetime.now().date()
    for i in range(29, -1, -1):
        date = today - timedelta(days=i)
        count = AlarmEvent.query.filter(
            func.date(AlarmEvent.detected_at) == date
        ).count()
        month_alarms.append({'date': date.strftime('%m-%d'), 'count': count})

    # 按区域统计
    region_stats = db.session.query(
        Camera.location, func.count(AlarmEvent.id)
    ).join(AlarmEvent, AlarmEvent.camera_id == Camera.id).group_by(
        Camera.location
    ).order_by(func.count(AlarmEvent.id).desc()).limit(10).all()
    region_data = [{'name': r[0] or '未知', 'value': r[1]} for r in region_stats]

    # 按报警级别统计
    level_stats = db.session.query(
        AlarmEvent.alarm_level, func.count(AlarmEvent.id)
    ).group_by(AlarmEvent.alarm_level).all()
    level_map = {1: '紧急', 2: '重要', 3: '一般', 4: '提示'}
    level_data = [{'name': level_map.get(r[0], '未知'), 'value': r[1]} for r in level_stats]

    # 设备在线率
    device_online_rate = round(online_cameras / total_cameras * 100, 1) if total_cameras > 0 else 0

    # 最近报警事件
    recent_events = AlarmEvent.query.order_by(
        AlarmEvent.detected_at.desc()
    ).limit(10).all()

    return render_template(
        'dashboard.html',
        total_cameras=total_cameras,
        online_cameras=online_cameras,
        total_cloud_boxes=total_cloud_boxes,
        total_alarms=total_alarms,
        pending_alarms=pending_alarms,
        device_online_rate=device_online_rate,
        week_alarms_json=json.dumps(week_alarms, ensure_ascii=False),
        month_alarms_json=json.dumps(month_alarms, ensure_ascii=False),
        region_data_json=json.dumps(region_data, ensure_ascii=False),
        level_data_json=json.dumps(level_data, ensure_ascii=False),
        recent_events=recent_events,
        user=user,
    )


# =========================================================================
# 系统设置模块
# =========================================================================

@main_bp.route('/system/config')
@login_required
@admin_required
def system_config():
    """系统配置页面"""
    configs = SystemConfig.query.order_by(SystemConfig.config_key).all()
    return render_template('system/config.html', configs=configs)


@main_bp.route('/system/department')
@login_required
@admin_required
def department():
    """部门管理页面"""
    departments = Department.query.order_by(Department.sort_order).all()
    return render_template('system/department.html', departments=departments)


@main_bp.route('/system/user')
@login_required
@admin_required
def user_management():
    """用户管理页面"""
    users = User.query.order_by(User.created_at.desc()).all()
    departments = Department.query.filter_by(status=1).order_by(Department.sort_order).all()
    roles = Role.query.filter_by(status=1).all()
    return render_template('system/user.html', users=users, departments=departments, roles=roles)


@main_bp.route('/system/role')
@login_required
@admin_required
def role_management():
    """角色管理页面"""
    roles = Role.query.order_by(Role.created_at.desc()).all()
    return render_template('system/role.html', roles=roles)


@main_bp.route('/system/datadict')
@login_required
@admin_required
def datadict():
    """数据字典页面"""
    dicts = DataDict.query.order_by(DataDict.dict_type, DataDict.sort_order).all()
    dict_types = db.session.query(DataDict.dict_type).distinct().all()
    return render_template('system/datadict.html', dicts=dicts,
                           dict_types=[t[0] for t in dict_types])


# =========================================================================
# 设备管理模块
# =========================================================================

@main_bp.route('/device/cloudbox')
@login_required
def cloudbox():
    """AI智能云盒管理页面"""
    cloud_boxes = AICloudBox.query.order_by(AICloudBox.created_at.desc()).all()
    return render_template('device/cloudbox.html', cloud_boxes=cloud_boxes)


@main_bp.route('/device/camera')
@login_required
def camera_management():
    """摄像头管理页面"""
    cameras = Camera.query.order_by(Camera.created_at.desc()).all()
    cloud_boxes = AICloudBox.query.filter(AICloudBox.status.in_([1, 3])).all()
    return render_template('device/camera.html', cameras=cameras, cloud_boxes=cloud_boxes)


# =========================================================================
# 报警事件管理模块
# =========================================================================

@main_bp.route('/alarm/event')
@login_required
def alarm_event():
    """报警事件管理页面"""
    events = AlarmEvent.query.order_by(AlarmEvent.detected_at.desc()).limit(100).all()
    return render_template('alarm/event.html', events=events)


@main_bp.route('/alarm/review')
@login_required
def alarm_review():
    """事件处理审核页面"""
    events = AlarmEvent.query.filter(
        AlarmEvent.process_status.in_([1, 2])  # 待处理、处理中
    ).order_by(AlarmEvent.detected_at.desc()).all()
    return render_template('alarm/review.html', events=events)


@main_bp.route('/alarm/camera-fault')
@login_required
def camera_fault():
    """摄像头故障页面"""
    faults = CameraFault.query.order_by(CameraFault.occurred_at.desc()).all()

    # 故障统计（按日/周/月/年）
    today_faults = CameraFault.query.filter(
        func.date(CameraFault.occurred_at) == datetime.now().date()
    ).count()
    week_faults = CameraFault.query.filter(
        CameraFault.occurred_at >= datetime.now() - timedelta(days=7)
    ).count()
    month_faults = CameraFault.query.filter(
        CameraFault.occurred_at >= datetime.now() - timedelta(days=30)
    ).count()
    year_faults = CameraFault.query.filter(
        CameraFault.occurred_at >= datetime.now() - timedelta(days=365)
    ).count()

    fault_stats = {
        'today': today_faults,
        'week': week_faults,
        'month': month_faults,
        'year': year_faults,
    }

    return render_template('alarm/camera_fault.html', faults=faults, fault_stats=fault_stats)


@main_bp.route('/alarm/cloudbox-fault')
@login_required
def cloudbox_fault():
    """AI云盒故障页面"""
    faults = CloudBoxFault.query.order_by(CloudBoxFault.occurred_at.desc()).all()

    today_faults = CloudBoxFault.query.filter(
        func.date(CloudBoxFault.occurred_at) == datetime.now().date()
    ).count()
    week_faults = CloudBoxFault.query.filter(
        CloudBoxFault.occurred_at >= datetime.now() - timedelta(days=7)
    ).count()
    month_faults = CloudBoxFault.query.filter(
        CloudBoxFault.occurred_at >= datetime.now() - timedelta(days=30)
    ).count()
    year_faults = CloudBoxFault.query.filter(
        CloudBoxFault.occurred_at >= datetime.now() - timedelta(days=365)
    ).count()

    fault_stats = {
        'today': today_faults,
        'week': week_faults,
        'month': month_faults,
        'year': year_faults,
    }

    return render_template('alarm/cloudbox_fault.html', faults=faults, fault_stats=fault_stats)


# =========================================================================
# 日志管理模块
# =========================================================================

@main_bp.route('/log/access')
@login_required
def access_log():
    """访问日志页面"""
    logs = AccessLog.query.order_by(AccessLog.created_at.desc()).limit(200).all()
    return render_template('log/access.html', logs=logs)


@main_bp.route('/log/operation')
@login_required
def operation_log():
    """操作日志页面"""
    logs = OperationLog.query.order_by(OperationLog.created_at.desc()).limit(200).all()
    return render_template('log/operation.html', logs=logs)
