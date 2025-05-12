from enum import Enum
from ..extensions import db
from .order import Order

class MessageType(Enum):
    """消息类型枚举"""
    TEXT = 'text'               # 文本信息
    IMAGE = 'image'             # 图片信息
    FILE = 'file'               # 文件信息   
    INVITATION = 'invitation'   # 拼车邀请信息

    @classmethod
    def values(cls):
        return [member.value for member in cls]

class Message(db.Model):
    """
    消息表
    +-------------------+------------------+------+-----+------------+---------------------+
    | Field             | Type             | Null | Key | Default    | Comment             |
    +-------------------+------------------+------+-----+------------+---------------------+
    | id                | Integer          | NO   | PRI | NULL       | 消息ID              |
    | conversation_id   | Integer          | NO   | MUL | NULL       | 会话ID              |
    | sender_id         | Integer          | NO   | MUL | NULL       | 发送者ID            |
    | content           | Text             | NO   |     | NULL       | 消息内容            |
    | message_type      | Enum             | NO   |     | 'text'     | 消息类型            |
    | created_at        | DateTime         | YES  |     | now()      | 创建时间            |
    | order_id          | Integer          | YES  | MUL | NULL       | 关联拼车订单ID       |
    +-------------------+------------------+------+-----+------------+---------------------+
    """
    __tablename__ = 'messages'
    __table_args__ = {'comment': '消息表'}

    id = db.Column(db.Integer, primary_key=True, comment='消息ID')
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, comment='会话ID')
    sender_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False, comment='发送者ID')
    content = db.Column(db.Text, nullable=False, comment='消息内容')
    message_type = db.Column(db.Enum(*MessageType.values(), name='message_type_enum'), default=MessageType.TEXT.value, nullable=False, comment='消息类型')
    created_at = db.Column(db.DateTime, default=db.func.now(), comment='创建时间')

    # 当消息类型是拼车邀请时
    order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id', ondelete='SET NULL'), nullable=True, comment='关联拼车订单ID')

    # 关联关系
    conversation = db.relationship('Conversation', back_populates='messages') # 所属会话
    sender = db.relationship('User', back_populates='sent_messages')          # 发送者
    order = db.relationship('Order', back_populates='messages')               # 拼车邀请对应的订单

    def get_message_payload(self):
        """获取消息内容"""
        payload = {
            'id': self.id,
            'type': self.message_type,
            'content': self.content,
            'sender': {
                'id': self.sender_id,
                'name': self.sender.username
            },
            'created_at': self.created_at.isoformat(),
            'is_read': self.is_read
        }

        # 拼车订单消息
        if self.message_type == MessageType.INVITATION.value and self.order:
            payload['order'] = {
                'id': self.order.order_id,
                'start_loc': self.order.start_loc,
                'dest_loc': self.order.dest_loc,
                'start_time': self.order.start_time.isoformat(),
                'price': float(self.order.price),
                'status': self.order.status.value,
                'initiator_id': self.order.initiator_id
            }

        return payload
