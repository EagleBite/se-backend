from flask import current_app
from datetime import datetime
from ..extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from .association import user_car
from ..utils.logger import get_logger

class User(db.Model):
    """用户模型类"""
    __tablename__ = 'user'
    __table_args__ = {'comment': '用户表'}

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), nullable=False, unique=True, comment='用户名')
    # 修改为LongBlob类型存储二进制数据
    user_avatar = db.Column(db.LargeBinary(length=(2**32)-1), nullable=True, comment='头像二进制数据')
    realname = db.Column(db.String(50), nullable=False, comment='真实姓名')
    identity_id = db.Column(db.String(18), nullable=False, unique=True, comment='身份证号')
    gender = db.Column(db.Enum('男', '女', name='gender_enum'), nullable=False, comment='性别')
    telephone = db.Column(db.String(15), nullable=False, unique=True, comment='手机号')
    password_hash = db.Column(db.String(255), nullable=False, comment='加密密码')
    rate = db.Column(db.Numeric(3, 2), default=0.00, comment='评分')
    order_time = db.Column(db.Integer, default=0, comment='订单次数')
    status = db.Column(db.Enum('在线', '离线', '隐身', name='user_status_enum'), nullable=False, default='离线', comment='用户状态')
    last_active = db.Column(db.DateTime, comment='最后活跃时间')

    # 管理员角色（一个用户最多一个管理员身份）
    manager_role = db.relationship('Manager', back_populates='user', uselist=False, cascade='all, delete-orphan')

    # 多对多关系（一个用户可拥有多辆车）
    cars = db.relationship(
        'Car', 
        secondary=user_car,  # 指定关联表
        back_populates='owners',  # 双向关系
        lazy='dynamic',  # 延迟加载
        cascade='save-update, merge'
    )
    # 参与的订单（一个用户可以参与到多个订单中）
    participated_orders = db.relationship(
        'OrderParticipant',
        foreign_keys='OrderParticipant.participator_id',
        back_populates='participator',
        cascade='all, delete-orphan'
    )
    # 订单发起者与订单的关系
    initiated_orders = db.relationship(
        'Order',
        foreign_keys='Order.initiator_id',
        back_populates='initiator',
        cascade='all, delete-orphan'
    )

    # 密码加密处理
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_manager(self):
        """检查用户是否为管理员"""
        return self.manager_role is not None
    
    # 更新最后活跃时间
    def update_last_active(self):
        self.last_active = datetime.utcnow()
        db.session.add(self)
        db.session.commit()

    def __repr__(self):
        return f'<User {self.user_id}: {self.username}>'
    
    @classmethod
    def calculate_age(cls, indentity_id):
        """
        计算用户年龄
        :param identity_id: 身份证号
        :return: 年龄
        """
        if len(indentity_id) != 18:
            return None
        
        birth_date = datetime.strptime(indentity_id[6:14], '%Y%m%d')
        age = (datetime.utcnow() - birth_date).days // 365
        return age
    
    @staticmethod
    def create_user(data):
        """
        创建用户信息（封装业务逻辑）
        :param data: 包含用户信息的字典
        :return: (user_object, error_message)
        """
        logger = get_logger(__name__)

        try:
            user = User(
                username=data['username'],
                realname=data['realname'],
                identity_id=data['identity_id'],
                gender=data['gender'],
                telephone=data['telephone'],
                password_hash=generate_password_hash(data['password']),
                user_avatar=None  # 默认头像
            )
            db.session.add(user)
            user.update_last_active()
            db.session.commit()

            return user, None       
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建用户失败: {str(e)}")
            return None, "创建用户失败"