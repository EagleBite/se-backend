from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from ..extensions import db
from ..models import User
from ..utils.logger import get_logger
from werkzeug.utils import secure_filename
import os
import requests
import base64

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
        
        # 处理头像数据
        avatar_data = None
        if user.user_avatar:
            if isinstance(user.user_avatar, bytes):
                avatar_data = f"data:image/jpeg;base64,{base64.b64encode(user.user_avatar).decode('utf-8')}"
            else:
                avatar_data = user.user_avatar

        logger.info(f"获取用户基础数据: {user_id}")
        return jsonify({
            "code": 200,
            "data": {
                "user_id": user.user_id,
                "username": user.username,
                "gender": user.gender,
                "age": age, # 年龄根据身份证号计算
                "avatar": avatar_data or current_app.config['DEFAULT_AVATAR_URL'],
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

    try:
        # 获取用户信息
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 404, "message": "用户不存在"}), 404
        
        # 处理头像数据
        avatar_data = None
        if user.user_avatar:
            if isinstance(user.user_avatar, bytes):
                avatar_data = f"data:image/jpeg;base64,{base64.b64encode(user.user_avatar).decode('utf-8')}"
            else:
                avatar_data = user.user_avatar

        profile = {
            "user_info": {
                "realname": user.realname,
                "gender": user.gender,
                "telephone": user.telephone,
                "identity_masked": user.identity_id[:3] + '****' + user.identity_id[-4:] if user.identity_id else None,
                "order_count": user.order_time,
                "last_active": user.last_active.isoformat() if user.last_active else None,
                "avatar": avatar_data or current_app.config['DEFAULT_AVATAR_URL']
            },
            "vehicles": [{
                "car_id": car.car_id,
                "plate_number": car.license,
                "brand_model": f"{car.brand} {car.model}"
            } for car in user.cars]
        }

        return jsonify({"code": 200, "data": profile}), 200
    except Exception as e:
        logger.error(f"获取用户档案失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500

@user_bp.route('/<int:user_id>/modifiable_data', methods=['GET'])
def get_user_modifiable_data(user_id):
    """
    获取用户可修改的信息
    """
    logger = get_logger(__name__)

    try:
        # 获取用户信息
        user = User.query.get(user_id)
        if not user:
            logger.warning(f"用户不存在: {user_id}")
            return jsonify({"code": 404, "message": "用户不存在"}), 404

        # 处理头像数据
        avatar_data = None
        if user.user_avatar:
            if isinstance(user.user_avatar, bytes):
                avatar_data = f"data:image/jpeg;base64,{base64.b64encode(user.user_avatar).decode('utf-8')}"
            else:
                avatar_data = user.user_avatar

        logger.info(f"获取用户可修改数据: {user_id}")
    
        return jsonify({
            "code": 200,
            "data": {
                "user_id": user.user_id,
                "username": user.username,
                "gender": user.gender,
                "avatar": avatar_data or current_app.config['DEFAULT_AVATAR_URL'],
                "telephone": user.telephone,
            }
        }), 200
        
    except Exception as e:
        logger.error(f"获取用户可修改信息失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500
    
@user_bp.route('/<int:user_id>/trips', methods=['GET'])
def get_user_trips(user_id):
    """
    获取用户的行程记录
    """
    logger = get_logger(__name__)

    try:
        # 获取用户信息
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 404, "message": "用户不存在"}), 404
        
        # TODO: 获取用户的行程记录
        # trips = user.get_trips()
        return jsonify({"code": 200, "data": []}), 200
    except Exception as e:
        logger.error(f"获取用户行程失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500

# 身份证号计算年龄工具函数
def calculate_age_from_id(identity_id):
    """根据身份证号计算年龄"""
    birth_date_str = identity_id[6:14]  # 18位身份证的生日部分
    birth_date = datetime.strptime(birth_date_str, "%Y%m%d")
    today = datetime.now()
    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day))
    return age

@user_bp.route('/update/<int:user_id>', methods=['POST'])
def update_user(user_id):
    logger = get_logger(__name__)
    
    # 确保请求包含JSON数据
    if not request.is_json:
        return jsonify({"code": 400, "message": "请求必须为JSON格式"}), 400
        
    data = request.get_json()    
    logger.debug(f"更新用户数据: {data}")
    
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 404, "message": "用户不存在"}), 404
            
        # 更新基本信息
        if 'username' in data:
            user.username = data['username']
        if 'telephone' in data:
            user.telephone = data['telephone']
        if 'gender' in data:
            user.gender = data['gender']
            
        # 更新密码（如果有提供）
        if 'password' in data and data['password']:
            user.set_password(data['password'])
            
        db.session.commit()
        
        return jsonify({
            "code": 200, 
            "message": "个人信息已保存",
            "data": {
                "username": user.username,
                "telephone": user.telephone,
                "gender": user.gender
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新用户信息失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误: " + str(e)}), 500

@user_bp.route('/upload_avatar/<int:user_id>', methods=['POST'])
def upload_avatar(user_id):
    """
    上传/更新用户头像 (Base64版本)
    """
    logger = get_logger(__name__)

    # 检查是否有Base64编码的图片数据
    if not request.is_json or 'base64_data' not in request.json:
        logger.error("没有上传Base64数据")
        return jsonify({"code": 400, "message": "请上传Base64数据"}), 400

    try:
        user = User.query.get(user_id)
        if not user:
            logger.error(f"用户不存在: {user_id}")
            return jsonify({"code": 404, "message": "用户不存在"}), 404

        # 处理Base64上传
        base64_str = request.json['base64_data'].split(',')[-1]  # 去掉Base64前缀(如果有)
        avatar_data = base64.b64decode(base64_str)  # 解码Base64字符串为二进制数据
        user.user_avatar = avatar_data

        db.session.commit()

        logger.info(f"用户 {user_id} 上传头像成功")
        return jsonify({
            "code": 200,
            "message": "头像上传成功"
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"上传头像失败: {e}")
        return jsonify({"code": 500, "message": f"服务器错误: {str(e)}"}), 500

@user_bp.route('/avatar/<int:user_id>', methods=['GET'])
def get_avatar(user_id):
    """
    获取用户头像(Base64版本)
    """
    logger = get_logger(__name__)
    
    try:
        user = User.query.get(user_id)
        if not user:
            logger.warning(f"用户不存在: {user_id}")
            return jsonify({"code": 404, "message": "用户不存在"}), 404
            
        if not user.user_avatar:
            return jsonify({
                "code": 200,
                "data": {
                    "avatar_url": current_app.config['DEFAULT_AVATAR_URL']
                }
            }), 200
            
        # 将二进制数据编码为Base64字符串
        avatar_base64 = base64.b64encode(user.user_avatar).decode('utf-8')
        # 添加Data URL前缀
        avatar_url = f"data:image/jpeg;base64,{avatar_base64}"

        return jsonify({
            "code": 200,
            "data": {
                "avatar_url": avatar_url
            }
        }), 200
    except Exception as e:
        logger.error(f"获取用户头像失败: {e}")
        return jsonify({"code": 500, "message": str(e)}), 500