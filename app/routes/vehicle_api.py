from flask import Blueprint, jsonify, request
from ..models import User, Car
from ..models.association import user_car
from ..utils.logger import get_logger, log_requests
from ..extensions import db
from ..utils.Response import ApiResponse
from flask_jwt_extended import jwt_required, get_jwt_identity

vehicle_bp = Blueprint('vehicle_api', __name__)

@vehicle_bp.route('', methods=['GET'])
@jwt_required()
@log_requests()
def get_user_cars():
    """
    获取当前用户的车辆列表
    """
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    logger.info(f"开始获取用户 {current_user_id} 的车辆列表")

    try:
        # 验证用户存在
        user = User.query.get(current_user_id)
        if not user:
            logger.warning(f"用户不存在: {current_user_id}")
            return ApiResponse.error("用户不存在", code=404).to_json_response(200)

        # 获取车辆列表
        cars = [{
            "car_id": car.car_id,
            "plate_number": car.license,
            "brand_model": car.car_type,
            "color": car.color,
            "seats": car.seat_num,
        } for car in user.cars]

        logger.success(f"成功获取用户 {current_user_id} 的 {len(cars)} 辆车辆")
        return ApiResponse.success(
            "获取车辆列表成功",
            data={
                "count": len(cars),
                "vehicles": cars
            }
        ).to_json_response(200)

    except Exception as e:
        logger.error(f"获取用户车辆失败: {str(e)}")
        return ApiResponse.error(
            f"获取车辆列表失败: {str(e)}",
            code=500
        ).to_json_response(200)

@vehicle_bp.route('/add', methods=['POST'])
@jwt_required()
@log_requests()
def add_user_car():
    """添加用户车辆"""
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # 参数校验
    required_fields = ['number', 'color', 'model', 'seats']
    if not data or not all(k in data for k in required_fields):
        logger.warning("缺少必要参数")
        return ApiResponse.error("缺少必要参数", code=400).to_json_response(200)
    
    try:
        user = User.query.get(current_user_id)
        if not user:
            logger.warning(f"用户不存在: {current_user_id}")
            return ApiResponse.error("用户不存在", code=404).to_json_response(200)

        # 检查车牌是否已存在
        existing_car = Car.query.filter_by(license=data['number']).first()
        
        if existing_car:
            # 比对车辆信息是否完全一致
            is_info_match = (
                existing_car.color == data['color'] and
                existing_car.car_type == data['model'] and
                existing_car.seat_num == data['seats']
            )
            
            if not is_info_match:
                logger.warning(f"车辆信息不匹配: {data['number']}")
                return ApiResponse.success(
                    "车辆信息不匹配",
                    data={
                        "existing_info": {
                            "color": existing_car.color,
                            "model": existing_car.car_type,
                            "seats": existing_car.seat_num
                        }
                    }
                ).to_json_response(200)
            
            # 信息一致，检查是否已关联
            if existing_car in user.cars:
                logger.info(f"车辆已关联: {data['number']}")
                return ApiResponse.success(
                    "车辆已关联",
                    data={
                        "car_id": existing_car.car_id,
                        "plate_number": existing_car.license
                    }
                ).to_json_response(200)
                
            # 添加关联关系
            user.cars.append(existing_car)
            db.session.commit()

            logger.success(f"成功关联已有车辆: {data['number']}")
            return ApiResponse.success(
                "关联成功",
                data={
                    "car_id": existing_car.car_id,
                    "plate_number": existing_car.license
                }
            ).to_json_response(200)
            
        # 全新车辆
        new_car = Car(
            license=data['number'],
            color=data['color'],
            car_type=data['model'],
            seat_num=data['seats']
        )
        db.session.add(new_car)
        user.cars.append(new_car)
        db.session.commit()

        logger.success(f"成功添加新车辆: {data['number']}")
        return ApiResponse.success(
            "添加成功",
            data={
                "car_id": new_car.car_id,
                "plate_number": new_car.license,
                "brand_model": new_car.car_type,
                "color": new_car.color,
                "seats": new_car.seat_num,
            }
        ).to_json_response(200)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"添加车辆失败: {str(e)}")
        return ApiResponse.error(
            f"添加车辆失败: {str(e)}",
            code=500
        ).to_json_response(200)

