from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import User, Car
from ..utils.logger import get_logger
from ..extensions import db

vehicle_bp = Blueprint('vehicle_api', __name__)

@vehicle_bp.route('/user/cars/<int:user_id>', methods=['GET'])
def get_user_cars(user_id):
    """获取用户车辆列表"""
    logger = get_logger(__name__)
    user = User.query.get(user_id)
    if not user:
        return jsonify({"code": 404, "message": "用户不存在"}), 404
    try:  
        cars = [{
            "car_id": car.car_id,
            "plate_number": car.license,
            "brand_model": car.car_type,
            "color": car.color,
            "seats": car.seat_num
        } for car in user.cars]
        
        return jsonify(cars), 200
        
    except Exception as e:
        logger.error(f"获取用户车辆失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500

@vehicle_bp.route('/user/cars/<int:user_id>', methods=['POST'])
@jwt_required()
def add_user_car(user_id):
    """添加用户车辆"""
    logger = get_logger(__name__)
    user_id = get_jwt_identity()
    
    data = request.get_json()
    if not data or not all(k in data for k in ['number', 'color', 'model', 'seats']):
        return jsonify({"code": 400, "message": "缺少必要参数"}), 400
    
    try:
        # 检查车牌是否已存在
        existing_car = Car.query.filter_by(license=data['number']).first()
        if existing_car:
            return jsonify({"code": 409, "message": "车牌已存在"}), 409
            
        # 创建新车
        new_car = Car(
            license=data['number'],
            color=data['color'],
            car_type=data['model'],
            seat_num=data['seats']
        )
        db.session.add(new_car)
        
        # 关联用户和车辆
        user = User.query.get(user_id)
        user.cars.append(new_car)
        
        db.session.commit()
        
        return jsonify({"success": True, "message": "添加成功"}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"添加车辆失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500

@vehicle_bp.route('/user/cars/<string:old_number>', methods=['PUT'])
@jwt_required()
def update_user_car(old_number):
    """更新用户车辆信息"""
    logger = get_logger(__name__)
    user_id = get_jwt_identity()
    
    data = request.get_json()
    if not data or not all(k in data for k in ['number', 'color', 'model', 'seats']):
        return jsonify({"code": 400, "message": "缺少必要参数"}), 400
    
    try:
        # 查找要更新的车辆
        user = User.query.get(user_id)
        car = next((c for c in user.cars if c.license == old_number), None)
        
        if not car:
            return jsonify({"code": 404, "message": "车辆不存在"}), 404
            
        # 检查新车牌是否已被其他车辆使用
        if data['number'] != old_number:
            existing = Car.query.filter(
                Car.license == data['number'],
                Car.car_id != car.car_id
            ).first()
            if existing:
                return jsonify({"code": 409, "message": "车牌已存在"}), 409
        
        # 更新车辆信息
        car.license = data['number']
        car.color = data['color']
        car.car_type = data['model']
        car.seat_num = data['seats']
        
        db.session.commit()
        
        return jsonify({"success": True, "message": "修改成功"}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新车辆失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500

@vehicle_bp.route('/user/cars/<string:number>', methods=['DELETE'])
@jwt_required()
def unbind_user_car(number):
    """解绑用户车辆"""
    logger = get_logger(__name__)
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        car = next((c for c in user.cars if c.license == number), None)
        
        if not car:
            return jsonify({"code": 404, "message": "车辆不存在"}), 404
            
        # 从用户车辆列表中移除
        user.cars.remove(car)
        
        # 如果没有其他用户关联这辆车，则删除车辆记录
        if len(car.owners) == 0:
            db.session.delete(car)
            
        db.session.commit()
        
        return jsonify({"success": True, "message": "解绑成功"}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"解绑车辆失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500