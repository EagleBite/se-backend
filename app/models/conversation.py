# from datetime import datetime
# from ..extensions import db

# # 聊天会话关联表（多对多）
# conversation_members = db.Table(
#     'conversation_members',
#     db.Column('user_in_con_id', db.Integer, primary_key=True, autoincrement=True),
#     db.Column('conversation_id', db.Integer, db.ForeignKey('conversations.conversation_id', ondelete='CASCADE'), nullable=False),
#     db.Column('user_id', db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False),
#     db.Column('join_time', db.DateTime, default=datetime.utcnow)
# )

# class Conversation(db.Model):
#     """聊天会话模型"""
#     __tablename__ = 'conversations'
    
#     conversation_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='会话ID')
#     conversation_type = db.Column(db.Enum('private', 'group', name='conversation_type'), nullable=False)
#     conversation_avatar = db.Column(db.String(255), nullable=False)
#     conversation_name = db.Column(db.String(255), comment='群聊名称')
#     last_message_id = db.Column(db.Integer, db.ForeignKey('messages.mess_id', ondelete='SET NULL'))
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
#     # 关系定义
#     messages = db.relationship('Message', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')
#     members = db.relationship(
#         'User',
#         secondary=conversation_members,
#         backref=db.backref('conversations', lazy='dynamic'),
#         passive_deletes=True
#     )
#     statuses = db.relationship('UserConversationStatus', backref='conversation', cascade='all, delete-orphan')

#     @property
#     def is_group(self):
#         return self.conversation_type == 'group'

# class Message(db.Model):
#     """消息模型"""
#     __tablename__ = 'messages'
    
#     mess_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='消息ID')
#     conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.conversation_id', ondelete='CASCADE'), nullable=False)
#     sender_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False)
#     content_type = db.Column(db.Enum('纯文字', '图片', '拼单信息', name='content_type'), nullable=False)
#     content = db.Column(db.Text)
#     image_url = db.Column(db.String(255))
#     order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id', ondelete='CASCADE'))
#     status = db.Column(db.Enum('发送中', '已发送', name='message_status'), default='发送中')
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)

# class UserConversationStatus(db.Model):
#     """用户会话状态模型"""
#     __tablename__ = 'user_conversation_status'
    
#     user_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), primary_key=True)
#     conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.conversation_id', ondelete='CASCADE'), primary_key=True)
#     unread_count = db.Column(db.Integer, default=0)
#     last_read_message_id = db.Column(db.Integer, db.ForeignKey('messages.mess_id', ondelete='SET NULL'))
#     last_read_time = db.Column(db.DateTime)

#     # 关系定义
#     last_message = db.relationship('Message', foreign_keys=[last_read_message_id])

# def __repr__(self):
#     return f'<Conversation {self.conversation_id}: {self.conversation_name or "Private Chat"}'
from datetime import datetime
from ..extensions import db

# 聊天会话关联表（多对多）
conversation_members = db.Table(
    'conversation_members',
    db.Column('user_in_con_id', db.Integer, primary_key=True, autoincrement=True),
    db.Column('conversation_id', db.Integer, db.ForeignKey('conversations.conversation_id', ondelete='CASCADE'), nullable=False),
    db.Column('user_id', db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False),
    db.Column('join_time', db.DateTime, default=datetime.utcnow)
)

class Conversation(db.Model):
    """聊天会话模型"""
    __tablename__ = 'conversations'

    conversation_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='会话ID')
    conversation_type = db.Column(db.Enum('private', 'group', name='conversation_type'), nullable=False)
    conversation_avatar = db.Column(db.String(255), nullable=False)
    conversation_name = db.Column(db.String(255), comment='群聊名称')
    last_message_id = db.Column(db.Integer, db.ForeignKey('messages.mess_id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系定义
    messages = db.relationship(
        'Message',
        backref='conversation',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='Message.conversation_id'  # 重点修复
    )

    members = db.relationship(
        'User',
        secondary=conversation_members,
        backref=db.backref('conversations', lazy='dynamic'),
        passive_deletes=True
    )

    statuses = db.relationship('UserConversationStatus', backref='conversation', cascade='all, delete-orphan')

    last_message = db.relationship(
        'Message',
        foreign_keys=[last_message_id],
        post_update=True  # 避免依赖循环
    )

    @property
    def is_group(self):
        return self.conversation_type == 'group'

    def __repr__(self):
        return f'<Conversation {self.conversation_id}: {self.conversation_name or "Private Chat"}>'


class Message(db.Model):
    """消息模型"""
    __tablename__ = 'messages'

    mess_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='消息ID')
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.conversation_id', ondelete='CASCADE'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False)
    content_type = db.Column(db.Enum('纯文字', '图片', '拼单信息', name='content_type'), nullable=False)
    content = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id', ondelete='CASCADE'))
    status = db.Column(db.Enum('发送中', '已发送', name='message_status'), default='发送中')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Message {self.mess_id} in Conv {self.conversation_id}>'


class UserConversationStatus(db.Model):
    """用户会话状态模型"""
    __tablename__ = 'user_conversation_status'

    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.conversation_id', ondelete='CASCADE'), primary_key=True)
    unread_count = db.Column(db.Integer, default=0)
    last_read_message_id = db.Column(db.Integer, db.ForeignKey('messages.mess_id', ondelete='SET NULL'))
    last_read_time = db.Column(db.DateTime)

    # 显式指定 foreign_keys，避免混淆
    last_message = db.relationship('Message', foreign_keys=[last_read_message_id])

    def __repr__(self):
        return f'<UserConversationStatus user={self.user_id}, conv={self.conversation_id}>'
