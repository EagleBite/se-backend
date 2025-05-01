import eventlet
eventlet.monkey_patch()

import os, argparse, socket
from app import create_app
from app.extensions import socketio

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Flask SocketIO Server")
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--host', help='Override default host binding')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    return parser.parse_args()

def get_local_ip():
    """获取本机局域网IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 连接一个外部地址
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"  # 失败时回退到本地

def main():
    """主函数入口"""
    args = parse_args()

    # 根据调试模式选择配置
    config = "config.DevelopmentConfig" if args.debug else "config.ProductionConfig"
    app = create_app(config)

    mode = "开发" if args.debug else "生产"
    app.logger.info(f"🔧 {mode}模式：{'启用' if args.debug else '禁用'}调试")

    host = args.host if args.host else '0.0.0.0'
    port = args.port if args.port else 5000

    # 打印运行信息
    app.logger.info(f"🚀 服务监听在: http://{host}:{port}")
    if host == '0.0.0.0':
        app.logger.info(f"👉 本地访问: http://127.0.0.1:{port}")
        app.logger.info(f"👉 局域网访问: http://{get_local_ip()}:{port}")

    socketio.run(app, host=host, port=port, debug=os.getenv('FLASK_DEBUG') == '1', use_reloader=False)

if __name__ == '__main__':
    main()