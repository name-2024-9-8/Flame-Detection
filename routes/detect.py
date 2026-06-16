"""
=============================================================================
边缘检测数据接入API — 代理到王永林的PHP后端
用于接收郭俊奇边缘端（Orange Pi 5）上报的报警/视频/心跳/故障数据

安全认证: X-API-Key 共享密钥（边缘设备 ↔ Flask代理层）
          PHP后端进一步验证 device_id 是否在数据库注册
=============================================================================
"""
from flask import Blueprint, request, jsonify, current_app
import requests

PHP_API_BASE = 'http://localhost:8080/index.php/api'
detect_bp = Blueprint('detect', __name__, url_prefix='/api')


def _verify_api_key():
    """验证边缘设备API密钥，不通过返回(响应,状态码)，通过返回None"""
    api_key = request.headers.get('X-API-Key', '')
    expected = current_app.config.get('EDGE_API_KEY', '')
    if not expected:
        return jsonify({
            'code': 500,
            'message': '服务器配置错误：EDGE_API_KEY 未设置',
            'data': None
        }), 500
    if not api_key or api_key != expected:
        return jsonify({
            'code': 401,
            'message': '未授权：缺少有效的边缘设备API密钥（X-API-Key头）',
            'data': None
        }), 401
    return None


def _proxy_post(endpoint, data=None, files=None, timeout=30):
    """通用POST代理到PHP后端"""
    url = PHP_API_BASE + endpoint
    try:
        if files:
            resp = requests.post(url, files=files, data=data, timeout=timeout)
        else:
            resp = requests.post(url, json=data, timeout=timeout,
                                 headers={'Content-Type': 'application/json'})
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({'code': 500, 'message': 'PHP API连接失败: ' + str(e), 'data': None}), 500


# ─────────────────────────────────────────────
#  POST /api/detect/alarm — 报警事件上报
# ─────────────────────────────────────────────

@detect_bp.route('/detect/alarm', methods=['POST'])
def detect_alarm():
    """接收边缘端报警事件（代理到PHP）"""
    auth_err = _verify_api_key()
    if auth_err is not None:
        return auth_err
    data = request.get_json(force=True, silent=True) or {}
    return _proxy_post('/detect/alarm', data=data)


# ─────────────────────────────────────────────
#  POST /api/detect/upload — 视频文件上传
# ─────────────────────────────────────────────

@detect_bp.route('/detect/upload', methods=['POST'])
def detect_upload():
    """接收边缘端视频上传（代理到PHP）"""
    auth_err = _verify_api_key()
    if auth_err is not None:
        return auth_err
    files = {}
    if 'file' in request.files:
        f = request.files['file']
        files['file'] = (f.filename, f.stream, f.content_type)
    data = {
        'camera_id': request.form.get('camera_id', '0'),
        'timestamp': request.form.get('timestamp', ''),
    }
    return _proxy_post('/detect/upload', data=data, files=files, timeout=60)


# ─────────────────────────────────────────────
#  POST /api/device/heartbeat — 设备心跳
# ─────────────────────────────────────────────

@detect_bp.route('/device/heartbeat', methods=['POST'])
def device_heartbeat():
    """接收边缘设备心跳（代理到PHP）"""
    auth_err = _verify_api_key()
    if auth_err is not None:
        return auth_err
    data = request.get_json(force=True, silent=True) or {}
    return _proxy_post('/device/heartbeat', data=data)


# ─────────────────────────────────────────────
#  POST /api/device/error — 设备故障上报
# ─────────────────────────────────────────────

@detect_bp.route('/device/error', methods=['POST'])
def device_error():
    """接收边缘设备故障上报（代理到PHP）"""
    auth_err = _verify_api_key()
    if auth_err is not None:
        return auth_err
    data = request.get_json(force=True, silent=True) or {}
    return _proxy_post('/device/error', data=data)
