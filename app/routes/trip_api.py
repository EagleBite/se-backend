from flask import Blueprint, jsonify, request
from datetime import datetime
from decimal import Decimal
from ..extensions import db
from ..models import Order, OrderParticipant, User, Car, Manager,association
from ..utils.logger import get_logger

trip_bp = Blueprint('trip_api', __name__)

def map_status_to_frontend(db_status):
    """将数据库状态枚举值映射为前端显示的中文字符串"""
    mapping = {
        'PENDING': '处理中',
        'COMPLETED': '已完成',
        'TO_REVIEW': '待评价',
        'NOT_STARTED': '未开始', # 初始状态
        'IN_PROGRESS': '进行中',
        'REJECTED': '已拒绝'
    }
    return mapping.get(db_status, db_status)

def format_datetime(dt):
    """将 datetime 对象格式化为前端适用的字符串"""
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d %H:%M')
    return str(dt)

def decimal_to_float(d):
    """将 Decimal 类型转换为 float 类型，用于 JSON 序列化"""
    if isinstance(d, Decimal):
        return float(d)
    return d

@trip_bp.route('/<int:order_id>/rate', methods=['GET'])
def rate_trip(order_id):
    """提交对特定行程/订单的评分"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体不能为空"}), 400
        rating_value = data.get('rating_value')
        if rating_value is None or not isinstance(rating_value, int) or not (1 <= rating_value <= 5):
            return jsonify({"error": "无效的评分值。必须是 1 到 5 之间的整数。"}), 400

        order = db.session.query(Order).filter_by(order_id=order_id).first()
        if not order:
            return jsonify({"error": "未找到该行程"}), 404

        if order.status != 'TO_REVIEW':  # Ensure this matches the enum value in the database
            print(f"警告：正在评价状态为 '{order.status}' 的订单 {order_id}，而非 'to-review' 状态。")

        order.rate = str(rating_value)
        order.status = 'COMPLETED'  # Ensure this matches the enum value in the database
        db.session.commit()
        print(f"订单 {order_id} 评分成功，评分为 {rating_value} 星。")
        return jsonify({"message": "评价提交成功！"}), 201
    except Exception as e:
        db.session.rollback()
        print(f"评价行程 {order_id} 时出错: {e}")
        description = str(e)
        return jsonify({"error": "服务器内部错误", "description": description}), 500
    pass

@trip_bp.route('/<int:order_id>', methods=['GET'])
def get_trip_detail(order_id):
    """获取特定行程/订单的详细信息"""
    try:
        order = db.session.query(Order).filter_by(order_id=order_id).first()
        if not order:
            return jsonify({"error": "未找到该行程"}), 404

        driver_participant = db.session.query(OrderParticipant)\
            .filter_by(order_id=order.order_id, identity='driver')\
            .first()

        driver_info = {
            "userAvatar": '../../static/default_avatar.png',
            "orderCount": 0,
            "driverUserId": None
        }
        if driver_participant:
            driver = db.session.query(User).filter_by(user_id=driver_participant.participator_id).first()
            if driver:
                driver_info["userAvatar"] = driver.user_avatar or '../../static/default_avatar.png'
                driver_info["orderCount"] = driver.order_time or 0
                driver_info["driverUserId"] = driver.user_id

        trip_data = {
            "id": order.order_id,
            "date": format_datetime(order.start_time),
            "startPoint": order.start_loc,
            "endPoint": order.dest_loc,
            "price": decimal_to_float(order.price) if order.price else 0.0,
            "carType": order.car_type or "未知车型", # 使用 orders 表中的 car_type
            "orderCount": driver_info["orderCount"],
            "userAvatar": driver_info["userAvatar"],
            "state": map_status_to_frontend(order.status),
            "driverUserId": driver_info["driverUserId"],
        }
        return jsonify(trip_data), 200
    except Exception as e:
        print(f"获取行程 {order_id} 详情时出错: {e}")
        return jsonify({"error": "服务器内部错误"}), 500
    pass

