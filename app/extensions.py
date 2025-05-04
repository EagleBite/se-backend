from flask import jsonify
from flask_sqlalchemy import SQLAlchemy # SQLAlchemy用于ORM
from flask_migrate import Migrate # 数据库迁移工具
from flask_login import LoginManager 
from flask_cors import CORS # CORS用于跨域资源共享
from flask_jwt_extended import JWTManager # JWT用于身份验证
from flask_socketio import SocketIO # SocketIO用于实时通信
from .utils.logger import get_logger

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
cors = CORS()
jwt = JWTManager()
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='eventlet'
)

def register_extensions(app):
    """Register Flask extensions."""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cors.init_app(app)
    jwt.init_app(app) 
    socketio.init_app(app)

    # 设置JWT的回调函数
    from .models import User
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        return User.query.get(jwt_data["sub"])
        
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        """
        处理过期的JWT token
        当JWT token过期时自动调用

        参数:
            jwt_header: JWT头部信息 (dict)
            jwt_payload: JWT有效载荷 (dict)

        返回:
            JSON响应: 包含错误信息的JSON响应
        """
        logger = get_logger(__name__)
        logger.warning(f"Token已过期: {jwt_payload}")
        return jsonify({
            "code": 401,
            "message": "Token已过期，请重新登录",
            "data": None
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(jwt_header, jwt_payload):
        """
        处理无效的JWT token
        当JWT token无效时自动调用

        参数:
            jwt_header: JWT头部信息 (dict)
            jwt_payload: JWT有效载荷 (dict)

        返回:
            JSON响应: 包含错误信息的JSON响应
        """
        logger = get_logger(__name__)
        logger.warning(f"Token无效: {jwt_payload}")
        return jsonify({
            "code": 401,
            "message": "Token无效，请重新登录",
            "data": None
        }), 401
    

            

