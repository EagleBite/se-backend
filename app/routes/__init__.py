from .main import main_bp as main_blueprint
from .auth_api import auth_bp as auth_blueprint
from .user_api import user_bp as user_blueprint
from .trip_api import trip_bp as trip_blueprint
from .vehicle_api import vehicle_bp as vehicle_blueprint
from .order_api import order_bp as order_blueprint

def register_blueprints(app):
    """注册所有蓝图"""
    app.register_blueprint(main_blueprint, url_prefix='/api')
    app.register_blueprint(auth_blueprint, url_prefix='/api/auth')
    app.register_blueprint(user_blueprint, url_prefix='/api/user')
    app.register_blueprint(trip_blueprint, url_prefix='/api/trip')
    app.register_blueprint(vehicle_blueprint, url_prefix='/api/user')
    app.register_blueprint(order_blueprint, url_prefix='/api/order')