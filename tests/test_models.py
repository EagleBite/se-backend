from app.models import User, Car, init_relationships
from datetime import datetime

def test_user_creation(db_session):
    """测试用户模型"""
    user = User(username='testuser', rate=4.5)
    db_session.session.add(user)
    db_session.session.commit()    
        
    assert user.user_id is not None
    assert User.query.filter_by(username='testuser').first() == user

def test_car_ownership(db_session):
    """测试用户-车辆关联"""
    user = User(username='driver1')
    car = Car(license='京A12345', car_type='SUV', color='black', seat_num=5)
    
    # 建立关联
    user.cars.append(car)
    db_session.session.add_all([user, car])
    db_session.session.commit()
    
    assert len(user.cars) == 1
    assert user.cars[0].license == '京A12345'
    assert car.owners[0].username == 'driver1'
        