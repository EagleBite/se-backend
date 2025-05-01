from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from decimal import Decimal
from ..extensions import db
import base64
from ..models import Order, OrderParticipant
from ..utils.logger import get_logger, log_requests
from ..utils.Response import ApiResponse
import json
from flask_jwt_extended import jwt_required, get_jwt_identity

order_bp = Blueprint('order_api', __name__)

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
    print(data)
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
        if 'availableSeats' not in data or data['availableSeats'] is None:
            return jsonify({"error": "司机发布订单必须填写余座数 (availableSeats)"}), 400
        order_car_type = data.get('carType')  # 尝试获取前端传的 carType
    elif identity == 'passenger':
        if 'passengerCount' not in data or data['passengerCount'] is None:
            return jsonify({"error": "乘客发布订单必须填写同乘人数 (passengerCount)"}), 400
        order_car_type = None  # 乘客订单通常不指定车型
    else:
        return jsonify({"error": "无效的身份类型 (identity)"}), 400

    # --- 数据处理和创建 ---
    try:
        # 转换时间字符串
        try:
            start_time_dt = datetime.strptime(data['departureTime'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return jsonify({"error": "无效的出发时间格式，请使用 'YYYY-MM-DD HH:MM:SS'"}), 400

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
            status='pending',  # 初始状态
            order_type=identity,
            car_type=order_car_type,  # 使用上面确定的 car_type
            travel_partner_num=data.get('passengerCount') if identity == 'passenger' else None,
            spare_seat_num=data.get('availableSeats') if identity == 'driver' else None
        )
        db.session.add(new_order)
        db.session.flush()  # 先 flush 获取 new_order.order_id

        # 创建 OrderParticipant 对象 (发起人自己)
        new_participant = OrderParticipant(
            participator_id=initiator_id,
            initiator_id=initiator_id,
            order_id=new_order.order_id,
            identity=identity
        )
        db.session.add(new_participant)

        db.session.commit()  # 提交事务

        print(f"新订单创建成功，ID: {new_order.order_id}, 发起人: {initiator_id}, 类型: {identity}")
        return jsonify({"message": "订单发布成功", "orderId": new_order.order_id}), 200  # Created

    except Exception as e:
        db.session.rollback()
        print(f"创建订单时出错: {e}")
        # 检查是否是外键约束错误 (例如 initiator_id 不存在于 user 表)
        if 'foreign key constraint' in str(e).lower():
            return jsonify({"error": "发起人用户ID无效"}), 400
        return jsonify({"error": "服务器内部错误，无法创建订单"}), 500

@order_bp.route('/calendar/<int:user_id>', methods=['GET'])
def get_calendar_orders(user_id):
    """获取日历视图的订单数据"""
    logger = get_logger(__name__)
    
    try:
        # 从请求参数中获取 params
        params_str = request.args.get('params')
        if not params_str:
            return jsonify({"code": 400, "error": "缺少 params 参数"}), 400
        
        # 解析 params 参数
        try:
            params = json.loads(params_str)
            year = params.get('year')
            month = params.get('month')
        except json.JSONDecodeError:
            return jsonify({"code": 400, "error": "params 参数格式错误，必须是有效的 JSON"}), 400
        
        # 验证 year 和 month 是否存在
        if not year or not month:
            return jsonify({"code": 400, "error": "缺少 year 或 month 参数"}), 400
        
        # 转换 year 和 month 为整数
        try:
            year = int(year)
            month = int(month)
        except ValueError:
            return jsonify({"code": 400, "error": "year 和 month 参数必须是整数"}), 400
        
        # 计算月份的开始和结束日期
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
        
        print(start_date, end_date)
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

@order_bp.route('/user/trips', methods=['GET'])
@jwt_required()
@log_requests()
def get_user_trips():
    """获取用户最近的行程记录"""
    logger = get_logger(__name__)

    current_user_id = get_jwt_identity()
    logger.info(f"获取用户 {current_user_id} 的行程记录")
    
    try:
        # 获取查询参数，限制返回的记录数
        limit = int(request.args.get('limit', 3))
        
        # 查询用户作为发起者或参与者的订单
        orders = Order.query.filter(
            or_(
                Order.initiator_id == current_user_id,
                Order.order_id.in_(
                    db.session.query(OrderParticipant.order_id)
                    .filter(OrderParticipant.participator_id == current_user_id)
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
        
        logger.success(f"成功获取用户 {current_user_id} 的行程记录")
        return ApiResponse.success(
            "获取行程记录成功",
            data=trips_data
        ).to_json_response(200)
        
    except Exception as e:
        logger.error(f"获取行程记录失败: {str(e)}")
        return ApiResponse.error(
            "获取行程记录失败",
            code=500
        ).to_json_response(200)

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