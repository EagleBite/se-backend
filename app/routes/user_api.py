import base64
from datetime import datetime
from ..models import User,Car,Order,OrderParticipant
from ..utils.logger import get_logger, log_requests
from ..utils.Response import ApiResponse
from ..models.association import user_car
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db

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

@user_bp.route('/<int:user_id>/vehicles', methods=['GET'])
def get_user_vehicles(user_id):
    """获取指定用户的车辆列表 (模拟数据)"""
    user = User.query.get(user_id)
    if not user:
       return jsonify({"error": "User not found"}), 404
    vehicles = Car.query.join(user_car, user_car.c.user_id == user_id).all()
    result = [{"id": car.car_id, "plateNumber": car.license, "seats": car.seat_num, "carType": car.car_type} for car in vehicles]
    print(f"获取用户 {user_id} 的车辆列表成功")
    return jsonify({
        "code": 200, 
        "message": "获取车辆列表成功",
        "data": result
    }), 200

@user_bp.route('/<int:user_id>/orders', methods=['GET'])
def get_user_orders(user_id):
    """
    获取用户订单记录
    """
    logger = get_logger(__name__)
    try:
        user = User.query.get(user_id)
        
        # 解析查询参数
        order_type = request.args.get('type', 'all')
        status = request.args.get('status', 'all')
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        day = request.args.get('day', type=int)
        sort = request.args.get('sort', 'time-desc')
        page = request.args.get('page', 1, type=int)
        page_size = min(request.args.get('page_size', 10, type=int), 100)

        # 构建基础查询
        query = Order.query.filter(
            db.or_(
                Order.initiator_id == user_id,
                Order.participants.any(OrderParticipant.participator_id == user_id)
            )
        )

        # 类型过滤
        if order_type != 'all' and order_type in ['driver', 'passenger']:
            query = query.filter(Order.order_type == order_type)

        # 状态过滤
        if status != 'all' and status in ['pending','completed','rejected','not-started','in-progress','to-pay','to-review']:
            query = query.filter(Order.status == status)

        # 时间过滤
        if year:
            query = query.filter(db.extract('year', Order.start_time) == year)
            if month and 1 <= month <= 12:
                query = query.filter(db.extract('month', Order.start_time) == month)
                if day and 1 <= day <= 31:
                    query = query.filter(db.extract('day', Order.start_time) == day)

        # 排序逻辑
        sort_mapping = {
            'time-asc': Order.start_time.asc(),
            'time-desc': Order.start_time.desc(),
            'price-asc': Order.price.asc(),
            'price-desc': Order.price.desc()
        }
        query = query.order_by(sort_mapping.get(sort, Order.start_time.desc()))

        # 分页处理
        pagination = query.paginate(
            page=page,
            per_page=page_size,
            error_out=False
        )

        # 构建响应数据
        orders_data = []
        for order in pagination.items:
            order_data = {
                "order_id": order.order_id,
                "type": order.order_type,
                "status": order.status,
                "start_time": order.start_time.isoformat(),
                "start_loc": order.start_loc,
                "dest_loc": order.dest_loc,
                "price": float(order.price),
                "car_type": order.car_type,
                "participants": [{
                    "user_id": p.participator.user_id,
                    "username": p.participator.username
                } for p in order.participants]
            }
            if order.reject_reason:
                order_data["reject_reason"] = order.reject_reason
            orders_data.append(order_data)

        return jsonify({
            "code": 200,
            "data": {
                "total": pagination.total,
                "page": pagination.page,
                "page_size": pagination.per_page,
                "orders": orders_data
            }
        }), 200

    except Exception as e:
        logger.error(f"获取订单失败: {str(e)}", exc_info=True)
        return jsonify({"code": 500, "message": "服务器内部错误"}), 500