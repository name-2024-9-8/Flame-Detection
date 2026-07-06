"""
=============================================================================
Python版PHP API替代服务器 — 替代 CodeIgniter PHP后端
端口: 8080  |  连接MySQL  |  JWT鉴权
=============================================================================
"""
import sys
import io
import os
import json
import math
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

import pymysql
import jwt as pyjwt
from flask import Flask, request, jsonify, g
from flask.json.provider import DefaultJSONProvider

# =====================================================================
# Config
# =====================================================================
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': os.environ.get('MYSQL_PASSWORD', ''),
    'database': 'flame_detection',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}

JWT_KEY = 'vai2026_flame_jwt_secret_2026'
JWT_EXPIRE = 86400

app = Flask(__name__)


# =====================================================================
# Custom JSON encoder — handle bytes and datetime
# =====================================================================
class CustomJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        return json.dumps(obj, default=self._custom_default, **kwargs)

    @staticmethod
    def _custom_default(o):
        if isinstance(o, bytes):
            return o.decode('utf-8', errors='replace')
        if isinstance(o, datetime):
            return o.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(o, timedelta):
            return str(o)
        raise TypeError(f'Object of type {type(o).__name__} is not JSON serializable')

app.json = CustomJSONProvider(app)


# =====================================================================
# Global error handler to catch all exceptions
# =====================================================================
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    traceback.print_exc()
    return jsonify({'code': 500, 'message': str(e), 'data': None}), 500


# =====================================================================
# Database helper
# =====================================================================
def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(**DB_CONFIG)
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query(sql, params=None, single=False):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(sql, params)
    if sql.strip().upper().startswith('SELECT'):
        rows = cursor.fetchall()
        cursor.close()
        return rows[0] if single and rows else (rows if not single else None)
    else:
        db.commit()
        lastid = cursor.lastrowid
        cursor.close()
        return lastid


# =====================================================================
# JWT helpers
# =====================================================================
def generate_token(user_id, account):
    payload = {
        'iss': 'flame_detection',
        'iat': int(datetime.now().timestamp()),
        'exp': int((datetime.now() + timedelta(seconds=JWT_EXPIRE)).timestamp()),
        'user_id': user_id,
        'account': account,
    }
    return pyjwt.encode(payload, JWT_KEY, algorithm='HS256')


def require_auth():
    """Extract and verify JWT from Authorization header"""
    auth = request.headers.get('Authorization', '')
    token = None
    if auth.startswith('Bearer '):
        token = auth[7:]
    else:
        token = auth

    if not token:
        return None, jsonify({'code': 401, 'message': '缺少认证 Token，请先登录', 'data': None}), 401

    try:
        payload = pyjwt.decode(token, JWT_KEY, algorithms=['HS256'])
        g.current_user_id = payload['user_id']
        g.current_account = payload['account']
        return payload, None, None
    except pyjwt.ExpiredSignatureError:
        return None, jsonify({'code': 401, 'message': 'Token 已过期，请重新登录', 'data': None}), 401
    except pyjwt.InvalidTokenError:
        return None, jsonify({'code': 401, 'message': 'Token 无效，请重新登录', 'data': None}), 401
    except Exception as e:
        import traceback
        print(f'JWT decode error: {e}')
        traceback.print_exc()
        return None, jsonify({'code': 401, 'message': f'Token 验证失败: {str(e)}', 'data': None}), 401


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload, err_resp, err_code = require_auth()
        if err_resp:
            return err_resp, err_code
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload, err_resp, err_code = require_auth()
        if err_resp:
            return err_resp, err_code
        # Check if user is admin
        u = query("SELECT Account FROM T_User WHERE Id = %s AND IsDelete = 0",
                  (g.current_user_id,), single=True)
        if u and u['Account'] == 'admin':
            return f(*args, **kwargs)
        # Check role
        ur = query("SELECT * FROM T_UserRole WHERE UserId = %s AND RoleId = 1",
                   (g.current_user_id,), single=True)
        if not ur:
            return jsonify({'code': 403, 'message': '需要超级用户权限', 'data': None}), 403
        return f(*args, **kwargs)
    return decorated


def success(data=None, message='success', code=200):
    return jsonify({'code': code, 'message': message, 'data': data})


def error(message='error', code=400, data=None):
    return jsonify({'code': code, 'message': message, 'data': data}), code


