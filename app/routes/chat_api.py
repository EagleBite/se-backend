"""与聊天功能有关的API"""
import base64
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, current_user, get_jwt_identity
from ..extensions import db, socketio
from ..models import User, Conversation, Message, Order
from ..models import ConversationParticipant as Participant
from ..models.Chat_messgae import MessageType
from ..utils.logger import get_logger, log_requests
from ..utils.Response import ApiResponse

chat_bp = Blueprint('chat', __name__)

def get_or_create_private_conversation(user1_id, user2_id):
    """查找或创建私聊会话"""
    conv = Conversation.query.filter(
        Conversation.type == 'private',
        Conversation.participants.any(user_id=user1_id),
        Conversation.participants.any(user_id=user2_id)
    ).first()

    if not conv:
        conv = Conversation(type='private')
        db.session.add(conv)
        db.session.flush()  # 获取conv.id

        db.session.add_all([
            Participant(user_id=user1_id, conversation_id=conv.id),
            Participant(user_id=user2_id, conversation_id=conv.id)
        ])
        db.session.commit()

    return conv

@chat_bp.route('/conversations', methods=['GET'])
@jwt_required()
@log_requests()
def get_conversations():
    """获取当前用户的所有会话列表（包含最后一条消息）"""
    logger = get_logger(__name__)

    current_user_id = get_jwt_identity()
    logger.info(f"获取用户 {current_user_id} 的会话列表")

    try:
        # 查询用户参加的所有会话Conversation
        participants = Participant.query.filter_by(
            user_id=current_user_id
        ).options(
            db.joinedload(Participant.conversation)
            .joinedload(Conversation.messages)
        ).all()

        conversations_data = []
        for participant in participants:
            conversation = participant.conversation

            # 获取最后一条消息
            last_message = Message.query.filter_by(
                conversation_id=conversation.id
            ).order_by(
                Message.created_at.desc()
            ).first()

            # 获取会话的其他参与者（排除自己）
            other_participants = Participant.query.filter(
                Participant.conversation_id == conversation.id,
                Participant.user_id != current_user_id
            ).options(
                db.joinedload(Participant.user)
            ).all()

            # 构建参与者信息
            participants_info = []
            for p in other_participants:
                participants_info.append({
                    'user_id': p.user.user_id,
                    'username': p.user.username,
                    'avatar': base64.b64encode(p.user.user_avatar).decode('utf-8') if p.user.user_avatar else None,
                    'realname': p.user.realname,
                    'last_read_message_id': p.last_read_message_id
                })
            
            # 构建会话数据
            conversation_data = {
                'conversation_id': conversation.id,
                'type': conversation.type,
                'created_at': conversation.created_at.isoformat() if conversation.created_at else None,
                'title': conversation.title if conversation.title else None,
                'avatar': base64.b64encode(conversation.avatar).decode('utf-8') if conversation.avatar else None,
                'unread_count': Message.query.filter(
                    Message.conversation_id == conversation.id,
                    Message.sender_id != current_user_id,
                    Message.id > participant.last_read_message_id
                ).count() if participant.last_read_message_id is not None else 0,
                'last_message': {
                    'message_id': last_message.id if last_message else None,
                    'content': last_message.content if last_message else None,
                    'type': last_message.message_type if last_message else None,
                    'sender_id': last_message.sender_id if last_message else None,
                    'created_at': last_message.created_at.isoformat() if last_message else None,
                } if last_message else None,
                'participants': participants_info
            }
            conversations_data.append(conversation_data)

        # 按最后消息时间降序排序
        conversations_data.sort(
            key=lambda x: (
                datetime.fromisoformat(x['last_message']['created_at']) 
                if x['last_message'] 
                else datetime.fromisoformat(x['created_at'])
            ),
            reverse=True
        )

        logger.success(f"成功获取用户会话列表数据: {current_user_id}")
        return ApiResponse.success(
            "获取会话列表成功",
            data=conversations_data
        ).to_json_response(200)

    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}", exc_info=True)
        return ApiResponse.error(
            "获取会话列表失败",
            code=500
        ).to_json_response(200)

