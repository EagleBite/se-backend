from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import User
from ..utils.logger import get_logger
from werkzeug.utils import secure_filename
import os
import requests


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
            "last_active": user.last_active.isoformat() if user.last_active else None,
        },
        "vehicles": [{
            "car_id": car.car_id,
            "plate_number": car.license,
            "brand_model": f"{car.brand} {car.model}"
        } for car in user.cars]
    }

    return jsonify({"code": 200, "data": profile}), 200

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

        # 计算年龄
        age = calculate_age_from_id(user.identity_id) if user.identity_id else None

        logger.info(f"获取用户基础数据: {user_id}")
        return jsonify({
                "code": 200,
                "data": {
                    "user_id": user.user_id,
                    "username": user.username,
                    "gender": user.gender,
                    "avatar": user.user_avatar or current_app.config['DEFAULT_AVATAR_URL'],
                    "telephone": user.telephone,
                }
            }), 200
    except Exception as e:
        logger.error(f"获取用户基础信息失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500
    
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


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@user_bp.route('/update/<int:user_id>', methods=['POST'])
def update_user(user_id):
    # 确保请求包含JSON数据
    if not request.is_json:
        return jsonify({"code": 400, "message": "请求必须为JSON格式"}), 400
        
    data = request.get_json()        
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 404, "message": "用户不存在"}), 404
            
        # 验证并更新数据
        if 'username' in data:
            # 检查用户名是否已存在
            existing = User.query.filter(
                User.username == data['username'],
                User.user_id != user_id
            ).first()
            if existing:
                return jsonify({"code": 400, "message": "用户名已被使用"}), 400
            user.username = data['username']
            
        if 'telephone' in data:
            # 检查手机号是否已存在
            existing = User.query.filter(
                User.telephone == data['telephone'],
                User.user_id != user_id
            ).first()
            if existing:
                return jsonify({"code": 400, "message": "手机号已被使用"}), 400
            user.telephone = data['telephone']
            
        if 'gender' in data:
            if data['gender'] not in ['男', '女']:
                return jsonify({"code": 400, "message": "无效的性别参数"}), 400
            user.gender = data['gender']
            
        db.session.commit()
        return jsonify({"code": 200, "message": "个人信息已保存"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "message": "服务器错误"}), 500

@user_bp.route('/upload_avatar/<int:user_id>', methods=['POST'])
def upload_avatar(user_id):
    """
    上传/更新用户头像
    """
    logger = get_logger(__name__)

    # 检查是否有文件URL
    if 'file_url' not in request.json:
        logger.error("没有上传文件URL")
        return jsonify({"code": 400, "message": "没有上传文件URL"}), 400

    file_url = request.json['file_url']

    try:
        user = User.query.get(user_id)
        if not user:
            logger.error(f"用户不存在: {user_id}")
            return jsonify({"code": 404, "message": "用户不存在"}), 404

        # 创建上传目录（如果不存在）
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/avatars')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        # 下载文件
        response = requests.get(file_url)
        if response.status_code != 200:
            logger.error(f"下载文件失败: {file_url}")
            return jsonify({"code": 500, "message": "下载文件失败"}), 500

        # 生成安全的文件名
        filename = secure_filename(f"user_{user_id}.jpg")  # 假设文件为jpg格式
        filepath = os.path.join(upload_folder, filename)

        # 保存文件
        with open(filepath, 'wb') as f:
            f.write(response.content)

        # 更新用户头像URL
        user.user_avatar = f"/{upload_folder}/{filename}"
        db.session.commit()

        logger.info(f"用户 {user_id} 上传头像成功")
        return jsonify({
            "code": 200,
            "message": "头像上传成功",
            "data": {
                "avatar_url": user.user_avatar
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"上传头像失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500

