# 配置文件
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv() # 加载.env文件中的环境变量

class Config:
    """基础配置"""
    SECRET_KEY = os.getenv("SECRECT_KEY", "development")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.getenv("DEBUG", "True") == "True"
    TESTING = os.getenv("TESTING", "False") == "True"
    DEFAULT_AVATAR_URL = "../../static/user.jpeg" # 默认头像URL
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'} # 允许上传的文件格式

    # JWT 配置
    # JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)  # 默认使用SECRET_KEY
    # JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)  # Token有效期1小时
    # JWT_TOKEN_LOCATION = ['headers']  # 从请求头获取Token
    # JWT_HEADER_NAME = 'Authorization'  # 请求头字段名
    # JWT_HEADER_TYPE = 'Bearer'        # Token类型

class DevelopmentConfig(Config):
    """开发环境配置"""
    ENV = "development"
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DEV_DATABASE_URL", "sqlite:///dev.db")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=3)  # 开发环境延长有效期

class TestingConfig(Config):
    """测试环境配置"""
    ENV = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///test.db")
    SQLALCHEMY_ECHO = False  # 测试时关闭SQL日志
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=300)  # 测试环境短有效期

class ProductionConfig(Config):
    """生产环境配置"""
    ENV = "production"
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("PROD_DATABASE_URL", "sqlite:///prod.db")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # 生产环境必须显式配置
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)  # 生产环境较短有效期
    # 其他生产环境配置