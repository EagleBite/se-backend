from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
from decimal import Decimal
from ..extensions import db
from ..models import Order, OrderParticipant
from ..utils.logger import get_logger

order_bp = Blueprint('order_api', __name__, url_prefix='/api/orders')

@order_bp.route('', methods=['POST'])
def create_order():
    """创建新的拼车订单"""
    logger = get_logger(__name__)

    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400
    
    order, error = Order.create_carpool_order(data)
    if error:
        return jsonify({"error": error}), 400
    
    logger.info(f"新订单创建成功: {order.order_id}")
    return jsonify({
            "message": "订单创建成功",
            "orderId": order.order_id,
            "startTime": order.start_time.isoformat()
        }), 201
    