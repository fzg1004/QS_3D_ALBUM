#PyJWT
import jwt
import datetime
import os
from dotenv import load_dotenv
import bcrypt

from config import Config

# 加载环境变量
load_dotenv()

# JWT配置
JWT_SECRET = Config.JWT_SECRET_KEY
JWT_EXPIRE = Config.JWT_EXPIRE_SECONDS
def generate_jwt(user_id, username):
    """生成JWT令牌（包含用户ID和过期时间）"""
    payload = {
        'user_id': user_id,
        'user_name': username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=JWT_EXPIRE)
    }
    # 生成JWT
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    # 兼容pyjwt 2.x版本（返回bytes需转字符串）
    return token if isinstance(token, str) else token.decode('utf-8')

def verify_jwt(token):
    """验证JWT令牌，返回用户ID或None"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload.get('user_id')
    except jwt.ExpiredSignatureError:
        # 令牌过期
        return None
    except jwt.InvalidTokenError:
        # 令牌无效
        return None
    
    
def hash_password(plain_password):
    """明文密码加密（加盐哈希）"""
    # 生成盐值 + 哈希
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
    return password_hash.decode('utf-8')  # 转字符串存储

def verify_password(plain_password, password_hash):
    """验证明文密码是否匹配加密密码"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        password_hash.encode('utf-8')
    )
