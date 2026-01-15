from flask import jsonify
from typing import Any, Optional, Union, Dict, List

def json_response(code: int = 200, 
                  msg: str = "操作成功", 
                  data: Optional[Any] = None,) -> Dict:
    """
    统一的JSON响应函数
    
    Args:
        code: HTTP状态码/业务状态码
        message: 提示信息
        data: 返回的数据（任意类型）
        success: 操作是否成功（可选，根据code自动判断）
    
    Returns:
        Flask JSON Response
    """
    
    response_data = {
        'code': code,
        'msg': msg,
        'data': data if data is not None else {}  # 确保data不为None
    }
    
    return jsonify(response_data)