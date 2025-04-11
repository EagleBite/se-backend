import logging
import os
from logging.handlers import RotatingFileHandler
from flask import current_app
from typing import Optional
from datetime import datetime

"""
日志的使用方法

方式1：直接使用Flask应用日志记录器
current_app.logger.debug("Using app logger directly")

# 方式2：获取模块专属日志记录器 (推荐)
logger = get_logger(__name__)
logger.info(f"Attempting to create user: {user_data['username']}")
logger.debug("User creation successful")
logger.error(f"User creation failed: {str(e)}", exc_info=True)

日志输出效果
2023-05-01 16:20:12,345 - app.services.user_service - INFO - Attempting to create user: testuser (user_service.py:15)
"""

class ColorFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: grey + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
    
def setup_app_logger(app=None, log_dir: str = 'logs', max_bytes: int = 10*1024*1024, backup_count: int = 3):
    """
    配置Flask应用日志记录器
    
    :param app: Flask应用实例
    :param log_dir: 日志目录名
    :param max_bytes: 单个日志文件最大字节数
    :param backup_count: 保留的备份文件数
    """
    if app is None:
        app = current_app
    
    # 确保日志目录存在
    full_log_dir = os.path.join(app.root_path, log_dir)
    os.makedirs(full_log_dir, exist_ok=True)
    
    # 移除默认处理器
    app.logger.handlers.clear()
    
    # 文件处理器 (轮转日志)
    file_handler = RotatingFileHandler(
        filename=os.path.join(full_log_dir, 'app.log'),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    
    # 控制台处理器 (带颜色)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter())
    
    # 设置处理器和日志级别
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
    
    # 禁止传播到父记录器
    app.logger.propagate = False
    
    app.logger.info("Logger setup completed")

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取一个配置好的日志记录器
    
    :param name: 记录器名称 (通常使用 __name__)
    :return: 配置好的Logger实例
    """
    if name is None:
        return current_app.logger
    
    logger = logging.getLogger(name)
    
    # 如果已经配置过处理器则直接返回
    if logger.handlers:
        return logger
    
    # 继承Flask应用的处理器配置
    for handler in current_app.logger.handlers:
        logger.addHandler(handler)
    
    logger.setLevel(current_app.logger.level)
    logger.propagate = False
    
    return logger