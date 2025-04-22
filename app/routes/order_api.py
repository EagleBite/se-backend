from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
from decimal import Decimal
from ..extensions import db
from ..models import Order, OrderParticipant
from ..utils.logger import get_logger

order_bp = Blueprint('order_api', __name__, url_prefix='/api/orders')

def map_status_to_frontend(db_status):
    """将数据库状态枚举值映射为前端显示的中文字符串"""
    mapping = {
        'pending': '处理中',
        'completed': '已完成',
        'to-review': '待评价',
        'not-started': '未开始', # 初始状态
        'in-progress': '进行中',
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

@order_bp.route('', methods=['POST'])
def create_order():
    """创建新的拼车订单"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    # --- 基本字段验证 ---
    required_fields = ['identity', 'startAddress', 'endAddress', 'departureTime', 'price', 'initiator_id']
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    if missing_fields:
        return jsonify({"error": f"缺少必填字段: {', '.join(missing_fields)}"}), 400

    identity = data['identity']
    initiator_id = data['initiator_id']

    # --- 身份特定字段验证 ---
    if identity == 'driver':
        if 'vehicleId' not in data or data['vehicleId'] is None:
            return jsonify({"error": "司机发布订单必须选择车辆 (vehicleId)"}), 400
        if 'availableSeats' not in data or data['availableSeats'] is None:
            return jsonify({"error": "司机发布订单必须填写余座数 (availableSeats)"}), 400
        # 尝试从数据库获取车辆信息 (如果需要用 car_id 或更详细的 car_type)
        # car = Car.query.get(data['vehicleId'])
        # if not car:
        #     return jsonify({"error": "选择的车辆不存在"}), 400
        # 实际存储到 order 表的 car_type
        # order_car_type = car.car_type # 使用数据库中的车型
        # 简化处理：暂时接受前端可能传来的 plateNumber 或 carType
        order_car_type = data.get('carType') # 尝试获取前端传的 carType

    elif identity == 'passenger':
        if 'passengerCount' not in data or data['passengerCount'] is None:
            return jsonify({"error": "乘客发布订单必须填写同乘人数 (passengerCount)"}), 400
        order_car_type = None # 乘客订单通常不指定车型
    else:
        return jsonify({"error": "无效的身份类型 (identity)"}), 400

    # --- 数据处理和创建 ---
    try:
        # 转换时间字符串
        try:
            try:
                start_time_dt = datetime.strptime(data['departureTime'], '%Y-%m-%d %H:%M')
            except ValueError:
                start_time_dt = datetime.strptime(data['departureTime'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return jsonify({"error": "无效的出发时间格式，请使用 'YYYY-MM-DD HH:MM'"}), 400

        # 转换价格
        try:
            price_decimal = Decimal(str(data['price']))
            if price_decimal < 0:
                 return jsonify({"error": "价格不能为负数"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "无效的价格格式"}), 400

        # 创建 Order 对象
        new_order = Order(
            initiator_id=initiator_id,
            start_loc=data['startAddress'],
            dest_loc=data['endAddress'],
            start_time=start_time_dt,
            price=price_decimal,
            status='not-started', # 初始状态
            order_type=identity,
            car_type=order_car_type, # 使用上面确定的 car_type
            travel_partner_num=data.get('passengerCount') if identity == 'passenger' else None,
            spare_seat_num=data.get('availableSeats') if identity == 'driver' else None
        )
        db.session.add(new_order)
        db.session.flush() # 先 flush 获取 new_order.order_id

        # 创建 OrderParticipant 对象 (发起人自己)
        new_participant = OrderParticipant(
            participator_id=initiator_id,
            order_id=new_order.order_id,
            identity=identity
        )
        db.session.add(new_participant)

        db.session.commit() # 提交事务

        print(f"新订单创建成功，ID: {new_order.order_id}, 发起人: {initiator_id}, 类型: {identity}")
        return jsonify({"message": "订单发布成功", "orderId": new_order.order_id}), 201 # Created

    except Exception as e:
        db.session.rollback()
        print(f"创建订单时出错: {e}")
        # 检查是否是外键约束错误 (例如 initiator_id 不存在于 user 表)
        if 'foreign key constraint' in str(e).lower():
             return jsonify({"error": "发起人用户ID无效"}), 400
        return jsonify({"error": "服务器内部错误，无法创建订单"}), 500
    