from ..extensions import db
from .association import user_car

class Car(db.Model):
    """
    汽车表
    +------------+--------------+------+-----+---------+----------------+
    | Field      | Type         | Null | Key | Default | Comment        |
    +------------+--------------+------+-----+---------+----------------+
    | car_id     | Integer      | NO   | PRI | NULL    | 车辆ID         |
    | license    | String(10)   | NO   | UNI | NULL    | 车牌号         |
    | car_type   | String(50)   | NO   |     | NULL    | 车型           |
    | color      | String(20)   | NO   |     | NULL    | 颜色           |
    | seat_num   | Integer      | NO   |     | NULL    | 座位数         |
    +------------+--------------+------+-----+---------+----------------+
    """
    __tablename__ = 'car'
    __table_args__ = {'comment': '汽车表'}
    
    car_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='车辆ID')
    license = db.Column(db.String(10), nullable=False, unique=True, comment='车牌号')
    car_type = db.Column(db.String(50), nullable=False, comment='车型')
    color = db.Column(db.String(20), nullable=False, comment='颜色')
    seat_num = db.Column(db.Integer, nullable=False, comment='座位数')

    # 多对多反向关系（一辆车可属于多个用户）
    owners = db.relationship(
        'User', 
        secondary=user_car,  # 指定关联表
        back_populates='cars',
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<Car {self.car_id}: {self.license}>'

