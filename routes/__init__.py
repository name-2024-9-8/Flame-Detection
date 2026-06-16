"""
=============================================================================
视频AI智能识别及预警管理信息系统 - 火焰识别
路由模块初始化 (融合模式)
作者：人员C（前端） + 人员B（后端API桥接）
创建时间：2026-06-11
修改时间：2026-06-12  融合模式
=============================================================================
"""


def register_routes(app):
    """注册所有路由蓝图"""
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.api import api_bp
    from routes.detect import detect_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(detect_bp)
