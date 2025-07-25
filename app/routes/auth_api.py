from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from ..models import User, Manager
from ..extensions import db
from ..utils.logger import get_logger, log_requests
from ..utils.Response import ApiResponse
import base64

auth_bp = Blueprint('auth_api', __name__)

@auth_bp.route('/register', methods=['POST'])
@log_requests()
def register():
    """用户注册"""
    logger = get_logger(__name__)
    data = request.get_json()
   
    # 检查用户名、手机号、身份证号是否已存在
    if User.query.filter_by(username=data['username']).first():
        response = ApiResponse.error(message="用户名已经被注册", code=400)
        return response.to_json_response(400)

    if User.query.filter_by(telephone=data['telephone']).first():
        response = ApiResponse.error(message="手机号已被注册", code=400)
        return response.to_json_response(400)
    
    if User.query.filter_by(identity_id=data['identity_id']).first():
        response = ApiResponse.error(message="身份证号已被注册", code=400)
        return response.to_json_response(400)
    
    user, error = User.create_user(data)
    
    if error:
        response = ApiResponse.error(message=f"用户注册失败: {error}", code=400)
        return response.to_json_response(400)
    
    logger.success(f"用户注册成功: {user.user_id, user.username}")

    response = ApiResponse.success(message="登录成功", data={"userId": user.user_id})
    return response.to_json_response()

@auth_bp.route('/login', methods=['POST'])
@log_requests()
def login():
    """用户登陆"""
    logger = get_logger(__name__)

    # 获取请求数据
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # 查找用户并校验密码
    user = User.query.filter_by(username=username).first()
    if not user or not user.verify_password(password):
        logger.warning(f"用户名或密码错误: {username}")
        return ApiResponse.error("用户名或密码错误", code=401).to_json_response(401)
    
    # 创建JWT token
    access_token = create_access_token(
        identity=str(user.user_id),
        additional_claims={
            "user_info": {
                "ID": user.identity_id,
                "username": user.username
            }
        }
    )
    
    # 处理头像数据 - 如果是二进制数据则转换为base64
    avatar_data = None
    if user.user_avatar:
        if isinstance(user.user_avatar, bytes):
            avatar_data = f"data:image/jpeg;base64,{base64.b64encode(user.user_avatar).decode('utf-8')}"
        else:
            # 如果avatar是URL字符串，则直接使用
            avatar_data = user.user_avatar
    
    logger.success(f"用户登录成功: {user.user_id, user.username}")

    # 构建响应数据
    user_data = {
        "userId": user.user_id,
        "username": user.username,
        "gender": user.gender,
        "age": user.calculate_age(user.identity_id),
        "avatar": avatar_data or current_app.config['DEFAULT_AVATAR_URL'],
        "is_manager": user.is_manager
    }

    return ApiResponse.success(
        message="登录成功",
        data={
            "user": user_data,
            "access_token": access_token
        }
    ).to_json_response(200)

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)  # 必须用refresh_token
def refresh():
    identity = get_jwt_identity()
    new_token = create_access_token(identity=identity)
    return jsonify({
        "code": 200,
        "message": "刷新成功",
        "data": {
            "access_token": new_token
        }
    }), 200