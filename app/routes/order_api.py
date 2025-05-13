from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from decimal import Decimal
from ..extensions import db
import base64
from ..models import Order, OrderParticipant, User, Car, Conversation, ConversationParticipant
from ..models.order import OrderStatus, OrderType
from ..models.order_participant import ParticipantIdentity
from ..models.Chat_conversation import ConversationType
from ..utils.logger import get_logger, log_requests
from ..utils.Response import ApiResponse
import json
from flask_jwt_extended import jwt_required, get_jwt_identity

order_bp = Blueprint('order_api', __name__)

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

@order_bp.route('/list', methods=['GET'])
@jwt_required()
@log_requests()
def get_order_list():
    """获取订单列表"""
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    logger.info(f"用户 {current_user_id} 请求获取订单列表")

    try:
        # 基础查询构建
        query = Order.query.options(
            db.joinedload(Order.initiator)
        )

        # 排除不合理的订单（出发时间已过且未开始的订单）
        current_time = datetime.utcnow()
        query = query.filter(
            (Order.status == OrderStatus.IN_PROGRESS.value) |
            (Order.status == OrderStatus.NOT_STARTED.value) |
            (Order.start_time > current_time)
        )

        # 执行查询获取全部结果
        all_orders = query.all()

        def format_order_date(dt):
            """格式化日期显示"""
            now = datetime.now()
            if dt.date() == now.date():
                return f"今天{dt.strftime('%H:%M')}"
            elif dt.date() == (now.date() - timedelta(days=1)):
                return f"昨天{dt.strftime('%H:%M')}"
            return dt.strftime("%m月%d日%H:%M")

        # 转换为前端格式
        orders = []
        for order in all_orders:
            user = order.initiator
            avatar_data = None
            if order.initiator.user_avatar:
                if isinstance(order.initiator.user_avatar, bytes):
                    avatar_data = f"data:image/jpeg;base64,{base64.b64encode(order.initiator.user_avatar).decode('utf-8')}"
                elif isinstance(order.initiator.user_avatar, str) and order.initiator.user_avatar.startswith("http"):
                    avatar_data = order.initiator.user_avatar  # 如果是 URL，则直接使用
                else:
                    avatar_data = current_app.config['DEFAULT_AVATAR_URL']  # 默认头像
            else:
                avatar_data = current_app.config['DEFAULT_AVATAR_URL']  # 默认头像
            orders.append({
                'id': order.order_id,
                'infoType': '人找车' if order.order_type == OrderType.PERSON_FIND_CAR.value else '车找人',
                'date': format_order_date(order.start_time),
                'startPoint': order.start_loc,
                'endPoint': order.dest_loc,
                'price': float(order.price),
                'username': user.realname or user.username,
                'passengerCount': order.travel_partner_num,
                'maxSeats': order.spare_seat_num,
                'carType': order.car_type,
                'orderCount': user.order_time,
                'userAvatar': avatar_data,
                'status': order.status,
                'startTime': order.start_time.isoformat()
            })


        logger.success(f"用户 {current_user_id} 获取全部订单成功，共 {len(orders)} 条")
        return ApiResponse.success(
            "获取订单列表成功",
            data=orders
        ).to_json_response(200)
    except ValueError as e:
        logger.warning(f"参数错误: {str(e)}")
        return ApiResponse.error("请求参数错误", code=400).to_json_response(200)
    except Exception as e:
        logger.error(f"获取订单列表失败: {str(e)}")
        return ApiResponse.error("服务器内部错误", code=500).to_json_response(200)

