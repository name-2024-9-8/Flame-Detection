"""
=============================================================================
主页面路由 — 融合模式（页面数据从B的PHP API获取，模板保持不变）
作者：段林川（前端） + 王永林（后端API桥接）
创建时间：2026-06-11
修改时间：2026-06-16  修复：_list_items兼容bare list；消除双重API调用
=============================================================================
"""
from flask import Blueprint, render_template, request, session, redirect, url_for
from routes.auth import login_required, admin_required, get_current_user
from api_bridge import APIBridge
from datetime import datetime, timedelta
import json

main_bp = Blueprint('main', __name__)


# =========================================================================
# 辅助函数：获取桥接实例
# =========================================================================

def _get_bridge():
    """获取API桥接实例"""
    from api_bridge import APIBridge
    jwt = session.get('jwt_token', '')
    if jwt and not APIBridge.get_token():
        APIBridge.set_token(jwt)
    return APIBridge


def _success_or_empty(result, key='data'):
    """从桥接结果中提取数据，失败返回空"""
    if result and result.get('code') == 200:
        return result.get(key, {})
    return {}


def _list_items(result):
    """从桥接结果中提取列表项（兼容bare list和{items:[...]}两种格式）"""
    data = _success_or_empty(result)
    if isinstance(data, list):
        return data
    return data.get('items', []) if isinstance(data, dict) else []


# =========================================================================
# 上下文处理器 — 注入全局变量到模板
# =========================================================================

@main_bp.context_processor
def inject_globals():
    user = get_current_user()
    return {
        'current_user': user,
        'site_name': '视频AI智能识别及预警管理信息系统',
        'logo_text': 'AI火焰识别预警',
        'current_year': datetime.now().year,
    }


# =========================================================================
# 首页 — GIS数据大屏 ★ 核心页面
# =========================================================================

