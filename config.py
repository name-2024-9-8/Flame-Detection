"""
=============================================================================
视频AI智能识别及预警管理信息系统 - 火焰识别
配置文件
作者：人员C（前端开发与质量保障工程师）
创建时间：2026-06-11
功能描述：系统全局配置，包括数据库、JWT、地图、报警阈值等参数
=============================================================================
"""
import os
import secrets

# 项目根目录
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """基础配置"""
    # Flask密钥
    SECRET_KEY = secrets.token_hex(32)

    # 数据库配置 (开发环境使用SQLite，生产环境使用MySQL)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(BASE_DIR, "fire_alarm.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # 站点名称
    SITE_NAME = '视频AI智能识别及预警管理信息系统'

    # JWT配置 (与人员B的后端API对接)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'fire-alarm-jwt-secret-2026')
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24小时

    # 百度地图API配置
    BAIDU_MAP_AK = os.environ.get('BAIDU_MAP_AK', '您的百度地图AK密钥')

    # 火焰检测阈值配置
    FIRE_DETECTION_THRESHOLD = 0.85       # 火焰检测置信度阈值（默认85%）
    SMOKE_DETECTION_THRESHOLD = 0.80      # 烟雾检测置信度阈值（默认80%）
    ALARM_VIDEO_DURATION = 5              # 报警取证视频时长（秒）
    CAPTURE_IMAGE_WIDTH = 1920            # 取证图片宽度
    CAPTURE_IMAGE_HEIGHT = 1080           # 取证图片高度
    HEARTBEAT_INTERVAL = 30               # 心跳时间（秒）
    NETWORK_ABNORMAL_THRESHOLD = 60       # 网络异常阈值（秒）

    # 系统Logo文字
    SYSTEM_LOGO_TEXT = 'AI火焰识别预警'

    # 分页配置
    ITEMS_PER_PAGE = 15

    # 上传文件配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

    # 日志配置
    LOG_LEVEL = 'INFO'

    # 性能指标（验收标准）
    RECOGNITION_RATE_TARGET = 0.90    # 识别率≥90%
    FALSE_ALARM_RATE_TARGET = 0.05    # 误报率<5%
    LOCATION_ERROR_TARGET = 200       # 定位误差≤200米
    ALARM_DELAY_TARGET = 2            # 事件预警时延≤2秒

    # 并发摄像头数量
    MAX_CONCURRENT_CAMERAS = 30

    # SuperMap GIS预留接口配置
    SUPERMAP_ENABLED = False
    SUPERMAP_SERVER_URL = 'http://localhost:8090/iserver'


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# 配置字典
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
