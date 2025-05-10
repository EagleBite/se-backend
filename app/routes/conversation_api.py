from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import User
from ..models.conversation import Conversation, Message, conversation_members, UserConversationStatus
from ..utils.logger import get_logger
import base64

conversation_bp = Blueprint('conversation_api', __name__)

@conversation_bp.route('/list', methods=['GET'])
def get_conversation_list():
    """
    获取当前用户的所有会话（私聊 + 群聊），统一返回格式，适配前端
    """
    logger = get_logger(__name__)
    user_id = request.args.get('user_id', type=int)

    try:
        # 获取用户参与的所有会话 ID
        rows = db.session.execute(
            conversation_members.select().with_only_columns(conversation_members.c.conversation_id).where(
                conversation_members.c.user_id == user_id
            )
        ).fetchall()

        conversation_ids = [row.conversation_id for row in rows]
        conversations = Conversation.query.filter(
            Conversation.conversation_id.in_(conversation_ids)
        ).all()

        result = []
        for conv in conversations:
            # 最后一条消息
            last_msg = conv.last_message
            last_msg_text = last_msg.content if last_msg else ''
            timestamp = last_msg.created_at.isoformat() if last_msg else None

            # 未读消息数
            status = UserConversationStatus.query.filter_by(
                user_id=user_id, conversation_id=conv.conversation_id
            ).first()
            unread_count = status.unread_count if status else 0

            # 获取成员（排除自己）
            member_rows = db.session.execute(
                conversation_members.select().with_only_columns(conversation_members.c.user_id).where(
                    conversation_members.c.conversation_id == conv.conversation_id
                )
            ).fetchall()
            member_user_ids = [r.user_id for r in member_rows]
            member_users = User.query.filter(User.user_id.in_(member_user_ids)).all()
            user_dict = {user.user_id: user for user in member_users}
            member_list = []
            avatar_list = []
            for r in member_rows:
                user = user_dict.get(r.user_id)
                if not user:
                    continue
                if isinstance(user.user_avatar, bytes):
                    avatar = f"data:image/jpeg;base64,{base64.b64encode(user.user_avatar).decode('utf-8')}"
                elif isinstance(user.user_avatar, str):
                    avatar = user.user_avatar
                else:
                    avatar = current_app.config.get('DEFAULT_AVATAR_URL', '')

                member_list.append({
                    "user_id": user.user_id,
                    "username": user.username,
                    "avatar": avatar
                })

                # 仅前4位头像用于群聊头像
                if len(avatar_list) < 4:
                    avatar_list.append(avatar)

            # 统一结构返回
            if conv.is_group:
                result.append({
                    "conversation_id": conv.conversation_id,
                    "conversation_type": "group",
                    "conversation_avater": avatar_list,  # 你可以添加群聊头像字段
                    "conversation_name": conv.conversation_name or "群聊",
                    "last_message": {
                        "lastMessage": last_msg_text
                    },
                    "time_display": timestamp,
                    "unread_count": unread_count,
                    "members": member_list
                })
            else:
                other = member_list[0] if member_list else {}
                result.append({
                    "conversation_id": conv.conversation_id,
                    "other_user":True,
                    "conversation_type": "private",
                    "conversation_avater": other.get("avatar", current_app.config.get('DEFAULT_AVATAR_URL', '')),
                    "username": other.get("username", "未知用户"),
                    "last_message": {
                        "lastMessage": last_msg_text
                    },
                    "time_display": timestamp,
                    "unread_count": unread_count,
                    "members": []  # 私聊不返回成员列表
                })

        return jsonify({"code": 200, "data": result}), 200

    except Exception as e:
        logger.error(f"获取聊天列表失败: {e}")
        return jsonify({"code": 500, "message": "服务器错误"}), 500

