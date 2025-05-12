from ..extensions import db
from .Chat_messgae import Message

class ConversationParticipant(db.Model):
    """
    会话参与者表
    +------------------------+-------------+------+-----+---------+-----------------------+
    | Field                  | Type        | Null | Key | Default | Comment               |
    +------------------------+-------------+------+-----+---------+-----------------------+
    | user_id                | Integer     | NO   | PRI | NULL    | 用户ID                |
    | conversation_id        | Integer     | NO   | PRI | NULL    | 会话ID                |
    | joined_at              | DateTime    | YES  |     | now()   | 加入时间              |
    | last_read_message_id   | Integer     | YES  |     | NULL    | 最后读取的消息ID       |
    | unread_count           | Integer     | NO   |     | 0       | 未读消息数量          |
    +------------------------+-------------+------+-----+---------+-----------------------+
    """
    __tablename__ = 'conversation_participants'
    __table_args__ = {'comment': '会话参与者表'}

    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True, comment='用户ID')
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), primary_key=True, comment='会话ID')
    joined_at = db.Column(db.DateTime, default=db.func.now(), comment='加入时间')
    last_read_message_id = db.Column(db.Integer, db.ForeignKey('messages.id', ondelete='SET NULL'), nullable=True, comment='最后读取的消息 ID')
    unread_count = db.Column(db.Integer, default=0, nullable=False, comment='未读消息数量')

    # 关联关系
    user = db.relationship('User', back_populates='conversations')
    conversation = db.relationship('Conversation', back_populates='participants')
    last_read_message = db.relationship('Message')

    def update_unread_count(self):
        """更新未读消息数量"""
        if self.last_read_message_id:
            self.unread_count = Message.query.filter(
                Message.conversation_id == self.conversation_id,
                Message.id > self.last_read_message_id
            ).count()
        else:
            self.unread_count = Message.query.filter_by(
                conversation_id = self.conversation_id
            ).count()
        
        db.session.commit()

    def mark_as_read(self, message_id):
        """标记消息为已读并更新未读计数"""
        self.last_read_message_id = message_id
        self.unread_count = 0
        db.session.commit()

    def __repr__(self):
        return (f"<ConversationParticipant user_id={self.user_id}, "
                f"conversation_id={self.conversation_id}, "
                f"unread_count={self.unread_count}>")