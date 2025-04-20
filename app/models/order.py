from datetime import datetime
from decimal import Decimal
from enum import Enum
from ..extensions import db
from ..utils.logger import get_logger


class Order(db.Model):
    """拼车订单模型"""
    __tablename__ = 'orders'
    __table_args__ = {'comment': '拼车订单表'}
    
    order_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='订单ID')
    initiator_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), comment='发起人ID')
    start_loc = db.Column(db.String(100), nullable=False, index=True, comment='出发地')
    dest_loc = db.Column(db.String(100), nullable=False, comment='目的地')
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment='出发时间')
    price = db.Column(db.Numeric(10, 2), nullable=False, comment='价格')
    
    # 修改为直接在db.Enum中定义枚举值
    status = db.Column(db.Enum(
        'pending', 'completed', 'to-review', 'not-started', 'in-progress', 
        name='order_status_enum'
    ), default='not-started', nullable=False, index=True, comment='订单状态')
    
    order_type = db.Column(db.Enum(
        'driver', 'passenger',
        name='order_type_enum'
    ), nullable=False, comment='订单类型')
    
    car_type = db.Column(db.String(50), nullable=True, comment='车型要求')
    travel_partner_num = db.Column(db.Integer, nullable=True, comment='同行人数(乘客订单)')
    spare_seat_num = db.Column(db.Integer, nullable=True, comment='剩余座位(司机订单)')
    
    rate = db.Column(db.Enum(
        '0', '1', '2', '3', '4', '5',
        name='order_rate_enum'
    ), nullable=True, comment='评分')

    # 订单发起者与订单的关系
    initiator = db.relationship('User', back_populates='initiated_orders')
    # 订单参与者与订单的关系
    participants = db.relationship(
        'OrderParticipant',
        back_populates='order',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Order {self.order_id}: {self.start_loc}→{self.dest_loc}>'
    
    @classmethod
    def create_carpool_order(cls, data):
        """
        创建拼车订单（封装业务逻辑）
        :param data: 包含订单数据的字典
        :return: (order_object, error_message)
        """
        logger = get_logger(__name__)

        # --- 基本字段验证 ---
        required_fields = ['identity', 'startAddress', 'endAddress', 'departureTime', 'price', 'initiator_id']
        if missing_fields := [f for f in required_fields if not data.get(f)]:
            return None, f"缺少必填字段: {', '.join(missing_fields)}"
        
        identity = data['identity']
        initiator_id = data['initiator_id']

        # --- 身份特定验证 ---
        if identity == 'driver':
            if not data.get('vehicleId'):
                return None, "司机订单需要车辆ID"
            if not data.get('availableSeats'):
                return None, "请填写剩余座位数"
            car_type = data.get('carType')
        elif identity == 'passenger':
            if not data.get('passengerCount'):
                return None, "请填写同行人数"
            car_type = None
        else:
            return None, "无效的身份类型"
        
        # --- 数据转换 ---
        try:
            start_time = datetime.strptime(
                data['departureTime'], 
                '%Y-%m-%d %H:%M:%S' if ':' in data['departureTime'][-3:] else '%Y-%m-%d %H:%M'
            )
            price = Decimal(str(data['price']))
            if price < 0:
                return None, "价格不能为负数"
        except ValueError as e:
            return None, f"数据格式错误: {str(e)}"
        
        # --- 创建订单 ---
        try:
            order = cls(
                initiator_id=initiator_id,
                start_loc=data['startAddress'],
                dest_loc=data['endAddress'],
                start_time=start_time,
                price=price,
                status='not-started',
                order_type=identity,
                car_type=car_type,
                travel_partner_num=data.get('passengerCount'),
                spare_seat_num=data.get('availableSeats')
            )
            db.session.add(order)
            db.session.flush()  # 获取order_id
            
            # 创建参与记录
            from app.models.order_participant import OrderParticipant
            OrderParticipant.create_participation(
                user_id=initiator_id,
                order_id=order.order_id,
                identity=identity
            )
            
            return order, None
        except Exception as e:
            db.session.rollback()
            if 'foreign key constraint' in str(e).lower():
                return None, "无效的用户ID"
            logger.error(f"订单创建失败: {str(e)}")
            return None, "数据库操作失败"


