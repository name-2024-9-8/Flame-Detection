"""
=============================================================================
视频AI智能识别及预警管理信息系统 - 火焰识别
Flask主应用入口
作者：人员C（前端开发与质量保障工程师）
创建时间：2026-06-11
功能描述：系统启动入口，初始化Flask应用、数据库、蓝图注册、
          错误处理、访问日志中间件、初始化种子数据
=============================================================================
"""
import os
import sys
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from config import config_dict
from models import db, User, Department, Role, DataDict, SystemConfig
from models import Camera, AICloudBox, AlarmEvent, CameraFault, CloudBoxFault
from models import AccessLog, OperationLog
from routes import register_routes


def create_app(config_name=None):
    """创建Flask应用工厂函数"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_dict.get(config_name, config_dict['default']))

    # 确保上传目录存在
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)

    # 初始化数据库
    db.init_app(app)

    # 注册路由蓝图
    register_routes(app)

    # 注册错误处理
    register_error_handlers(app)

    # 注册中间件
    register_middleware(app)

    # 注册Jinja2自定义过滤器
    register_template_filters(app)

    return app


def register_error_handlers(app):
    """注册错误处理器"""

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return {'code': 404, 'msg': '请求的资源不存在', 'data': None}, 404
        return render_template('error.html', code=404, msg='页面未找到'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return {'code': 500, 'msg': '服务器内部错误', 'data': None}, 500
        return render_template('error.html', code=500, msg='服务器内部错误'), 500

    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith('/api/'):
            return {'code': 403, 'msg': '权限不足', 'data': None}, 403
        return render_template('error.html', code=403, msg='权限不足'), 403


def register_middleware(app):
    """注册中间件（访问日志记录）"""

    @app.before_request
    def before_request():
        """请求前处理"""
        g.start_time = time.time()

    @app.after_request
    def after_request(response):
        """请求后处理 - 记录访问日志"""
        if request.path.startswith('/static/'):
            return response

        try:
            duration = int((time.time() - g.get('start_time', time.time())) * 1000)
            log = AccessLog(
                user_id=session.get('user_id'),
                username=session.get('username', 'anonymous'),
                ip_address=request.remote_addr,
                request_method=request.method,
                request_url=request.path[:500],
                request_params=str(dict(request.args))[:1000] if request.args else None,
                response_code=response.status_code,
                user_agent=str(request.user_agent)[:500] if request.user_agent else '',
                duration_ms=duration,
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            pass  # 日志记录失败不影响主流程

        return response


def register_template_filters(app):
    """注册Jinja2模板自定义过滤器"""

    @app.template_filter('datetime_format')
    def datetime_format(value, fmt='%Y-%m-%d %H:%M:%S'):
        if value is None:
            return '-'
        if isinstance(value, str):
            return value
        return value.strftime(fmt)

    @app.template_filter('status_badge')
    def status_badge(status):
        """状态徽章HTML"""
        badges = {
            1: '<span class="badge badge-success">启用</span>',
            0: '<span class="badge badge-secondary">禁用</span>',
        }
        return badges.get(status, '<span class="badge badge-light">未知</span>')

    @app.template_filter('event_type_badge')
    def event_type_badge(event_type):
        """事件类型徽章"""
        badges = {
            1: '<span class="badge badge-danger">火焰报警</span>',
            2: '<span class="badge badge-warning">烟雾报警</span>',
            3: '<span class="badge badge-info">设备异常</span>',
        }
        return badges.get(event_type, '<span class="badge badge-light">未知</span>')

    @app.template_filter('alarm_level_badge')
    def alarm_level_badge(level):
        """报警级别徽章"""
        badges = {
            1: '<span class="badge badge-danger">紧急</span>',
            2: '<span class="badge badge-warning">重要</span>',
            3: '<span class="badge badge-info">一般</span>',
            4: '<span class="badge badge-light">提示</span>',
        }
        return badges.get(level, '<span class="badge badge-light">未知</span>')


# =========================================================================
# 初始化种子数据
# =========================================================================

def init_seed_data(app):
    """初始化系统种子数据"""
    with app.app_context():
        db.create_all()

        # 创建默认部门
        if Department.query.count() == 0:
            departments = [
                Department(name='技术部', code='TECH', sort_order=1),
                Department(name='监控中心', code='MONITOR', sort_order=2),
                Department(name='运维部', code='OPS', sort_order=3),
                Department(name='管理部', code='ADMIN', sort_order=4),
            ]
            db.session.add_all(departments)
            db.session.commit()

        # 创建默认角色
        if Role.query.count() == 0:
            admin_role = Role(
                name='超级管理员',
                code='SUPER_ADMIN',
                description='拥有系统全部权限',
            )
            admin_role.set_permissions([
                'system:config', 'system:department', 'system:user', 'system:role',
                'system:datadict', 'device:cloudbox', 'device:camera',
                'alarm:event', 'alarm:review', 'alarm:camera_fault', 'alarm:cloudbox_fault',
                'log:access', 'log:operation',
            ])

            handler_role = Role(
                name='事件处理员',
                code='HANDLER',
                description='负责报警事件处理和审核',
            )
            handler_role.set_permissions([
                'alarm:event', 'alarm:review', 'device:view',
                'alarm:camera_fault', 'alarm:cloudbox_fault',
            ])

            viewer_role = Role(
                name='普通用户',
                code='VIEWER',
                description='查看权限，无修改权限',
            )
            viewer_role.set_permissions([
                'alarm:event', 'device:view', 'log:view',
            ])

            db.session.add_all([admin_role, handler_role, viewer_role])
            db.session.commit()

        # 创建默认用户
        if User.query.count() == 0:
            admin_dept = Department.query.filter_by(code='ADMIN').first()
            admin_role = Role.query.filter_by(code='SUPER_ADMIN').first()

            admin_user = User(
                username='admin',
                real_name='系统管理员',
                email='admin@firealarm.com',
                user_type=1,  # 超级用户
                status=1,
                department_id=admin_dept.id if admin_dept else None,
                role_id=admin_role.id if admin_role else None,
            )
            admin_user.set_password('123456')

            normal_user = User(
                username='chuli001',
                real_name='处理员小王',
                email='handler@firealarm.com',
                user_type=2,  # 普通用户
                status=1,
                role_id=Role.query.filter_by(code='HANDLER').first().id if Role.query.filter_by(code='HANDLER').first() else None,
            )
            normal_user.set_password('123456')

            db.session.add_all([admin_user, normal_user])
            db.session.commit()

        # 创建默认系统配置
        if SystemConfig.query.count() == 0:
            defaults = [
                ('site_name', '视频AI智能识别及预警管理信息系统', 'string', '站点名称'),
                ('fire_threshold', '0.85', 'float', '火焰检测置信度阈值'),
                ('smoke_threshold', '0.80', 'float', '烟雾检测置信度阈值'),
                ('video_duration', '5', 'int', '报警取证视频时长(秒)'),
                ('image_width', '1920', 'int', '取证图片宽度'),
                ('image_height', '1080', 'int', '取证图片高度'),
                ('heartbeat_interval', '30', 'int', '心跳时间(秒)'),
                ('network_abnormal_threshold', '60', 'int', '网络异常阈值(秒)'),
                ('logo_text', 'AI火焰识别预警', 'string', '系统Logo文字'),
                ('baidu_map_ak', '', 'string', '百度地图API密钥'),
                ('alarm_retention_days', '90', 'int', '报警数据保留天数'),
                ('log_retention_days', '180', 'int', '日志数据保留天数'),
                ('max_concurrent_cameras', '30', 'int', '最大并发摄像头数量'),
            ]
            for key, value, ctype, desc in defaults:
                db.session.add(SystemConfig(
                    config_key=key, config_value=value,
                    config_type=ctype, description=desc
                ))
            db.session.commit()

        # 创建数据字典默认值
        if DataDict.query.count() == 0:
            dict_data = [
                # 区域设置
                ('region', '华东区', 'east', 1),
                ('region', '华南区', 'south', 2),
                ('region', '华北区', 'north', 3),
                ('region', '西部区', 'west', 4),
                # 事件紧急程度
                ('urgency', '紧急', 'urgent', 1),
                ('urgency', '重要', 'important', 2),
                ('urgency', '一般', 'normal', 3),
                ('urgency', '提示', 'info', 4),
                # 处理结果类型
                ('result_type', '确认为火灾', 'confirmed_fire', 1),
                ('result_type', '误报-烟雾', 'false_smoke', 2),
                ('result_type', '误报-阳光', 'false_sunlight', 3),
                ('result_type', '误报-其他', 'false_other', 4),
                ('result_type', '测试报警', 'test', 5),
                # 故障类型
                ('camera_fault_type', '离线', 'offline', 1),
                ('camera_fault_type', '画面异常', 'abnormal_image', 2),
                ('camera_fault_type', '云台故障', 'ptz_fault', 3),
                ('camera_fault_type', '网络异常', 'network_error', 4),
                ('camera_fault_type', '硬件故障', 'hardware_fault', 5),
                ('cloudbox_fault_type', '离线', 'offline', 1),
                ('cloudbox_fault_type', 'NPU异常', 'npu_error', 2),
                ('cloudbox_fault_type', 'CPU过载', 'cpu_overload', 3),
                ('cloudbox_fault_type', '内存不足', 'memory_low', 4),
                ('cloudbox_fault_type', '温度过高', 'overheat', 5),
            ]
            for dtype, label, value, order in dict_data:
                db.session.add(DataDict(
                    dict_type=dtype, dict_label=label,
                    dict_value=value, sort_order=order
                ))
            db.session.commit()

        print("[OK] 种子数据初始化完成")


# =========================================================================
# 应用入口
# =========================================================================

app = create_app()


@app.route('/health')
def health_check():
    """健康检查接口"""
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}


@app.route('/init-db')
def init_db():
    """手动初始化数据库（开发调试用）"""
    try:
        init_seed_data(app)
        return {'status': 'ok', 'msg': '数据库初始化成功'}
    except Exception as e:
        return {'status': 'error', 'msg': str(e)}, 500


if __name__ == '__main__':
    # 创建应用实例
    app = create_app(os.environ.get('FLASK_ENV', 'development'))

    # 初始化数据库和种子数据
    with app.app_context():
        db.create_all()

        # 检查是否需要初始化种子数据
        if User.query.count() == 0:
            print("[Init] 首次运行，正在初始化种子数据...")
            init_seed_data(app)

    print("=" * 60)
    print("  [Fire] 视频AI智能识别及预警管理信息系统")
    print("  火焰识别 - Web管理平台")
    print("=" * 60)
    print(f"  访问地址: http://127.0.0.1:5000")
    print(f"  管理后台: http://127.0.0.1:5000/dashboard")
    print(f"  数据大屏: http://127.0.0.1:5000/")
    print(f"  登录页面: http://127.0.0.1:5000/login")
    print(f"  管理员账号: admin / 123456")
    print(f"  处理员账号: chuli001 / 123456")
    print("=" * 60)

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False,
    )
