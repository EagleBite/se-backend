from flask import jsonify
from typing import Optional, Dict, Any

class ApiResponse:
    """统一API响应格式"""
    def __init__(self, code: int, message: str, data: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.data = data if data is not None else {}

    def set_code(self, code: int) -> 'ApiResponse':
        """设置响应状态码"""
        self.code = code
        return self
    
    def set_message(self, message: str) -> 'ApiResponse':
        """设置响应消息"""
        self.message = message
        return self
    
    def set_data(self, data: Dict[str, Any]) -> 'ApiResponse':
        """设置响应数据"""
        self.data = data
        return self
    
    def set_error(self, error: str, code: int = 400) -> 'ApiResponse':
        """设置错误信息"""
        self.code = code
        self.message = error
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "data": self.data
        }
    
    def to_json_response(self, http_status: int = 200) -> str:
        """将响应转换为JSON格式"""
        return jsonify(self.to_dict()), http_status
    
    @classmethod
    def success(cls, message: str = "成功", data: Optional[Dict[str, Any]] = None) -> 'ApiResponse':
        """成功响应"""
        return cls(200, message, data)
    
    @classmethod
    def error(cls, message: str = "失败", code: int = 400) -> 'ApiResponse':
        """错误响应"""
        return cls(code, message)