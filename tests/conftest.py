# pytest 的全局 fixture 配置
import pytest
from app import create_app
from app.extensions import db

@pytest.fixture
def app():
    app = create_app('config.TestingConfig')
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()