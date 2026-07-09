"""
=============================================================================
Mock API Server — 无MySQL依赖的演示用API服务器
端口: 8080  |  模拟PHP API响应格式  |  用于前端界面演示
=============================================================================
"""
import json
import time
import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask.json.provider import DefaultJSONProvider

app = Flask(__name__)

JWT_KEY = 'vai2026_flame_jwt_secret_2026'

# =====================================================================
# Custom JSON encoder
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
        return str(o)

app.json = CustomJSONProvider(app)


# =====================================================================
# Mock data
# =====================================================================
MOCK_USERS = {
    'admin': {
        'Id': 1, 'Account': 'admin', 'RealName': '系统管理员',
        'UserType': 1, 'Email': 'admin@fire.com', 'Phone': '13800000001',
        'DepartmentId': 1, 'RoleId': 1, 'RoleName': '超级管理员',
        'Status': 1
    },
    'operator': {
        'Id': 2, 'Account': 'operator', 'RealName': '操作员',
        'UserType': 2, 'Email': 'op@fire.com', 'Phone': '13800000002',
        'DepartmentId': 2, 'RoleId': 2, 'RoleName': '操作员',
        'Status': 1
    }
}

MOCK_PASSWORDS = {
    'admin': '123456',
    'operator': '123456'
}


# =====================================================================
# Helper — JWT
# =====================================================================
def make_jwt(user):
    import jwt as pyjwt
    payload = {
        'user_id': user['Id'],
        'username': user['Account'],
        'user_type': user['UserType'],
        'exp': int(time.time()) + 86400
    }
    return pyjwt.encode(payload, JWT_KEY, algorithm='HS256')


def check_jwt():
    import jwt as pyjwt
    auth = request.headers.get('Authorization', '')
    if not auth or not auth.startswith('Bearer '):
        return None
    try:
        return pyjwt.decode(auth[7:], JWT_KEY, algorithms=['HS256'])
    except Exception:
        return None


def success(data=None, msg='ok'):
    return jsonify({'code': 200, 'msg': msg, 'data': data})


def error(msg, code=400):
    return jsonify({'code': code, 'msg': msg, 'data': None})


# =====================================================================
# Auth routes
# =====================================================================
@app.route('/index.php/api/auth/login', methods=['POST'])
def auth_login():
    account = request.form.get('account', '')
    password = request.form.get('password', '')
    if account in MOCK_USERS and MOCK_PASSWORDS.get(account) == password:
        user = MOCK_USERS[account]
        token = make_jwt(user)
        return success({
            'token': token,
            'user': {k[0].lower() + k[1:]: v for k, v in user.items()}
        })
    return error('账号或密码错误', 401)


@app.route('/index.php/api/auth/profile', methods=['GET'])
def auth_profile():
    payload = check_jwt()
    if not payload:
        return error('未登录', 401)
    username = payload.get('username', 'admin')
    user = MOCK_USERS.get(username, MOCK_USERS['admin'])
    return success({k[0].lower() + k[1:]: v for k, v in user.items()})


@app.route('/index.php/api/auth/refresh', methods=['POST'])
def auth_refresh():
    payload = check_jwt()
    if not payload:
        return error('未登录', 401)
    username = payload.get('username', 'admin')
    user = MOCK_USERS.get(username, MOCK_USERS['admin'])
    token = make_jwt(user)
    return success({'token': token})


# =====================================================================
# Statistics routes
# =====================================================================
@app.route('/index.php/api/statistics/overview', methods=['GET'])
def statistics_overview():
    return success({
        'total_cameras': 36,
        'online_cameras': 30,
        'fault_cameras': 6,
        'total_cloud_boxes': 12,
        'online_cloud_boxes': 11,
        'fault_cloud_boxes': 1,
        'total_alarms': 158,
        'pending_alarms': 5,
        'today_alarms': 3
    })


@app.route('/index.php/api/statistics/by_date', methods=['GET'])
def statistics_by_date():
    days = int(request.args.get('days', 30))
    dates = []
    for i in range(days):
        d = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        d = d - timedelta(days=days - 1 - i)
        dates.append({
            'date': d.strftime('%Y-%m-%d'),
            'count': i % 5 + 1
        })
    return success(dates)


@app.route('/index.php/api/statistics/by_region', methods=['GET'])
def statistics_by_region():
    return success({
        'regions': [
            {'name': '厂区A', 'count': 45, 'lat': 30.5, 'lng': 114.3},
            {'name': '厂区B', 'count': 32, 'lat': 30.6, 'lng': 114.4},
            {'name': '仓库区', 'count': 28, 'lat': 30.55, 'lng': 114.35},
        ]
    })


@app.route('/index.php/api/statistics/by_level', methods=['GET'])
def statistics_by_level():
    return success({'items': [
        {'level': '一级', 'count': 8},
        {'level': '二级', 'count': 25},
        {'level': '三级', 'count': 55},
    ]})


@app.route('/index.php/api/statistics/heatmap', methods=['GET'])
def statistics_heatmap():
    return success({'points': []})


