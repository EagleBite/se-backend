import base64
from datetime import datetime
from ..models import User,Car
from ..utils.logger import get_logger, log_requests
from ..utils.Response import ApiResponse
from ..models.association import user_car
from ..extensions import db
from flask import Blueprint, jsonify, current_app, request
from flask_jwt_extended import jwt_required, get_jwt_identity

user_bp = Blueprint('user_api', __name__)

@user_bp.route('/basic', methods=['GET'])
@jwt_required()
@log_requests()
def get_user_basic():
    """
    获取用户基础信息
    """
    logger = get_logger(__name__)

    current_user_id = get_jwt_identity()
    logger.info(f"获取用户 {current_user_id} 的基础信息")

    try:
        # 获取用户信息
        user = User.query.get(current_user_id)
        if not user:
            logger.warning(f"用户不存在: {current_user_id}")
            return ApiResponse.error("用户不存在", code=401).to_json_response(200)

        # 计算年龄
        age = calculate_age_from_id(user.identity_id) if user.identity_id else None
        
        # 处理头像数据
        avatar_data = None
        if user.user_avatar:
            if isinstance(user.user_avatar, bytes):
                avatar_data = f"data:image/jpeg;base64,{base64.b64encode(user.user_avatar).decode('utf-8')}"
            else:
                avatar_data = user.user_avatar

        # 构建响应数据
        user_data = {
            "user_id": user.user_id,
            "username": user.username,
            "gender": user.gender,
            "age": age,
            "avatar": avatar_data or current_app.config['DEFAULT_AVATAR_URL'],
            "rate": float(user.rate) if user.rate else 0.0,
            "status": user.status
        }

        logger.success(f"成功获取用户基础数据: {current_user_id}")
        return ApiResponse.success(
            "获取用户基础信息成功",
            data=user_data
        ).to_json_response(200)

    except Exception as e:
        logger.error(f"获取用户基础信息失败: {str(e)}")
        return ApiResponse.error("服务器内部错误", code=500).to_json_response(200)

@user_bp.route('/profile', methods=['GET'])
@jwt_required()
@log_requests()
def get_user_profile():
    """
    获取用户完整档案（个人中心页面）
    """
    logger = get_logger(__name__)

    current_user_id = get_jwt_identity()
    logger.info(f"获取用户 {current_user_id} 的档案信息")

    try:
        # 获取用户信息
        user = User.query.get(current_user_id)
        if not user:
            logger.warning(f"用户不存在: {current_user_id}")
            return ApiResponse.error("用户不存在", code=401).to_json_response(401)

        # 处理头像数据
        avatar_data = None
        if user.user_avatar:
            if isinstance(user.user_avatar, bytes):
                avatar_data = f"data:image/jpeg;base64,{base64.b64encode(user.user_avatar).decode('utf-8')}"
            else:
                avatar_data = user.user_avatar

        # 构造响应数据
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

        logger.success(f"成功获取用户基础数据: {current_user_id}")
        return ApiResponse.success(
            "获取用户基础信息成功",
            data=profile
        ).to_json_response(200)
    except Exception as e:
        logger.error(f"获取用户档案失败: {str(e)}")
        return ApiResponse.error("服务器内部错误", code=500).to_json_response(200)

@user_bp.route('/modifiable_data', methods=['GET'])
@jwt_required()
@log_requests()
def get_user_modifiable_data():
    """
    获取用户可修改的信息
    """
    logger = get_logger(__name__)

    current_user_id = get_jwt_identity()
    logger.info(f"获取用户 {current_user_id} 的可修改信息")

    try:
        # 获取用户信息
        user = User.query.get(current_user_id)
        if not user:
            logger.warning(f"用户不存在: {current_user_id}")
            return ApiResponse.error("用户不存在", code=401).to_json_response(200)

        # 处理头像数据
        avatar_data = None
        if user.user_avatar:
            if isinstance(user.user_avatar, bytes):
                avatar_data = f"data:image/jpeg;base64,{base64.b64encode(user.user_avatar).decode('utf-8')}"
            else:
                avatar_data = user.user_avatar

        # 构建响应数据
        user_data = {
            "user_id": user.user_id,
            "username": user.username,
            "gender": user.gender,
            "avatar": avatar_data or current_app.config['DEFAULT_AVATAR_URL'],
            "telephone": user.telephone,
        }

        logger.success(f"成功获取用户可修改信息: {current_user_id}")
        return ApiResponse.success(
            "获取用户可修改信息成功",
            data=user_data
        ).to_json_response(200)        
    except Exception as e:
        logger.error(f"获取用户可修改信息失败: {str(e)}")
        return ApiResponse.error("服务器内部错误", code=500).to_json_response(200)
    
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

@user_bp.route('/avatar', methods=['GET'])
@jwt_required()
@log_requests()
def get_avatar():
    """
    获取用户头像(Base64版本)
    """
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    logger.info(f"开始获取用户 {current_user_id} 的头像")

    try:
        user = User.query.get(current_user_id)
        if not user:
            logger.warning(f"用户不存在: {current_user_id}")
            return ApiResponse.error("用户不存在", code=404).to_json_response(200)

        # 处理默认头像情况
        if not user.user_avatar:
            logger.info(f"用户 {current_user_id} 使用默认头像")
            return ApiResponse.success(
                "获取头像成功",
                data={
                    "avatar_url": current_app.config['DEFAULT_AVATAR_URL']
                }
            ).to_json_response(200)

        # 将二进制数据编码为Base64字符串
        avatar_base64 = base64.b64encode(user.user_avatar).decode('utf-8')
        avatar_url = f"data:image/jpeg;base64,{avatar_base64}"

        logger.success(f"成功获取用户 {current_user_id} 的头像")
        return ApiResponse.success(
            "获取头像成功",
            data={
                "avatar_url": avatar_url
            }
        ).to_json_response(200)

    except Exception as e:
        logger.error(f"获取用户头像失败: {str(e)}")
        return ApiResponse.error(
            "获取头像失败: " + str(e),
            code=500
        ).to_json_response(200)

@user_bp.route('/update', methods=['POST'])
@jwt_required()
@log_requests()
def update_user():
    """
    更新用户信息
    """
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    logger.info(f"开始更新用户 {current_user_id} 的信息")

    data = request.get_json()    
    logger.debug(f"更新用户数据: {data}")

    try:
        # 获取用户信息
        user = User.query.get(current_user_id)
        if not user:
            logger.warning(f"用户不存在: {current_user_id}")
            return ApiResponse.error("用户不存在", code=404).to_json_response(200)

        # 更新基本信息
        if 'username' in data:
            user.username = data['username']
        if 'telephone' in data:
            user.telephone = data['telephone']
        if 'gender' in data:
            user.gender = data['gender']

        # 更新密码
        if 'password' in data and data['password']:
            user.password = data['password']

        db.session.commit()
    
        # 构建响应数据
        response_data = {
            "username": user.username,
            "telephone": user.telephone,
            "gender": user.gender
        }

        logger.success(f"用户 {current_user_id} 信息更新成功")
        return ApiResponse.success(
            "个人信息已保存",
            data=response_data
        ).to_json_response(200)

    except Exception as e:
        db.session.rollback()
        logger.error(f"更新用户信息失败: {e}")
        return ApiResponse.error("服务器错误: " + str(e), code=500).to_json_response(200)