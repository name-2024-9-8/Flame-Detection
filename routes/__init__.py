"""
=============================================================================
视频AI智能识别及预警管理信息系统 - 火焰识别
路由模块初始化
作者：人员C（前端开发与质量保障工程师）
创建时间：2026-06-11
=============================================================================
"""
from flask import Blueprint

# 创建各模块蓝图
auth_bp = Blueprint('auth', __name__)
main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


def register_routes(app):
    """注册所有路由蓝图"""
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
