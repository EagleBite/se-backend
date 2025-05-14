from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from ..extensions import db
from ..utils.logger import get_logger
from ..models import User

class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = 'pending'          # 待审核
    COMPLETED = 'completed'      # 已完成
    REJECTED = 'rejected'        # 已拒绝
    NOT_STARTED = 'not-started'  # 未开始
    IN_PROGRESS = 'in-progress'  # 进行中
    TO_PAY = 'to-pay'            # 待付款
    TO_REVIEW = 'to-review'      # 待评价
    
    @classmethod
    def values(cls):
        return [member.value for member in cls]   
    
    @classmethod
    def get_chinese(cls, status):
        """获取状态的中文描述"""
        mapping = {
            cls.PENDING.value: '待审核',
            cls.COMPLETED.value: '已完成',
            cls.REJECTED.value: '已拒绝',
            cls.NOT_STARTED.value: '未开始',
            cls.IN_PROGRESS.value: '进行中',
            cls.TO_PAY.value: '待付款',
            cls.TO_REVIEW.value: '待评价'
        }
        return mapping.get(status, '未知状态')

class OrderType(Enum):
    """订单类型枚举"""
    PERSON_FIND_CAR = 'person-find-car' # 人找车 -- 当前没有司机 -- 司机接单后转变为车找人
    CAR_FIND_PERSON = 'car-find-person' # 车找人 -- 当前车没有坐满

    @classmethod
    def values(cls):
        return [member.value for member in cls]   

class OrderRate(Enum):
    """评分枚举"""
    ZERO = '0'
    ONE = '1'
    TWO = '2'
    THREE = '3'
    FOUR = '4'
    FIVE = '5'

    @classmethod
    def values(cls):
        return [member.value for member in cls]   

class Order(db.Model):
    """
    拼车订单表
    +---------------------+------------------------+------+-----+---------------------+-----------------------------+
    | Field               | Type                   | Null | Key | Default             | Comment                     |
    +---------------------+------------------------+------+-----+---------------------+-----------------------------+
    | order_id            | Integer                | NO   | PRI | auto_increment      | 订单ID                      |
    | initiator_id        | Integer                | NO   | MUL | NULL                | 发起人ID                    |
    | start_loc           | String(100)            | NO   | MUL | NULL                | 出发地(建立索引)            |
    | dest_loc            | String(100)            | NO   |     | NULL                | 目的地                      |
    | start_time          | DateTime               | NO   |     | CURRENT_TIMESTAMP   | 出发时间                    |
    | price               | Numeric(10,2)          | NO   |     | NULL                | 价格(精度:2位小数)          |
    | status              | Enum                   | NO   | MUL | 'not-started'       | 订单状态(建立索引)          |
    | order_type          | Enum                   | NO   |     | NULL                | 订单类型(人找车/车找人)     |
    | car_type            | String(50)             | YES  |     | NULL                | 车型要求                    |
    | travel_partner_num  | Integer                | YES  |     | NULL                | 同行人数(人找车订单)        |
    | spare_seat_num      | Integer                | YES  |     | NULL                | 剩余座位(车找人订单)        |
    | rate                | Enum                   | YES  |     | NULL                | 评分(0-5)                  |
    | reject_reason       | String(200)            | YES  |     | NULL                | 拒绝原因                   |
    +---------------------+------------------------+------+-----+---------------------+-----------------------------+
    """
    __tablename__ = 'orders'
    __table_args__ = {'comment': '拼车订单表'}
    
    order_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='订单ID')
    initiator_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), comment='发起人ID')
    start_loc = db.Column(db.String(100), nullable=False, index=True, comment='出发地')
    dest_loc = db.Column(db.String(100), nullable=False, comment='目的地')
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment='出发时间')
    price = db.Column(db.Numeric(10, 2), nullable=False, comment='价格')
    status = db.Column(db.Enum(*OrderStatus.values(), name='order_status_enum'), default=OrderStatus.NOT_STARTED.value ,nullable=False, index=True, comment='订单状态')
    order_type = db.Column(db.Enum(*OrderType.values(), name='order_type_enum'), nullable=False, comment='订单类型')
    car_type = db.Column(db.String(50), nullable=True, comment='车型要求')
    travel_partner_num = db.Column(db.Integer, nullable=True, comment='同行人数(人找车订单)')
    spare_seat_num = db.Column(db.Integer, nullable=True, comment='剩余座位(车找人订单)')
    rate = db.Column(db.Enum(*OrderRate.values(), name='order_rate_enum'), nullable=True, comment='评分')
    reject_reason = db.Column(db.String(200), nullable=True, comment='拒绝原因')

    # 关联关系
    initiator = db.relationship('User', back_populates='initiated_orders')                                         # 订单发起者
    participants = db.relationship('OrderParticipant', back_populates='order', cascade='all, delete-orphan')       # 订单参与者
    messages = db.relationship('Message', back_populates='order')                                                  # 发送该订单邀请的消息
    order_conversations = db.relationship('Conversation', back_populates='order', cascade='all, delete-orphan')    # 订单对应的会话

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
                spare_seat_num=data.get('availableSeats'),
                reject_reason=None
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

