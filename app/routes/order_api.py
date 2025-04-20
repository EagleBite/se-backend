from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from decimal import Decimal
from ..extensions import db
import base64
from ..models import Order, OrderParticipant
from ..utils.logger import get_logger

order_bp = Blueprint('order_api', __name__)

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

@order_bp.route('/calendar/<int:user_id>', methods=['GET'])
def get_calendar_orders(user_id):
    """获取日历视图的订单数据"""
    logger = get_logger(__name__)
    
    try:
        year = int(request.args.get('year', datetime.now().year))
        month = int(request.args.get('month', datetime.now().month))
        
        # 计算月份的开始和结束日期
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # 查询该用户在该月份内作为发起者或参与者的订单
        orders = Order.query.filter(
            and_(
                Order.start_time >= start_date,
                Order.start_time <= end_date,
                or_(
                    Order.initiator_id == user_id,
                    Order.order_id.in_(
                        db.session.query(OrderParticipant.order_id)
                        .filter(OrderParticipant.participator_id == user_id)
                    )
                )
            )
        ).options(
            db.joinedload(Order.initiator),
            db.joinedload(Order.participants).joinedload(OrderParticipant.participator)
        ).all()
        
        # 格式化返回数据
        orders_data = []
        for order in orders:
            # 处理头像数据
            avatar_data = None
            if order.initiator.user_avatar:
                if isinstance(order.initiator.user_avatar, bytes):
                    avatar_data = f"data:image/jpeg;base64,{base64.b64encode(order.initiator.user_avatar).decode('utf-8')}"
                else:
                    avatar_data = order.initiator.user_avatar
            
            order_data = {
                'order_id': order.order_id,
                'start_loc': order.start_loc,
                'dest_loc': order.dest_loc,
                'start_time': order.start_time.isoformat(),
                'price': float(order.price),
                'car_type': order.car_type,
                'status': order.status,
                'initiator': {
                    'user_id': order.initiator.user_id,
                    'username': order.initiator.username,
                    'avatar': avatar_data or current_app.config['DEFAULT_AVATAR_URL']
                },
                'participants_count': len(order.participants)
            }
            orders_data.append(order_data)
        
        # 统一返回格式
        return jsonify({
            "code": 200,
            "data": orders_data
        }), 200
        
    except ValueError as e:
        logger.error(f"Invalid date parameters: {str(e)}")
        return jsonify({
            "code": 400,
            "error": "无效的日期参数"
        }), 400
    except Exception as e:
        logger.error(f"Error fetching calendar orders: {str(e)}")
        return jsonify({
            "code": 500,
            "error": "获取日历数据失败"
        }), 500

@order_bp.route('/user/<int:user_id>/trips', methods=['GET'])
def get_user_trips(user_id):
    """获取用户最近的行程记录"""
    logger = get_logger(__name__)
    
    try:
        # 获取查询参数，限制返回的记录数
        limit = int(request.args.get('limit', 3))
        
        # 查询用户作为发起者或参与者的订单
        orders = Order.query.filter(
            or_(
                Order.initiator_id == user_id,
                Order.order_id.in_(
                    db.session.query(OrderParticipant.order_id)
                    .filter(OrderParticipant.participator_id == user_id)
                )
            )
        ).options(
            db.joinedload(Order.initiator),
            db.joinedload(Order.participants).joinedload(OrderParticipant.participator)
        ).order_by(Order.start_time.desc()).limit(limit).all()
        
        # 格式化返回数据
        trips_data = []
        for order in orders:
            # 处理头像数据
            avatar_data = None
            if order.initiator.user_avatar:
                if isinstance(order.initiator.user_avatar, bytes):
                    avatar_data = f"data:image/jpeg;base64,{base64.b64encode(order.initiator.user_avatar).decode('utf-8')}"
                else:
                    avatar_data = order.initiator.user_avatar
            
            trip_data = {
                'id': order.order_id,
                'date': order.start_time.isoformat(),
                'startPoint': order.start_loc,
                'endPoint': order.dest_loc,
                'price': float(order.price),
                'carType': order.car_type,
                'userAvatar': avatar_data or current_app.config['DEFAULT_AVATAR_URL'],
                'orderCount': len(order.participants),
                'status': order.status
            }
            trips_data.append(trip_data)
        
        return jsonify({
            "code": 200,
            "data": trips_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching user trips: {str(e)}")
        return jsonify({
            "code": 500,
            "error": "获取用户行程失败"
        }), 500
