"""
=============================================================================
RESTful API 路由 — 融合模式（代理到王永林的PHP API）
作者：段林川（前端） + 王永林（后端API桥接）
创建时间：2026-06-11
修改时间：2026-06-12  融合：全部CRUD改为调用B的PHP API桥接层
=============================================================================
"""
from flask import Blueprint, request, jsonify, session
from routes.auth import login_required, admin_required, get_current_user

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


# =========================================================================
# 通用响应格式（保持C原有格式）
# =========================================================================

def success(data=None, msg='操作成功'):
    return jsonify({'code': 200, 'msg': msg, 'data': data})


def fail(msg='操作失败', code=400, data=None):
    return jsonify({'code': code, 'msg': msg, 'data': data}), code


def _get_bridge():
    """获取API桥接实例，自动注入当前session中的JWT"""
    from api_bridge import APIBridge
    jwt = session.get('jwt_token', '')
    if jwt and not APIBridge.get_token():
        APIBridge.set_token(jwt)
    return APIBridge


# =========================================================================
# 用户认证API
# =========================================================================

@api_bp.route('/token', methods=['POST'])
def get_token():
    """获取JWT Token → 转发到B的PHP API"""
    data = request.get_json() or {}
    username = data.get('username', '')
    password = data.get('password', '')
    if not username or not password:
        return fail('用户名和密码不能为空', 400)

    bridge = _get_bridge()
    result = bridge.login(username, password)
    if result.get('code') != 200:
        return fail(result.get('msg', '用户名或密码错误'), result.get('code', 401))

    # 登录成功后同步session
    user_data = result.get('data', {}).get('user', {})
    session['user_id'] = user_data.get('id')
    session['username'] = user_data.get('username', username)
    session['user_type'] = user_data.get('user_type', 2)
    session['real_name'] = user_data.get('real_name') or username
    session['jwt_token'] = result.get('data', {}).get('token', '')

    return success(result.get('data'), '登录成功')


# =========================================================================
# 部门管理API（M7融合修复）
# =========================================================================

@api_bp.route('/departments', methods=['GET'])
@login_required
def get_departments():
    bridge = _get_bridge()
    return jsonify(bridge.department_list())


@api_bp.route('/departments', methods=['POST'])
@login_required
@admin_required
def create_department():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('name'):
        return fail('部门名称不能为空')
    bridge = _get_bridge()
    return jsonify(bridge.department_create(data))


@api_bp.route('/departments/<int:dept_id>', methods=['PUT'])
@login_required
@admin_required
def update_department(dept_id):
    data = request.get_json(force=True, silent=True) or {}
    bridge = _get_bridge()
    return jsonify(bridge.department_update(dept_id, data))


