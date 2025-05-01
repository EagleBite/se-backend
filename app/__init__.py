import os
from flask import Flask, current_app
from .utils.logger import setup_app_logger
from .routes import register_blueprints, socketio_api
from .extensions import register_extensions
from .command import register_commands

def create_app(config_class=None):
    """Create a Flask application instance."""
    app = Flask(__name__)

    # 动态加载配置
    if config_class is None:
        config_class = os.getenv('FLASK_CONFIG', 'config.Config')
    if isinstance(config_class, str):
        module_name, class_name = config_class.rsplit('.', 1)
        module = __import__(module_name, fromlist=[class_name])
        config_class = getattr(module, class_name)
    app.config.from_object(config_class)
    
    # 初始化日志系统
    setup_app_logger(app)

    register_extensions(app)
    register_commands(app) 
    register_blueprints(app)

    return app



