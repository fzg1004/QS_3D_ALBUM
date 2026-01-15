from functools import wraps
from flask import g
import jwt
from flask import request, jsonify
from config import Config
def login_required(f):
    """登录装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从header获取token
        token = request.headers.get('token', '') or request.cookies.get('token') or request.args.get('token')
        if not token:
            return jsonify({'code': 501, 'msg': '缺少登录凭证', 'data': {}})
        
        try:
            # 验证JWT token
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
            # 可将用户信息存入g对象，供后续使用
            g.user_id = payload.get('user_id')
            g.username = payload.get('user_name')
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return jsonify({'code': 502, 'msg': 'token无效或已过期', 'data': {}})
        
        return f(*args, **kwargs)
    return decorated_function