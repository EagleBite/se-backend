import os, logging, json, uuid
from logging import addLevelName
from logging.handlers import RotatingFileHandler
from flask import current_app, request, jsonify
from typing import Optional, Any, Dict
from datetime import datetime
from functools import wraps

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

# 首先定义SUCCESS级别 (介于WARNING和INFO之间)
SUCCESS_LEVEL_NUM = 25
logging.SUCCESS = SUCCESS_LEVEL_NUM  # 添加SUCCESS级别
addLevelName(SUCCESS_LEVEL_NUM, 'SUCCESS')  # 注册级别名称

# 修改Logger类添加success方法
def success(self, msg, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, msg, args, **kwargs)

logging.Logger.success = success

class ColorFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    green = "\x1b[32;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: grey + format_str + reset,
        logging.SUCCESS: green + format_str + reset,
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
    # app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
    app.logger.setLevel(logging.DEBUG)
    
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

def log_request_response(logger: Optional[logging.Logger] = None, 
                        log_level: int = logging.DEBUG,
                        max_body_length: int = 1000,
                        sensitive_fields: tuple = ('password', 'access_token', 'refresh_token')
                        ) -> None:
    """
    记录请求和响应信息的日志函数
    
    使用示例:
    @app.route('/some-endpoint')
    def some_endpoint():
        # 在视图函数开头调用
        log_request_response()
        # ...处理逻辑...
        response = jsonify({"result": "success"})
        # 在返回前调用记录响应
        log_request_response(response=response)
        return response
    
    :param logger: 可选的Logger实例，如果为None则使用current_app.logger
    :param log_level: 日志级别，默认为DEBUG
    :param max_body_length: 记录body的最大长度，超过会被截断
    :param sensitive_fields: 需要脱敏的敏感字段
    """
    # 获取或创建logger
    if logger is None:
        logger = current_app.logger if current_app else get_logger(__name__)

    def mask_sensitive_data(data: Any) -> Any:
        """脱敏敏感数据"""
        if isinstance(data, dict):
            return {k: '***MASKED***' if k in sensitive_fields else mask_sensitive_data(v) 
                    for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [mask_sensitive_data(item) for item in data]
        return data

    # 如果没有传入response参数，则记录请求信息
    if 'response' not in request.__dict__:
        try:
            # 收集请求信息
            request_info: Dict[str, Any] = {
                'method': request.method,
                'path': request.path,
                'url': request.url,
                'args': mask_sensitive_data(dict(request.args)),
                'headers': {k: v for k, v in request.headers.items() 
                           if k.lower() not in ('authorization', 'cookie')},
                'remote_addr': request.remote_addr,
            }
            
            # 处理请求体
            if request.content_length and request.content_length > 0:
                content_type = request.headers.get('Content-Type', '')
                
                if 'application/json' in content_type:
                    try:
                        body = request.get_json()
                        request_info['json_body'] = body
                    except Exception as e:
                        request_info['body'] = f"(Failed to parse JSON: {str(e)}) {request.data[:max_body_length]}"
                elif 'form' in content_type:
                    request_info['form_data'] = dict(request.form)
                    if request.files:
                        request_info['files'] = list(request.files.keys())
                else:
                    body_str = request.data.decode('utf-8', errors='replace')[:max_body_length]
                    request_info['body'] = body_str + ('...' if len(request.data) > max_body_length else '')
            
            logger.log(log_level, "Request received:\n%s", 
                       json.dumps(request_info, indent=2, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"Failed to log request: {str(e)}", exc_info=True)

    # 如果传入了response参数，则记录响应信息
    elif 'response' in request.__dict__:
        try:
            response = request.__dict__['response']
            response_data = response[0].get_json() if hasattr(response[0], 'get_json') else response[0]
            
            # 处理ApiResponse类型的响应
            if isinstance(response_data, dict) and 'code' in response_data:
                log_msg = {
                    'status': 'SUCCESS' if 200 <= response_data['code'] < 400 else 'ERROR',
                    'code': response_data['code'],
                    'message': response_data.get('message'),
                    'data_summary': str(response_data.get('data'))[:100] + '...' if response_data.get('data') else None,
                    'http_status': response[1]
                }
            else:
                log_msg = {
                    'http_status': response[1],
                    'data': mask_sensitive_data(response_data)[:100] + '...' if response_data else None
                }
            
            logger.log(log_level, "Response:\n%s", 
                      json.dumps(log_msg, indent=2, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"Failed to log response: {str(e)}", exc_info=True)

def log_requests(logger: Optional[logging.Logger] = None,
                 log_level: int = logging.INFO,
                 max_body_length: int = 1000,
                 sensitive_fields: tuple = ('password', 'access_token', 'refresh_token')):
    """
    装饰器版本，可以装饰视图函数自动记录请求和响应
    
    使用示例:
    @app.route('/some-endpoint')
    @log_requests()
    def some_endpoint():
        return jsonify({"result": "success"})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            # 记录请求
            log_request_response(logger=logger, log_level=log_level, 
                               max_body_length=max_body_length,
                               sensitive_fields=sensitive_fields)
            
            # 执行视图函数
            response = f(*args, **kwargs)

            # 记录响应
            request.__dict__['response'] = response
            log_request_response(logger=logger, log_level=log_level,
                               max_body_length=max_body_length,
                               sensitive_fields=sensitive_fields)
            
            return response
        return decorated_function
    return decorator
    