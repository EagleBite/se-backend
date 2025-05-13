import pytest
from app import create_app
from app.models import User
from app.extensions import db
from config import TestingConfig
import json
from flask_jwt_extended import create_refresh_token, create_access_token
import jwt
import time
from datetime import datetime, timedelta
from flask_jwt_extended.exceptions import WrongTokenError

@pytest.fixture
def app():
    """创建测试应用实例"""
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()

@pytest.fixture
def test_user(app):
    """创建测试用户"""
    with app.app_context():
        user = User(
            username='testuser',
            realname='Test User',
            identity_id='310101200407154222',
            gender='male',
            telephone='15800993469',
            password='password123'
        )
        db.session.add(user)
        db.session.commit()
        return user.user_id

@pytest.fixture
def auth_headers(app, test_user):
    """获取认证头"""
    with app.app_context():
        # 确保用户对象在会话中
        user = User.query.get(test_user)
        refresh_token = create_refresh_token(identity=str(user.user_id))
        return {'Authorization': f'Bearer {refresh_token}'}

# ================ 语句测试 ================

def test_register_success(client, app):
    """语句测试：用户注册成功"""
    test_data = {
        'username': 'newuser',
        'realname': 'New User',
        'identity_id': '310101200407154223',
        'gender': 'male',
        'telephone': '15800993470',
        'password': 'password123'
    }
    
    response = client.post(
        '/api/auth/register',
        json=test_data,
        content_type='application/json'
    )
    
    print("\n=== 测试1: 用户注册成功 ===")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
    
    assert response.status_code == 200
    data = response.json
    assert data['code'] == 200
    assert data['message'] == "登录成功"
    assert 'userId' in data['data']

def test_login_success(client, app, test_user):
    """语句测试：用户登录成功"""
    login_data = {
        'username': 'testuser',
        'password': 'password123'
    }
    
    response = client.post(
        '/api/auth/login',
        json=login_data,
        content_type='application/json'
    )
    
    print("\n=== 测试2: 用户登录成功 ===")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
    
    assert response.status_code == 200
    data = response.json
    assert data['code'] == 200
    assert data['message'] == "登录成功"
    assert 'access_token' in data['data']
    assert 'user' in data['data']
    assert data['data']['user']['username'] == 'testuser'

def test_refresh_token_success(client, app, test_user):
    """语句测试：刷新token成功"""
    with app.app_context():
        # 创建refresh token
        refresh_token = create_refresh_token(identity=str(test_user))
        headers = {'Authorization': f'Bearer {refresh_token}'}
        
        response = client.post(
            '/api/auth/refresh',
            headers=headers
        )
        
        print("\n=== 测试3: 刷新token成功 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
        
        assert response.status_code == 200
        data = response.json
        assert data['code'] == 200
        assert data['message'] == "刷新成功"
        assert 'access_token' in data['data']

# ================ 路径测试 ================

def test_register_duplicate_username(client, app):
    """路径测试：注册重复用户名"""
    # 先创建一个用户
    test_user = User(
        username='testuser',
        realname='Test User',
        identity_id='310101200407154223',
        gender='male',
        telephone='15800993470',
        password='password123'
    )
    with app.app_context():
        db.session.add(test_user)
        db.session.commit()
    
    # 尝试注册相同用户名
    test_data = {
        'username': 'testuser',
        'realname': 'Another User',
        'identity_id': '310101200407154224',
        'gender': 'male',
        'telephone': '15800993471',
        'password': 'password123'
    }
    
    response = client.post(
        '/api/auth/register',
        json=test_data,
        content_type='application/json'
    )
    
    print("\n=== 测试4: 注册重复用户名 ===")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
    
    assert response.status_code == 400
    data = response.json
    assert data['code'] == 400
    assert data['message'] == "用户名已经被注册"

def test_register_duplicate_telephone(client, app):
    """路径测试：注册重复手机号"""
    # 先创建一个用户
    test_user = User(
        username='testuser1',
        realname='Test User',
        identity_id='310101200407154223',
        gender='male',
        telephone='15800993469',
        password='password123'
    )
    with app.app_context():
        db.session.add(test_user)
        db.session.commit()
    
    # 尝试注册相同手机号
    test_data = {
        'username': 'testuser2',
        'realname': 'Another User',
        'identity_id': '310101200407154224',
        'gender': 'male',
        'telephone': '15800993469',
        'password': 'password123'
    }
    
    response = client.post(
        '/api/auth/register',
        json=test_data,
        content_type='application/json'
    )
    
    print("\n=== 测试5: 注册重复手机号 ===")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
    
    assert response.status_code == 400
    data = response.json
    assert data['code'] == 400
    assert data['message'] == "手机号已被注册"

def test_register_duplicate_identity_id(client, app):
    """路径测试：注册重复身份证号"""
    # 先创建一个用户
    test_user = User(
        username='testuser1',
        realname='Test User',
        identity_id='310101200407154222',
        gender='male',
        telephone='15800993470',
        password='password123'
    )
    with app.app_context():
        db.session.add(test_user)
        db.session.commit()
    
    # 尝试注册相同身份证号
    test_data = {
        'username': 'testuser2',
        'realname': 'Another User',
        'identity_id': '310101200407154222',
        'gender': 'male',
        'telephone': '15800993471',
        'password': 'password123'
    }
    
    response = client.post(
        '/api/auth/register',
        json=test_data,
        content_type='application/json'
    )
    
    print("\n=== 测试6: 注册重复身份证号 ===")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
    
    assert response.status_code == 400
    data = response.json
    assert data['code'] == 400
    assert data['message'] == "身份证号已被注册"

def test_login_wrong_password(client, app):
    """路径测试：登录密码错误"""
    # 先创建一个用户
    test_user = User(
        username='testuser',
        realname='Test User',
        identity_id='310101200407154222',
        gender='male',
        telephone='15800993469',
        password='password123'
    )
    with app.app_context():
        db.session.add(test_user)
        db.session.commit()
    
    # 尝试使用错误密码登录
    login_data = {
        'username': 'testuser',
        'password': 'wrongpassword'
    }
    
    response = client.post(
        '/api/auth/login',
        json=login_data,
        content_type='application/json'
    )
    
    print("\n=== 测试7: 登录密码错误 ===")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
    
    assert response.status_code == 401
    data = response.json
    assert data['code'] == 401
    assert data['message'] == "用户名或密码错误"

def test_login_nonexistent_user(client):
    """路径测试：登录不存在的用户"""
    login_data = {
        'username': 'nonexistent',
        'password': 'password123'
    }
    
    response = client.post(
        '/api/auth/login',
        json=login_data,
        content_type='application/json'
    )
    
    print("\n=== 测试8: 登录不存在的用户 ===")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
    
    assert response.status_code == 401
    data = response.json
    assert data['code'] == 401
    assert data['message'] == "用户名或密码错误"


def test_refresh_token_with_expired_token(client, app, test_user):
    """路径测试：使用过期的token刷新"""
    with app.app_context():
        # 创建一个立即过期的token
        expired_token = create_refresh_token(
            identity=str(test_user),
            expires_delta=timedelta(microseconds=1)
        )
        headers = {'Authorization': f'Bearer {expired_token}'}
        # 等待token过期
        time.sleep(0.1)     
        response = client.post(
            '/api/auth/refresh',
            headers=headers
        )
        
        print("\n=== 测试9: 使用过期的token刷新 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
        
        # 检查响应内容而不是状态码
        assert 'message' in response.json
        assert 'Token已过期，请重新登录' in response.json['message']

