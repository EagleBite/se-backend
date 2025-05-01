"""与socketio相关的路由"""
from datetime import datetime
from ..extensions import socketio
from ..utils.logger import get_logger
from ..extensions import db
from ..models import User, Message, Conversation, ConversationParticipant
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

            logger.debug(f"开始认证处理 [sid: {sid}]")
            logger.debug(f"请求头: {dict(request.headers)}")
            logger.debug(f"查询参数: {request.args}")
            logger.debug(f"Socket.IO auth: {getattr(request, 'auth', None)}")

            # 方式1: 从请求头获取
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]
                logger.debug(f"从请求头获取到Token [sid: {sid}]")

            # 方式2: 从查询参数获取
            if not token and request.args.get('token'):
                token = request.args.get('token')
                logger.debug(f"从查询参数获取到Token [sid: {sid}]")

            # 方式3: 从Socket.IO握手时的auth获取
            if not token and hasattr(request, 'auth') and request.auth:
                if isinstance(request.auth, dict) and 'token' in request.auth:
                    token = request.auth['token']
                    logger.debug(f"从Socket.IO auth获取到Token [sid: {sid}]")
                elif isinstance(request.auth, str):
                    token = request.auth
                    logger.debug(f"从Socket.IO auth(字符串)获取到Token [sid: {sid}]")

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

            logger.info(f"用户认证成功 [user_id: {decoded['sub']}, sid: {sid}]")
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
    
    logger.info(f"用户 {g.socketio_user['id']} 连接成功, socket_id: {request.sid}")

    user_id = g.socketio_user['id']

    online_users[user_id] = request.sid  # 将用户ID和SID存储在active_users字典中

@socketio.on('disconnect')
def handle_disconnect():
    """处理断开连接事件"""
    logger = get_logger(__name__)

    user_id = next((k for k,v in online_users.items() if v == request.sid), None)
    if user_id:
        online_users.pop(user_id, None)
        logger.info(f"用户 {user_id} 下线")

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
        emit('new_message', message_data, room=room)
        logger.info(f"已向房间 {room} 广播消息")
    
    except Exception as e:
        logger.error(f"处理消息时发生错误: {str(e)}")
        db.session.rollback()
        emit('message_error', {'error': '发送消息失败'})

    
# ---- 群组管理 ----
@socketio.on('create_group')
@socketio_jwt_required
def handle_create_group(data):
    """创建群组"""
    logger = get_logger(__name__)

    user_id = g.current_user_id
    group_name = data['name']
    member_ids = data.get('members', [])

    # 确保创建者在成员中
    if user_id not in member_ids:
        member_ids.append(user_id)

    # 创建群组
    group = Group(name=group_name)
    members = User.query.filter(User.id.in_(member_ids)).all()
    group.members.extend(members)
    
    db.session.add(group)
    db.session.commit()
    
    # 通知所有成员
    emit('group_created', {
        'group_id': group.id,
        'name': group.name,
        'members': [m.id for m in members]
    }, room=f"group_{group.id}")


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