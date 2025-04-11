from flask import Blueprint, jsonify, request
from datetime import datetime
from decimal import Decimal
from ..extensions import db
from ..models import Order, OrderParticipant, User, Car
from ..utils.logger import get_logger

trip_bp = Blueprint('trip_api', __name__)

@trip_bp.route('/<int:order_id>', methods=['GET'])
def get_trip_detail(order_id):
    """获取特定行程/订单的详细信息"""
    logger = get_logger(__name__)
    
    try:
        # 获取订单信息
        order = Order.query.get(order_id)
        if not order:
            return jsonify({"error": "未找到该行程"}), 404
        
        # 获取参与者信息
        participants = OrderParticipant.query.filter_by(order_id=order_id).all()

    except:
        pass

    

    # 获取参与者信息
    participants = OrderParticipant.query.filter_by(order_id=order_id).all()
    participant_info = []
    for participant in participants:
        user = User.query.get(participant.participator_id)
        if user:
            participant_info.append({
                "user_id": user.user_id,
                "username": user.username,
                "identity": participant.identity.value
            })

    # 获取车辆信息
    car = Car.query.get(order.car_id) if order.car_id else None
    car_info = {
        "car_id": car.car_id if car else None,
        "car_number": car.car_number if car else None,
        "car_model": car.model if car else None
    } if car else None

    # 构建响应数据
    response_data = {
        "order_id": order.order_id,
        "start_location": order.start_location,
        "end_location": order.end_location,
        "departure_time": order.departure_time.strftime("%Y-%m-%d %H:%M:%S"),
        "price": str(order.price),
        "participants": participant_info,
        "car_info": car_info
    }

    return jsonify(response_data), 200