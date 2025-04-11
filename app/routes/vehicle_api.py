from flask import Blueprint, jsonify
from ..models import User, Car
from ..utils.logger import get_logger

vehicle_bp = Blueprint('vehicle_api', __name__)

@vehicle_bp.route('/<int:user_id>/vehicles', methods=['GET'])
def get_user_vehicles(user_id):
    """获取指定用户的车辆列表"""
    pass