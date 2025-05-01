from ..extensions import db

class Message(db.Model):
    """消息表"""
    __tablename__ = 'messages'
    __table_args__ = {'comment': '消息表'}

    id = db.Column(db.Integer, primary_key=True, comment='消息ID')
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, comment='会话ID')
    sender_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False, comment='发送者ID')
    content = db.Column(db.Text, nullable=False, comment='消息内容')
    message_type = db.Column(db.Enum('text', 'image', 'file', 'audio', 'invitation', name='message_type_enum'), 
                             default='text', nullable=False, comment='消息类型')
    is_read = db.Column(db.Boolean, default=False, comment='是否已读')
    created_at = db.Column(db.DateTime, default=db.func.now(), comment='创建时间')

    # 关联关系
    conversation = db.relationship('Conversation', back_populates='messages') # 所属会话
    sender = db.relationship('User', back_populates='sent_messages') # 发送者