@main_bp.route('/')
@login_required
def index():
    """首页 — GIS地图数据大屏"""
    user = get_current_user()
    bridge = _get_bridge()

    # 统计概览
    overview = _success_or_empty(bridge.statistics_overview())

    total_cameras = overview.get('total_cameras', 0)
    online_cameras = overview.get('online_cameras', 0)
    fault_cameras = overview.get('fault_cameras', 0)
    total_cloud_boxes = overview.get('total_cloud_boxes', 0)
    online_cloud_boxes = overview.get('online_cloud_boxes', 0)
    fault_cloud_boxes = overview.get('fault_cloud_boxes', 0)
    total_alarms = overview.get('total_alarms', 0)
    pending_alarms = overview.get('pending_alarms', 0)
    today_alarms = overview.get('today_alarms', 0)

    # 摄像头列表（地图标注）
    camera_list = _list_items(bridge.camera_list(per_page=500))

    # 报警事件列表（最近50条，地图弹窗）
    alarm_list = _list_items(bridge.alarm_list(per_page=50))

    # 故障摄像头（数据大屏地图标注）
    cam_faults = _list_items(bridge.camera_fault_list(per_page=200))
    box_faults = _list_items(bridge.cloudbox_fault_list(per_page=200))
    # 合并两种故障数据，统一传给大屏
    fault_data = cam_faults + box_faults

    # ★ 计算地图三层标记数量（互不重叠，按摄像头位置独立计数）
    # 故障摄像头ID
    fault_cam_ids = set()
    for f in fault_data:
        cam_ref = f.get('camera') if isinstance(f.get('camera'), dict) else {}
        if cam_ref.get('id'):
            fault_cam_ids.add(cam_ref['id'])

    # 报警事件涉及的摄像头ID（全部，含故障的）
    alarm_cam_ids = set()
    for a in alarm_list:
        cid = a.get('camera_id')
        if cid:
            alarm_cam_ids.add(cid)

    # 🔴 报警事件标记数：有报警 且 非故障的摄像头数（地图上红色🔥标记）
    alarm_marker_count = len(alarm_cam_ids - fault_cam_ids)

    # 🔵 监控摄像头标记数：无故障 且 无报警的摄像头数（地图上蓝色标记）
    normal_marker_count = sum(
        1 for c in camera_list
        if c.get('id') not in fault_cam_ids and c.get('id') not in alarm_cam_ids
    )

    # 最近7天报警趋势
    alarm_by_date = _success_or_empty(bridge.statistics_by_date(days=7)) or []
    if isinstance(alarm_by_date, list):
        alarm_by_date = [{'date': d.get('date', ''), 'count': d.get('count', 0)} for d in alarm_by_date]

    # 按区域统计报警
    region_data = _success_or_empty(bridge.statistics_by_region()) or []
    if isinstance(region_data, list):
        region_data = [{'name': r.get('name', '未知'), 'value': r.get('value', 0)} for r in region_data]

    return render_template(
        'index.html',
        total_cameras=total_cameras,
        online_cameras=online_cameras,
        fault_cameras=fault_cameras,
        total_cloud_boxes=total_cloud_boxes,
        online_cloud_boxes=online_cloud_boxes,
        fault_cloud_boxes=fault_cloud_boxes,
        total_alarms=total_alarms,
        pending_alarms=pending_alarms,
        today_alarms=today_alarms,
        alarm_marker_count=alarm_marker_count,
        normal_marker_count=normal_marker_count,
        camera_list_json=json.dumps(camera_list, ensure_ascii=False),
        alarm_list_json=json.dumps(alarm_list, ensure_ascii=False),
        fault_camera_json=json.dumps(fault_data, ensure_ascii=False),
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
    bridge = _get_bridge()

    # 核心统计数据
    overview = _success_or_empty(bridge.statistics_overview())
    total_cameras = overview.get('total_cameras', 0)
    online_cameras = overview.get('online_cameras', 0)
    total_cloud_boxes = overview.get('total_cloud_boxes', 0)
    total_alarms = overview.get('total_alarms', 0)
    pending_alarms = overview.get('pending_alarms', 0)

    # 本月报警趋势 (30天，dashboard.html唯一引用的趋势图)
    month_alarms = _success_or_empty(bridge.statistics_by_date(days=30)) or []
    if isinstance(month_alarms, list):
        month_alarms = [{'date': d.get('date', ''), 'count': d.get('count', 0)} for d in month_alarms]

    # 按区域统计
    region_data = _success_or_empty(bridge.statistics_by_region()) or []
    if isinstance(region_data, list):
        region_data = [{'name': r.get('name', '未知'), 'value': r.get('value', 0)} for r in region_data]

    # 按级别统计
    level_data = _success_or_empty(bridge.statistics_by_level()) or []
    if isinstance(level_data, list):
        level_data = [{'name': l.get('name', '未知'), 'value': l.get('value', 0)} for l in level_data]

    # 设备在线率
    device_online_rate = round(online_cameras / total_cameras * 100, 1) if total_cameras > 0 else 0

    # 最近报警事件（10条）
    recent_events = _list_items(bridge.alarm_list(per_page=10))

    return render_template(
        'dashboard.html',
        total_cameras=total_cameras,
        online_cameras=online_cameras,
        total_cloud_boxes=total_cloud_boxes,
        total_alarms=total_alarms,
        pending_alarms=pending_alarms,
        device_online_rate=device_online_rate,
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
    """系统配置页面 — 数据由AJAX加载"""
    bridge = _get_bridge()
    configs_data = _success_or_empty(bridge.system_configs())
    configs = configs_data if isinstance(configs_data, list) else []
    return render_template('system/config.html', configs=configs)


@main_bp.route('/system/department')
@login_required
@admin_required
def department():
    """部门管理页面"""
    bridge = _get_bridge()
    dept_result = bridge.department_list()
    departments = _list_items(dept_result)
    return render_template('system/department.html', departments=departments)


@main_bp.route('/system/user')
@login_required
@admin_required
def user_management():
    """用户管理页面"""
    bridge = _get_bridge()
    depts = _list_items(bridge.department_list())
    role_result = bridge.role_list()
    roles = role_result.get('data', []) if role_result.get('code') == 200 else []
    return render_template('system/user.html', users=[], departments=depts, roles=roles)


@main_bp.route('/system/role')
@login_required
@admin_required
def role_management():
    """角色管理页面"""
    bridge = _get_bridge()
    role_result = bridge.role_list()
    roles = role_result.get('data', []) if role_result.get('code') == 200 else []
    return render_template('system/role.html', roles=roles)


@main_bp.route('/system/datadict')
@login_required
@admin_required
def datadict():
    """数据字典页面"""
    bridge = _get_bridge()
    result = bridge.datadict_list()
    items = []
    types = []
    if result.get('code') == 200:
        items = result.get('data', {}).get('items', [])
        types = result.get('data', {}).get('types', [])
    return render_template('system/datadict.html', dicts=items, dict_types=types)


# =========================================================================
# 设备管理模块
# =========================================================================

@main_bp.route('/device/cloudbox')
@login_required
def cloudbox():
    """AI智能云盒管理页面 — 数据由AJAX加载"""
    return render_template('device/cloudbox.html', cloud_boxes=[])


@main_bp.route('/device/camera')
@login_required
def camera_management():
    """摄像头管理页面 — 数据由AJAX加载"""
    return render_template('device/camera.html', cameras=[], cloud_boxes=[])


# =========================================================================
# 报警事件管理模块
# =========================================================================

@main_bp.route('/alarm/event')
@login_required
def alarm_event():
    """报警事件管理页面 — 数据由AJAX加载"""
    return render_template('alarm/event.html', events=[])


@main_bp.route('/alarm/review')
@login_required
def alarm_review():
    """事件处理审核页面 — 加载待审核(status=2)的报警事件"""
    bridge = _get_bridge()
    result = bridge.alarm_list(per_page=50, status='1')  # 审核页加载待处理(status=1)的报警
    events = _list_items(result)
    return render_template('alarm/review.html', events=events)


@main_bp.route('/alarm/camera-fault')
@login_required
def camera_fault():
    """摄像头故障页面"""
    bridge = _get_bridge()
    result = bridge.camera_fault_list(per_page=50)
    faults = _list_items(result)
    stats = result.get('data', {}).get('stats', {}) if result.get('code') == 200 else {}
    return render_template('alarm/camera_fault.html', faults=faults, fault_stats=stats)


@main_bp.route('/alarm/cloudbox-fault')
@login_required
def cloudbox_fault():
    """AI云盒故障页面"""
    bridge = _get_bridge()
    result = bridge.cloudbox_fault_list(per_page=50)
    faults = _list_items(result)
    stats = result.get('data', {}).get('stats', {}) if result.get('code') == 200 else {}
    return render_template('alarm/cloudbox_fault.html', faults=faults, fault_stats=stats)


# =========================================================================
# 日志管理模块
# =========================================================================

@main_bp.route('/log/access')
@login_required
def access_log():
    """访问日志页面"""
    return render_template('log/access.html', logs=[])


@main_bp.route('/log/operation')
@login_required
def operation_log():
    """操作日志页面"""
    return render_template('log/operation.html', logs=[])