# =====================================================================
# Device routes
# =====================================================================
@app.route('/index.php/api/device/camera_list', methods=['GET'])
def camera_list():
    return success({'items': [
        {'id': i, 'camera_name': f'摄像头-{i:02d}', 'camera_code': f'CAM{i:03d}',
         'location': f'位置{i}', 'ip_address': f'192.168.1.{i}',
         'status': 1 if i % 3 != 0 else 0,
         'lng': 114.3 + i * 0.01, 'lat': 30.5 + i * 0.008,
         'department_name': '监测中心', 'cloud_box_name': f'云盒-{i % 12 + 1:02d}',
         'install_time': '2025-06-15',
         'rtsp_url': f'rtsp://192.168.1.{i}:554/stream'}
        for i in range(1, 37)
    ], 'total': 36})


@app.route('/index.php/api/device/cloudbox_list', methods=['GET'])
def cloudbox_list():
    return success({'items': [
        {'id': i, 'box_name': f'云盒-{i:02d}', 'box_code': f'BOX{i:03d}',
         'location': f'机房{i}', 'status': 1 if i != 7 else 0,
         'ip_address': f'10.0.0.{i}', 'camera_count': 3}
        for i in range(1, 13)
    ], 'total': 12})


# =====================================================================
# Alarm routes
# =====================================================================
@app.route('/index.php/api/alarm/list', methods=['GET'])
def alarm_list():
    return success({'items': [
        {'id': i, 'event_name': f'火焰告警#{i}', 'camera_name': f'摄像头-{i:02d}',
         'alarm_level': 1 + i % 3, 'status': '1' if i > 3 else '2',
         'alarm_time': '2026-07-08 10:30:00', 'handler_remark': '',
         'fire_confidence': 0.92, 'lng': 114.3 + i * 0.01, 'lat': 30.5 + i * 0.008}
        for i in range(1, 11)
    ], 'total': 158})


# =====================================================================
# Fault routes
# =====================================================================
@app.route('/index.php/api/fault/camera_list', methods=['GET'])
def camera_fault_list():
    return success({'items': [
        {'id': i, 'camera_name': f'故障摄像头-{i}', 'fault_type': '连接断开',
         'fault_time': '2026-07-08 08:00:00', 'status': '0',
         'lng': 114.3 + i * 0.02, 'lat': 30.5 + i * 0.01}
        for i in range(1, 7)
    ], 'total': 6})


@app.route('/index.php/api/fault/cloudbox_list', methods=['GET'])
def cloudbox_fault_list():
    return success({'items': [
        {'id': 1, 'box_name': '云盒-07', 'fault_type': '网络异常',
         'fault_time': '2026-07-07 12:00:00', 'status': '0',
         'lng': 114.35, 'lat': 30.52}
    ], 'total': 1})


# =====================================================================
# User routes
# =====================================================================
@app.route('/index.php/api/user/list', methods=['GET'])
def user_list():
    users = list(MOCK_USERS.values())
    return success({'items': [{k[0].lower() + k[1:]: v for k, v in u.items()} for u in users],
                    'total': len(users)})


# =====================================================================
# Department / Role / Dictionary routes
# =====================================================================
@app.route('/index.php/api/department/list', methods=['GET'])
def department_list():
    return success({'items': [
        {'id': 1, 'name': '监测中心'},
        {'id': 2, 'name': '安全部'},
        {'id': 3, 'name': '运营部'},
    ]})


@app.route('/index.php/api/role/list', methods=['GET'])
def role_list():
    return success({'items': [
        {'id': 1, 'name': '超级管理员', 'permissions': 'all'},
        {'id': 2, 'name': '操作员', 'permissions': 'view'},
    ]})


@app.route('/index.php/api/dictionary/list', methods=['GET'])
def datadict_list():
    return success({'items': [
        {'id': 1, 'dict_type': 'alarm_level', 'dict_key': '1', 'dict_value': '一级告警'},
        {'id': 2, 'dict_type': 'alarm_level', 'dict_key': '2', 'dict_value': '二级告警'},
        {'id': 3, 'dict_type': 'alarm_level', 'dict_key': '3', 'dict_value': '三级告警'},
    ]})


# =====================================================================
# Config routes
# =====================================================================
@app.route('/index.php/api/system/configs', methods=['GET'])
def system_configs():
    return success({
        'alarm_threshold': 0.85,
        'smoke_threshold': 0.80,
        'detect_interval': 5,
        'storage_days': 90
    })


# =====================================================================
# Log routes
# =====================================================================
@app.route('/index.php/api/logs/access', methods=['GET'])
@app.route('/index.php/api/log/access', methods=['GET'])
def access_logs():
    return success({'items': [], 'total': 0})


@app.route('/index.php/api/logs/operation', methods=['GET'])
@app.route('/index.php/api/log/operation', methods=['GET'])
def operation_logs():
    return success({'items': [], 'total': 0})


# =====================================================================
# Catch-all for any unimplemented routes
# =====================================================================
@app.route('/index.php/api/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def catch_all(subpath):
    """未实现的API返回空成功，避免前端阻塞"""
    return success({})


# =====================================================================
# Main entry
# =====================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("  [Mock] API Server (演示模式 — 无MySQL依赖)")
    print("  端口: 8080")
    print("  用途: 前端界面演示")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8080, debug=False)
