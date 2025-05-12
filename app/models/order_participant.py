from ..extensions import db
from enum import Enum

class ParticipantIdentity(Enum):
    """参与者身份枚举"""
    DRIVER = 'driver'
    PASSENGER = 'passenger'

    @classmethod
    def values(cls):
        return [member.value for member in cls]   

# TODO: initiator_id字段可能需要删除
class OrderParticipant(db.Model):
    """
    订单参与者关联表
    +------------------+---------------------+------+-----+-------------------+-----------------------------+
    | Field            | Type                | Null | Key | Default           | Comment                     |
    +------------------+---------------------+------+-----+-------------------+-----------------------------+
    | participator_id  | Integer             | NO   | PRI | NULL              | 参与者ID(复合主键1)         |
    | order_id         | Integer             | NO   | PRI | NULL              | 订单ID(复合主键2)           |
    | initiator_id     | Integer             | YES  | MUL | NULL              | 发起人ID                    |
    | identity         | Enum('driver',      | NO   |     | NULL              | 参与者身份(driver/passenger)|
    | join_time        | DateTime            | NO   |     | CURRENT_TIMESTAMP | 加入时间                    |
    +------------------+---------------------+------+-----+-------------------+-----------------------------+
    """
    __tablename__ = 'order_participants'
    __table_args__ = {'comment': '订单参与者表'}

    # 复合主键
    participator_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), primary_key=True, comment='参与者ID')
    order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id', ondelete='CASCADE'), primary_key=True, comment='订单ID')
    initiator_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), nullable=True, comment='发起人ID')
    identity = db.Column(db.Enum(*ParticipantIdentity.values(), name='order_type_enum'), nullable=False, comment='身份(driver/passenger)')
    # join_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment='加入时间')

    # 关系定义
    participator = db.relationship('User', foreign_keys=[participator_id], back_populates='participated_orders')
    order = db.relationship('Order', back_populates='participants')

    def __repr__(self):
        return f'<OrderParticipant order:{self.order_id} user:{self.participator_id}>'

    @classmethod
    def create_participant(cls, order_id, user_id, identity, initiator_id=None):
        """
        创建订单参与者记录
        :param order_id: 订单ID
        :param user_id: 用户ID
        :param identity: 身份类型
        :param initiator_id: 发起人ID（可选）
        :return: (order_participant_object, error_message)
        """
        if not order_id or not user_id or not identity:
            return None, "缺少必填字段"
        
        # 验证身份类型
        if identity not in [ParticipantIdentity.DRIVER.value, ParticipantIdentity.PASSENGER.value]:
            return None, "无效的身份类型"
        
        # 创建参与者记录
        participant = cls(
            order_id=order_id,
            participator_id=user_id,
            identity=identity,
            initiator_id=initiator_id
        )
        
        return participant, None