@api_bp.route('/departments/<int:dept_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_department(dept_id):
    bridge = _get_bridge()
    return jsonify(bridge.department_delete(dept_id))


# =========================================================================
# 用户管理API（M7融合修复）
# =========================================================================

@api_bp.route('/users', methods=['GET'])
@login_required
def get_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    bridge = _get_bridge()
    return jsonify(bridge.user_list(page=page, per_page=per_page,
        username=request.args.get('username', ''),
        real_name=request.args.get('real_name', ''),
        user_type=request.args.get('user_type', '')))


@api_bp.route('/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('username') or not data.get('real_name'):
        return fail('用户名和姓名不能为空')
    bridge = _get_bridge()
    return jsonify(bridge.user_create(data))


@api_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    data = request.get_json(force=True, silent=True) or {}
    bridge = _get_bridge()
    return jsonify(bridge.user_update(user_id, data))


@api_bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    bridge = _get_bridge()
    return jsonify(bridge.user_delete(user_id))


@api_bp.route('/users/<int:user_id>/status', methods=['PUT'])
@login_required
@admin_required
def toggle_user_status(user_id):
    data = request.get_json(force=True, silent=True) or {}
    new_status = data.get('status', 0)
    bridge = _get_bridge()
    return jsonify(bridge.user_update(user_id, {'status': new_status}))


# =========================================================================
# 角色管理API（M7融合修复）
# =========================================================================

@api_bp.route('/roles', methods=['GET'])
@login_required
def get_roles():
    bridge = _get_bridge()
    return jsonify(bridge.role_list())


@api_bp.route('/roles', methods=['POST'])
@login_required
@admin_required
def create_role():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('name'):
        return fail('角色名称不能为空')
    bridge = _get_bridge()
    return jsonify(bridge.role_create(data))


@api_bp.route('/roles/<int:role_id>', methods=['PUT'])
@login_required
@admin_required
def update_role(role_id):
    data = request.get_json(force=True, silent=True) or {}
    bridge = _get_bridge()
    return jsonify(bridge.role_update(role_id, data))


@api_bp.route('/roles/<int:role_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_role(role_id):
    bridge = _get_bridge()
    return jsonify(bridge.role_delete(role_id))


# =========================================================================
# 数据字典API
# =========================================================================

@api_bp.route('/datadicts', methods=['GET'])
@login_required
def get_datadicts():
    bridge = _get_bridge()
    return jsonify(bridge.datadict_list(request.args.get('dict_type', '')))


@api_bp.route('/datadicts', methods=['POST'])
@login_required
@admin_required
def create_datadict():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('dict_type') or not data.get('dict_value'):
        return fail('字典类型和值不能为空')
    bridge = _get_bridge()
    return jsonify(bridge.datadict_create(data))


@api_bp.route('/datadicts/<int:dd_id>', methods=['PUT'])
@login_required
@admin_required
def update_datadict(dd_id):
    data = request.get_json(force=True, silent=True) or {}
    bridge = _get_bridge()
    return jsonify(bridge.datadict_update(dd_id, data))


@api_bp.route('/datadicts/<int:dd_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_datadict(dd_id):
    bridge = _get_bridge()
    return jsonify(bridge.datadict_delete(dd_id))


# =========================================================================
# 系统配置API
# =========================================================================

@api_bp.route('/system-configs', methods=['GET'])
@login_required
@admin_required
def get_system_configs():
    bridge = _get_bridge()
    return jsonify(bridge.system_configs())


@api_bp.route('/system-configs', methods=['PUT'])
@login_required
@admin_required
def update_system_configs():
    data = request.get_json() or {}
    bridge = _get_bridge()
    return jsonify(bridge.update_system_configs(data))


# =========================================================================
# AI智能云盒管理API ★ 核心
# =========================================================================

@api_bp.route('/cloudboxes', methods=['GET'])
@login_required
def get_cloudboxes():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    status = request.args.get('status', type=int)
    keyword = request.args.get('keyword', '')

    filters = {}
    if status:
        filters['status'] = status
    if keyword:
        filters['keyword'] = keyword

    bridge = _get_bridge()
    return jsonify(bridge.cloudbox_list(page=page, per_page=per_page, **filters))


@api_bp.route('/cloudboxes', methods=['POST'])
@login_required
def create_cloudbox():
    data = request.get_json() or {}
    if not data.get('device_name') or not data.get('device_code'):
        return fail('设备名称和编码不能为空')
    bridge = _get_bridge()
    return jsonify(bridge.cloudbox_create(data))


@api_bp.route('/cloudboxes/<int:cb_id>', methods=['PUT'])
@login_required
def update_cloudbox(cb_id):
    data = request.get_json() or {}
    bridge = _get_bridge()
    return jsonify(bridge.cloudbox_update(cb_id, data))


@api_bp.route('/cloudboxes/<int:cb_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_cloudbox(cb_id):
    bridge = _get_bridge()
    return jsonify(bridge.cloudbox_delete(cb_id))


# =========================================================================
# 摄像头管理API ★ 核心
# =========================================================================

@api_bp.route('/cameras', methods=['GET'])
@login_required
def get_cameras():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    status = request.args.get('status', type=int)
    keyword = request.args.get('keyword', '')
    cloud_box_id = request.args.get('cloud_box_id', type=int)

    filters = {}
    if status:
        filters['status'] = status
    if keyword:
        filters['keyword'] = keyword
    if cloud_box_id:
        filters['device_id'] = cloud_box_id

    bridge = _get_bridge()
    return jsonify(bridge.camera_list(page=page, per_page=per_page, **filters))


@api_bp.route('/cameras', methods=['POST'])
@login_required
def create_camera():
    data = request.get_json() or {}
    if not data.get('device_name') or not data.get('device_code'):
        return fail('设备名称和编码不能为空')
    bridge = _get_bridge()
    return jsonify(bridge.camera_create(data))


@api_bp.route('/cameras/<int:camera_id>', methods=['PUT'])
@login_required
def update_camera(camera_id):
    data = request.get_json() or {}
    bridge = _get_bridge()
    return jsonify(bridge.camera_update(camera_id, data))


@api_bp.route('/cameras/<int:camera_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_camera(camera_id):
    bridge = _get_bridge()
    return jsonify(bridge.camera_delete(camera_id))


# =========================================================================
# 报警事件API ★ 核心
# =========================================================================

@api_bp.route('/alarm-events', methods=['GET'])
@login_required
def get_alarm_events():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    event_type = request.args.get('event_type', type=int)
    process_status = request.args.get('process_status', type=int)
    alarm_level = request.args.get('alarm_level', type=int)
    keyword = request.args.get('keyword', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    filters = {}
    if event_type:
        filters['event_type'] = event_type
    if process_status:
        filters['status'] = process_status
    if alarm_level:
        filters['alarm_level'] = alarm_level
    if keyword:
        filters['keyword'] = keyword
    if date_from:
        filters['start_time'] = date_from
    if date_to:
        filters['end_time'] = date_to

    bridge = _get_bridge()
    return jsonify(bridge.alarm_list(page=page, per_page=per_page, **filters))


@api_bp.route('/alarm-events/<int:event_id>', methods=['GET'])
@login_required
def get_alarm_event_detail(event_id):
    bridge = _get_bridge()
    return jsonify(bridge.alarm_detail(event_id))


@api_bp.route('/alarm-events/<int:event_id>/process', methods=['PUT'])
@login_required
def process_alarm_event(event_id):
    data = request.get_json() or {}
    action = data.get('action', '')
    remark = data.get('remark', data.get('handler_remark', ''))
    user = get_current_user()

    # C的action→B的action映射
    if action == 'approve':
        bridge_action = 'audit'
    elif action == 'reject':
        bridge_action = 'process'
    else:
        return fail('无效操作，可选值：approve / reject')

    bridge = _get_bridge()
    return jsonify(bridge.alarm_process(
        event_id,
        action=bridge_action,
        user_id=user.get('id') if user else 1,
        handler_remark=remark,
    ))


# =========================================================================
# 故障管理（B端暂无独立API → 返回空）
# =========================================================================

@api_bp.route('/camera-faults', methods=['GET'])
@login_required
def get_camera_faults():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    bridge = _get_bridge()
    return jsonify(bridge.camera_fault_list(page=page, per_page=per_page))


@api_bp.route('/camera-faults/<int:fault_id>/repair', methods=['PUT'])
@login_required
@admin_required
def repair_camera_fault(fault_id):
    data = request.get_json(force=True, silent=True) or {}
    remark = data.get('remark', '')
    bridge = _get_bridge()
    return jsonify(bridge.camera_fault_repair(fault_id, remark))


@api_bp.route('/cloudbox-faults', methods=['GET'])
@login_required
def get_cloudbox_faults():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    bridge = _get_bridge()
    return jsonify(bridge.cloudbox_fault_list(page=page, per_page=per_page))


@api_bp.route('/cloudbox-faults/<int:fault_id>/repair', methods=['PUT'])
@login_required
@admin_required
def repair_cloudbox_fault(fault_id):
    data = request.get_json(force=True, silent=True) or {}
    remark = data.get('remark', '')
    bridge = _get_bridge()
    return jsonify(bridge.cloudbox_fault_repair(fault_id, remark))


# =========================================================================
# 统计图表数据API ★ 核心
# =========================================================================

@api_bp.route('/statistics/overview', methods=['GET'])
@login_required
def get_overview_statistics():
    bridge = _get_bridge()
    return jsonify(bridge.statistics_overview())


@api_bp.route('/statistics/alarm-by-date', methods=['GET'])
@login_required
def get_alarm_by_date():
    days = request.args.get('days', 30, type=int)
    bridge = _get_bridge()
    return jsonify(bridge.statistics_by_date(days=days))


@api_bp.route('/statistics/alarm-by-region', methods=['GET'])
@login_required
def get_alarm_by_region():
    bridge = _get_bridge()
    return jsonify(bridge.statistics_by_region())


@api_bp.route('/statistics/alarm-by-level', methods=['GET'])
@login_required
def get_alarm_by_level():
    bridge = _get_bridge()
    return jsonify(bridge.statistics_by_level())


@api_bp.route('/statistics/device-fault-stats', methods=['GET'])
@login_required
def get_device_fault_stats():
    bridge = _get_bridge()
    camera_stats = bridge.camera_fault_stats()
    cloudbox_stats = bridge.cloudbox_fault_stats()
    return success({
        'camera_faults': camera_stats,
        'cloudbox_faults': cloudbox_stats,
    })


@api_bp.route('/statistics/heatmap', methods=['GET'])
@login_required
def get_heatmap_data():
    bridge = _get_bridge()
    return jsonify(bridge.statistics_heatmap())


# =========================================================================
# 日志查询 ★ 融合新增
# =========================================================================

@api_bp.route('/logs/access', methods=['GET'])
@login_required
def query_access_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    username = request.args.get('username', '')
    bridge = _get_bridge()
    return jsonify(bridge.access_logs(page=page, per_page=per_page, username=username))


@api_bp.route('/logs/operation', methods=['GET'])
@login_required
def query_operation_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    username = request.args.get('username', '')
    operation_type = request.args.get('operation_type', '')
    bridge = _get_bridge()
    return jsonify(bridge.operation_logs(
        page=page, per_page=per_page,
        username=username, operation_type=operation_type,
    ))