@vehicle_bp.route('/<int:user_id>/<string:old_number>', methods=['PUT'])
def update_user_car(user_id, old_number):
    """更新用户车辆信息（增强校验版）"""
    logger = get_logger(__name__)
    data = request.get_json()
    
    if not data or not all(k in data for k in ['number', 'color', 'model', 'seats']):
        return jsonify({"code": 400, "message": "缺少必要参数"}), 400
    
    try:
        # 获取当前用户和原车辆
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 404, "message": "用户不存在"}), 404
            
        original_car = next((c for c in user.cars if c.license == old_number), None)
        if not original_car:
            return jsonify({"code": 404, "message": "原车辆不存在"}), 404
        
        # 检查新车牌是否已存在（排除自身）
        new_number = data['number']
        existing_car = Car.query.filter(
            Car.license == new_number,
            Car.car_id != original_car.car_id
        ).first()
        
        if existing_car:
            # 比对车辆信息是否完全一致
            is_info_match = (
                existing_car.color == data['color'] and
                existing_car.car_type == data['model'] and
                existing_car.seat_num == data['seats']
            )
            
            if not is_info_match:
                return jsonify({
                    "code": 200,
                    "message": "车辆信息不匹配",
                    "data": {
                        "existing_info": {
                            "color": existing_car.color,
                            "model": existing_car.car_type,
                            "seats": existing_car.seat_num
                        }
                    }
                }), 200
            
            # 信息一致，执行合并操作
            # 1. 将原车的所有关联用户转移到新车上
            for owner in original_car.owners:
                if existing_car not in owner.cars:
                    owner.cars.append(existing_car)
                owner.cars.remove(original_car)
            
            # 2. 删除原车记录
            db.session.delete(original_car)
            db.session.commit()
            
            return jsonify({
                "code": 200,
                "message": "合并成功",
                "data": {
                    "car_id": existing_car.car_id,
                    "plate_number": existing_car.license,
                    "brand_model": existing_car.car_type,
                    "color": existing_car.color,
                    "seats": existing_car.seat_num
                }
            }), 200
        
        # 普通更新流程（车牌不存在或为自身）
        original_car.license = new_number
        original_car.color = data['color']
        original_car.car_type = data['model']
        original_car.seat_num = data['seats']
        
        db.session.commit()
        
        return jsonify({
            "code": 200,
            "message": "修改成功",
            "data": {
                "car_id": original_car.car_id,
                "plate_number": original_car.license,
                "brand_model": original_car.car_type,
                "color": original_car.color,
                "seats": original_car.seat_num
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新车辆失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500
    
@vehicle_bp.route('/<int:user_id>/<string:number>', methods=['DELETE'])
def unbind_user_car(user_id, number):
    """解绑用户车辆"""
    logger = get_logger(__name__)
    try:
        # 获取用户和车辆
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 404, "message": "用户不存在"}), 404
            
        car = Car.query.filter_by(license=number).first()
        if not car:
            return jsonify({"code": 404, "message": "车辆不存在"}), 404
            
        # 检查用户是否拥有该车
        if car not in user.cars:
            return jsonify({"code": 400, "message": "用户未绑定该车辆"}), 400
            
        # 从用户车辆列表中移除
        user.cars.remove(car)
        
        # 检查是否还有其他用户拥有该车
        other_owners_count = db.session.query(user_car)\
            .filter(user_car.c.car_id == car.car_id)\
            .count()
            
        # 如果没有其他用户拥有该车，则删除车辆记录
        if other_owners_count == 0:
            db.session.delete(car)
            
        db.session.commit()
        
        return jsonify({
            "code": 200,
            "message": "解绑成功",
            "data": {
                "car_id": car.car_id,
                "plate_number": car.license
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"解绑车辆失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500