# =====================================================================
# Auth API
# =====================================================================
@app.route('/index.php/api/auth/login', methods=['POST'])
def auth_login():
    # Accept both form data and JSON
    if request.is_json:
        data = request.get_json(force=True, silent=True) or {}
        account = data.get('account', data.get('username', ''))
        password = data.get('password', '')
    else:
        account = request.form.get('account', '')
        password = request.form.get('password', '')

    if not account or not password:
        return error('账号和密码不能为空')

    user = query("SELECT * FROM T_User WHERE Account = %s AND IsDelete = 0", (account,), single=True)
    if not user:
        return error('账号或密码错误', 401)

    # Verify password (bcrypt hash or plaintext)
    import bcrypt
    stored = user['Password']
    valid = False
    try:
        if stored.startswith('$2'):
            valid = bcrypt.checkpw(password.encode('utf-8'), stored.encode('utf-8'))
        else:
            valid = (stored == password)
    except Exception:
        valid = (stored == password)

    if not valid:
        return error('账号或密码错误', 401)

    token = generate_token(user['Id'], user['Account'])

    # Get role info
    role_data = query("""
        SELECT r.Id as RoleId, r.Name as RoleName
        FROM T_UserRole ur JOIN T_Role r ON ur.RoleId = r.Id
        WHERE ur.UserId = %s LIMIT 1
    """, (user['Id'],), single=True)

    # Get branch info
    branch_data = query("SELECT Id, Name FROM T_Branch WHERE Id = %s",
                        (user.get('BranchId'),), single=True)

    data = {
        'token': token,
        'expires_in': JWT_EXPIRE,
        'user': {
            'Id': user['Id'],
            'Account': user['Account'],
            'Name': user.get('Name', ''),
            'Email': user.get('Email', ''),
            'Phone': user.get('Phone', ''),
            'AreaId': user.get('AreaId'),
            'BranchId': user.get('BranchId'),
            'BranchName': branch_data['Name'] if branch_data else '',
            'RoleId': role_data['RoleId'] if role_data else None,
            'RoleName': role_data['RoleName'] if role_data else '',
        }
    }

    # Log access
    query("INSERT INTO T_AccessLog (UserId, Url, Method, IP, CreateTime) VALUES (%s, 'api/auth/login', 'POST', %s, NOW())",
          (user['Id'], request.remote_addr or ''))

    return jsonify({'code': 200, 'message': '登录成功', 'data': data})


@app.route('/index.php/api/auth/profile', methods=['GET'])
@login_required
def auth_profile():
    user = query("""
        SELECT u.*, r.Name as RoleName, b.Name as BranchName
        FROM T_User u
        LEFT JOIN T_UserRole ur ON u.Id = ur.UserId
        LEFT JOIN T_Role r ON ur.RoleId = r.Id
        LEFT JOIN T_Branch b ON u.BranchId = b.Id
        WHERE u.Id = %s
    """, (g.current_user_id,), single=True)

    if not user:
        return error('用户不存在', 404)

    return success({
        'Id': user['Id'],
        'Account': user['Account'],
        'Name': user.get('Name', ''),
        'Email': user.get('Email', ''),
        'Phone': user.get('Phone', ''),
        'AreaId': user.get('AreaId'),
        'BranchId': user.get('BranchId'),
        'BranchName': user.get('BranchName', ''),
        'RoleName': user.get('RoleName', ''),
    })


@app.route('/index.php/api/auth/refresh', methods=['POST'])
@login_required
def auth_refresh():
    token = generate_token(g.current_user_id, g.current_account)
    return success({'token': token, 'expires_in': JWT_EXPIRE}, 'Token 刷新成功')


@app.route('/index.php/api/auth/logout', methods=['POST'])
@login_required
def auth_logout():
    return success(None, '登出成功')


# =====================================================================
# Alarm Events API
# =====================================================================
@app.route('/index.php/api/alarm/events', methods=['GET'])
@login_required
def alarm_events():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, request.args.get('per_page', 15, type=int))

    where = []
    params = []

    for key, col in [('status', 'Status'), ('event_type', 'EventType'), ('area_id', 'AreaId'),
                      ('device_id', 'DeviceId'), ('camera_id', 'CameraId'),
                      ('urgency_degree', 'UrgencyDegree'), ('keyword', None)]:
        val = request.args.get(key)
        if val and val != '' and val is not None:
            if key == 'keyword':
                where.append("(Location LIKE %s OR Description LIKE %s)")
                kw = f"%{val}%"
                params.extend([kw, kw])
            elif key == 'event_type':
                where.append(f"{col} = %s")
                params.append(val)
            elif key == 'start_time':
                where.append("CreatTime >= %s")
                params.append(val)
            elif key == 'end_time':
                where.append("CreatTime <= %s")
                params.append(val)
            else:
                where.append(f"{col} = %s")
                params.append(val)

    # Time filters
    for key, op in [('start_time', '>='), ('end_time', '<=')]:
        val = request.args.get(key)
        if val:
            where.append(f"CreatTime {op} %s")
            params.append(val)

    where_clause = " WHERE " + " AND ".join(where) if where else ""

    total = query(f"SELECT COUNT(*) as cnt FROM T_DetectResult{where_clause}", tuple(params), single=True)['cnt']

    offset = (page - 1) * per_page
    rows = query(f"""
        SELECT dr.*, c.Name as CameraName, d.Address as DeviceAddress
        FROM T_DetectResult dr
        LEFT JOIN T_Camera c ON dr.CameraId = c.Id
        LEFT JOIN T_Device d ON dr.DeviceId = d.Id
        {where_clause}
        ORDER BY dr.CreatTime DESC
        LIMIT %s OFFSET %s
    """, tuple(params + [per_page, offset]))

    return success({
        'list': rows or [],
        'total': total,
        'page': page,
        'per_page': per_page,
    })


