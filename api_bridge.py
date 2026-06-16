"""
=============================================================================
API 桥接层 — Flask前端 ↔ PHP后端
作者：王永林（后端开发与系统集成工程师）
创建时间：2026-06-12
修改时间：2026-06-16  修复：移除datadict_list死桩；修复部门/角色/字典数据管道
功能描述：封装所有对B的PHP REST API的HTTP调用，处理字段映射和格式转换，
          使C的Flask前端可以无感知地切换数据源（从SQLite到B的MySQL+PHP）
=============================================================================
"""
import math
import requests
from datetime import datetime

# B的PHP API 基础地址
PHP_API_BASE = 'http://localhost:8080/index.php/api'


class APIBridge:
    """PHP API 调用桥接，类级别缓存 JWT Token"""

    _token = None
    _user_info = None

    # =========================================================================
    # 底层 HTTP 调用
    # =========================================================================

    @classmethod
    def _get(cls, path, params=None, auth=True):
        """GET 请求"""
        headers = {}
        if auth and cls._token:
            headers['Authorization'] = 'Bearer ' + str(cls._token)
        try:
            resp = requests.get(
                PHP_API_BASE + '/' + path,
                params=params,
                headers=headers,
                timeout=10
            )
            return resp.json()
        except requests.RequestException as e:
            return {'code': 500, 'message': 'API连接失败: ' + str(e), 'data': None}

    @classmethod
    def _post(cls, path, data=None, auth=True):
        """POST 请求"""
        headers = {}
        if auth and cls._token:
            headers['Authorization'] = 'Bearer ' + str(cls._token)
        try:
            resp = requests.post(
                PHP_API_BASE + '/' + path,
                data=data,
                headers=headers,
                timeout=10
            )
            return resp.json()
        except requests.RequestException as e:
            return {'code': 500, 'message': 'API连接失败: ' + str(e), 'data': None}

    @classmethod
    def _to_c_format(cls, php_result):
        """将B的PHP响应 {code, message, data} → C的Flask格式 {code, msg, data}"""
        if php_result is None:
            return {'code': 500, 'msg': '无响应', 'data': None}
        return {
            'code': php_result.get('code', 500),
            'msg': php_result.get('message', 'error'),
            'data': php_result.get('data', None),
        }

    # =========================================================================
    # 认证相关
    # =========================================================================

    @classmethod
    def login(cls, account, password):
        """登录 → 获取JWT，返回C格式的用户数据"""
        result = cls._post('auth/login', data={
            'account': account,
            'password': password,
        }, auth=False)

        if result.get('code') == 200:
            data = result.get('data', {})
            cls._token = data.get('token')
            cls._user_info = data.get('user', {})
            return {
                'code': 200,
                'msg': '登录成功',
                'data': {
                    'token': data.get('token'),
                    'token_type': 'Bearer',
                    'expires_in': data.get('expires_in', 86400),
                    'user': cls._map_user(cls._user_info),
                }
            }
        return cls._to_c_format(result)

    @classmethod
    def get_profile(cls):
        """获取当前用户信息"""
        result = cls._get('auth/profile')
        if result.get('code') == 200:
            data = result.get('data', {})
            return {
                'code': 200,
                'msg': 'success',
                'data': cls._map_user(data),
            }
        return cls._to_c_format(result)

    @classmethod
    def refresh_token(cls):
        """刷新JWT"""
        result = cls._post('auth/refresh')
        if result.get('code') == 200:
            data = result.get('data', {})
            cls._token = data.get('token')
            return {
                'code': 200, 'msg': 'Token刷新成功',
                'data': {
                    'token': cls._token,
                    'expires_in': data.get('expires_in', 86400),
                }
            }
        return cls._to_c_format(result)

    @classmethod
    def logout(cls):
        """登出（清空本地缓存）"""
        cls._token = None
        cls._user_info = None
        return {'code': 200, 'msg': '登出成功', 'data': None}

    @classmethod
    def set_token(cls, token):
        """从外部设置token（session恢复时）"""
        cls._token = token

    @classmethod
    def get_token(cls):
        return cls._token

    @classmethod
    def get_user_info(cls):
        return cls._user_info

    # =========================================================================
    # 报警事件
    # =========================================================================

    @classmethod
    def alarm_list(cls, page=1, per_page=15, **filters):
        """分页查询报警事件列表"""
        params = {'page': page, 'per_page': per_page}
        # B的过滤参数
        filter_map = {
            'status': 'status',
            'event_type': 'event_type',
            'area_id': 'area_id',
            'urgency_degree': 'urgency_degree',
            'device_id': 'device_id',
            'camera_id': 'camera_id',
            'start_time': 'start_time',
            'end_time': 'end_time',
            'keyword': 'keyword',
            'alarm_level': 'alarm_level',
        }
        for c_key, b_key in filter_map.items():
            if c_key in filters and filters[c_key] is not None and filters[c_key] != '':
                val = filters[c_key]
                # C用数字(1/2/3)，B用字符串(fire/smoke)
                if c_key == 'event_type':
                    val = {1: 'fire', 2: 'smoke', 3: 'device'}.get(val, val)
                if c_key == 'status':
                    val = str(val)  # B用字符串状态
                # C用数字(1-4)，B用中文(紧急/重要/一般/提示)
                if c_key == 'alarm_level':
                    val = {1: '紧急', 2: '重要', 3: '一般', 4: '提示'}.get(val, val)
                params[b_key] = val

        result = cls._get('alarm/events', params=params)
        if result.get('code') == 200:
            data = result.get('data', {})
            items = [cls._map_alarm(item) for item in data.get('list', [])]
            total = data.get('total', 0)
            return {
                'code': 200, 'msg': 'success',
                'data': {
                    'items': items,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'pages': max(1, math.ceil(total / per_page)),
                }
            }
        return cls._to_c_format(result)

    @classmethod
    def alarm_detail(cls, event_id):
        """报警事件详情"""
        result = cls._get('alarm/events/' + str(event_id))
        if result.get('code') == 200:
            return {
                'code': 200, 'msg': 'success',
                'data': cls._map_alarm(result.get('data', {}), detail=True),
            }
        return cls._to_c_format(result)

    @classmethod
    def alarm_process(cls, event_id, action, user_id, handler_remark='', urgency_degree=None):
        """处理/审核报警事件"""
        data = {
            'action': action,  # 'process' or 'audit'
            'operate_result': handler_remark,
            'description': handler_remark,
        }
        if urgency_degree:
            data['urgency_degree'] = urgency_degree
        result = cls._post('alarm/events/' + str(event_id) + '/update', data=data)
        return cls._to_c_format(result)

    # =========================================================================
    # 设备管理 - AI云盒
    # =========================================================================

    @classmethod
    def cloudbox_list(cls, page=1, per_page=15, **filters):
        """AI云盒列表"""
        params = {'page': page, 'per_page': per_page, 'type': 'device'}
        if filters.get('status') is not None:
            params['status'] = filters['status']
        if filters.get('area_id') is not None:
            params['area_id'] = filters['area_id']
        if filters.get('keyword'):
            params['keyword'] = filters['keyword']

        result = cls._get('devices', params=params)
        if result.get('code') == 200:
            data = result.get('data', {})
            items = [cls._map_cloudbox(item) for item in data.get('list', [])]
            total = data.get('total', 0)
            return {
                'code': 200, 'msg': 'success',
                'data': {
                    'items': items,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'pages': max(1, math.ceil(total / per_page)),
                }
            }
        return cls._to_c_format(result)

    @classmethod
    def cloudbox_create(cls, data):
        """新增AI云盒"""
        php_data = {
            'type': 'device',
            'mac': data.get('device_code', ''),
            'address': data.get('location') or data.get('device_name', ''),
            'lng': str(data.get('longitude', '')),
            'lat': str(data.get('latitude', '')),
            'model_info': data.get('device_model', ''),
            'maintainer': data.get('remark', ''),
            'area_id': data.get('area_id'),
            'structural_info': data.get('firmware_version', ''),
        }
        result = cls._post('devices/create', data=php_data)
        if result.get('code') == 201:
            result['code'] = 200
            result['message'] = 'AI云盒添加成功'
        return cls._to_c_format(result)

    @classmethod
    def cloudbox_update(cls, cb_id, data):
        """修改AI云盒"""
        php_data = {'type': 'device'}
        field_map = {
            'ip_address': 'ip',
            'location': 'address',
            'longitude': 'lng',
            'latitude': 'lat',
            'device_model': 'model_info',
            'remark': 'remark',
            'device_name': 'address',
        }
        for c_field, b_field in field_map.items():
            if c_field in data and data[c_field] is not None:
                php_data[b_field] = data[c_field]
        if 'device_code' in data:
            pass  # B的表中没有device_code字段，跳过
        if 'status' in data:
            pass  # B的表中没有status字段，跳过

        result = cls._post('devices/' + str(cb_id) + '/update', data=php_data)
        return cls._to_c_format(result)

    @classmethod
    def cloudbox_delete(cls, cb_id):
        """删除AI云盒"""
        result = cls._get('devices/' + str(cb_id) + '/delete', params={'type': 'device'})
        return cls._to_c_format(result)

    # =========================================================================
    # 设备管理 - 摄像头
    # =========================================================================

    @classmethod
    def camera_list(cls, page=1, per_page=15, **filters):
        """摄像头列表"""
        params = {'page': page, 'per_page': per_page, 'type': 'camera'}
        if filters.get('area_id') is not None:
            params['area_id'] = filters['area_id']
        if filters.get('device_id') is not None:
            params['device_id'] = filters['device_id']
        if filters.get('keyword'):
            params['keyword'] = filters['keyword']

        result = cls._get('devices', params=params)
        if result.get('code') == 200:
            data = result.get('data', {})
            items = [cls._map_camera(item) for item in data.get('list', [])]
            total = data.get('total', 0)
            return {
                'code': 200, 'msg': 'success',
                'data': {
                    'items': items,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'pages': max(1, math.ceil(total / per_page)),
                }
            }
        return cls._to_c_format(result)

    @classmethod
    def camera_create(cls, data):
        """新增摄像头"""
        php_data = {
            'type': 'camera',
            'name': data.get('device_name', ''),
            'ip': data.get('ip_address', ''),
            'camera_url': data.get('rtsp_url', ''),
            'lng': str(data.get('longitude', '')),
            'lat': str(data.get('latitude', '')),
            'area_id': data.get('area_id'),
            'device_id': data.get('cloud_box_id'),
            'camera_type': data.get('camera_type', ''),
            'mac': data.get('device_code', ''),
            'maintainer': data.get('remark', ''),
        }
        result = cls._post('devices/create', data=php_data)
        if result.get('code') == 201:
            result['code'] = 200
            result['message'] = '摄像头添加成功'
        return cls._to_c_format(result)

    @classmethod
    def camera_update(cls, cam_id, data):
        """修改摄像头"""
        php_data = {'type': 'camera'}
        field_map = {
            'device_name': 'name',
            'ip_address': 'ip',
            'rtsp_url': 'camera_url',
            'longitude': 'lng',
            'latitude': 'lat',
            'area_id': 'area_id',
            'cloud_box_id': 'device_id',
            'camera_type': 'camera_type',
            'remark': 'remark',
        }
        for c_field, b_field in field_map.items():
            if c_field in data and data[c_field] is not None:
                php_data[b_field] = data[c_field]

        result = cls._post('devices/' + str(cam_id) + '/update', data=php_data)
        return cls._to_c_format(result)

    @classmethod
    def camera_delete(cls, cam_id):
        """删除摄像头"""
        result = cls._get('devices/' + str(cam_id) + '/delete', params={'type': 'camera'})
        return cls._to_c_format(result)

    # =========================================================================
    # 统计分析
    # =========================================================================

    @classmethod
    def statistics_overview(cls):
        """概览统计（聚合多个API — 真实故障数据）"""
        summary_result = cls._get('statistics', params={'dimension': 'summary'})
        devices_result = cls._get('devices', params={'per_page': 1})
        cameras_result = cls._get('devices', params={'type': 'camera', 'per_page': 1})
        alarms_result = cls._get('alarm/events', params={'per_page': 1})
        # ★ 获取真实故障数
        cam_fault_result = cls._get('faults/camera', params={'per_page': 1})
        box_fault_result = cls._get('faults/device', params={'per_page': 1})

        total_cameras = cameras_result.get('data', {}).get('total', 0)
        total_boxes = devices_result.get('data', {}).get('total', 0)
        fault_cameras = cam_fault_result.get('data', {}).get('total', 0) if cam_fault_result.get('code') == 200 else 0
        fault_boxes = box_fault_result.get('data', {}).get('total', 0) if box_fault_result.get('code') == 200 else 0
        total_alarms = alarms_result.get('data', {}).get('total', 0)
        pending_alarms = int(summary_result.get('data', {}).get('pending_count', 0)) if summary_result.get('code') == 200 else 0

        # 今日告警 = 当日故障数（camera + device）
        cam_stats = cam_fault_result.get('data', {}).get('stats', {}) if cam_fault_result.get('code') == 200 else {}
        box_stats = box_fault_result.get('data', {}).get('stats', {}) if box_fault_result.get('code') == 200 else {}
        today_alarms = cam_stats.get('today', 0) + box_stats.get('today', 0)

        # 本月报警数（从summary获取当月数据）
        month_alarms = 0
        result = cls._get('statistics', params={'dimension': 'summary',
            'start_time': datetime.now().strftime('%Y-%m-01 00:00:00'),
            'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
        if result.get('code') == 200:
            month_alarms = result.get('data', {}).get('total', 0)

        return {
            'code': 200, 'msg': 'success',
            'data': {
                'total_cameras': total_cameras,
                'online_cameras': max(0, total_cameras - fault_cameras),
                'fault_cameras': fault_cameras,
                'total_cloud_boxes': total_boxes,
                'online_cloud_boxes': max(0, total_boxes - fault_boxes),
                'fault_cloud_boxes': fault_boxes,
                'total_alarms': total_alarms,
                'pending_alarms': pending_alarms,
                'today_alarms': today_alarms,
                'month_alarms': month_alarms,
            }
        }

    @classmethod
    def statistics_by_date(cls, days=30):
        """按日期统计"""
        from datetime import timedelta
        end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        result = cls._get('statistics', params={
            'dimension': 'time',
            'granularity': 'day',
            'start_time': start,
            'end_time': end,
        })
        if result.get('code') == 200:
            data = []
            for row in result.get('data', []):
                data.append({
                    'date': row.get('time_label', ''),
                    'count': row.get('total', 0),
                })
            return {'code': 200, 'msg': 'success', 'data': data}
        return cls._to_c_format(result)

    @classmethod
    def statistics_by_region(cls):
        """按区域统计"""
        result = cls._get('statistics', params={'dimension': 'area'})
        if result.get('code') == 200:
            data = []
            for row in result.get('data', []):
                data.append({
                    'name': row.get('area_name', '未知区域'),
                    'value': row.get('total', 0),
                })
            return {'code': 200, 'msg': 'success', 'data': data}
        return cls._to_c_format(result)

    @classmethod
    def statistics_by_level(cls):
        """按紧急程度统计（★修复：从PHP level维度获取真实报警级别分布）"""
        result = cls._get('statistics', params={'dimension': 'level'})
        if result.get('code') == 200:
            level_order = {'紧急': 1, '重要': 2, '一般': 3, '提示': 4}
            data = []
            for row in result.get('data', []):
                name = row.get('urgency_name', '未知')
                data.append({
                    'name': name,
                    'value': row.get('total', 0),
                    'order': level_order.get(name, 99),
                })
            # 按紧急程度排序
            data.sort(key=lambda x: x['order'])
            return {
                'code': 200, 'msg': 'success',
                'data': [{'name': d['name'], 'value': d['value']} for d in data]
            }
        return cls._to_c_format(result)

    @classmethod
    def statistics_heatmap(cls):
        """热力图数据（报警事件坐标汇总）"""
        result = cls._get('alarm/events', params={'per_page': 500})
        points = []
        if result.get('code') == 200:
            for item in result.get('data', {}).get('list', []):
                lng = item.get('Longitude')
                lat = item.get('Latitude')
                if lng and lat:
                    try:
                        points.append({
                            'lng': float(lng),
                            'lat': float(lat),
                            'count': 1,
                        })
                    except (ValueError, TypeError):
                        pass
        return {'code': 200, 'msg': 'success', 'data': {
            'hour_stats': [],
            'heatmap_points': points,
        }}

    # =========================================================================
    # 日志查询
    # =========================================================================

    @classmethod
    def access_logs(cls, page=1, per_page=20, **filters):
        """访问日志查询"""
        params = {'page': page, 'per_page': per_page}
        if filters.get('username'):
            params['username'] = filters['username']
        result = cls._get('logs/access', params=params)
        if result.get('code') == 200:
            data = result.get('data', {})
            data['items'] = data.get('items', []) or data.get('list', [])
            data.setdefault('pages', max(1, math.ceil(
                data.get('total', 0) / max(1, per_page)
            )))
        return cls._to_c_format(result)

    @classmethod
    def operation_logs(cls, page=1, per_page=20, **filters):
        """操作日志查询"""
        params = {'page': page, 'per_page': per_page}
        if filters.get('username'):
            params['username'] = filters['username']
        if filters.get('operation_type'):
            params['operation_type'] = filters['operation_type']
        if filters.get('operation_module'):
            params['operation_module'] = filters['operation_module']
        result = cls._get('logs/operation', params=params)
        if result.get('code') == 200:
            data = result.get('data', {})
            data['items'] = data.get('items', []) or data.get('list', [])
            data.setdefault('pages', max(1, math.ceil(
                data.get('total', 0) / max(1, per_page)
            )))
        return cls._to_c_format(result)

    # =========================================================================
    # 字段映射函数 (B的PHP格式 → C的Flask格式)
    # =========================================================================

    @classmethod
    def _map_user(cls, b_user):
        """B用户 → C用户（使用真实部门/角色数据）"""
        if not b_user:
            return {}
        account = b_user.get('Account', b_user.get('account', ''))
        real_name = b_user.get('Name', b_user.get('name', ''))
        role_name = b_user.get('RoleName', '') or ''
        is_admin = (account == 'admin' or
                    role_name == '超级管理员' or
                    real_name == '管理员')
        return {
            'id': b_user.get('Id') or b_user.get('id'),
            'username': account,
            'real_name': real_name,
            'email': b_user.get('Email', b_user.get('email', '')),
            'phone': b_user.get('Phone', b_user.get('phone', '')),
            'user_type': 1 if is_admin else 2,
            'user_type_name': '超级用户' if is_admin else '普通用户',
            'status': 1 if not b_user.get('IsDelete') else 0,
            'department_id': b_user.get('BranchId', b_user.get('branch_id')),
            'department_name': b_user.get('BranchName', b_user.get('department_name', '')),
            'role_id': b_user.get('RoleId', b_user.get('role_id')),
            'role_name': role_name,
            'login_count': 0,
        }

    @classmethod
    def _map_alarm(cls, b_item, detail=False):
        """B报警事件 → C报警事件"""
        if not b_item:
            return {}
        # 事件类型映射：B用字符串fire/smoke，C用数字1/2
        event_type_str = b_item.get('EventType', 'smoke')
        event_type = {'fire': 1, 'smoke': 2, 'device': 3}.get(event_type_str, 2)

        # 状态映射：B用'1'/'2'/'3'，C用1/2/3/4/5
        status_str = str(b_item.get('Status', '1'))
        status_map = {'1': 1, '2': 2, '3': 3}  # 1待处理 2处理中 3已处理
        process_status = status_map.get(status_str, 1)

        # 紧急程度映射
        urgency_map = {'紧急': 1, '重要': 2, '一般': 3, '提示': 4}
        alarm_level = urgency_map.get(b_item.get('UrgencyDegree', '一般'), 3)

        item = {
            'id': b_item.get('Id'),
            'event_code': 'EVT-' + str(b_item.get('Id', '')).zfill(6),
            'event_type': event_type,
            'event_type_name': {1: '火焰报警', 2: '烟雾报警', 3: '设备异常'}.get(event_type, '未知'),
            'alarm_level': alarm_level,
            'alarm_level_name': {1: '紧急', 2: '重要', 3: '一般', 4: '提示'}.get(alarm_level, '未知'),
            'detection_confidence': float(b_item.get('Confidence', 0)) if b_item.get('Confidence') else 0.0,
            'fire_area_ratio': None,
            'longitude': b_item.get('Longitude'),
            'latitude': b_item.get('Latitude'),
            'location_description': b_item.get('Location', ''),
            'image_url': b_item.get('Picture'),
            'video_url': b_item.get('VideoUrl'),
            'camera_id': b_item.get('CameraId'),
            'camera_name': b_item.get('CameraName', ''),
            'cloud_box_id': b_item.get('DeviceId'),
            'cloud_box_name': b_item.get('DeviceAddress', ''),
            'process_status': process_status,
            'process_status_name': {1: '待处理', 2: '处理中', 3: '已处理', 4: '已驳回', 5: '已关闭'}.get(process_status,
                                                                                                    '未知'),
            'handler_remark': b_item.get('OperateResult', ''),
            'detected_at': b_item.get('CreatTime', ''),
            'handled_at': b_item.get('OperateTime', ''),
            'created_at': b_item.get('CreatTime', ''),
        }
        if detail:
            item['handler_name'] = b_item.get('OperateName', '')
            item['audit_name'] = b_item.get('AuditName', '')
            item['audit_time'] = b_item.get('AuditTime', '')
            item['description'] = b_item.get('Description', '')
        return item

    @classmethod
    def _map_cloudbox(cls, b_item):
        """B AI云盒 → C AI云盒"""
        if not b_item:
            return {}
        return {
            'id': b_item.get('Id'),
            'device_code': b_item.get('MAC', ''),
            'device_name': b_item.get('Address', b_item.get('MAC', '')),
            'device_model': b_item.get('ModelInfo', 'RK3399 Pro D'),
            'ip_address': '',
            'mac_address': b_item.get('MAC', ''),
            'firmware_version': b_item.get('StructuralInfo', ''),
            'cpu_usage': 0,
            'memory_usage': 0,
            'storage_usage': 0,
            'npu_temperature': None,
            'status': 1,  # B没有status字段
            'status_name': '在线',
            'is_online': True,
            'last_heartbeat': b_item.get('LastConnectTime'),
            'location': b_item.get('Address', ''),
            'longitude': b_item.get('Longitude'),
            'latitude': b_item.get('Latitude'),
            'remark': b_item.get('Remark', ''),
            'camera_count': b_item.get('camera_count', 0),
            'created_at': b_item.get('CreateTime', ''),
        }

    # =========================================================================
    # 用户管理 CRUD（M7融合修复新增）
    # =========================================================================

    @classmethod
    def user_list(cls, page=1, per_page=20, **filters):
        """用户列表"""
        params = {'page': page, 'per_page': per_page}
        for k in ('username', 'real_name', 'user_type'):
            if filters.get(k):
                params[k] = filters[k]
        result = cls._get('users', params=params)
        if result.get('code') == 200:
            data = result.get('data', {})
            items = [cls._map_user(item) for item in data.get('list', [])]
            total = data.get('total', 0)
            return {'code': 200, 'msg': 'success', 'data': {
                'items': items, 'total': total, 'page': page,
                'per_page': per_page,
                'pages': max(1, math.ceil(total / max(1, per_page))),
            }}
        return cls._to_c_format(result)

    @classmethod
    def user_create(cls, data):
        """创建用户"""
        php_data = {
            'account': data.get('username', ''),
            'name': data.get('real_name', ''),
            'password': data.get('password', '123456'),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'branch_id': data.get('department_id'),
            'area_id': data.get('area_id'),
            'role_id': data.get('role_id'),
        }
        result = cls._post('users/create', data=php_data)
        if result.get('code') == 201:
            result['code'] = 200
            result['message'] = '用户创建成功'
        return cls._to_c_format(result)

    @classmethod
    def user_update(cls, user_id, data):
        """更新用户"""
        php_data = {}
        field_map = {
            'real_name': 'name', 'username': 'account',
            'email': 'email', 'phone': 'phone',
            'department_id': 'branch_id', 'area_id': 'area_id',
            'role_id': 'role_id',
        }
        for c_field, b_field in field_map.items():
            if c_field in data and data[c_field] is not None:
                php_data[b_field] = data[c_field]
        if data.get('password'):
            php_data['password'] = data['password']
        result = cls._post('users/' + str(user_id) + '/update', data=php_data)
        return cls._to_c_format(result)

    @classmethod
    def user_delete(cls, user_id):
        """删除用户"""
        result = cls._get('users/' + str(user_id) + '/delete')
        return cls._to_c_format(result)

    # =========================================================================
    # 角色管理 CRUD（M7融合修复新增）
    # =========================================================================

    @classmethod
    def role_list(cls):
        """角色列表"""
        result = cls._get('roles')
        if result.get('code') == 200:
            items = []
            for item in result.get('data', {}).get('list', []):
                items.append({
                    'id': item.get('Id'),
                    'name': item.get('Name', ''),
                    'code': item.get('Name', ''),
                    'description': item.get('Description', ''),
                    'permissions': [a.get('Authority', '') for a in item.get('authorities', [])],
                    'status': 1 if not item.get('IsDelete') else 0,
                    'created_at': item.get('CreateTime', ''),
                    'authority_count': item.get('authority_count', 0),
                    'user_count': item.get('user_count', 0),
                })
            return {'code': 200, 'msg': 'success', 'data': items}
        return cls._to_c_format(result)

    @classmethod
    def role_create(cls, data):
        """创建角色"""
        php_data = {
            'name': data.get('name', ''),
            'description': data.get('description', ''),
            'authorities': data.get('permissions', []),
        }
        result = cls._post('roles/create', data=php_data)
        if result.get('code') == 201: result['code'] = 200
        return cls._to_c_format(result)

    @classmethod
    def role_update(cls, role_id, data):
        """更新角色"""
        php_data = {}
        if 'name' in data: php_data['name'] = data['name']
        if 'description' in data: php_data['description'] = data['description']
        if 'permissions' in data: php_data['authorities'] = data['permissions']
        result = cls._post('roles/' + str(role_id) + '/update', data=php_data)
        return cls._to_c_format(result)

    @classmethod
    def role_delete(cls, role_id):
        """删除角色"""
        result = cls._get('roles/' + str(role_id) + '/delete')
        return cls._to_c_format(result)

    # =========================================================================
    # 部门管理 CRUD（M7融合修复新增）
    # =========================================================================

    @classmethod
    def department_list(cls):
        """部门列表"""
        result = cls._get('branches')
        if result.get('code') == 200:
            items = []
            for item in result.get('data', {}).get('list', []):
                items.append({
                    'id': item.get('Id'),
                    'name': item.get('Name', ''),
                    'code': item.get('Name', ''),
                    'parent_id': item.get('ParentId'),
                    'parent_name': item.get('ParentName', ''),
                    'sort_order': 0,
                    'status': 1,
                    'created_at': item.get('CreateTime', ''),
                    'remark': item.get('Remark', ''),
                    'leader_name': item.get('LeaderName', ''),
                })
            return {'code': 200, 'msg': 'success', 'data': items}
        return cls._to_c_format(result)

    @classmethod
    def department_create(cls, data):
        """创建部门"""
        php_data = {
            'name': data.get('name', ''),
            'parent_id': data.get('parent_id', 0),
            'leader_id': data.get('leader_id'),
            'remark': data.get('remark', ''),
        }
        result = cls._post('branches/create', data=php_data)
        if result.get('code') == 201: result['code'] = 200
        return cls._to_c_format(result)

    @classmethod
    def department_update(cls, dept_id, data):
        """更新部门"""
        php_data = {}
        for k in ('name', 'parent_id', 'leader_id', 'remark'):
            if k in data and data[k] is not None:
                php_data[k] = data[k]
        result = cls._post('branches/' + str(dept_id) + '/update', data=php_data)
        return cls._to_c_format(result)

    @classmethod
    def department_delete(cls, dept_id):
        """删除部门"""
        result = cls._get('branches/' + str(dept_id) + '/delete')
        return cls._to_c_format(result)

    # =========================================================================
    # 数据字典修复 + CRUD（M7融合修复）
    # =========================================================================

    @classmethod
    def datadict_list(cls, dict_type=None):
        """数据字典列表（修复：从PHP API获取）"""
        params = {}
        if dict_type:
            params['dict_type'] = dict_type
        result = cls._get('dictionary', params=params)
        if result.get('code') == 200:
            items = []
            for item in result.get('data', {}).get('list', []):
                items.append({
                    'id': item.get('Id'),
                    'dict_type': item.get('Key', ''),
                    'dict_label': item.get('Value', ''),
                    'dict_value': item.get('Value', ''),
                    'sort_order': 0,
                    'status': 1,
                    'remark': item.get('Remark', ''),
                })
            types = [item['dict_type'] for item in items]
            return {
                'code': 200, 'msg': 'success',
                'data': {'items': items, 'types': list(set(types))},
            }
        return cls._to_c_format(result)

    @classmethod
    def datadict_create(cls, data):
        """新增字典项"""
        php_data = {
            'key': data.get('dict_type', ''),
            'value': data.get('dict_value', ''),
            'remark': data.get('remark', ''),
        }
        result = cls._post('dictionary/create', data=php_data)
        if result.get('code') == 201: result['code'] = 200
        return cls._to_c_format(result)

    @classmethod
    def datadict_update(cls, dd_id, data):
        """更新字典项"""
        php_data = {}
        if 'dict_type' in data: php_data['key'] = data['dict_type']
        if 'dict_value' in data: php_data['value'] = data['dict_value']
        if 'remark' in data: php_data['remark'] = data['remark']
        result = cls._post('dictionary/' + str(dd_id) + '/update', data=php_data)
        return cls._to_c_format(result)

    @classmethod
    def datadict_delete(cls, dd_id):
        """删除字典项"""
        result = cls._get('dictionary/' + str(dd_id) + '/delete')
        return cls._to_c_format(result)

    # =========================================================================
    # 系统配置修复（M7融合修复）
    # =========================================================================

    @classmethod
    def system_configs(cls):
        """获取系统配置（修复：从PHP config API获取T_Site + Flask config常量）"""
        result = cls._get('config')
        t_site = {}
        if result.get('code') == 200:
            t_site = result.get('data', {})

        from config import Config
        return {
            'code': 200, 'msg': 'success',
            'data': [
                {'id': 1, 'config_key': 'site_name', 'config_value': Config.SITE_NAME,
                 'config_type': 'string', 'description': '站点名称'},
                {'id': 2, 'config_key': 'fire_threshold',
                 'config_value': str(t_site.get('thresh', 0.85)),
                 'config_type': 'float', 'description': '火焰检测置信度阈值'},
                {'id': 3, 'config_key': 'smoke_threshold',
                 'config_value': str(float(t_site.get('thresh', 0.8)) * 0.95),
                 'config_type': 'float', 'description': '烟雾检测置信度阈值'},
                {'id': 4, 'config_key': 'logo_text', 'config_value': Config.SYSTEM_LOGO_TEXT,
                 'config_type': 'string', 'description': '系统Logo文字'},
                {'id': 5, 'config_key': 'video_duration',
                 'config_value': str(t_site.get('video_times', 5)),
                 'config_type': 'int', 'description': '视频取证时长(秒)'},
                {'id': 6, 'config_key': 'image_width',
                 'config_value': str(t_site.get('width', 640)),
                 'config_type': 'int', 'description': '取证图片宽度'},
                {'id': 7, 'config_key': 'image_height',
                 'config_value': str(t_site.get('height', 480)),
                 'config_type': 'int', 'description': '取证图片高度'},
                {'id': 8, 'config_key': 'heartbeat_interval',
                 'config_value': str(int(float(t_site.get('heartBeat', 0.5)) * 60)),
                 'config_type': 'int', 'description': '心跳间隔(秒)'},
                {'id': 9, 'config_key': 'network_abnormal_threshold',
                 'config_value': str(int(float(t_site.get('exception_times', 10)) * 60)),
                 'config_type': 'int', 'description': '网络异常阈值(秒)'},
                {'id': 10, 'config_key': 'max_concurrent_cameras',
                 'config_value': '30', 'config_type': 'int', 'description': '最大并发摄像头数'},
                {'id': 11, 'config_key': 'amap_key',
                 'config_value': Config.AMAP_KEY, 'config_type': 'string',
                 'description': '高德地图JSAPI Key'},
                {'id': 12, 'config_key': 'amap_security_code',
                 'config_value': Config.AMAP_SECURITY_CODE, 'config_type': 'string',
                 'description': '高德地图安全密钥'},
                {'id': 13, 'config_key': 'alarm_retention_days',
                 'config_value': '90', 'config_type': 'int', 'description': '报警数据保留天数'},
                {'id': 14, 'config_key': 'log_retention_days',
                 'config_value': '180', 'config_type': 'int', 'description': '日志保留天数'},
            ]
        }

    @classmethod
    def update_system_configs(cls, data):
        """更新系统配置（修复：写入T_Site）"""
        # 字段映射：C的config_key → T_Site字段
        site_data = {}
        key_map = {
            'fire_threshold': ('thresh', float),
            'video_duration': ('video_times', float),
            'image_width': ('width', float),
            'image_height': ('height', float),
            'heartbeat_interval': ('heartBeat', lambda v: float(v) / 60.0),
            'network_abnormal_threshold': ('exception_times', lambda v: float(v) / 60.0),
        }
        for config_key, config_value in data.items():
            if isinstance(config_value, dict):
                config_value = config_value.get('config_value', config_value)
            if config_key in key_map:
                site_col, convert = key_map[config_key]
                site_data[site_col] = convert(config_value)

        if site_data:
            result = cls._post('config/update', data=site_data)
            return cls._to_c_format(result)
        return {'code': 200, 'msg': '无变更（非T_Site配置项不持久化）', 'data': None}

    # =========================================================================
    # 故障管理（M7融合修复新增）
    # =========================================================================

    @classmethod
    def camera_fault_list(cls, page=1, per_page=15, **filters):
        """摄像头故障列表"""
        params = {'page': page, 'per_page': per_page}
        result = cls._get('faults/camera', params=params)
        if result.get('code') == 200:
            data = result.get('data', {})
            items = []
            for item in data.get('list', []):
                fault_type_map = {'1': '网络故障', '2': '图像质量差'}
                items.append({
                    'id': item.get('Id'),
                    'fault_code': 'CAM-ERR-' + str(item.get('Id', '')).zfill(4),
                    'camera': {
                        'device_name': item.get('CameraName', ''),
                        'id': item.get('CameraId'),
                    },
                    'fault_type_name': fault_type_map.get(item.get('ErrorCode', ''), item.get('ErrorCode', '')),
                    'fault_description': item.get('ErrorMsg', ''),
                    'fault_level': 1,
                    'process_status': 1,
                    'occurred_at': item.get('CreateTime', ''),
                    # 数据大屏地图用
                    'device_name': item.get('CameraName', ''),
                    'device_code': item.get('CameraIP', ''),
                    'longitude': item.get('Longitude'),
                    'latitude': item.get('Latitude'),
                    'location': item.get('CameraName', ''),
                    'status_name': '故障',
                })
            total = data.get('total', 0)
            stats = data.get('stats', {})
            return {'code': 200, 'msg': 'success', 'data': {
                'items': items, 'total': total, 'page': page,
                'per_page': per_page,
                'pages': max(1, math.ceil(total / max(1, per_page))),
                'stats': stats,
            }}
        return cls._to_c_format(result)

    @classmethod
    def camera_fault_repair(cls, fault_id, remark=''):
        """维修摄像头故障"""
        result = cls._post('faults/camera/' + str(fault_id) + '/repair',
                           data={'remark': remark})
        return cls._to_c_format(result)

    @classmethod
    def cloudbox_fault_list(cls, page=1, per_page=15, **filters):
        """云盒故障列表"""
        params = {'page': page, 'per_page': per_page}
        result = cls._get('faults/device', params=params)
        if result.get('code') == 200:
            data = result.get('data', {})
            items = []
            for item in data.get('list', []):
                fault_type_map = {'HEARTBEAT_LOST': '设备心跳丢失'}
                items.append({
                    'id': item.get('Id'),
                    'fault_code': 'DEV-ERR-' + str(item.get('Id', '')).zfill(4),
                    'cloud_box': {
                        'device_name': item.get('DeviceAddress', ''),
                        'id': item.get('DeviceId'),
                    },
                    'fault_type_name': fault_type_map.get(item.get('ErrorCode', ''), item.get('ErrorCode', '')),
                    'fault_description': item.get('ErrorMsg', ''),
                    'fault_level': 1,
                    'process_status': 1,
                    'occurred_at': item.get('CreateTime', ''),
                    # 数据大屏地图用
                    'device_name': item.get('DeviceAddress', ''),
                    'device_code': item.get('DeviceMAC', ''),
                    'longitude': item.get('Longitude'),
                    'latitude': item.get('Latitude'),
                    'location': item.get('DeviceAddress', ''),
                    'status_name': '故障',
                })
            total = data.get('total', 0)
            stats = data.get('stats', {})
            return {'code': 200, 'msg': 'success', 'data': {
                'items': items, 'total': total, 'page': page,
                'per_page': per_page,
                'pages': max(1, math.ceil(total / max(1, per_page))),
                'stats': stats,
            }}
        return cls._to_c_format(result)

    @classmethod
    def cloudbox_fault_repair(cls, fault_id, remark=''):
        """维修云盒故障"""
        result = cls._post('faults/device/' + str(fault_id) + '/repair',
                           data={'remark': remark})
        return cls._to_c_format(result)

    @classmethod
    def camera_fault_stats(cls):
        """故障统计"""
        result = cls._get('faults/camera', params={'per_page': 1})
        return result.get('data', {}).get('stats', {'today': 0, 'week': 0, 'month': 0, 'year': 0})

    @classmethod
    def cloudbox_fault_stats(cls):
        """故障统计"""
        result = cls._get('faults/device', params={'per_page': 1})
        return result.get('data', {}).get('stats', {'today': 0, 'week': 0, 'month': 0, 'year': 0})

    @classmethod
    def _map_camera(cls, b_item):
        """B摄像头 → C摄像头"""
        if not b_item:
            return {}
        return {
            'id': b_item.get('Id'),
            'device_code': b_item.get('MAC', b_item.get('Name', '')),
            'device_name': b_item.get('Name', ''),
            'device_model': b_item.get('Type', ''),
            'camera_type': b_item.get('Type', '固定摄像头'),
            'rtsp_url': b_item.get('CameraUrl', ''),
            'ip_address': b_item.get('IP', ''),
            'port': 554,
            'resolution': '1920x1080',
            'frame_rate': 25,
            'ptz_support': False,
            'monitor_substance': '火焰/烟雾',
            'location': b_item.get('Name', ''),
            'longitude': b_item.get('Longitude'),
            'latitude': b_item.get('Latitude'),
            'altitude': 0,
            'view_range': 500,
            'image_url': '',
            'status': 1,
            'status_name': '正常',
            'cloud_box_id': b_item.get('DeviceId'),
            'cloud_box_name': b_item.get('DeviceAddress', ''),
            'created_at': b_item.get('InstallTime', ''),
        }
