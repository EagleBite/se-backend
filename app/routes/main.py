from flask import Blueprint, jsonify

# 创建蓝图实例
main_bp = Blueprint('main', __name__)

# 定义路由
@main_bp.route('/')
def index():
    """首页路由"""
    return jsonify({"message": "Welcome to the Flask API!"})

@main_bp.route('/hello/<name>')
def hello(name):
    """Hello route"""
    return jsonify({"greeting": f"Hello, {name}!"})