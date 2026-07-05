"""
=============================================================================
视频AI智能识别及预警管理信息系统 - 火焰识别
Flask主应用入口 (融合模式 — 数据源为王永林的PHP API)
作者：段林川（前端） + 王永林（后端API桥接）
创建时间：2026-06-11
修改时间：2026-06-12  融合：移除SQLite/SQLAlchemy，改为API桥接模式
=============================================================================
"""
import os
import time
from datetime import datetime
from flask import Flask, render_template, request, session, g
from config import config_dict
from routes import register_routes


def create_app(config_name=None):
    """创建Flask应用工厂函数"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_dict.get(config_name, config_dict['default']))

    # 开发环境：EDGE_API_KEY 未设置时使用开发密钥（生产环境必须通过环境变量设置）
    if not app.config.get('EDGE_API_KEY'):
        if app.config.get('DEBUG'):
            app.config['EDGE_API_KEY'] = 'flame-edge-dev-key-2026'
            print("[DEV] EDGE_API_KEY 未设置，使用开发默认密钥: flame-edge-dev-key-2026")
        else:
            print("[WARNING] EDGE_API_KEY 未设置！边缘设备API将拒绝所有请求。")
            print("          请设置环境变量: set EDGE_API_KEY=<your-secure-key>")

    # 确保上传目录存在
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)

    # 注册路由蓝图
    register_routes(app)

    # 注册错误处理
    register_error_handlers(app)

    # 注册中间件
    register_middleware(app)

    # 注册Jinja2自定义过滤器
    register_template_filters(app)

    # 注册健康检查接口（修复：移到create_app内部避免404）
    @app.route('/health')
    def health_check():
        """健康检查接口 — 同时检测PHP API连通性"""
        import requests as req_lib
        try:
            php_status = 'ok'
            resp = req_lib.get('http://127.0.0.1:8080/index.php/api/statistics/health', timeout=5)
            if resp.status_code != 200:
                php_status = 'degraded'
        except Exception:
            php_status = 'unreachable'

        return {
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'fusion_mode': True,
            'php_api': php_status,
            'php_api_base': app.config.get('PHP_API_BASE', 'http://127.0.0.1:8080/index.php/api'),
        }

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
        if request.path.startswith('/api/'):
            return {'code': 500, 'msg': '服务器内部错误', 'data': None}, 500
        return render_template('error.html', code=500, msg='服务器内部错误'), 500

    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith('/api/'):
            return {'code': 403, 'msg': '权限不足', 'data': None}, 403
        return render_template('error.html', code=403, msg='权限不足'), 403


def register_middleware(app):
    """注册中间件（请求计时）"""

    @app.before_request
    def before_request():
        g.start_time = time.time()

    @app.after_request
    def after_request(response):
        # 简单计时，不再写本地数据库
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
        badges = {
            1: '<span class="badge badge-success">启用</span>',
            0: '<span class="badge badge-secondary">禁用</span>',
        }
        return badges.get(status, '<span class="badge badge-light">未知</span>')

    @app.template_filter('event_type_badge')
    def event_type_badge(event_type):
        badges = {
            1: '<span class="badge badge-danger">火焰报警</span>',
            2: '<span class="badge badge-warning">烟雾报警</span>',
            3: '<span class="badge badge-info">设备异常</span>',
        }
        return badges.get(event_type, '<span class="badge badge-light">未知</span>')

    @app.template_filter('alarm_level_badge')
    def alarm_level_badge(level):
        badges = {
            1: '<span class="badge badge-danger">紧急</span>',
            2: '<span class="badge badge-warning">重要</span>',
            3: '<span class="badge badge-info">一般</span>',
            4: '<span class="badge badge-light">提示</span>',
        }
        return badges.get(level, '<span class="badge badge-light">未知</span>')


# =========================================================================
# 应用入口
# =========================================================================

app = create_app()


if __name__ == '__main__':
    # 使用模块级app实例（避免重复创建导致/health等路由丢失）
    # 通过环境变量切换配置
    import sys, io
    # 修复Windows控制台中文乱码
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    print("=" * 60)
    print("  [Fire] 视频AI智能识别及预警管理信息系统")
    print("  火焰识别 - Web管理平台 (融合模式)")
    print("=" * 60)
    print("  融合架构: Flask前端 → PHP API → MySQL")
    print("  PHP API地址: {}".format(app.config.get('PHP_API_BASE', 'http://127.0.0.1:8080/index.php/api')))
    print("  访问地址: http://127.0.0.1:5000")
    print("  管理后台: http://127.0.0.1:5000/dashboard")
    print("  数据大屏: http://127.0.0.1:5000/")
    print("  登录页面: http://127.0.0.1:5000/login")
    print("  管理员账号: admin / 123456")
    print("  健康检查: http://127.0.0.1:5000/health")
    print("=" * 60)

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True,
    )
