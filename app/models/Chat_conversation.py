from ..extensions import db

class Conversation(db.Model):
    """聊天会话"""
    __tablename__ = 'conversations'
    __table_args__ = {'comment': '聊天会话表'}

    id = db.Column(db.Integer, primary_key=True, comment='会话ID')
    type = db.Column(db.Enum('private', 'group', name='conversation_type_enum'), nullable=False, comment='会话类型')
    created_at = db.Column(db.DateTime, default=db.func.now(), comment='创建时间')

    # 关联关系
    messages = db.relationship('Message', back_populates='conversation', cascade='all, delete-orphan')
    participants = db.relationship('ConversationParticipant', back_populates='conversation', cascade='all, delete-orphan')

