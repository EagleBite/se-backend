# from flask import current_app
# from datetime import datetime
# from ..extensions import db
# from werkzeug.security import generate_password_hash, check_password_hash
# from ..utils.logger import get_logger

# class UserCar(db.Model):
#     __tablename__ = 'user_car'
#     user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
#     car_id = db.Column(db.Integer, db.ForeignKey('car.car_id'), primary_key=True)