@chat_bp.route('/conversations/<int:conversation_id>/messages', methods=['GET'])
@jwt_required()
@log_requests()
def get_messages(conversation_id):
    """获取指定会话的历史消息"""
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    logger.info(f"获取会话 {conversation_id} 的消息记录")

    try:
        # 验证用户是否参与该会话
        participant = Participant.query.filter_by(
            conversation_id=conversation_id,
            user_id=current_user_id
        ).first()

        if not participant:
            return ApiResponse.error(
                "您没有权限访问此会话",
                code=403
            ).to_json_response(403)
        
        # 获取查询参数
        before = request.args.get('before')
        before_time = datetime.fromisoformat(before) if before else None

        # 构建基础查询
        query = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(
            Message.created_at.asc()
        )

        # 应用时间筛选
        if before_time:
            query = query.filter(Message.created_at < before_time)

        # 执行查询
        messages = query.all()

        # 更新最后读取消息ID
        if messages:
            last_message = messages[0]  # 因为按时间倒序排列
            participant.last_read_message_id = last_message.id
            db.session.commit()

        # 格式化响应数据
        messages_data = []
        for msg in messages:
            message_data = {
                'message_id': msg.id,
                'content': msg.content,
                'type': msg.message_type,
                'created_at': msg.created_at.isoformat(),
                'sender': {
                    'user_id': msg.sender.user_id,
                    'username': msg.sender.username,
                    'avatar': base64.b64encode(msg.sender.user_avatar).decode('utf-8') 
                              if msg.sender.user_avatar else None,
                    'realname': msg.sender.realname
                }
            }

            # 如果是申请相关的消息，加入订单信息
            if msg.message_type in [
                MessageType.APPLY_JOIN.value, MessageType.APPLY_JOIN_ACCEPT.value, MessageType.APPLY_JOIN_REJECT.value,
                MessageType.APPLY_ORDER.value, MessageType.APPLY_ORDER_ACCEPT.value, MessageType.APPLY_ORDER_REJECT.value
                ]:
                # 查找相关订单
                order = Order.query.filter_by(
                    order_id=msg.order_id  # 假设消息中有order_id字段
                ).first()

                if order:
                    message_data['order_info'] = {
                        'order_id': order.order_id,
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

            messages_data.append(message_data)

        logger.success(f"成功获取会话 {conversation_id} 的消息记录")
        return ApiResponse.success(
            "获取消息成功",
            data=messages_data
        ).to_json_response(200)
    
    except ValueError as e:
        logger.error(f"时间参数格式错误: {str(e)}")
        return ApiResponse.error(
            "时间参数格式不正确，请使用ISO格式(如 2023-07-20T10:30:00)",
            code=400
        ).to_json_response(400)
    except Exception as e:
        logger.error(f"获取消息失败: {str(e)}", exc_info=True)
        return ApiResponse.error(
            "获取消息失败",
            code=500
        ).to_json_response(500)
    
# chat_api.py 新增路由
@chat_bp.route('/conversations/private', methods=['POST'])
@jwt_required()
@log_requests()
def create_private_conversation():
    """创建私聊会话"""
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()
    
    try:
        data = request.get_json()
        # 参数校验
        required_fields = ['target_user_id', 'order_id']
        if not all(field in data for field in required_fields):
            return ApiResponse.error("缺少必要参数: target_user_id 或 order_id").to_json_response(400)

        target_user_id = data['target_user_id']
        order_id = data['order_id']

        # 验证订单有效性
        order = Order.query.get(order_id)
        if not order or order.initiator_id != target_user_id:
            return ApiResponse.error("无效的订单ID").to_json_response(404)

        # 获取或创建会话
        conv = get_or_create_private_conversation(current_user_id, target_user_id)
        
        # 关联订单与会话
        conv.trip_id = order_id
        db.session.commit()

        # 获取对方用户信息
        target_user = User.query.get(target_user_id)
        participants_info = [{
            'user_id': target_user.user_id,
            'username': target_user.username,
            'avatar': base64.b64encode(target_user.user_avatar).decode('utf-8') 
                      if target_user.user_avatar else None,
            'realname': target_user.realname
        }]

        # 触发Socket事件
        socketio.emit('conversation_created', {
            'conversation_id': conv.id,
            'initiator_id': current_user_id,
            'target_user_id': target_user_id,
            'order_id': order_id,
            'created_at': datetime.utcnow().isoformat()
        }, room=str(target_user_id))

        logger.success(f"私聊会话创建成功: {conv.id}")
        return ApiResponse.success(
            "会话创建成功",
            data={
                'conversation_id': conv.id,
                'type': 'private',
                'avatar': base64.b64encode(target_user.user_avatar).decode('utf-8') 
                      if target_user.user_avatar else None,
                'title': target_user.realname or target_user.username,
                'created_at': conv.created_at.isoformat(),
                'participants': participants_info
            }
        ).to_json_response(200)

    except Exception as e:
        logger.error(f"创建私聊会话失败: {str(e)}", exc_info=True)
        return ApiResponse.error("服务器内部错误").to_json_response(500)

@chat_bp.route('/messages', methods=['POST'])
@jwt_required()
@log_requests()
def create_message():
    """发送初始消息"""
    logger = get_logger(__name__)
    current_user_id = get_jwt_identity()

    try:
        data = request.get_json()
        # 参数校验
        required_fields = ['conversation_id', 'order_id', 'content']
        if not all(field in data for field in required_fields):
            return ApiResponse.error("缺少必要参数").to_json_response(400)

        # 验证会话权限
        participant = Participant.query.filter_by(
            conversation_id=data['conversation_id'],
            user_id=current_user_id
        ).first()
        if not participant:
            return ApiResponse.error("无权限发送消息").to_json_response(403)

        # 创建消息记录
        new_message = Message(
            conversation_id=data['conversation_id'],
            sender_id=current_user_id,
            content=data['content'],
            message_type='invitation',
            is_read=False
        )
        db.session.add(new_message)
        db.session.commit()

        # 关联订单
        if data['order_id']:
            order = Order.query.get(data['order_id'])
            if order:
                new_message.special_type = 'order_invitation'
                new_message.order_id = order.order_id
                db.session.commit()

        # 构造响应数据
        message_data = {
            'mess_id': new_message.id,
            'content': new_message.content,
            'created_at': new_message.created_at.isoformat(),
            'sender': {
                'user_id': current_user_id,
                'username': current_user.username,
                'avatar': base64.b64encode(current_user.user_avatar).decode('utf-8') 
                          if current_user.user_avatar else None
            },
            'order_id': data['order_id']
        }

        # 触发Socket事件
        socketio.emit('message_sent', {
            'conversation_id': data['conversation_id'],
            **message_data
        }, room=str(data['conversation_id']))

        logger.success(f"初始消息发送成功: {new_message.id}")
        return ApiResponse.success(
            "消息发送成功",
            data=message_data
        ).to_json_response(200)

    except Exception as e:
        logger.error(f"消息发送失败: {str(e)}", exc_info=True)
        return ApiResponse.error("消息发送失败").to_json_response(500)
