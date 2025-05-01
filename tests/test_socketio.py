from socketio import Client
import time, requests

def get_token():
    """获取JWT token"""
    login_url = 'http://100.80.119.36:5000/api/auth/login'
    data = {
        'username': '李闯',
        'password': '123456'
    }
    response = requests.post(login_url, json=data)
    if response.status_code == 200:
        return response.json()['data']['access_token']
    else:
        raise Exception("获取token失败")

# 获取Token
token = get_token()
print(f"获取的token: {token}")

# 创建Socket.IO客户端
sio = Client()
sio.connect('http://100.80.119.36:5000', transports=['websocket'], headers={'Authorization': f'Bearer {token}'})
sio.emit('send_message', {'ConversationId': 1 ,'content': 'Hello, World!'})
sio.wait()  # 等待1秒钟以确保消息发送完成
sio.disconnect()
    
@sio.event
def connect():
    print("[Client] 成功连接到服务器")

@sio.event
def disconnect():
    print("[Client] 与服务器断开连接")

@sio.event
def welcome(data):
    print(f"[Client] 服务端欢迎消息: {data}")

@sio.event
def message(data):
    print(f"[Client] 服务端回复: {data}")

@sio.event
def broadcast_msg(data):
    print(f"[Client] 收到广播消息: {data}")