@app.route('/index.php/api/alarm/events/<int:event_id>/update', methods=['POST'])
@login_required
def alarm_update(event_id):
    data = request.json or {}
    action = data.get('action', 'process')
    remark = data.get('operate_result', data.get('description', ''))
    urgency = data.get('urgency_degree')

    updates = []
    params = []
    if urgency:
        updates.append("UrgencyDegree = %s")
        params.append(urgency)
    if remark:
        updates.append("OperateResult = %s")
        params.append(remark)

    if action == 'audit':
        updates.append("Status = '3'")
        updates.append("AuditUserId = %s")
        updates.append("AuditTime = NOW()")
        params.append(g.current_user_id)
    else:
        updates.append("Status = '2'")
        updates.append("OperateUserId = %s")
        updates.append("OperateTime = NOW()")
        params.append(g.current_user_id)

    params.append(event_id)
    query(f"UPDATE T_DetectResult SET {', '.join(updates)} WHERE Id = %s", tuple(params))
    return success(None, '更新成功')


# =====================================================================
# Device API (AI Cloud Boxes + Cameras)
# =====================================================================
@app.route('/index.php/api/devices', methods=['GET'])
@login_required
def devices_list():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, request.args.get('per_page', 15, type=int))
    device_type = request.args.get('type', 'device')

    if device_type == 'camera':
        table = 'T_Camera'
        cols = "c.*, d.Address as DeviceAddress"
        join = "LEFT JOIN T_Device d ON c.DeviceId = d.Id"
        alias = "c"
    else:
        table = 'T_Device'
        cols = "d.*, (SELECT COUNT(*) FROM T_Camera WHERE DeviceId = d.Id) as camera_count"
        join = ""
        alias = "d"

    # Filters
    where = []
    params = []
    for key, col in [('area_id', 'AreaId'), ('device_id', 'DeviceId'), ('keyword', None)]:
        val = request.args.get(key)
        if val:
            if key == 'keyword':
                if device_type == 'camera':
                    where.append("(c.Name LIKE %s OR c.IP LIKE %s)")
                else:
                    where.append("(d.Address LIKE %s OR d.MAC LIKE %s)")
                kw = f"%{val}%"
                params.extend([kw, kw])
            else:
                where.append(f"{alias}.{col} = %s")
                params.append(val)

    where_clause = " WHERE " + " AND ".join(where) if where else ""

    total_sql = f"SELECT COUNT(*) as cnt FROM {table} {alias} {join}{where_clause}"
    total = query(total_sql, tuple(params), single=True)['cnt']

    offset = (page - 1) * per_page
    rows = query(f"SELECT {cols} FROM {table} {alias} {join}{where_clause} LIMIT %s OFFSET %s",
                 tuple(params + [per_page, offset]))

    return success({'list': rows or [], 'total': total, 'page': page, 'per_page': per_page})


@app.route('/index.php/api/devices/create', methods=['POST'])
@login_required
def device_create():
    data = request.json or {}
    device_type = data.get('type', 'device')

    if device_type == 'camera':
        cols = ['IP', 'MAC', 'CameraUrl', 'Name', 'Longitude', 'Latitude', 'AreaId',
                'Type', 'InstallTime', 'Maintainer', 'DeviceId', 'Remark']
        vals = [data.get(k.lower(), data.get(k)) for k in
                ['IP', 'MAC', 'CameraUrl', 'Name', 'Longitude', 'Latitude', 'AreaId',
                 'Type', 'InstallTime', 'Maintainer', 'DeviceId', 'Remark']]
        vals[7] = vals[7] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        placeholders = ', '.join(['%s'] * len(cols))
        query(f"INSERT INTO T_Camera ({', '.join(cols)}) VALUES ({placeholders})", tuple(vals))
    else:
        cols = ['MAC', 'Longitude', 'Latitude', 'Address', 'AreaId', 'ModelPerson',
                'ModelInfo', 'Maintainer', 'CreateTime', 'StructuralInfo', 'DetailInfo', 'Remark']
        vals = [data.get(k.lower(), data.get(k)) for k in
                ['MAC', 'Longitude', 'Latitude', 'Address', 'AreaId', 'ModelPerson',
                 'ModelInfo', 'Maintainer', 'CreateTime', 'StructuralInfo', 'DetailInfo', 'Remark']]
        vals[8] = vals[8] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        placeholders = ', '.join(['%s'] * len(cols))
        query(f"INSERT INTO T_Device ({', '.join(cols)}) VALUES ({placeholders})", tuple(vals))

    return jsonify({'code': 201, 'message': '创建成功', 'data': None})


