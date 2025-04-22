from app import create_app
import os

# 根据是否启用调试模式选择配置
if os.getenv('FLASK_DEBUG') == '1':
    app = create_app("config.DevelopmentConfig")
    app.logger.info("🔧 开发模式：启用调试")
else:
    app = create_app("config.ProductionConfig")
    app.logger.info("🔧 生产模式：禁用调试")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)