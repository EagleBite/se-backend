"""与socketio相关的路由"""
from datetime import datetime
from ..extensions import socketio
from ..utils.logger import get_logger
from ..extensions import db
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

# ---- 私聊功能 ----
@socketio.on('private_message')
@socketio_jwt_required
def handle_private_message(data):
    """处理私聊消息"""
    logger = get_logger(__name__)

    logger.info(f"用户 {g.socketio_user_id} 向 {recipient_id} 发送私聊消息: {message}")

    sender_id = g.current_user_id
    recipient_id = data['to_user_id']
    content = data['content']

    # 存储消息到数据库
    message = Message(
        sender_id=sender_id,
        recipient_id=recipient_id,
        content=content,
        is_group=False
    )
    db.session.add(message)
    db.session.commit()

    # 构造消息体
    msg_payload = {
        'message_id': message.id,
        'sender_id': sender_id,
        'recipient_id': recipient_id,
        'content': content,
        'timestamp': message.created_at.isoformat(),
        'is_group': False
    }

    # 发送给接收者（如果在线）
    if recipient_id in online_users:
        emit('new_message', msg_payload, room=f"user_{recipient_id}")

    # 同时发给发送者（实现消息同步）
    emit('new_message', msg_payload, room=request.sid)

# ---- 群聊功能 ----
@socketio.on('group_message')
@socketio_jwt_required
def handle_group_message(data):
    """处理群聊消息"""
    logger = get_logger(__name__)

    sender_id = g.current_user_id
    group_id = data['group_id']
    content = data['content']

    group_id = data['group_id']
    sender_id = g.socketio_user_id
    content = data['content']

    # 验证用户是否在群组中
    group = Group.query.filter(
        Group.id == group_id,
        Group.members.any(id=sender_id)
    ).first()
    if not group:
        return emit('error', {'message': '不在该群组中'})

    # 存储消息到数据库
    message = Message(
        sender_id=sender_id,
        group_id=group_id,
        content=content,
        is_group=True
    )
    db.session.add(message)
    db.session.commit()

    # 构造消息体
    msg_payload = {
        'message_id': message.id,
        'sender_id': sender_id,
        'group_id': group_id,
        'content': content,
        'timestamp': message.created_at.isoformat(),
        'is_group': True
    }

    # 广播到群组
    emit('new_message', msg_payload, room=f"group_{group_id}")

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