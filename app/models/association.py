from ..extensions import db

# 多对多关联表（没有采用创建模型类的方式）
user_car = db.Table(
    'user_car',
    db.Column('user_id', db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), primary_key=True, comment='用户ID'),
    db.Column('car_id', db.Integer, db.ForeignKey('car.car_id', ondelete='CASCADE'), primary_key=True, comment='车辆ID'),
    info={'bind_key': None}
)