import os
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
from decimal import Decimal # 用于处理 Decimal 类型

# --- Configuration ---
app = Flask(__name__)
CORS(app) # 允许跨域请求

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:xbsg20040619@localhost/software_design'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False # 设置为 True 可以看到生成的 SQL 查询语句

db = SQLAlchemy(app)

# --- Database Models ---

class User(db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    user_avatar = db.Column(db.String(255), default='../../static/default_avatar.png')
    rate = db.Column(db.Numeric(3, 2), default=0.00)
    order_time = db.Column(db.Integer, default=0)
    # 假设 user 表有车辆关联 (虽然 schema 中是 user_car 表)
    # cars = db.relationship('Car', secondary='user_car', backref='owners') # 如果需要通过 User 获取车辆

# --- 新增 Car 模型 (根据 schema) ---
class Car(db.Model):
    __tablename__ = 'car'
    car_id = db.Column(db.Integer, primary_key=True)
    license = db.Column(db.String(10), nullable=False) # 车牌号
    car_type = db.Column(db.String(50), nullable=False) # 车型
    color = db.Column(db.String(20), nullable=False)
    seat_num = db.Column(db.Integer, nullable=False) # 总座位数

# --- 新增 UserCar 模型 (关联表) ---
class UserCar(db.Model):
    __tablename__ = 'user_car'
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('car.car_id'), primary_key=True)


class Order(db.Model):
    __tablename__ = 'orders'
    order_id = db.Column(db.Integer, primary_key=True)
    initiator_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))
    start_loc = db.Column(db.String(100), nullable=False)
    dest_loc = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum('pending', 'completed', 'to-review', 'not-started', 'in-progress'), default='not-started')
    order_type = db.Column(db.Enum('driver', 'passenger'), nullable=False)
    car_type = db.Column(db.String(50), nullable=True) # 允许为空
    # --- 添加以下两个字段 ---
    travel_partner_num = db.Column(db.Integer, nullable=True) # 乘客订单的同乘人数
    spare_seat_num = db.Column(db.Integer, nullable=True)     # 司机订单的剩余座位数
    # ------------------------
    rate = db.Column(db.Enum('0','1', '2', '3', '4', '5'), default=None)

    initiator = db.relationship('User', backref='initiated_orders')
    participants = db.relationship('OrderParticipant', backref='order', cascade="all, delete-orphan")

class OrderParticipant(db.Model):
    __tablename__ = 'order_participants'
    participator_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id'), primary_key=True)
    identity = db.Column(db.Enum('driver', 'passenger'), nullable=False)

    user = db.relationship('User', backref='participations')

# --- Helper Functions ---

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

# --- API Endpoints ---

# (get_trip_details 和 rate_trip 保持不变)
@app.route('/api/trip/<int:order_id>', methods=['GET'])
def get_trip_details(order_id):
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
            "driverUserId": driver_info["driverUserId"]
        }
        return jsonify(trip_data), 200
    except Exception as e:
        print(f"获取行程 {order_id} 详情时出错: {e}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/trip/<int:order_id>/rate', methods=['POST'])
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

        if order.status != 'to-review':
            print(f"警告：正在评价状态为 '{order.status}' 的订单 {order_id}，而非 'to-review' 状态。")

        order.rate = str(rating_value)
        order.status = 'completed'
        db.session.commit()
        print(f"订单 {order_id} 评分成功，评分为 {rating_value} 星。")
        return jsonify({"message": "评价提交成功！"}), 201
    except Exception as e:
        db.session.rollback()
        print(f"评价行程 {order_id} 时出错: {e}")
        description = str(e)
        return jsonify({"error": "服务器内部错误", "description": description}), 500

# --- 新增获取用户车辆列表的接口 (模拟) ---
@app.route('/api/user/<int:user_id>/vehicles', methods=['GET'])
def get_user_vehicles(user_id):
    """获取指定用户的车辆列表 (模拟数据)"""
    # 在真实应用中，这里应该查询 user_car 和 car 表
    user = User.query.get(user_id)
    if not user:
       return jsonify({"error": "User not found"}), 404
    vehicles = Car.query.join(UserCar).filter(UserCar.user_id == user_id).all()
    result = [{"id": car.car_id, "plateNumber": car.license, "seats": car.seat_num, "carType": car.car_type} for car in vehicles]

    # --- 使用模拟数据 ---
    # print(f"模拟获取用户 {user_id} 的车辆列表")
    # mock_vehicles = [
    #     {"id": 1, "plateNumber": "沪A88888", "seats": 5, "carType": "舒适轿车"},
    #     {"id": 2, "plateNumber": "沪B66666", "seats": 7, "carType": "商务MPV"},
    #     {"id": 3, "plateNumber": "沪C12345", "seats": 5, "carType": "经济型"}
    # ]
    return jsonify(result), 200

# --- 新增创建订单的接口 ---
@app.route('/api/orders', methods=['POST'])
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

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # 确保新加的 Car, UserCar 模型表以及 Order 的新字段被创建
    app.run(host='0.0.0.0', port=5000, debug=True)