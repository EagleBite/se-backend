import pytest
from app import create_app
from app.models import User, Car
from app.extensions import db
from config import TestingConfig
import json
import base64
from datetime import datetime
from flask_jwt_extended import create_access_token
import jwt

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
        access_token = create_access_token(identity=str(test_user))
        return {'Authorization': f'Bearer {access_token}'}

# ================ 语句测试 ================

def test_get_user_basic_success(client, app, test_user, auth_headers):
    """语句测试：获取用户基础信息成功"""
    with app.app_context():
        response = client.get(
            '/api/user/basic',
            headers=auth_headers
        )
        
        print("\n=== 测试1: 获取用户基础信息成功 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
        
        assert response.status_code == 200
        data = response.json
        assert data['code'] == 200
        assert data['message'] == "获取用户基础信息成功"
        assert 'user_id' in data['data']
        assert 'username' in data['data']
        assert 'gender' in data['data']
        assert 'age' in data['data']
        assert 'avatar' in data['data']
        assert 'rate' in data['data']
        assert 'status' in data['data']

def test_get_user_profile_success(client, app, test_user, auth_headers):
    """语句测试：获取用户完整档案成功"""
    with app.app_context():
        response = client.get(
            '/api/user/profile',
            headers=auth_headers
        )
        
        print("\n=== 测试2: 获取用户完整档案成功 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
        
        assert response.status_code == 200
        data = response.json
        assert data['code'] == 200
        assert data['message'] == "获取用户基础信息成功"
        assert 'user_info' in data['data']
        assert 'vehicles' in data['data']
        assert 'realname' in data['data']['user_info']
        assert 'gender' in data['data']['user_info']
        assert 'telephone' in data['data']['user_info']
        assert 'identity_masked' in data['data']['user_info']
        assert 'order_count' in data['data']['user_info']
        assert 'last_active' in data['data']['user_info']
        assert 'avatar' in data['data']['user_info']

def test_get_user_modifiable_data_success(client, app, test_user, auth_headers):
    """语句测试：获取用户可修改信息成功"""
    with app.app_context():
        response = client.get(
            '/api/user/modifiable_data',
            headers=auth_headers
        )
        
        print("\n=== 测试3: 获取用户可修改信息成功 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
        
        assert response.status_code == 200
        data = response.json
        assert data['code'] == 200
        assert data['message'] == "获取用户可修改信息成功"
        assert 'user_id' in data['data']
        assert 'username' in data['data']
        assert 'gender' in data['data']
        assert 'avatar' in data['data']
        assert 'telephone' in data['data']

# ================ 路径测试 ================

def test_get_user_basic_no_auth(client):
    """路径测试：未认证访问用户基础信息"""
    response = client.get('/api/user/basic')
    assert response.status_code == 401

def test_get_user_basic_user_not_found(client, app):
    """路径测试：获取不存在的用户基础信息"""
    with app.app_context():
        # 创建一个不存在的用户ID的token
        access_token = create_access_token(identity='99999')
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = client.get(
            '/api/user/basic',
            headers=headers
        )
        
        print("\n=== 测试4: 获取不存在的用户基础信息 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
        
        # JWT验证失败会返回401
        assert response.status_code == 401
        data = response.json
        assert 'msg' in data
        assert 'Error loading the user' in data['msg']


def test_get_user_basic_no_token(client):
    """路径测试：无token访问用户基础信息"""
    response = client.get('/api/user/basic')
    
    print("\n=== 测试5: 无token访问用户基础信息 ===")
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
    
    # JWT验证失败会返回401
    assert response.status_code == 401
    data = response.json
    assert 'msg' in data
    assert 'Missing Authorization Header' in data['msg']

def test_upload_avatar_success(client, app, test_user):
    """路径测试：上传头像成功"""
    with app.app_context():
        # 创建一个测试用的base64图片数据
        test_image = base64.b64encode(b'test_image_data').decode('utf-8')
        
        response = client.post(
            f'/api/user/upload_avatar/{test_user}',
            json={'base64_data': f'data:image/jpeg;base64,{test_image}'}
        )
        
        print("\n=== 测试6: 上传头像成功 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
        
        assert response.status_code == 200
        data = response.json
        assert data['code'] == 200
        assert data['message'] == "头像上传成功"

def test_upload_avatar_no_data(client, app, test_user):
    """路径测试：上传头像无数据"""
    with app.app_context():
        response = client.post(
            f'/api/user/upload_avatar/{test_user}',
            json={}
        )
        
        print("\n=== 测试7: 上传头像无数据 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
        
        assert response.status_code == 400
        data = response.json
        assert data['code'] == 400
        assert data['message'] == "请上传Base64数据"

def test_update_user_success(client, app, test_user, auth_headers):
    """路径测试：更新用户信息成功"""
    with app.app_context():
        update_data = {
            'username': 'newusername',
            'telephone': '15800993470',
            'gender': 'female'
        }
        
        response = client.post(
            '/api/user/update',
            headers=auth_headers,
            json=update_data
        )
        
        print("\n=== 测试8: 更新用户信息成功 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
        
        assert response.status_code == 200
        data = response.json
        assert data['code'] == 200
        assert data['message'] == "个人信息已保存"
        assert data['data']['username'] == 'newusername'
        assert data['data']['telephone'] == '15800993470'
        assert data['data']['gender'] == 'female'

def test_update_user_no_auth(client):
    """路径测试：未认证更新用户信息"""
    response = client.post(
        '/api/user/update',
        json={'username': 'newusername'}
    )
    assert response.status_code == 401

def test_get_avatar_success(client, app, test_user, auth_headers):
    """路径测试：获取用户头像成功"""
    with app.app_context():
        # 先上传一个头像
        test_image = base64.b64encode(b'test_image_data').decode('utf-8')
        client.post(
            f'/api/user/upload_avatar/{test_user}',
            json={'base64_data': f'data:image/jpeg;base64,{test_image}'}
        )
        
        # 获取头像
        response = client.get(
            '/api/user/avatar',
            headers=auth_headers
        )
        
        print("\n=== 测试9: 获取用户头像成功 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json, ensure_ascii=False, indent=2)}")
        
        assert response.status_code == 200
        data = response.json
        assert data['code'] == 200
        assert data['message'] == "获取头像成功"
        assert 'avatar_url' in data['data']
