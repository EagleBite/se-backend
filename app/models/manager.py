from ..extensions import db

class Manager(db.Model):
    """管理员模型"""
    __tablename__ = 'manager'
    __table_args__ = {'comment': '管理员表'}

    manager_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='管理员ID')
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False, comment='关联用户ID')

    # 关系定义
    user = db.relationship('User', back_populates='manager_role', uselist=False)

    def __repr__(self):
        return f'<Manager {self.manager_id}>'