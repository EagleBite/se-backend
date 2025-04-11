from flask import Blueprint, jsonify, request
from datetime import datetime
from decimal import Decimal
from ..extensions import db
from ..models import Order, OrderParticipant, User, Car
from ..utils.logger import get_logger

trip_bp = Blueprint('trip_api', __name__)

@trip_bp.route('/<int:user_id>', methods=['GET'])
def get_trips(user_id):
    """获取用户的订单记录"""
    pass

@trip_bp.route('/<int:order_id>', methods=['GET'])
def get_trip_detail(order_id):
    """获取特定行程/订单的详细信息"""
    pass