@order_bp.route('', methods=['POST'])
@jwt_required()
@log_requests()
def create_order():
    """创建新的拼车订单并初始化聊天会话"""
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    logger.info(f"用户 {current_user_id} 尝试创建订单")

    data = request.get_json()

    # --- 基本字段验证 ---
    required_fields = ['identity', 'startAddress', 'endAddress', 'departureTime', 'price', 'initiator_id']
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    if missing_fields:
        logger.warning(f"缺少必填字段: {missing_fields}")
        return ApiResponse.error(f"缺少必填字段: {', '.join(missing_fields)}", code=400).to_json_response(200)

    identity = data['identity']         # 订单发起者参与的身份
    initiator_id = data['initiator_id'] # 订单发起者ID

    # --- 身份特定字段验证 ---
    if identity == 'driver':
        if 'availableSeats' not in data or data['availableSeats'] is None:
            logger.warning("司机订单缺少availableSeats字段")
            return ApiResponse.error("司机发布订单必须填写余座数", code=400).to_json_response(200)
        order_car_type = data.get('carType')
    elif identity == 'passenger':
        if 'passengerCount' not in data or data['passengerCount'] is None:
            logger.warning("乘客订单缺少passengerCount字段")
            return ApiResponse.error("乘客发布订单必须填写同乘人数", code=400).to_json_response(200)
        order_car_type = None
    else:
        logger.warning(f"无效的身份类型: {identity}")
        return ApiResponse.error("无效的身份类型 (必须是driver或passenger)", code=400).to_json_response(200)

    # --- 数据处理和创建 ---
    try:
        # 转换时间字符串
        try:
            start_time_dt = datetime.strptime(data['departureTime'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            logger.warning("无效的时间格式")
            return ApiResponse.error("无效的出发时间格式，请使用 'YYYY-MM-DD HH:MM:SS'", code=400).to_json_response(200)

        # 转换价格
        try:
            price_decimal = Decimal(str(data['price']))
            if price_decimal < 0:
                logger.warning("价格不能为负数")
                return ApiResponse.error("价格不能为负数", code=400).to_json_response(200)
        except (ValueError, TypeError):
            logger.warning("无效的价格格式")
            return ApiResponse.error("无效的价格格式", code=400).to_json_response(200)

        # 创建 Order 对象
        new_order = Order(
            initiator_id=initiator_id,
            start_loc=data['startAddress'],
            dest_loc=data['endAddress'],
            start_time=start_time_dt,
            price=price_decimal,
            status=OrderStatus.PENDING.value, # 初始状态
            order_type=OrderType.CAR_FIND_PERSON.value if data['order_type'] == "车找人" else OrderType.PERSON_FIND_CAR.value,
            car_type=order_car_type,  # 使用上面确定的 car_type
            travel_partner_num=data.get('passengerCount') if identity == 'passenger' else None,
            spare_seat_num=data.get('availableSeats') if identity == 'driver' else None
        )
        db.session.add(new_order)
        db.session.flush()  # 先 flush 获取 new_order.order_id

        # --- 创建聊天会话 ---
        # 生成会话标题（示例："北京西站→首都机场 | 05-15 14:30"）
        conversation_title = (
            f"{data['startAddress']}→{data['endAddress']} | "
            f"{start_time_dt.strftime('%m-%d %H:%M')}"
        )

        new_conversation = Conversation(
            type=ConversationType.GROUP.value,
            title=conversation_title,
            order_id=new_order.order_id,
            created_at=datetime.utcnow()
        )
        db.session.add(new_conversation)
        db.session.flush()  # 获取new_conversation.id


        # 添加发起人到会话
        db.session.add(ConversationParticipant(
            user_id=current_user_id,
            conversation_id=new_conversation.id,
            joined_at=datetime.utcnow()
        ))

        # 创建 OrderParticipant 对象 (发起人自己)
        new_participant = OrderParticipant(
            participator_id=initiator_id,
            initiator_id=initiator_id,
            order_id=new_order.order_id,
            identity=identity
        )
        db.session.add(new_participant)

        db.session.commit()  # 提交事务

        logger.success(f"订单创建成功，ID: {new_order.order_id}，会话ID: {new_conversation.id}")
        return ApiResponse.success(
            "订单发布成功",
            data={
                "order_id": new_order.order_id,
                "conversation_id": new_conversation.id,
                "conversation_title": conversation_title
            }
        ).to_json_response(200)

    except Exception as e:
        db.session.rollback()
        logger.error(f"创建订单失败: {str(e)}")
        # 检查是否是外键约束错误 (例如 initiator_id 不存在于 user 表)
        if 'foreign key constraint' in str(e).lower():
            return ApiResponse.error("用户ID无效", code=400).to_json_response(200)
        return ApiResponse.error(f"创建订单失败: {str(e)}", code=500).to_json_response(200)

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
            end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
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
    ""r"获取用户最近的行程记录"""
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

@order_bp.route('/<int:order_id>/rate', methods=['POST'])
def rate_trip(order_id):
    """提交对特定行程/订单的评分"""
    try:
        # 获取请求体数据
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体不能为空"}), 400

        # 验证评分值
        rating_value = data.get('rating_value')
        if rating_value is None or not isinstance(rating_value, int) or not (0 <= rating_value <= 5):
            return jsonify({"error": "无效的评分值。必须是 0 到 5 之间的整数。"}), 400

        # 查询订单
        order = db.session.query(Order).filter_by(order_id=order_id).first()
        if not order:
            return jsonify({"error": "未找到该行程"}), 404

        # 验证订单状态是否允许评分
        if order.status != "to-review":  # 确保状态为 "待评价"
            return jsonify({"error": f"订单当前状态为 '{order.status}'，无法进行评分"}), 400

        # 更新订单评分和状态
        order.status = "completed"  # 更新状态为 "已完成"
        db.session.commit()

        print(f"订单 {order_id} 评分成功，评分为 {rating_value} 星。")
        return jsonify({"code": 200,"message": "评价提交成功！"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"评价行程 {order_id} 时出错: {e}")
        description = str(e)
        return jsonify({"error": "服务器内部错误", "description": description}), 500
    pass

@order_bp.route('/<int:order_id>', methods=['GET'])
@jwt_required()
@log_requests()
def get_trip_detail(order_id):
    """获取特定行程/订单的详细信息"""
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    logger.info(f"用户 {current_user_id} 请求获取订单 {order_id} 详情")

    try:
        # 查询订单
        order = db.session.query(Order).filter_by(order_id=order_id).first()
        if not order:
            logger.warning(f"订单不存在: {order_id}")
            return ApiResponse.error("未找到该行程", code=404).to_json_response(200)

        # 查询司机信息
        # 查询司机参与者信息
        driver_participant = OrderParticipant.query.filter_by(
            order_id=order_id,
            identity=ParticipantIdentity.DRIVER.value
        ).first()

        def _process_avatar(avatar_data):
            """处理头像数据"""
            if not avatar_data:
                return current_app.config['DEFAULT_AVATAR_URL']
            if isinstance(avatar_data, bytes):
                return f"data:image/jpeg;base64,{base64.b64encode(avatar_data).decode('utf-8')}"
            return avatar_data

        # 初始化司机信息
        driver_info = {
            "driverUserId": None,
            "userAvatar": '',
            "orderCount": 0,
        }
        if driver_participant:
            driver = db.session.query(User).filter_by(user_id=driver_participant.participator_id).first()
            if driver:
                driver_info.update({
                    "driverUserId": driver.user_id,
                    "userAvatar": _process_avatar(driver.user_avatar),
                    "orderCount": driver.order_time or 0,
                })

        # 构造返回数据
        response_data = {
            "id": order.order_id,
            "date": format_datetime(order.start_time),
            "startPoint": order.start_loc,
            "endPoint": order.dest_loc,
            "price": decimal_to_float(order.price) if order.price else 0.0,
            "carType": order.car_type or "未知车型",  # 使用 orders 表中的 car_type
            "orderCount": driver_info["orderCount"],
            "userAvatar": driver_info["userAvatar"],
            "state": order.status,
            "driverUserId": driver_info["driverUserId"],
        }

        logger.success(f"成功获取订单 {order_id} 详情")
        return ApiResponse.success(
            "获取行程信息成功",
            data=response_data
        ).to_json_response(200)
    except Exception as e:
        logger.error(f"获取订单详情失败: {str(e)}")
        return ApiResponse.error(
            f"获取行程信息失败: {str(e)}",
            code=500
        ).to_json_response(200)

@order_bp.route('/<int:order_id>/paid', methods=['POST'])
def mark_order_as_paid(order_id):
    """标记订单为已支付并更新状态为 completed"""
    logger = get_logger(__name__)
    try:
        # 查询订单
        order = Order.query.get(order_id)
        if not order:
            return jsonify({"code": 404, "error": "订单不存在"}), 404

        # 验证订单当前状态是否允许支付
        if order.status != 'to-pay':  # 假设支付前的状态为 'to-pay'
            return jsonify({"code": 400, "error": f"订单当前状态为 '{order.status}'，无法标记为已支付"}), 400

        # 更新订单状态为 completed
        order.status = 'to-review'
        db.session.commit()

        logger.info(f"订单 {order_id} 已标记为已支付")
        return jsonify({"code": 200, "message": "订单支付成功"}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"标记订单 {order_id} 为已支付时出错: {str(e)}")
        return jsonify({"code": 500, "error": "标记订单为已支付失败"}), 500

@order_bp.route('/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    """
    删除订单（仅限未开始状态）
    """
    logger = get_logger(__name__)
    try:
        # 获取订单
        order = Order.query.get(order_id)
        if not order:
            return jsonify({"code": 404, "message": "订单不存在"}), 404
            
        # 检查订单状态
        if order.status != 'not-started':
            return jsonify({
                "code": 403,
                "message": "只有未开始状态的订单可以删除"
            }), 403

        # 删除订单
        db.session.delete(order)
        db.session.commit()
        
        return jsonify({"code": 200, "message": "订单已删除"}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除订单失败: {str(e)}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500
    
@order_bp.route('/not-started', methods=['GET'])
def get_not_started_orders():
    """
    获取所有状态为not-started的订单列表
    """
    logger = get_logger(__name__)
    
    try:
        # 获取查询参数
        identity = request.args.get('identity', 'passenger')  # 默认乘客身份
        keyword = request.args.get('keyword', '').strip()

        # 参数验证
        if identity not in ['driver', 'passenger']:
            return jsonify({
                "code": 400,
                "error": "无效的身份类型，只能是driver或passenger"
            }), 400

        # 构建基础查询
        base_query = Order.query.filter(
            and_(
                Order.status == 'not-started',
                Order.order_type == identity
            )
        ).options(
            db.joinedload(Order.initiator)
        )

        # 添加关键词过滤
        if keyword:
            search_pattern = f"%{keyword}%"
            base_query = base_query.filter(
                or_(
                    Order.start_loc.ilike(search_pattern),
                    Order.dest_loc.ilike(search_pattern)
                )
            )

        # 执行查询并排序（按出发时间正序）
        orders = base_query.order_by(Order.start_time.asc()).all()

        # 构造响应数据
        orders_data = []
        for order in orders:
            # 处理用户头像
            avatar_url = current_app.config['DEFAULT_AVATAR_URL']
            if order.initiator.user_avatar:
                if isinstance(order.initiator.user_avatar, bytes):
                    avatar_url = f"data:image/jpeg;base64,{base64.b64encode(order.initiator.user_avatar).decode('utf-8')}"
                else:
                    avatar_url = order.initiator.user_avatar

            # 构造订单数据
            order_data = {
                "order_id": order.order_id,
                "initiator_id": order.initiator_id,
                "start_loc": order.start_loc,
                "dest_loc": order.dest_loc,
                "start_time": order.start_time.isoformat(),
                "price": float(order.price),
                "order_type": order.order_type,
                "car_type": order.car_type,
                "travel_partner_num": order.travel_partner_num,
                "spare_seat_num": order.spare_seat_num,
                "user": {
                    "user_id": order.initiator.user_id,
                    "username": order.initiator.username,
                    "user_avatar": avatar_url,
                    "order_count": len(order.initiator.initiated_orders)
                }
            }
            orders_data.append(order_data)

        return jsonify({
            "code": 200,
            "message": "success",
            "data": orders_data
        }), 200

    except Exception as e:
        logger.error(f"获取未开始订单失败: {str(e)}")
        return jsonify({
            "code": 500,
            "error": "服务器内部错误，获取订单失败"
        }), 500
    
@order_bp.route('/driver/accept', methods=['POST'])
@jwt_required()
@log_requests()
def accept_order():
    """司机接单接口"""
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    data = request.get_json()

    try:
        # 参数校验
        if not data or 'orderId' not in data:
            raise ValueError("缺少必要参数")
        
        order_id = data['orderId']
        vehicle_id = data['vehicleId']
        logger.info(f"用户 {current_user_id} 尝试用车辆 {vehicle_id} 接单 {order_id}")

        # 验证车辆归属（通过多对多关系验证）
        vehicle = Car.query.filter_by(car_id=vehicle_id).first()
        if not vehicle:
            logger.warning(f"车辆 {vehicle_id} 不存在")
            return ApiResponse.error("车辆不存在", code=404).to_json_response()
        
        # 检查当前用户是否是车主
        is_owner = vehicle.owners.filter_by(user_id=current_user_id).count() > 0
        if not is_owner:
            logger.warning(f"用户 {current_user_id} 不是车辆 {vehicle_id} 的车主")
            return ApiResponse.error("您不是该车辆的车主", code=403).to_json_response()

        # 获取订单
        order = Order.query.get(order_id)
        if not order:
            logger.warning(f"订单 {order_id} 不存在")
            return ApiResponse.error("订单不存在", code=404).to_json_response()
        
        # 校验订单状态
        if order.status != OrderStatus.NOT_STARTED.value:
            logger.warning(f"订单 {order_id} 状态 {order.status} 不可接单")
            return ApiResponse.error("当前订单状态不可接单").to_json_response()
        
        # 校验订单类型
        if order.order_type != OrderType.PERSON_FIND_CAR.value:
            logger.warning(f"订单 {order_id} 类型 {order.order_type} 不是人找车类型")
            return ApiResponse.error("只能接人找车类型的订单").to_json_response()
        
        # 检查是否已参与
        existing = OrderParticipant.query.filter_by(
            order_id=order_id,
            participator_id=current_user_id
        ).first()
        if existing:
            logger.warning(f"用户 {current_user_id} 已参与订单 {order_id}")
            return ApiResponse.error("您已参与此订单").to_json_response()
        
        # 添加参与者(司机)
        participant = OrderParticipant(
            participator_id=current_user_id,
            order_id=order_id,
            identity=ParticipantIdentity.DRIVER.value,
            initiator_id=order.initiator_id
        )
        db.session.add(participant)
        
        # 更新订单信息
        order.order_type = OrderType.CAR_FIND_PERSON.value
        order.status = OrderStatus.IN_PROGRESS.value
        order.car_type = f"{vehicle.car_type}"  # 记录车辆信息
        
        # 计算剩余座位数（考虑司机座位和原有同行人数）
        base_seats = vehicle.seat_num - 1
        if order.travel_partner_num:
            order.spare_seat_num = base_seats - order.travel_partner_num
        else:
            order.spare_seat_num = base_seats

        # 确保座位数不会为负
        order.spare_seat_num = max(0, order.spare_seat_num)

        # --- 查找会话并加入会话 ---
        conversation = Conversation.query.filter_by(order_id=order_id).first()
        if not ConversationParticipant.query.filter_by(
            conversation_id=conversation.id,
            user_id=current_user_id
        ).first():
            db.session.add(ConversationParticipant(
                user_id=current_user_id,
                conversation_id=conversation.id,
                joined_at=datetime.utcnow()
            ))
        

        db.session.commit()

        logger.success(f"用户 {current_user_id} 接单 {order_id} 成功，已加入会话 {conversation.id}")
        return ApiResponse.success("接单成功", data={
            "conversation_id": conversation.id
        }).to_json_response()
    
    except ValueError as e:
        logger.warning(f"参数错误: {str(e)}")
        return ApiResponse.error(str(e), code=400).to_json_response()
    except Exception as e:
        db.session.rollback()
        logger.error(f"接单失败: {str(e)}")
        db.session.rollback()
        return ApiResponse.error("接单失败", code=500).to_json_response()
    
@order_bp.route('/passenger/apply', methods=['POST'])
@jwt_required()
@log_requests()
def apply_order():
    """乘客申请接口(拼车/搭车)"""
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    data = request.get_json()

    try:
        # 参数校验
        if not data or 'orderId' not in data:
            raise ValueError("缺少必要参数")
        
        order_id = data['orderId']
        logger.info(f"用户 {current_user_id} 申请订单 {order_id}")

        # 获取订单
        order = Order.query.get(order_id)
        if not order:
            logger.warning(f"订单 {order_id} 不存在")
            return ApiResponse.error("订单不存在", code=404).to_json_response()
        
        # 校验订单状态
        if order.status not in [OrderStatus.NOT_STARTED.value, OrderStatus.IN_PROGRESS.value]:
            logger.warning(f"订单 {order_id} 状态 {order.status} 不可申请")
            return ApiResponse.error("当前订单状态不可申请").to_json_response()
        
        # 检查是否已参与
        existing = OrderParticipant.query.filter_by(
            order_id=order_id,
            participator_id=current_user_id
        ).first()
        if existing:
            logger.warning(f"用户 {current_user_id} 已参与订单 {order_id}")
            return ApiResponse.error("您已参与此订单").to_json_response()
        
        # 检查剩余座位(车找人订单)
        if order.order_type == OrderType.CAR_FIND_PERSON.value:
            if order.spare_seat_num <= 0:
                logger.warning(f"订单 {order_id} 座位已满")
                return ApiResponse.error("座位已满").to_json_response()
            
        # 添加参与者(乘客)
        participant = OrderParticipant(
            participator_id=current_user_id,
            order_id=order_id,
            identity=ParticipantIdentity.PASSENGER.value
        )
        db.session.add(participant)
        
        # 车找人订单: 更新剩余座位数
        if order.order_type == OrderType.CAR_FIND_PERSON.value:
            order.spare_seat_num -= 1
            
            # 如果座位已满，更新状态
            if order.spare_seat_num <= 0:
                order.status = OrderStatus.IN_PROGRESS.value
        # 人找车订单: 更新同行人数
        elif order.order_type == OrderType.PERSON_FIND_CAR.value:
            order.travel_partner_num += 1

        # 查找并加入会话
        conversation = Conversation.query.filter_by(order_id=order_id).first()
        if not ConversationParticipant.query.filter_by(
            conversation_id=conversation.id,
            user_id=current_user_id
        ).first():
            db.session.add(ConversationParticipant(
                user_id=current_user_id,
                conversation_id=conversation.id,
                joined_at=datetime.utcnow()
            ))

        db.session.commit()

        logger.success(f"用户 {current_user_id} 申请订单 {order_id} 成功，已加入会话 {conversation.id}")
        return ApiResponse.success("申请成功", data={
            "conversation_id": conversation.id
        }).to_json_response()
    
    except ValueError as e:
        logger.warning(f"参数错误: {str(e)}")
        return ApiResponse.error(str(e), code=400).to_json_response()
    except Exception as e:
        db.session.rollback()
        logger.error(f"申请失败: {str(e)}")
        db.session.rollback()
        return ApiResponse.error("申请失败", code=500).to_json_response()
    