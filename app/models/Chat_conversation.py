from enum import Enum
from ..extensions import db
from .Chat_conversation_participant import ConversationParticipant
from .Chat_messgae import Message

class ConversationType(Enum):
    """会话类型枚举"""
    PRIVATE = 'private'
    GROUP = 'group'

    @classmethod
    def values(cls):
        return [member.value for member in cls]

class Conversation(db.Model):
    """
    聊天会话
    +------------+------------------+------+-----+---------+------------------+
    | Field      | Type             | Null | Key | Default | Comment          |
    +------------+------------------+------+-----+---------+------------------+
    | id         | Integer          | NO   | PRI | NULL    | 会话ID           |
    | type       | Enum             | NO   |     | NULL    | 会话类型          |
    | title      | String(100)      | YES  |     | NULL    | 会话标题          |
    | avatar     | String(255)      | YES  |     | NULL    | 会话头像URL       |
    | created_at | DateTime         | YES  |     | now()   | 创建时间          |
    +------------+------------------+------+-----+---------+------------------+
    """
    __tablename__ = 'conversations'
    __table_args__ = {'comment': '聊天会话表'}

    id = db.Column(db.Integer, primary_key=True, comment='会话ID')
    type = db.Column(db.Enum(*ConversationType.values(), name='conversation_type_enum'), nullable=False, comment='会话类型')
    title = db.Column(db.String(100), nullable=True, comment='会话标题')
    avatar = db.Column(db.String(255), nullable=True, comment='会话头像URL')
    created_at = db.Column(db.DateTime, default=db.func.now(), comment='创建时间')

    # 关联关系
    messages = db.relationship('Message', back_populates='conversation', cascade='all, delete-orphan')
    participants = db.relationship('ConversationParticipant', back_populates='conversation', cascade='all, delete-orphan')

    def get_display_title(self, current_user_id):
        """获取适合当前用户显示的会话标题"""

        # 1. 群聊: 使用自定义标题或者默认群聊标题
        if self.type == ConversationType.GROUP.value:
            return self.title or f"群聊({len(self.participants)}人)"
        
        # 2. 私聊: 始终显示对方用户名(不存存储)
        other_user = next(
            (p.user for p in self.participants if p.user_id != current_user_id),
            None
        )
        return f"与{other_user.username}的对话" if other_user else "私聊会话"
    
    @classmethod
    def get_user_conversations(cls, current_user_id):
        """获取指定用户的所有会话列表"""

        from sqlalchemy import or_

        # 单次数据库访问获取所有必要的数据
        conversations = cls.query.join(
            ConversationParticipant,
            cls.id == ConversationParticipant.conversation_id
        ).filter(
            ConversationParticipant.user_id == current_user_id
        ).options(
            db.joinedload(cls.participants).joinedload(ConversationParticipant.user),
            db.joinedload(cls.messages).order_by(Message.created_at.desc()).limit(1)
        ).all()

        result = []
        for conv in conversations:
            # 获取最后一条消息
            last_msg = conv.messages[0] if conv.messages else None
            
            # 获取当前用户的未读计数
            participant = next(
                (p for p in conv.participants if p.user_id == current_user_id), 
                None
            )

            # TODO: 消息内容需要根据类型修改一下
            result.append({
                "conversation_id": conv.id,
                "type": conv.type,
                "display_title": conv.get_display_title(current_user_id),
                "avatar": conv.avatar or conv.default_avatar,
                "unread_count": participant.unread_count if participant else 0,
                "last_message": {
                    "content": last_msg.content[:50] + "..." if last_msg else None,
                    "sender_name": last_msg.sender.username if last_msg else None,
                    "timestamp": last_msg.created_at.isoformat() if last_msg else None,
                    "message_type": last_msg.message_type if last_msg else None
                } if last_msg else None
            })
    
        # 按最后消息时间降序排序
        result.sort(
            key=lambda x: (
                x["last_message"]["timestamp"] 
                if x["last_message"] 
                else "1970-01-01"
            ),
            reverse=True
        )

        return result



