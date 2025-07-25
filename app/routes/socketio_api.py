"""与socketio相关的路由"""
from datetime import datetime
from ..extensions import socketio
from ..utils.logger import get_logger
from ..extensions import db
from ..models import User, Message, Conversation, ConversationParticipant, Order
from ..models.Chat_messgae import MessageType
from flask import request, g
from functools import wraps
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from flask_jwt_extended import decode_token
from flask_socketio import join_room, leave_room, emit
from flask_socketio import disconnect

"""
要实现基于Socket.IO的在线聊天功能，需要在连接建立后处理消息收发、房间管理和用户状态维护。
"""

def socketio_jwt_required(fn):
    """
    装饰器, 用于在SocketIO事件处理函数中验证JWT_token
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        logger = get_logger(__name__)

        try:

            token = None
            sid = request.sid  # 当前Socket.IO会话ID

            # 方式1: 从请求头获取
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]

            # 方式2: 从查询参数获取
            if not token and request.args.get('token'):
                token = request.args.get('token')

            # 方式3: 从Socket.IO握手时的auth获取
            if not token and hasattr(request, 'auth') and request.auth:
                if isinstance(request.auth, dict) and 'token' in request.auth:
                    token = request.auth['token']
                elif isinstance(request.auth, str):
                    token = request.auth

            if not token:
                logger.warning(f"未找到认证Token [sid: {sid}]")
                disconnect()
                return {'code': 401, 'message': 'Authentication token is missing'}
            
            # Token解码和验证
            decoded = decode_token(token)

            # 将用户信息临时存储到Flask的g对象
            g.socketio_user = {
                'id': decoded['sub'],
                'claims': decoded,
                'sid': sid
            }

            return fn(*args, **kwargs)
        
        except ExpiredSignatureError:
            logger.error(f"认证失败: Token已过期 [sid: {sid}]")
            disconnect()
            return {'code': 401, 'message': 'Token has expired'}
        except InvalidTokenError as e:
            logger.error(f"认证失败: Token无效 [sid: {sid}] {str(e)}")
            disconnect()
            return {'code': 401, 'message': 'Invalid token'}
        except Exception as e:
            logger.error(f"认证过程中发生意外错误 [sid: {sid}, error: {str(e)}]")
            disconnect()
            return {'code': 500, 'message': 'Internal authentication error'}
        
    return wrapper

# ---- 连接管理 ----
online_users = {}  # {user_id: socket_id}

@socketio.on('connect')
@socketio_jwt_required
def handle_connect(auth=None):
    """处理连接事件"""
    logger = get_logger(__name__)
    
    logger.success(f"用户 {g.socketio_user['id']} 连接成功, socket_id: {request.sid}")

    user_id = g.socketio_user['id']

    online_users[user_id] = request.sid  # 将用户ID和SID存储在active_users字典中

@socketio.on('disconnect')
def handle_disconnect():
    """处理断开连接事件"""
    logger = get_logger(__name__)

    user_id = next((k for k,v in online_users.items() if v == request.sid), None)
    if user_id:
        online_users.pop(user_id, None)
        logger.success(f"用户 {user_id} 下线")

@socketio.on('join_conversation')
@socketio_jwt_required
def handle_join_conversation(data):
    """加入会话"""
    logger = get_logger(__name__)

    conversation_id = data['conversationId']
    user_id = g.socketio_user['id']

    # 验证用户是否在该会话中
    participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation_id,
        user_id=user_id
    ).first()

    if not participant:
        logger.warning(f"用户 {user_id} 尝试加入未参与的会话 {conversation_id}")
        return {'code': 403, 'message': 'You are not a participant of this conversation'}

    # 加入房间
    room = f'conversation_{conversation_id}'
    join_room(room)
    logger.info(f"用户 {user_id} 加入房间 {room}")

@socketio.on('leave_conversation')
@socketio_jwt_required
def handle_leave_conversation(data):
    """离开会话"""
    logger = get_logger(__name__)

    conversation_id = data['conversationId']
    user_id = g.socketio_user['id']

    # 验证用户是否在该会话中（可选，根据业务需求）
    participant = ConversationParticipant.query.filter_by(
        conversation_id=conversation_id,
        user_id=user_id
    ).first()

    if not participant:
        logger.warning(f"用户 {user_id} 尝试离开未参与的会话 {conversation_id}")
        return {'code': 403, 'message': 'You are not a participant of this conversation'}

    # 离开房间
    room = f'conversation_{conversation_id}'
    leave_room(room)
    logger.info(f"用户 {user_id} 离开房间 {room}")

@socketio.on('send_message')
@socketio_jwt_required
def handle_send_message(data):
    """处理发送消息"""
    logger = get_logger(__name__)

    try:
        # 获取消息内容
        sender_id = g.socketio_user['id']
        conversation_id = data['conversationId']
        content = data['content']

        # 1. 存储到数据库
        new_message = Message(
            sender_id=sender_id,
            conversation_id=conversation_id,
            content=content,
            message_type=data.get('messageType', 'text'),  # 默认消息类型为文本
            created_at=datetime.now()
        )
        db.session.add(new_message)
        db.session.commit()

        logger.info(f"消息已存储，ID: {new_message.id}")

        # 2. 构建返回给前端的数据
        message_data = {
            'id': new_message.id,
            'conversationId': conversation_id,
            'sender': {
                'id': sender_id,
                'username': g.socketio_user.get('username'),
                'avatar': g.socketio_user.get('avatar')
            },
            'content': content,
            'createdAt': new_message.created_at.isoformat(),
            'type': 'text'
        }

        # 3. 向该会话的所有成员广播消息
        room = f'conversation_{conversation_id}'

        # 获取房间内的客户端数量
        clients_in_room = len(socketio.server.manager.rooms.get(room, {}))
        logger.info(f"准备向房间 {room} 广播消息，当前房间内用户数: {clients_in_room}")

        emit('new_message', message_data, room=room)
        logger.info(f"已向房间 {room} 广播消息")
    
    except Exception as e:
        logger.error(f"处理消息时发生错误: {str(e)}")
        db.session.rollback()
        emit('message_error', {'error': '发送消息失败'})

@socketio.on('send_invitation')
@socketio_jwt_required
def handle_send_invitation(data):
    """发送订单邀请消息到指定会话"""
    logger = get_logger(__name__)
    sender_id = g.socketio_user['id']

    try:
        logger.info(data)
        # 参数校验
        if not data or 'conversationId' not in data or 'orderId' not in data:
            raise ValueError("缺少必要参数: conversationId 或 orderId")
        
        conversation_id = data['conversationId']
        order_id = data['orderId']
        
        logger.info(f"用户 {sender_id} 在会话 {conversation_id} 发送订单 {order_id} 邀请")

        # 验证会话是否存在
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            logger.warning(f"会话 {conversation_id} 不存在")
            emit('invitation_error', {'error': '会话不存在'})
            return

        # 验证订单是否存在
        order = Order.query.get(order_id)
        if not order:
            logger.warning(f"订单 {order_id} 不存在")
            emit('invitation_error', {'error': '订单不存在'})
            return
        
        # 创建邀请消息
        sender = User.query.get(sender_id)
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=f"{sender.username} 邀请加入订单",
            message_type=MessageType.INVITATION.value,
            created_at=datetime.utcnow(),
            order_id=order_id
        )
        db.session.add(message)
        db.session.commit()

        # 构建返回数据
        message_data = {
            'id': message.id,
            'conversationId': conversation_id,
            'sender': {
                'id': sender_id,
                'username': sender.username,
                'avatar': sender.user_avatar
            },
            'content': message.content,
            'createdAt': message.created_at.isoformat(),
            'type': MessageType.INVITATION.value,
            'orderId': order_id,
            'orderInfo': {  # 一些订单基本信息
                'initiator_id': order.initiator_id,
                'start_loc': order.start_loc,
                'dest_loc': order.dest_loc,
                'start_time': order.start_time.isoformat(),
                'price': str(order.price),
                'status': order.status,
                'order_type': order.order_type,
                'car_type': order.car_type,
                'travel_partner_num': order.travel_partner_num,
                'spare_seat_num': order.spare_seat_num
            }
        }

        # 广播消息到会话房间
        room = f'conversation_{conversation_id}'
        emit('new_message', message_data, room=room)
        logger.info(f"邀请消息已发送到房间 {room}")

    except ValueError as e:
        logger.warning(f"参数错误: {str(e)}")
        emit('invitation_error', {'error': str(e)})
    except Exception as e:
        db.session.rollback()
        logger.error(f"发送邀请失败: {str(e)}")
        emit('invitation_error', {'error': '发送邀请失败'})

@socketio.on('test_event') 
@socketio_jwt_required
def handle_test_event(data):
    """测试事件"""
    logger = get_logger(__name__)
    user_id = g.socketio_user['id']
    logger.info(f"用户 {user_id} 触发测试事件: {data}")

    # 返回响应
    emit('test_response', {
        'status': 'success',
        'message': f"收到你的消息: {data['content']}",
        'timestamp': datetime.now().isoformat()
    })