@app.route('/index.php/api/devices/<int:dev_id>/update', methods=['POST'])
@login_required
def device_update(dev_id):
    data = request.json or {}
    device_type = data.get('type', 'device')

    if device_type == 'camera':
        table = 'T_Camera'
        field_map = {'name': 'Name', 'ip': 'IP', 'camera_url': 'CameraUrl',
                      'lng': 'Longitude', 'lat': 'Latitude', 'area_id': 'AreaId',
                      'device_id': 'DeviceId', 'camera_type': 'Type', 'maintainer': 'Maintainer',
                      'remark': 'Remark', 'type': 'Type'}
    else:
        table = 'T_Device'
        field_map = {'mac': 'MAC', 'address': 'Address', 'lng': 'Longitude', 'lat': 'Latitude',
                      'area_id': 'AreaId', 'model_info': 'ModelInfo', 'maintainer': 'Maintainer',
                      'remark': 'Remark', 'structural_info': 'StructuralInfo'}

    updates = []
    params = []
    for json_key, db_col in field_map.items():
        if json_key in data and data[json_key] is not None:
            updates.append(f"{db_col} = %s")
            params.append(data[json_key])

    if not updates:
        return success(None, '无变更')

    params.append(dev_id)
    query(f"UPDATE {table} SET {', '.join(updates)} WHERE Id = %s", tuple(params))
    return success(None, '更新成功')


@app.route('/index.php/api/devices/<int:dev_id>/delete', methods=['GET'])
@login_required
def device_delete(dev_id):
    device_type = request.args.get('type', 'device')
    table = 'T_Camera' if device_type == 'camera' else 'T_Device'
    query(f"DELETE FROM {table} WHERE Id = %s", (dev_id,))
    return success(None, '删除成功')


