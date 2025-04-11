from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import User
from ..utils.logger import get_logger

user_bp = Blueprint('user_api', __name__)

@user_bp.route('/basic/<int:user_id>', methods=['GET'])
def get_user_basic(user_id):
    """
    获取用户基础信息
    """
    logger = get_logger(__name__)

    try:
        # 获取用户信息
        user = User.query.get(user_id)
        if not user:
            logger.warning(f"用户不存在: {user_id}")
            return jsonify({"code": 404, "message": "用户不存在"}), 404

        # 计算年龄
        age = calculate_age_from_id(user.identity_id) if user.identity_id else None

        logger.info(f"获取用户基础数据: {user_id}")
        return jsonify({
                "code": 200,
                "data": {
                    "user_id": user.user_id,
                    "username": user.username,
                    "gender": user.gender,
                    "age": age, # 年龄根据身份证号计算
                    "avatar": user.user_avatar or current_app.config['DEFAULT_AVATAR_URL'],
                    "rate": float(user.rate) if user.rate else 0.0,
                    "status": user.status
                }
            }), 200
    except Exception as e:
        logger.error(f"获取用户基础信息失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500

@user_bp.route('/<int:user_id>/profile', methods=['GET'])
def get_user_profile(user_id):
    """
    获取用户完整档案（个人中心页面）
    """
    logger = get_logger(__name__)

    # 获取用户信息
    user = User.query.get(user_id)
    if not user:
        return jsonify({"code": 404, "message": "用户不存在"}), 404
    
    profile = {
        "user_info": {
            "realname": user.realname,
            "gender": user.gender,
            "telephone": user.telephone,
            "identity_masked": user.identity_id[:3] + '****' + user.identity_id[-4:] if user.identity_id else None,
            "order_count": user.order_time,
            "last_active": user.last_active.isoformat() if user.last_active else None
        },
        "vehicles": [{
            "car_id": car.car_id,
            "plate_number": car.plate_number,
            "brand_model": f"{car.brand} {car.model}"
        } for car in user.cars]
    }

    return jsonify({"code": 200, "data": profile}), 200

@user_bp.route('/<int:user_id>/trips', methods=['GET'])
def get_user_trips(user_id):
    """
    获取用户的行程记录
    """
    logger = get_logger(__name__)

    # 获取用户信息
    user = User.query.get(user_id)
    if not user:
        return jsonify({"code": 404, "message": "用户不存在"}), 404
    
    # TODO: 获取用户的行程记录
    # trips = user.get_trips()

# 身份证号计算年龄工具函数
def calculate_age_from_id(identity_id):
    """根据身份证号计算年龄"""
    birth_date_str = identity_id[6:14]  # 18位身份证的生日部分
    birth_date = datetime.strptime(birth_date_str, "%Y%m%d")
    today = datetime.now()
    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day))
    return age