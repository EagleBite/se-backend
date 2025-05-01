from ..extensions import db

class ConversationParticipant(db.Model):
    """会话参与者表"""
    __tablename__ = 'conversationParticipants'
    __table_args__ = {'comment': '会话参与者表'}

    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True, comment='用户ID')
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), primary_key=True, comment='会话ID')
    joined_at = db.Column(db.DateTime, default=db.func.now(), comment='加入时间')
    last_read_message_id = db.Column(db.Integer, nullable=True, comment='最后读取的消息 ID')

    # 关联关系
    user = db.relationship('User', back_populates='conversations')
    conversation = db.relationship('Conversation', back_populates='participants')

    def __repr__(self):
        return f"<ConversationParticipant user_id={self.user_id}, conversation_id={self.conversation_id}>"