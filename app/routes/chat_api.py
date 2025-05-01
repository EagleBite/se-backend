"""与聊天功能有关的API"""
import base64
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, current_user, get_jwt_identity
from ..extensions import db, socketio
from ..models import User, Conversation, Message, Order
from ..models import ConversationParticipant as Participant
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
                # 'title': conversation.title if conversation.title else None,
                # 'avatar': base64.b64encode(conversation.avatar).decode('utf-8') if conversation.avatar else None,
                'unread_count': Message.query.filter(
                    Message.conversation_id == conversation.id,
                    Message.id > participant.last_read_message_id,
                    Message.sender_id != current_user_id
                ).count(),
                'last_message': {
                    'message_id': last_message.id if last_message else None,
                    'content': last_message.content if last_message else None,
                    'type': last_message.message_type if last_message else None,
                    'sender_id': last_message.sender_id if last_message else None,
                    'created_at': last_message.created_at.isoformat() if last_message else None,
                    'is_read': last_message.is_read if last_message else None
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
    """获取指定会话的历史消息（分页）"""
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
                error_code=403
            ).to_json_response(403)
        
        # 获取查询参数
        limit = request.args.get('limit', default=50, type=int)
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
        messages = query.limit(limit).all()

        # 更新最后读取消息ID
        if messages:
            last_message = messages[0]  # 因为按时间倒序排列
            participant.last_read_message_id = last_message.id
            db.session.commit()

        # 格式化响应数据
        messages_data = []
        for msg in messages:
            messages_data.append({
                'message_id': msg.id,
                'content': msg.content,
                'type': msg.message_type,
                'is_read': msg.is_read,
                'created_at': msg.created_at.isoformat(),
                'sender': {
                    'user_id': msg.sender.user_id,
                    'username': msg.sender.username,
                    'avatar': base64.b64encode(msg.sender.user_avatar).decode('utf-8') 
                              if msg.sender.user_avatar else None,
                    'realname': msg.sender.realname
                }
            })

        logger.success(f"成功获取会话 {conversation_id} 的消息记录")
        return ApiResponse.success(
            "获取消息成功",
            data=messages_data
        ).to_json_response(200)
    
    except ValueError as e:
        logger.error(f"时间参数格式错误: {str(e)}")
        return ApiResponse.error(
            "时间参数格式不正确，请使用ISO格式(如 2023-07-20T10:30:00)",
            error_code=400
        ).to_json_response(400)
    except Exception as e:
        logger.error(f"获取消息失败: {str(e)}", exc_info=True)
        return ApiResponse.error(
            "获取消息失败",
            error_code=500
        ).to_json_response(500)
