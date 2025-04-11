from ..extensions import db
from enum import Enum

class ParticipantIdentity(Enum):
    """参与者身份枚举"""
    DRIVER = 'driver'
    PASSENGER = 'passenger'

class OrderParticipant(db.Model):
    """订单参与者关联模型"""
    __tablename__ = 'order_participants'
    __table_args__ = {'comment': '订单参与者表'}

    # 复合主键
    participator_id = db.Column(
        db.Integer, 
        db.ForeignKey('user.user_id', ondelete='CASCADE'), 
        primary_key=True,
        comment='参与者ID'
    )
    order_id = db.Column(
        db.Integer, 
        db.ForeignKey('orders.order_id', ondelete='CASCADE'), 
        primary_key=True,
        comment='订单ID'
    )
    # 用户参与到订单的身份
    identity = db.Column(
        db.Enum(ParticipantIdentity),
        nullable=False,
        comment='身份(driver/passenger)'
    )

    # 与用户的关系
    participator = db.relationship(
        'User', 
        foreign_keys=[participator_id],
        back_populates='participated_orders'
    )
    # 与订单的关系
    order = db.relationship(
        'Order', 
        back_populates='participants'
    )

    def __repr__(self):
        return f'<OrderParticipant order:{self.order_id} user:{self.participator_id}>'
    
    @classmethod
    def create_pariticipant(cls, order_id, user_id, identity):
        """
        创建订单参与者记录
        :param order_id: 订单ID
        :param user_id: 用户ID
        :param identity: 身份类型
        :return: (order_participant_object, error_message)
        """
        if not order_id or not user_id or not identity:
            return None, "缺少必填字段"
        
        # 验证身份类型
        if identity not in [ParticipantIdentity.DRIVER.value, ParticipantIdentity.PASSENGER.value]:
            return None, "无效的身份类型"
        
        # 创建参与者记录
        participant = cls(order_id=order_id, participator_id=user_id, identity=identity)
        
        return participant, None