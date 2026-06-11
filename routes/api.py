"""
=============================================================================
视频AI智能识别及预警管理信息系统 - 火焰识别
RESTful API 路由
作者：人员C（前端开发与质量保障工程师）
创建时间：2026-06-11
功能描述：提供前端所有CRUD操作的API接口，数据格式统一为JSON，
          支持JWT鉴权（与人员B后端对接），统一HTTP状态码规范
=============================================================================
"""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session
from models import db, User, Department, Role, DataDict, SystemConfig
from models import Camera, AICloudBox, AlarmEvent, CameraFault, CloudBoxFault
from models import AccessLog, OperationLog
from routes.auth import login_required, admin_required, get_current_user, _log_operation
from sqlalchemy import func, or_
import uuid

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


# =========================================================================
# 通用响应格式
# =========================================================================

def success(data=None, msg='操作成功'):
    """成功响应"""
    return jsonify({'code': 200, 'msg': msg, 'data': data})

def fail(msg='操作失败', code=400, data=None):
    """失败响应"""
    return jsonify({'code': code, 'msg': msg, 'data': data}), code


# =========================================================================
# 用户认证API
# =========================================================================

@api_bp.route('/token', methods=['POST'])
def get_token():
    """获取JWT Token（与人员B API对接）"""
    from config import Config
    data = request.get_json() or {}
    username = data.get('username', '')
    password = data.get('password', '')

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return fail('用户名或密码错误', 401)

    if user.status == 0:
        return fail('账户已被禁用', 403)

    token = user.generate_token(Config.JWT_SECRET_KEY)
    return success({
        'token': token,
        'token_type': 'Bearer',
        'expires_in': Config.JWT_ACCESS_TOKEN_EXPIRES,
        'user': user.to_dict(),
    })


# =========================================================================
# 部门管理API
# =========================================================================

@api_bp.route('/departments', methods=['GET'])
@login_required
def get_departments():
    """获取部门列表"""
    departments = Department.query.order_by(Department.sort_order).all()
    return success([d.to_dict() for d in departments])


@api_bp.route('/departments', methods=['POST'])
@login_required
@admin_required
def create_department():
    """新建部门"""
    data = request.get_json() or {}
    if not data.get('name'):
        return fail('部门名称不能为空')

    if Department.query.filter_by(name=data['name']).first():
        return fail('部门名称已存在')

    dept = Department(
        name=data['name'],
        code=data.get('code', ''),
        parent_id=data.get('parent_id') or None,
        sort_order=data.get('sort_order', 0),
        remark=data.get('remark', ''),
    )
    db.session.add(dept)
    db.session.commit()

    _log_operation(get_current_user(), 'CREATE', 'department',
                   f'新建部门：{dept.name}', request,
                   target_table='departments', target_id=dept.id,
                   new_data=dept.to_dict())
    return success(dept.to_dict(), '部门创建成功')


@api_bp.route('/departments/<int:dept_id>', methods=['PUT'])
@login_required
@admin_required
def update_department(dept_id):
    """修改部门"""
    dept = Department.query.get(dept_id)
    if not dept:
        return fail('部门不存在', 404)

    data = request.get_json() or {}
    old_data = dept.to_dict()

    if 'name' in data:
        existing = Department.query.filter(
            Department.name == data['name'], Department.id != dept_id
        ).first()
        if existing:
            return fail('部门名称已存在')
        dept.name = data['name']
    if 'code' in data:
        dept.code = data['code']
    if 'parent_id' in data:
        dept.parent_id = data['parent_id'] or None
    if 'sort_order' in data:
        dept.sort_order = data['sort_order']
    if 'status' in data:
        dept.status = data['status']
    if 'remark' in data:
        dept.remark = data['remark']

    dept.updated_at = datetime.now()
    db.session.commit()

    _log_operation(get_current_user(), 'UPDATE', 'department',
                   f'修改部门：{dept.name}', request,
                   target_table='departments', target_id=dept.id,
                   old_data=old_data, new_data=dept.to_dict())
    return success(dept.to_dict(), '部门修改成功')


