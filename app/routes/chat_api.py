"""与聊天功能有关的API"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, current_user, get_jwt_identity
from ..extensions import db, socketio
from ..models import User, Conversation, Message, Order
from ..models import ConversationParticipant as Participant
from ..utils.logger import get_logger

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
def get_conversations():
    """获取当前用户的所有会话列表（包含最后一条消息）"""
    logger = get_logger(__name__)

    current_user_id = get_jwt_identity()
    logger.info(f"获取用户 {current_user_id} 的会话列表")
    
    return jsonify({
        'code': 200,
        'message': '获取会话列表成功',
        'data': []
    }), 200

    return jsonify([{
        'id': conv.id,
        'type': conv.type,
        'trip_id': conv.trip_id,
        'last_message': last_message,
        'last_message_time': last_message_time.isoformat() if last_message_time else None,
        'participants': [p.user_id for p in conv.participants if p.user_id != current_user.id]
    } for conv, last_message, last_message_time in conversations])

@chat_bp.route('/messages/<int:conversation_id>', methods=['GET'])
def get_messages(conversation_id):
    """获取指定会话的历史消息（分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    messages = Message.query.filter_by(conversation_id=conversation_id)\
                           .order_by(Message.created_at.desc())\
                           .paginate(page=page, per_page=per_page)
    
    return jsonify({
        'items': [{
            'id': msg.id,
            'sender_id': msg.sender_id,
            'text': msg.text,
            'created_at': msg.created_at.isoformat(),
            'is_read': msg.is_read
        } for msg in messages.items],
        'total': messages.total,
        'pages': messages.pages
    })