# =====================================================================
# Statistics API
# =====================================================================
@app.route('/index.php/api/statistics', methods=['GET'])
@login_required
def statistics():
    dim = request.args.get('dimension', 'summary')

    if dim == 'summary':
        exclude_fault = request.args.get('exclude_fault_camera', '0') == '1'

        if exclude_fault:
            # 排除故障摄像头的报警（故障摄像头无法检测火情）
            # ★ 按摄像头去重：每个摄像头只算一个报警事件（与地图标记数一致）
            fault_filter = " AND CameraId NOT IN (SELECT CameraId FROM T_CameraError)"
            total_alarms = query(
                "SELECT COUNT(DISTINCT CameraId) as cnt FROM T_DetectResult WHERE 1=1" + fault_filter,
                single=True)['cnt']
            pending = query(
                "SELECT COUNT(DISTINCT CameraId) as cnt FROM T_DetectResult WHERE Status = '1'" + fault_filter,
                single=True)['cnt']
            today_count = query(
                "SELECT COUNT(DISTINCT CameraId) as cnt FROM T_DetectResult WHERE DATE(CreatTime) = CURDATE()" + fault_filter,
                single=True)['cnt']
        else:
            total_alarms = query("SELECT COUNT(DISTINCT CameraId) as cnt FROM T_DetectResult", single=True)['cnt']
            pending = query("SELECT COUNT(DISTINCT CameraId) as cnt FROM T_DetectResult WHERE Status = '1'", single=True)['cnt']
            today_count = query("SELECT COUNT(DISTINCT CameraId) as cnt FROM T_DetectResult WHERE DATE(CreatTime) = CURDATE()", single=True)['cnt']

        return success({'total': total_alarms, 'pending_count': pending, 'today_count': today_count})

    elif dim == 'time':
        start = request.args.get('start_time', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00'))
        end = request.args.get('end_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        rows = query("""
            SELECT DATE(CreatTime) as time_label, COUNT(*) as total
            FROM T_DetectResult
            WHERE CreatTime BETWEEN %s AND %s
            GROUP BY DATE(CreatTime) ORDER BY time_label
        """, (start, end))
        return success(rows or [])

    elif dim == 'area':
        rows = query("""
            SELECT COALESCE(a.Name, '未知区域') as area_name, COUNT(*) as total
            FROM T_DetectResult dr
            LEFT JOIN T_Area a ON dr.AreaId = a.Id
            GROUP BY a.Name ORDER BY total DESC
        """)
        return success(rows or [])

    elif dim == 'level':
        rows = query("""
            SELECT COALESCE(UrgencyDegree, '一般') as urgency_name, COUNT(*) as total
            FROM T_DetectResult
            GROUP BY UrgencyDegree ORDER BY FIELD(UrgencyDegree, '紧急', '重要', '一般', '提示')
        """)
        return success(rows or [])

    return success({})


@app.route('/index.php/api/statistics/health', methods=['GET'])
def statistics_health():
    return jsonify({'code': 200, 'message': 'ok', 'data': {'status': 'healthy'}})


# =====================================================================
# User Management API
# =====================================================================
@app.route('/index.php/api/users', methods=['GET'])
@login_required
def users_list():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, request.args.get('per_page', 20, type=int))

    where = ["u.IsDelete = 0"]
    params = []

    for key in ['username', 'real_name']:
        val = request.args.get(key)
        if val:
            col = 'Account' if key == 'username' else 'Name'
            where.append(f"u.{col} LIKE %s")
            params.append(f"%{val}%")

    user_type = request.args.get('user_type')
    if user_type == '1':
        where.append("r.Name = '超级管理员'")

    where_clause = " WHERE " + " AND ".join(where)

    total = query(f"""
        SELECT COUNT(*) as cnt FROM T_User u
        LEFT JOIN T_UserRole ur ON u.Id = ur.UserId
        LEFT JOIN T_Role r ON ur.RoleId = r.Id
        {where_clause}
    """, tuple(params), single=True)['cnt']

    offset = (page - 1) * per_page
    rows = query(f"""
        SELECT u.*, r.Name as RoleName, b.Name as BranchName
        FROM T_User u
        LEFT JOIN T_UserRole ur ON u.Id = ur.UserId
        LEFT JOIN T_Role r ON ur.RoleId = r.Id
        LEFT JOIN T_Branch b ON u.BranchId = b.Id
        {where_clause}
        ORDER BY u.Id LIMIT %s OFFSET %s
    """, tuple(params + [per_page, offset]))

    return success({'list': rows or [], 'total': total, 'page': page, 'per_page': per_page})


@app.route('/index.php/api/users/create', methods=['POST'])
@login_required
def user_create():
    data = request.json or {}
    if not data.get('account'):
        return error('账号不能为空')
    if not data.get('name'):
        return error('姓名不能为空')

    exist = query("SELECT Id FROM T_User WHERE Account = %s", (data['account'],), single=True)
    if exist:
        return error('该账号已存在')

    import bcrypt
    pwd = bcrypt.hashpw(data.get('password', '123456').encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    uid = query("""
        INSERT INTO T_User (Account, Name, Password, Email, Phone, AreaId, BranchId, CreateTime, CreateBy, IsDelete, Remark)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, 0, %s)
    """, (data.get('account'), data.get('name'), pwd,
          data.get('email'), data.get('phone'),
          data.get('area_id'), data.get('branch_id'),
          g.current_user_id, data.get('remark', '')))

    if data.get('role_id'):
        query("INSERT INTO T_UserRole (UserId, RoleId) VALUES (%s, %s)", (uid, data['role_id']))

    return jsonify({'code': 201, 'message': '用户创建成功', 'data': {'id': uid}})


@app.route('/index.php/api/users/<int:user_id>/update', methods=['POST'])
@login_required
def user_update(user_id):
    data = request.json or {}
    updates = []
    params = []

    field_map = {'name': 'Name', 'email': 'Email', 'phone': 'Phone',
                  'area_id': 'AreaId', 'branch_id': 'BranchId', 'remark': 'Remark'}
    for json_key, db_col in field_map.items():
        if json_key in data and data[json_key] is not None:
            updates.append(f"{db_col} = %s")
            params.append(data[json_key])

    if data.get('password'):
        import bcrypt
        pwd = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        updates.append("Password = %s")
        params.append(pwd)

    if updates:
        params.append(user_id)
        query(f"UPDATE T_User SET {', '.join(updates)} WHERE Id = %s", tuple(params))

    if data.get('role_id') is not None:
        query("DELETE FROM T_UserRole WHERE UserId = %s", (user_id,))
        if data['role_id']:
            query("INSERT INTO T_UserRole (UserId, RoleId) VALUES (%s, %s)", (user_id, data['role_id']))

    return success(None, '更新成功')


@app.route('/index.php/api/users/<int:user_id>/delete', methods=['GET'])
@login_required
def user_delete(user_id):
    u = query("SELECT Account FROM T_User WHERE Id = %s", (user_id,), single=True)
    if u and u['Account'] == 'admin':
        return error('不允许删除管理员账号')
    query("UPDATE T_User SET IsDelete = 1 WHERE Id = %s", (user_id,))
    return success(None, '删除成功')


# =====================================================================
# Role Management API
# =====================================================================
@app.route('/index.php/api/roles', methods=['GET'])
@login_required
def roles_list():
    rows = query("""
        SELECT r.*,
               (SELECT COUNT(*) FROM T_Authority WHERE RoleId = r.Id) as authority_count,
               (SELECT COUNT(*) FROM T_UserRole WHERE RoleId = r.Id) as user_count
        FROM T_Role r
        WHERE r.IsDelete = 0
    """)
    return success({'list': rows or []})


@app.route('/index.php/api/roles/create', methods=['POST'])
@login_required
def role_create():
    data = request.json or {}
    if not data.get('name'):
        return error('角色名称不能为空')

    rid = query("INSERT INTO T_Role (Name, Description, IsDelete) VALUES (%s, %s, 0)",
                (data['name'], data.get('description', '')))

    for auth in data.get('authorities', []):
        query("INSERT INTO T_Authority (RoleId, Authority) VALUES (%s, %s)", (rid, auth))

    return jsonify({'code': 201, 'message': '创建成功', 'data': {'id': rid}})


@app.route('/index.php/api/roles/<int:role_id>/update', methods=['POST'])
@login_required
def role_update(role_id):
    data = request.json or {}
    updates = []
    params = []
    if 'name' in data:
        updates.append("Name = %s")
        params.append(data['name'])
    if 'description' in data:
        updates.append("Description = %s")
        params.append(data['description'])

    if updates:
        params.append(role_id)
        query(f"UPDATE T_Role SET {', '.join(updates)} WHERE Id = %s", tuple(params))

    if 'authorities' in data:
        query("DELETE FROM T_Authority WHERE RoleId = %s", (role_id,))
        for auth in data['authorities']:
            query("INSERT INTO T_Authority (RoleId, Authority) VALUES (%s, %s)", (role_id, auth))

    return success(None, '更新成功')


@app.route('/index.php/api/roles/<int:role_id>/delete', methods=['GET'])
@login_required
def role_delete(role_id):
    query("UPDATE T_Role SET IsDelete = 1 WHERE Id = %s", (role_id,))
    return success(None, '删除成功')


# =====================================================================
# Branch/Department API
# =====================================================================
@app.route('/index.php/api/branches', methods=['GET'])
@login_required
def branches_list():
    rows = query("""
        SELECT b.*, p.Name as ParentName, u.Name as LeaderName
        FROM T_Branch b
        LEFT JOIN T_Branch p ON b.ParentId = p.Id
        LEFT JOIN T_User u ON b.LeaderId = u.Id
        ORDER BY b.Id
    """)
    return success({'list': rows or []})


@app.route('/index.php/api/branches/create', methods=['POST'])
@login_required
def branch_create():
    data = request.json or {}
    if not data.get('name'):
        return error('部门名称不能为空')
    bid = query("INSERT INTO T_Branch (Name, ParentId, LeaderId, CreateTime, CreateBy, Remark) VALUES (%s, %s, %s, NOW(), %s, %s)",
                (data['name'], data.get('parent_id', 0), data.get('leader_id'), g.current_user_id, data.get('remark', '')))
    return jsonify({'code': 201, 'message': '创建成功', 'data': {'id': bid}})


@app.route('/index.php/api/branches/<int:branch_id>/update', methods=['POST'])
@login_required
def branch_update(branch_id):
    data = request.json or {}
    updates = []
    params = []
    for k in ('name', 'parent_id', 'leader_id', 'remark'):
        if k in data and data[k] is not None:
            col = 'Name' if k == 'name' else ('ParentId' if k == 'parent_id' else ('LeaderId' if k == 'leader_id' else 'Remark'))
            updates.append(f"{col} = %s")
            params.append(data[k])
    if updates:
        params.append(branch_id)
        query(f"UPDATE T_Branch SET {', '.join(updates)} WHERE Id = %s", tuple(params))
    return success(None, '更新成功')


@app.route('/index.php/api/branches/<int:branch_id>/delete', methods=['GET'])
@login_required
def branch_delete(branch_id):
    query("DELETE FROM T_Branch WHERE Id = %s", (branch_id,))
    return success(None, '删除成功')


# =====================================================================
# Dictionary API
# =====================================================================
@app.route('/index.php/api/dictionary', methods=['GET'])
@login_required
def dictionary_list():
    dict_type = request.args.get('dict_type', '')
    if dict_type:
        rows = query("SELECT * FROM T_Dictionary WHERE `Key` = %s ORDER BY Id", (dict_type,))
    else:
        rows = query("SELECT * FROM T_Dictionary ORDER BY `Key`, Id")
    return success({'list': rows or []})


@app.route('/index.php/api/dictionary/create', methods=['POST'])
@login_required
def dictionary_create():
    data = request.json or {}
    did = query("INSERT INTO T_Dictionary (`Key`, `Value`, Remark) VALUES (%s, %s, %s)",
                (data.get('key', ''), data.get('value', ''), data.get('remark', '')))
    return jsonify({'code': 201, 'message': '创建成功', 'data': {'id': did}})


@app.route('/index.php/api/dictionary/<int:dict_id>/update', methods=['POST'])
@login_required
def dictionary_update(dict_id):
    data = request.json or {}
    updates = []
    params = []
    for json_k, db_k in [('key', 'Key'), ('value', 'Value'), ('remark', 'Remark')]:
        if json_k in data and data[json_k] is not None:
            updates.append(f"`{db_k}` = %s")
            params.append(data[json_k])
    if updates:
        params.append(dict_id)
        query(f"UPDATE T_Dictionary SET {', '.join(updates)} WHERE Id = %s", tuple(params))
    return success(None, '更新成功')


@app.route('/index.php/api/dictionary/<int:dict_id>/delete', methods=['GET'])
@login_required
def dictionary_delete(dict_id):
    query("DELETE FROM T_Dictionary WHERE Id = %s", (dict_id,))
    return success(None, '删除成功')


# =====================================================================
# System Config API
# =====================================================================
@app.route('/index.php/api/config', methods=['GET'])
@login_required
def config_get():
    site = query("SELECT * FROM T_Site LIMIT 1", single=True)
    return success(site or {})


@app.route('/index.php/api/config/update', methods=['POST'])
@login_required
def config_update():
    data = request.json or {}
    updates = []
    params = []
    field_map = {'thresh': 'thresh', 'width': 'width', 'height': 'height',
                  'video_times': 'video_times', 'heartBeat': 'heartBeat',
                  'exception_times': 'exception_times'}
    for k, v in field_map.items():
        if k in data:
            updates.append(f"{v} = %s")
            params.append(data[k])
    if updates:
        query(f"UPDATE T_Site SET {', '.join(updates)}", tuple(params))
    return success(None, '更新成功')


# =====================================================================
# Faults API
# =====================================================================
@app.route('/index.php/api/faults/camera', methods=['GET'])
@login_required
def camera_faults():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, request.args.get('per_page', 15, type=int))

    total = query("SELECT COUNT(*) as cnt FROM T_CameraError", single=True)['cnt']
    today = query("SELECT COUNT(*) as cnt FROM T_CameraError WHERE DATE(CreateTime) = CURDATE()", single=True)['cnt']

    offset = (page - 1) * per_page
    rows = query("""
        SELECT ce.*, c.Name as CameraName, c.IP as CameraIP, c.Longitude, c.Latitude
        FROM T_CameraError ce
        LEFT JOIN T_Camera c ON ce.CameraId = c.Id
        ORDER BY ce.CreateTime DESC LIMIT %s OFFSET %s
    """, (per_page, offset))

    return success({
        'list': rows or [], 'total': total, 'page': page, 'per_page': per_page,
        'stats': {'today': today, 'week': 0, 'month': 0, 'year': 0}
    })


@app.route('/index.php/api/faults/device', methods=['GET'])
@login_required
def device_faults():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, request.args.get('per_page', 15, type=int))

    total = query("SELECT COUNT(*) as cnt FROM T_DeviceError", single=True)['cnt']
    today = query("SELECT COUNT(*) as cnt FROM T_DeviceError WHERE DATE(CreateTime) = CURDATE()", single=True)['cnt']

    offset = (page - 1) * per_page
    rows = query("""
        SELECT de.*, d.Address as DeviceAddress, d.MAC as DeviceMAC, d.Longitude, d.Latitude
        FROM T_DeviceError de
        LEFT JOIN T_Device d ON de.DeviceId = d.Id
        ORDER BY de.CreateTime DESC LIMIT %s OFFSET %s
    """, (per_page, offset))

    return success({
        'list': rows or [], 'total': total, 'page': page, 'per_page': per_page,
        'stats': {'today': today, 'week': 0, 'month': 0, 'year': 0}
    })


@app.route('/index.php/api/faults/camera/<int:fault_id>/repair', methods=['POST'])
@login_required
def camera_fault_repair(fault_id):
    query("DELETE FROM T_CameraError WHERE Id = %s", (fault_id,))
    return success(None, '维修成功')


@app.route('/index.php/api/faults/device/<int:fault_id>/repair', methods=['POST'])
@login_required
def device_fault_repair(fault_id):
    query("DELETE FROM T_DeviceError WHERE Id = %s", (fault_id,))
    return success(None, '维修成功')


# =====================================================================
# Detect API (Edge AI) - requires X-API-Key
# =====================================================================
@app.route('/index.php/api/detect/alarm', methods=['POST'])
def detect_alarm():
    data = request.json or {}
    query("""
        INSERT INTO T_DetectResult (EventType, Confidence, Longitude, Latitude, Location,
            CameraId, DeviceId, Status, CreatTime, UrgencyDegree)
        VALUES (%s, %s, %s, %s, %s, %s, %s, '1', NOW(), %s)
    """, (data.get('event_type', 'fire'), data.get('confidence', 0),
          data.get('longitude'), data.get('latitude'), data.get('location', ''),
          data.get('camera_id'), data.get('device_id'),
          data.get('urgency_degree', '一般')))
    return jsonify({'code': 201, 'message': '报警已记录', 'data': None})


@app.route('/index.php/api/detect/upload', methods=['POST'])
def detect_upload():
    return jsonify({'code': 201, 'message': '上传成功', 'data': None})


@app.route('/index.php/api/device/heartbeat', methods=['POST'])
def device_heartbeat():
    data = request.json or {}
    device_id = data.get('device_id')
    if device_id:
        query("UPDATE T_Device SET LastConnectTime = NOW() WHERE Id = %s", (device_id,))
    return jsonify({'code': 200, 'message': '心跳已接收', 'data': None})


@app.route('/index.php/api/device/error', methods=['POST'])
def device_error():
    data = request.json or {}
    query("INSERT INTO T_DeviceError (DeviceId, MAC, CreateTime, ErrorCode, ErrorMsg) VALUES (%s, %s, NOW(), %s, %s)",
          (data.get('device_id'), data.get('mac', ''), data.get('error_code', ''), data.get('error_msg', '')))
    return jsonify({'code': 201, 'message': '故障已记录', 'data': None})


# =====================================================================
# Logs API
# =====================================================================
@app.route('/index.php/api/logs/access', methods=['GET'])
@login_required
def logs_access():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, request.args.get('per_page', 20, type=int))

    where = []
    params = []
    username = request.args.get('username')
    if username:
        where.append("u.Account LIKE %s")
        params.append(f"%{username}%")

    where_clause = " WHERE " + " AND ".join(where) if where else ""

    total_sql = f"""
        SELECT COUNT(*) as cnt FROM T_AccessLog al
        LEFT JOIN T_User u ON al.UserId = u.Id
        {where_clause}
    """
    total = query(total_sql, tuple(params), single=True)['cnt']
    offset = (page - 1) * per_page

    rows_sql = f"""
        SELECT al.*, u.Account as Username
        FROM T_AccessLog al
        LEFT JOIN T_User u ON al.UserId = u.Id
        {where_clause}
        ORDER BY al.CreateTime DESC LIMIT %s OFFSET %s
    """
    rows = query(rows_sql, tuple(params + [per_page, offset]))

    return success({'list': rows or [], 'total': total, 'page': page, 'per_page': per_page})


@app.route('/index.php/api/logs/operation', methods=['GET'])
@login_required
def logs_operation():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, request.args.get('per_page', 20, type=int))

    total = query("SELECT COUNT(*) as cnt FROM T_OperateLog", single=True)['cnt']
    offset = (page - 1) * per_page
    rows = query("""
        SELECT ol.*, u.Account as Username
        FROM T_OperateLog ol
        LEFT JOIN T_User u ON ol.UserId = u.Id
        ORDER BY ol.CreateTime DESC LIMIT %s OFFSET %s
    """, (per_page, offset))

    return success({'list': rows or [], 'total': total, 'page': page, 'per_page': per_page})


# =====================================================================
# Main entry
# =====================================================================
if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    print("=" * 60)
    print("  [PHP-Alt] Python API Server (替代PHP后端)")
    print("  MySQL: 127.0.0.1:3306  flame_detection")
    print("  端口: 8080")
    print("=" * 60)

    app.run(host='127.0.0.1', port=8080, debug=True)