@api_bp.route('/departments/<int:dept_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_department(dept_id):
    """删除部门"""
    dept = Department.query.get(dept_id)
    if not dept:
        return fail('部门不存在', 404)

    # 检查是否有子部门
    if dept.children.count() > 0:
        return fail('该部门下存在子部门，无法删除')

    # 检查是否有用户
    if dept.users.count() > 0:
        return fail('该部门下存在用户，无法删除')

    dept_name = dept.name
    old_data = dept.to_dict()
    db.session.delete(dept)
    db.session.commit()

    _log_operation(get_current_user(), 'DELETE', 'department',
                   f'删除部门：{dept_name}', request,
                   target_table='departments', target_id=dept_id,
                   old_data=old_data)
    return success(msg=f'部门"{dept_name}"已删除')


# =========================================================================
# 用户管理API
# =========================================================================

@api_bp.route('/users', methods=['GET'])
@login_required
def get_users():
    """获取用户列表（支持多条件筛选）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    username = request.args.get('username', '')
    real_name = request.args.get('real_name', '')
    user_type = request.args.get('user_type', type=int)
    status = request.args.get('status', type=int)
    department_id = request.args.get('department_id', type=int)
    role_id = request.args.get('role_id', type=int)

    query = User.query
    if username:
        query = query.filter(User.username.like(f'%{username}%'))
    if real_name:
        query = query.filter(User.real_name.like(f'%{real_name}%'))
    if user_type:
        query = query.filter_by(user_type=user_type)
    if status is not None:
        query = query.filter_by(status=status)
    if department_id:
        query = query.filter_by(department_id=department_id)
    if role_id:
        query = query.filter_by(role_id=role_id)

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return success({
        'items': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
    })


@api_bp.route('/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    """新建用户"""
    data = request.get_json() or {}
    if not data.get('username') or not data.get('password'):
        return fail('用户名和密码不能为空')

    if User.query.filter_by(username=data['username']).first():
        return fail('用户名已存在')

    user = User(
        username=data['username'],
        real_name=data.get('real_name', ''),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        user_type=data.get('user_type', 2),
        status=data.get('status', 1),
        department_id=data.get('department_id') or None,
        role_id=data.get('role_id') or None,
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()

    _log_operation(get_current_user(), 'CREATE', 'user',
                   f'新建用户：{user.username}', request,
                   target_table='users', target_id=user.id,
                   new_data=user.to_dict())
    return success(user.to_dict(), '用户创建成功')


@api_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    """修改用户"""
    user = User.query.get(user_id)
    if not user:
        return fail('用户不存在', 404)

    data = request.get_json() or {}
    old_data = user.to_dict()

    if 'username' in data and data['username'] != user.username:
        if User.query.filter_by(username=data['username']).first():
            return fail('用户名已存在')
        user.username = data['username']
    if 'real_name' in data:
        user.real_name = data['real_name']
    if 'email' in data:
        user.email = data['email']
    if 'phone' in data:
        user.phone = data['phone']
    if 'user_type' in data:
        user.user_type = data['user_type']
    if 'status' in data:
        user.status = data['status']
    if 'department_id' in data:
        user.department_id = data['department_id'] or None
    if 'role_id' in data:
        user.role_id = data['role_id'] or None
    if data.get('password'):
        user.set_password(data['password'])

    user.updated_at = datetime.now()
    db.session.commit()

    _log_operation(get_current_user(), 'UPDATE', 'user',
                   f'修改用户：{user.username}', request,
                   target_table='users', target_id=user.id,
                   old_data=old_data, new_data=user.to_dict())
    return success(user.to_dict(), '用户修改成功')


@api_bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户"""
    user = User.query.get(user_id)
    if not user:
        return fail('用户不存在', 404)

    # 不能删除自己
    if user.id == get_current_user().id:
        return fail('不能删除当前登录用户')

    username = user.username
    old_data = user.to_dict()
    db.session.delete(user)
    db.session.commit()

    _log_operation(get_current_user(), 'DELETE', 'user',
                   f'删除用户：{username}', request,
                   target_table='users', target_id=user_id,
                   old_data=old_data)
    return success(msg=f'用户"{username}"已删除')


@api_bp.route('/users/<int:user_id>/status', methods=['PUT'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """切换用户启用/禁用状态"""
    user = User.query.get(user_id)
    if not user:
        return fail('用户不存在', 404)
    if user.id == get_current_user().id:
        return fail('不能修改自己的状态')

    user.status = 1 if user.status == 0 else 0
    user.updated_at = datetime.now()
    db.session.commit()

    action = '启用' if user.status == 1 else '禁用'
    _log_operation(get_current_user(), 'UPDATE', 'user',
                   f'{action}用户：{user.username}', request,
                   target_table='users', target_id=user.id)
    return success(msg=f'用户已{action}')


# =========================================================================
# 角色管理API
# =========================================================================

@api_bp.route('/roles', methods=['GET'])
@login_required
def get_roles():
    """获取角色列表"""
    roles = Role.query.order_by(Role.created_at.desc()).all()
    return success([r.to_dict() for r in roles])


@api_bp.route('/roles', methods=['POST'])
@login_required
@admin_required
def create_role():
    """新建角色"""
    data = request.get_json() or {}
    if not data.get('name'):
        return fail('角色名称不能为空')

    if Role.query.filter_by(name=data['name']).first():
        return fail('角色名称已存在')

    role = Role(
        name=data['name'],
        code=data.get('code', ''),
        description=data.get('description', ''),
        status=data.get('status', 1),
    )
    if data.get('permissions'):
        role.set_permissions(data['permissions'])
    db.session.add(role)
    db.session.commit()

    _log_operation(get_current_user(), 'CREATE', 'role',
                   f'新建角色：{role.name}', request,
                   target_table='roles', target_id=role.id)
    return success(role.to_dict(), '角色创建成功')


@api_bp.route('/roles/<int:role_id>', methods=['PUT'])
@login_required
@admin_required
def update_role(role_id):
    """修改角色"""
    role = Role.query.get(role_id)
    if not role:
        return fail('角色不存在', 404)

    data = request.get_json() or {}
    old_data = role.to_dict()

    if 'name' in data:
        existing = Role.query.filter(Role.name == data['name'], Role.id != role_id).first()
        if existing:
            return fail('角色名称已存在')
        role.name = data['name']
    if 'code' in data:
        role.code = data['code']
    if 'description' in data:
        role.description = data['description']
    if 'status' in data:
        role.status = data['status']
    if 'permissions' in data:
        role.set_permissions(data['permissions'])

    role.updated_at = datetime.now()
    db.session.commit()

    _log_operation(get_current_user(), 'UPDATE', 'role',
                   f'修改角色：{role.name}', request,
                   target_table='roles', target_id=role.id,
                   old_data=old_data, new_data=role.to_dict())
    return success(role.to_dict(), '角色修改成功')


@api_bp.route('/roles/<int:role_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_role(role_id):
    """删除角色"""
    role = Role.query.get(role_id)
    if not role:
        return fail('角色不存在', 404)

    if role.users.count() > 0:
        return fail('该角色下存在用户，无法删除')

    role_name = role.name
    db.session.delete(role)
    db.session.commit()

    _log_operation(get_current_user(), 'DELETE', 'role',
                   f'删除角色：{role_name}', request,
                   target_table='roles', target_id=role_id)
    return success(msg=f'角色"{role_name}"已删除')


# =========================================================================
# 数据字典API
# =========================================================================

@api_bp.route('/datadicts', methods=['GET'])
@login_required
def get_datadicts():
    """获取数据字典列表"""
    dict_type = request.args.get('dict_type', '')
    query = DataDict.query
    if dict_type:
        query = query.filter_by(dict_type=dict_type)
    dicts = query.order_by(DataDict.dict_type, DataDict.sort_order).all()
    return success([d.to_dict() for d in dicts])


@api_bp.route('/datadicts', methods=['POST'])
@login_required
@admin_required
def create_datadict():
    """新建数据字典项"""
    data = request.get_json() or {}
    if not data.get('dict_type') or not data.get('dict_label'):
        return fail('字典类型和标签不能为空')

    dd = DataDict(
        dict_type=data['dict_type'],
        dict_label=data['dict_label'],
        dict_value=data.get('dict_value', ''),
        sort_order=data.get('sort_order', 0),
        remark=data.get('remark', ''),
    )
    db.session.add(dd)
    db.session.commit()
    return success(dd.to_dict(), '数据字典项创建成功')


@api_bp.route('/datadicts/<int:dd_id>', methods=['PUT'])
@login_required
@admin_required
def update_datadict(dd_id):
    """修改数据字典项"""
    dd = DataDict.query.get(dd_id)
    if not dd:
        return fail('数据字典项不存在', 404)

    data = request.get_json() or {}
    if 'dict_type' in data:
        dd.dict_type = data['dict_type']
    if 'dict_label' in data:
        dd.dict_label = data['dict_label']
    if 'dict_value' in data:
        dd.dict_value = data['dict_value']
    if 'sort_order' in data:
        dd.sort_order = data['sort_order']
    if 'status' in data:
        dd.status = data['status']
    if 'remark' in data:
        dd.remark = data['remark']

    dd.updated_at = datetime.now()
    db.session.commit()
    return success(dd.to_dict(), '数据字典项修改成功')


@api_bp.route('/datadicts/<int:dd_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_datadict(dd_id):
    """删除数据字典项"""
    dd = DataDict.query.get(dd_id)
    if not dd:
        return fail('数据字典项不存在', 404)
    db.session.delete(dd)
    db.session.commit()
    return success(msg='数据字典项已删除')


# =========================================================================
# 系统配置API
# =========================================================================

@api_bp.route('/system-configs', methods=['GET'])
@login_required
@admin_required
def get_system_configs():
    """获取系统配置列表"""
    configs = SystemConfig.query.order_by(SystemConfig.config_key).all()
    return success([c.to_dict() for c in configs])


@api_bp.route('/system-configs', methods=['PUT'])
@login_required
@admin_required
def update_system_configs():
    """批量更新系统配置"""
    data = request.get_json() or {}
    user = get_current_user()

    for key, value in data.items():
        config = SystemConfig.query.filter_by(config_key=key).first()
        if config:
            config.config_value = str(value)
            config.updated_at = datetime.now()
        else:
            config = SystemConfig(
                config_key=key,
                config_value=str(value),
                description=f'用户添加的配置项',
            )
            db.session.add(config)

    db.session.commit()
    _log_operation(user, 'UPDATE', 'system_config', '更新系统配置', request)
    return success(msg='系统配置更新成功')


# =========================================================================
# AI智能云盒管理API
# =========================================================================

@api_bp.route('/cloudboxes', methods=['GET'])
@login_required
def get_cloudboxes():
    """获取AI云盒列表（支持多条件筛选）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    status = request.args.get('status', type=int)
    keyword = request.args.get('keyword', '')

    query = AICloudBox.query
    if status:
        query = query.filter_by(status=status)
    if keyword:
        query = query.filter(or_(
            AICloudBox.device_name.like(f'%{keyword}%'),
            AICloudBox.device_code.like(f'%{keyword}%'),
            AICloudBox.ip_address.like(f'%{keyword}%'),
        ))

    pagination = query.order_by(AICloudBox.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return success({
        'items': [cb.to_dict() for cb in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages,
    })


@api_bp.route('/cloudboxes', methods=['POST'])
@login_required
def create_cloudbox():
    """新增AI云盒"""
    data = request.get_json() or {}
    if not data.get('device_name') or not data.get('device_code'):
        return fail('设备名称和编码不能为空')

    if AICloudBox.query.filter_by(device_code=data['device_code']).first():
        return fail('设备编码已存在')

    cb = AICloudBox(
        device_code=data['device_code'],
        device_name=data['device_name'],
        device_model=data.get('device_model', 'RK3399 Pro D'),
        ip_address=data.get('ip_address', ''),
        mac_address=data.get('mac_address', ''),
        firmware_version=data.get('firmware_version', ''),
        location=data.get('location', ''),
        longitude=data.get('longitude'),
        latitude=data.get('latitude'),
        status=data.get('status', 1),
        remark=data.get('remark', ''),
    )
    db.session.add(cb)
    db.session.commit()

    _log_operation(get_current_user(), 'CREATE', 'cloudbox',
                   f'新增AI云盒：{cb.device_name}', request,
                   target_table='ai_cloud_boxes', target_id=cb.id)
    return success(cb.to_dict(), 'AI云盒添加成功')


@api_bp.route('/cloudboxes/<int:cb_id>', methods=['PUT'])
@login_required
def update_cloudbox(cb_id):
    """修改AI云盒"""
    cb = AICloudBox.query.get(cb_id)
    if not cb:
        return fail('AI云盒不存在', 404)

    data = request.get_json() or {}
    old_data = cb.to_dict()

    for field in ['device_code', 'device_name', 'device_model', 'ip_address',
                   'mac_address', 'firmware_version', 'location', 'remark', 'status']:
        if field in data:
            setattr(cb, field, data[field])
    if 'longitude' in data:
        cb.longitude = data['longitude']
    if 'latitude' in data:
        cb.latitude = data['latitude']

    cb.updated_at = datetime.now()
    db.session.commit()

    _log_operation(get_current_user(), 'UPDATE', 'cloudbox',
                   f'修改AI云盒：{cb.device_name}', request,
                   target_table='ai_cloud_boxes', target_id=cb.id,
                   old_data=old_data, new_data=cb.to_dict())
    return success(cb.to_dict(), 'AI云盒修改成功')


@api_bp.route('/cloudboxes/<int:cb_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_cloudbox(cb_id):
    """删除AI云盒"""
    cb = AICloudBox.query.get(cb_id)
    if not cb:
        return fail('AI云盒不存在', 404)

    # 解除关联的摄像头
    if cb.cameras.count() > 0:
        return fail('该云盒下存在关联摄像头，请先解除关联')

    cb_name = cb.device_name
    db.session.delete(cb)
    db.session.commit()

    _log_operation(get_current_user(), 'DELETE', 'cloudbox',
                   f'删除AI云盒：{cb_name}', request,
                   target_table='ai_cloud_boxes', target_id=cb_id)
    return success(msg=f'AI云盒"{cb_name}"已删除')


# =========================================================================
# 摄像头管理API
# =========================================================================

@api_bp.route('/cameras', methods=['GET'])
@login_required
def get_cameras():
    """获取摄像头列表（支持多条件筛选）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    status = request.args.get('status', type=int)
    keyword = request.args.get('keyword', '')
    cloud_box_id = request.args.get('cloud_box_id', type=int)

    query = Camera.query
    if status:
        query = query.filter_by(status=status)
    if cloud_box_id:
        query = query.filter_by(cloud_box_id=cloud_box_id)
    if keyword:
        query = query.filter(or_(
            Camera.device_name.like(f'%{keyword}%'),
            Camera.device_code.like(f'%{keyword}%'),
            Camera.location.like(f'%{keyword}%'),
            Camera.device_model.like(f'%{keyword}%'),
        ))

    pagination = query.order_by(Camera.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return success({
        'items': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages,
    })


@api_bp.route('/cameras', methods=['POST'])
@login_required
def create_camera():
    """新增摄像头"""
    data = request.get_json() or {}
    if not data.get('device_name') or not data.get('device_code'):
        return fail('设备名称和编码不能为空')
    if not data.get('longitude') or not data.get('latitude'):
        return fail('经纬度坐标不能为空')

    if Camera.query.filter_by(device_code=data['device_code']).first():
        return fail('设备编码已存在')

    camera = Camera(
        device_code=data['device_code'],
        device_name=data['device_name'],
        device_model=data.get('device_model', ''),
        camera_type=data.get('camera_type', '固定摄像头'),
        rtsp_url=data.get('rtsp_url', ''),
        ip_address=data.get('ip_address', ''),
        port=data.get('port', 554),
        resolution=data.get('resolution', '1920x1080'),
        frame_rate=data.get('frame_rate', 25),
        ptz_support=data.get('ptz_support', False),
        ptz_pan=data.get('ptz_pan'),
        ptz_tilt=data.get('ptz_tilt'),
        ptz_zoom=data.get('ptz_zoom'),
        monitor_substance=data.get('monitor_substance', '火焰/烟雾'),
        location=data.get('location', ''),
        longitude=data['longitude'],
        latitude=data['latitude'],
        altitude=data.get('altitude', 0),
        view_range=data.get('view_range', 500),
        image_url=data.get('image_url', ''),
        cloud_box_id=data.get('cloud_box_id') or None,
        status=data.get('status', 1),
    )
    db.session.add(camera)
    db.session.commit()

    _log_operation(get_current_user(), 'CREATE', 'camera',
                   f'新增摄像头：{camera.device_name}', request,
                   target_table='cameras', target_id=camera.id)
    return success(camera.to_dict(), '摄像头添加成功')


@api_bp.route('/cameras/<int:camera_id>', methods=['PUT'])
@login_required
def update_camera(camera_id):
    """修改摄像头"""
    camera = Camera.query.get(camera_id)
    if not camera:
        return fail('摄像头不存在', 404)

    data = request.get_json() or {}
    old_data = camera.to_dict()

    for field in ['device_code', 'device_name', 'device_model', 'camera_type',
                   'rtsp_url', 'ip_address', 'resolution', 'frame_rate',
                   'monitor_substance', 'location', 'image_url', 'status', 'remark']:
        if field in data:
            setattr(camera, field, data[field])
    for field in ['port', 'ptz_support', 'longitude', 'latitude', 'altitude',
                   'view_range', 'cloud_box_id', 'ptz_pan', 'ptz_tilt', 'ptz_zoom']:
        if field in data:
            setattr(camera, field, data[field])

    camera.updated_at = datetime.now()
    db.session.commit()

    _log_operation(get_current_user(), 'UPDATE', 'camera',
                   f'修改摄像头：{camera.device_name}', request,
                   target_table='cameras', target_id=camera.id,
                   old_data=old_data, new_data=camera.to_dict())
    return success(camera.to_dict(), '摄像头修改成功')


@api_bp.route('/cameras/<int:camera_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_camera(camera_id):
    """删除摄像头"""
    camera = Camera.query.get(camera_id)
    if not camera:
        return fail('摄像头不存在', 404)

    camera_name = camera.device_name
    db.session.delete(camera)
    db.session.commit()

    _log_operation(get_current_user(), 'DELETE', 'camera',
                   f'删除摄像头：{camera_name}', request,
                   target_table='cameras', target_id=camera_id)
    return success(msg=f'摄像头"{camera_name}"已删除')


# =========================================================================
# 报警事件API
# =========================================================================

@api_bp.route('/alarm-events', methods=['GET'])
@login_required
def get_alarm_events():
    """获取报警事件列表（支持多条件查找）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    event_type = request.args.get('event_type', type=int)
    alarm_level = request.args.get('alarm_level', type=int)
    process_status = request.args.get('process_status', type=int)
    keyword = request.args.get('keyword', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = AlarmEvent.query
    if event_type:
        query = query.filter_by(event_type=event_type)
    if alarm_level:
        query = query.filter_by(alarm_level=alarm_level)
    if process_status:
        query = query.filter_by(process_status=process_status)
    if keyword:
        query = query.filter(or_(
            AlarmEvent.event_code.like(f'%{keyword}%'),
            AlarmEvent.location_description.like(f'%{keyword}%'),
        ))
    if date_from:
        query = query.filter(func.date(AlarmEvent.detected_at) >= date_from)
    if date_to:
        query = query.filter(func.date(AlarmEvent.detected_at) <= date_to)

    pagination = query.order_by(AlarmEvent.detected_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return success({
        'items': [e.to_dict() for e in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages,
    })


@api_bp.route('/alarm-events/<int:event_id>', methods=['GET'])
@login_required
def get_alarm_event_detail(event_id):
    """获取报警事件详情"""
    event = AlarmEvent.query.get(event_id)
    if not event:
        return fail('事件不存在', 404)
    return success(event.to_dict())


@api_bp.route('/alarm-events/<int:event_id>/process', methods=['PUT'])
@login_required
def process_alarm_event(event_id):
    """处理报警事件（审核通过/驳回）"""
    event = AlarmEvent.query.get(event_id)
    if not event:
        return fail('事件不存在', 404)

    data = request.get_json() or {}
    action = data.get('action', '')  # 'approve' or 'reject'
    remark = data.get('remark', '')
    user = get_current_user()

    if action == 'approve':
        event.process_status = 3  # 已处理
        event.handler_remark = remark
        event.handler_id = user.id
        event.handled_at = datetime.now()
        msg = '报警事件审核通过'
    elif action == 'reject':
        event.process_status = 4  # 已驳回
        event.handler_remark = remark
        event.handler_id = user.id
        event.handled_at = datetime.now()
        msg = '报警事件已驳回'
    else:
        # 更新处理状态
        if 'process_status' in data:
            event.process_status = data['process_status']
        if 'handler_remark' in data:
            event.handler_remark = data['handler_remark']
        if not event.handler_id:
            event.handler_id = user.id
            event.handled_at = datetime.now()
        msg = '事件状态已更新'

    db.session.commit()

    _log_operation(user, 'UPDATE', 'alarm_event',
                   f'{msg}：{event.event_code}', request,
                   target_table='alarm_events', target_id=event.id)
    return success(event.to_dict(), msg)


# =========================================================================
# 摄像头故障API
# =========================================================================

@api_bp.route('/camera-faults', methods=['GET'])
@login_required
def get_camera_faults():
    """获取摄像头故障列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    fault_type = request.args.get('fault_type', type=int)
    process_status = request.args.get('process_status', type=int)

    query = CameraFault.query
    if fault_type:
        query = query.filter_by(fault_type=fault_type)
    if process_status:
        query = query.filter_by(process_status=process_status)

    pagination = query.order_by(CameraFault.occurred_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return success({
        'items': [f.to_dict() for f in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages,
    })


@api_bp.route('/camera-faults/<int:fault_id>/repair', methods=['PUT'])
@login_required
def repair_camera_fault(fault_id):
    """修复摄像头故障"""
    fault = CameraFault.query.get(fault_id)
    if not fault:
        return fail('故障记录不存在', 404)

    data = request.get_json() or {}
    user = get_current_user()

    fault.process_status = 3  # 已修复
    fault.repair_description = data.get('repair_description', '')
    fault.repair_user_id = user.id
    fault.repaired_at = datetime.now()
    db.session.commit()

    _log_operation(user, 'UPDATE', 'camera_fault',
                   f'修复摄像头故障：{fault.fault_code}', request,
                   target_table='camera_faults', target_id=fault.id)
    return success(fault.to_dict(), '故障已修复')


# =========================================================================
# AI云盒故障API
# =========================================================================

@api_bp.route('/cloudbox-faults', methods=['GET'])
@login_required
def get_cloudbox_faults():
    """获取AI云盒故障列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    fault_type = request.args.get('fault_type', type=int)
    process_status = request.args.get('process_status', type=int)

    query = CloudBoxFault.query
    if fault_type:
        query = query.filter_by(fault_type=fault_type)
    if process_status:
        query = query.filter_by(process_status=process_status)

    pagination = query.order_by(CloudBoxFault.occurred_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return success({
        'items': [f.to_dict() for f in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages,
    })


@api_bp.route('/cloudbox-faults/<int:fault_id>/repair', methods=['PUT'])
@login_required
def repair_cloudbox_fault(fault_id):
    """修复AI云盒故障"""
    fault = CloudBoxFault.query.get(fault_id)
    if not fault:
        return fail('故障记录不存在', 404)

    data = request.get_json() or {}
    user = get_current_user()

    fault.process_status = 3  # 已修复
    fault.repair_description = data.get('repair_description', '')
    fault.repair_user_id = user.id
    fault.repaired_at = datetime.now()
    db.session.commit()

    _log_operation(user, 'UPDATE', 'cloudbox_fault',
                   f'修复AI云盒故障：{fault.fault_code}', request,
                   target_table='cloud_box_faults', target_id=fault.id)
    return success(fault.to_dict(), '故障已修复')


# =========================================================================
# 统计图表数据API
# =========================================================================

@api_bp.route('/statistics/overview', methods=['GET'])
@login_required
def get_overview_statistics():
    """获取概览统计数据"""
    now = datetime.now()
    today = now.date()

    return success({
        'total_cameras': Camera.query.count(),
        'online_cameras': Camera.query.filter_by(status=1).count(),
        'fault_cameras': Camera.query.filter(Camera.status.in_([2, 3])).count(),
        'total_cloud_boxes': AICloudBox.query.count(),
        'online_cloud_boxes': AICloudBox.query.filter_by(status=1).count(),
        'total_alarms': AlarmEvent.query.count(),
        'pending_alarms': AlarmEvent.query.filter_by(process_status=1).count(),
        'today_alarms': AlarmEvent.query.filter(
            func.date(AlarmEvent.detected_at) == today
        ).count(),
        'month_alarms': AlarmEvent.query.filter(
            func.date(AlarmEvent.detected_at) >= today.replace(day=1)
        ).count(),
    })


@api_bp.route('/statistics/alarm-by-date', methods=['GET'])
@login_required
def get_alarm_by_date():
    """按日期统计报警数量"""
    days = request.args.get('days', 30, type=int)
    data = []
    for i in range(days - 1, -1, -1):
        date = datetime.now().date() - timedelta(days=i)
        count = AlarmEvent.query.filter(
            func.date(AlarmEvent.detected_at) == date
        ).count()
        data.append({'date': date.strftime('%Y-%m-%d'), 'count': count})
    return success(data)


@api_bp.route('/statistics/alarm-by-region', methods=['GET'])
@login_required
def get_alarm_by_region():
    """按区域统计报警数量"""
    results = db.session.query(
        Camera.location, func.count(AlarmEvent.id)
    ).join(AlarmEvent, AlarmEvent.camera_id == Camera.id).group_by(
        Camera.location
    ).order_by(func.count(AlarmEvent.id).desc()).all()
    data = [{'name': r[0] or '未知区域', 'value': r[1]} for r in results]
    return success(data)


@api_bp.route('/statistics/alarm-by-level', methods=['GET'])
@login_required
def get_alarm_by_level():
    """按报警级别统计"""
    level_map = {1: '紧急', 2: '重要', 3: '一般', 4: '提示'}
    results = db.session.query(
        AlarmEvent.alarm_level, func.count(AlarmEvent.id)
    ).group_by(AlarmEvent.alarm_level).all()
    data = [{'name': level_map.get(r[0], '未知'), 'value': r[1]} for r in results]
    return success(data)


@api_bp.route('/statistics/device-fault-stats', methods=['GET'])
@login_required
def get_device_fault_stats():
    """设备故障统计"""
    now = datetime.now()
    return success({
        'camera_faults': {
            'today': CameraFault.query.filter(func.date(CameraFault.occurred_at) == now.date()).count(),
            'week': CameraFault.query.filter(CameraFault.occurred_at >= now - timedelta(days=7)).count(),
            'month': CameraFault.query.filter(CameraFault.occurred_at >= now - timedelta(days=30)).count(),
        },
        'cloudbox_faults': {
            'today': CloudBoxFault.query.filter(func.date(CloudBoxFault.occurred_at) == now.date()).count(),
            'week': CloudBoxFault.query.filter(CloudBoxFault.occurred_at >= now - timedelta(days=7)).count(),
            'month': CloudBoxFault.query.filter(CloudBoxFault.occurred_at >= now - timedelta(days=30)).count(),
        },
    })


@api_bp.route('/statistics/heatmap', methods=['GET'])
@login_required
def get_heatmap_data():
    """获取热力图数据（高风险时间和区域）"""
    # 按小时统计
    hour_data = db.session.query(
        extract('hour', AlarmEvent.detected_at), func.count(AlarmEvent.id)
    ).group_by(extract('hour', AlarmEvent.detected_at)).all()
    hour_stats = [{'hour': int(r[0] or 0), 'count': r[1]} for r in hour_data]

    # 按区域统计
    region_data = db.session.query(
        Camera.longitude, Camera.latitude, func.count(AlarmEvent.id)
    ).join(AlarmEvent, AlarmEvent.camera_id == Camera.id).group_by(
        Camera.longitude, Camera.latitude
    ).all()
    heatmap_points = [
        {'lng': r[0], 'lat': r[1], 'count': r[2]} for r in region_data if r[0] and r[1]
    ]

    return success({
        'hour_stats': hour_stats,
        'heatmap_points': heatmap_points,
    })


# =========================================================================
# 日志查询API
# =========================================================================

@api_bp.route('/logs/access', methods=['GET'])
@login_required
def query_access_logs():
    """查询访问日志"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    username = request.args.get('username', '')

    query = AccessLog.query
    if username:
        query = query.filter(AccessLog.username.like(f'%{username}%'))

    pagination = query.order_by(AccessLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return success({
        'items': [l.to_dict() for l in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages,
    })


@api_bp.route('/logs/operation', methods=['GET'])
@login_required
def query_operation_logs():
    """查询操作日志"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    username = request.args.get('username', '')
    operation_type = request.args.get('operation_type', '')
    operation_module = request.args.get('operation_module', '')

    query = OperationLog.query
    if username:
        query = query.filter(OperationLog.username.like(f'%{username}%'))
    if operation_type:
        query = query.filter_by(operation_type=operation_type)
    if operation_module:
        query = query.filter_by(operation_module=operation_module)

    pagination = query.order_by(OperationLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return success({
        'items': [l.to_dict() for l in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages,
    })
