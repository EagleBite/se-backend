from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from decimal import Decimal
from ..extensions import db
import base64
from ..models import Order, OrderParticipant
from ..utils.logger import get_logger
import json

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

@order_bp.route('/manage/list', methods=['GET'])
def get_managed_orders():
    """获取管理后台的订单列表"""
    logger = get_logger(__name__)
    
    try:
        params_str = request.args.get('params')
        if params_str:
            try:
                params = json.loads(params_str)
                status = params.get('status', 'all')
                order_type = params.get('type', 'all')
                year = params.get('year', None)
                month = params.get('month', None)
            except json.JSONDecodeError:
                return jsonify({"code": 400, "error": "参数格式错误，params 必须是有效的 JSON"}), 400
        else:
            # 如果没有 params，则从普通查询参数中获取
            status = request.args.get('status', 'all')
            order_type = request.args.get('type', 'all')
            year = request.args.get('year', None)
            month = request.args.get('month', None)
        # 构建基础查询
        query = Order.query.options(
            db.joinedload(Order.initiator),
            db.joinedload(Order.participants).joinedload(OrderParticipant.participator)
        )
        
        # 状态筛选
        if status != 'all':
            if status == 'approved':
                # approved 包含所有非 pending 和 rejected 的状态
                query = query.filter(Order.status.notin_(['pending', 'rejected']))
            else:
                query = query.filter(Order.status == status)

        # 类型筛选
        if order_type != 'all':
            query = query.filter(Order.order_type == order_type)
        
        # 时间筛选 - 重新设计的健壮逻辑
        if year or month:
            # 验证年份
            if year:
                if not year.isdigit():
                    return jsonify({
                        "code": 400,
                        "error": "年份参数必须是数字"
                    }), 400
                year = int(year)
                current_year = datetime.now().year
                if not (2020 <= year <= current_year + 1):  # 假设2020年是系统最早年份
                    return jsonify({
                        "code": 400,
                        "error": f"年份必须在2020到{current_year + 1}之间"
                    }), 400
            
            # 验证月份
            if month:
                if not month.isdigit():
                    return jsonify({
                        "code": 400,
                        "error": "月份参数必须是数字"
                    }), 400
                month = int(month)
                if not 1 <= month <= 12:
                    return jsonify({
                        "code": 400,
                        "error": "月份必须在1到12之间"
                    }), 400
            
            # 构建时间筛选条件
            if year and month:
                # 同时有年和月 - 筛选特定年月
                start_date = datetime(year, month, 1)
                if month == 12:
                    end_date = datetime(year + 1, 1, 1)
                else:
                    end_date = datetime(year, month + 1, 1)
                end_date = end_date - timedelta(seconds=1)
                query = query.filter(Order.start_time.between(start_date, end_date))
            elif year:
                # 只有年 - 筛选整年
                start_date = datetime(year, 1, 1)
                end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
                query = query.filter(Order.start_time.between(start_date, end_date))
            elif month:
                # 只有月 - 筛选所有年份的这个月
                query = query.filter(db.extract('month', Order.start_time) == month)
        
        # 排序
        orders = query.order_by(Order.start_time.desc()).all()
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
            
            # 格式化日期
            formatted_date = order.start_time.strftime('%Y年%m月%d日%H:%M')
            
            order_data = {
                'id': order.order_id,
                'type': order.order_type,
                'status': order.status,
                'date': formatted_date,
                'startPoint': order.start_loc,
                'endPoint': order.dest_loc,
                'price': float(order.price),
                'carType': order.car_type,
                'publisher': order.initiator.username,
                'userAvatar': avatar_data or current_app.config['DEFAULT_AVATAR_URL'],
                'rejectReason': order.reject_reason
            }
            orders_data.append(order_data)
        return jsonify({
            "code": 200,
            "data": orders_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching managed orders: {str(e)}")
        return jsonify({
            "code": 500,
            "error": "获取订单列表失败"
        }), 500

@order_bp.route('/manage/<int:order_id>/approve', methods=['POST'])
def approve_order(order_id):
    """审核通过订单"""
    logger = get_logger(__name__)
    
    try:
        order = Order.query.get(order_id)
        if not order:
            return jsonify({"code": 404, "error": "订单不存在"}), 404
        
        if order.status != 'pending':
            return jsonify({"code": 400, "error": "只能审核待处理的订单"}), 400
        
        # 更新状态为 not-started (根据业务需求)
        order.status = 'not-started'
        db.session.commit()
        
        return jsonify({
            "code": 200,
            "message": "订单审核通过"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error approving order {order_id}: {str(e)}")
        return jsonify({
            "code": 500,
            "error": "审核订单失败"
        }), 500

@order_bp.route('/manage/<int:order_id>/reject', methods=['POST'])
def reject_order(order_id):
    """拒绝订单"""
    logger = get_logger(__name__)
    
    try:
        data = request.get_json()
        if not data or 'reason' not in data:
            return jsonify({"code": 400, "error": "缺少拒绝原因"}), 400
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({"code": 404, "error": "订单不存在"}), 404
        
        if order.status != 'pending':
            return jsonify({"code": 400, "error": "只能拒绝待处理的订单"}), 400
        
        # 更新状态和拒绝原因
        order.status = 'rejected'
        order.reject_reason = data['reason']
        db.session.commit()
        
        return jsonify({
            "code": 200,
            "message": "订单已拒绝"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error rejecting order {order_id}: {str(e)}")
        return jsonify({
            "code": 500,
            "error": "拒绝订单失败"
        }), 500