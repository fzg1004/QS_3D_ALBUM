import random
import string
import requests
from flask import Blueprint, jsonify, request, session, redirect, url_for, request
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.tools import *

from db.db import *
from error_code.JsonError import json_response
from config import Config

# 创建登录蓝图
login_bp = Blueprint('login', __name__)


def get_wx_openid(code):
    # 替换为你的小程序AppID和AppSecret（公众平台开发设置里找）
    appid = Config.APPID
    appsecret = Config.APPSECRET
    # 微信官方接口，用code换openid
    url = f"https://api.weixin.qq.com/sns/jscode2session?appid={appid}&secret={appsecret}&js_code={code}&grant_type=authorization_code"
    
    try:
        # 核心：Flask中发送GET请求并解析JSON
        res = requests.get(url)
        res_data = res.json()  # 解析返回的JSON数据
        
        # 3. 处理返回结果
        openid = res_data.get('openid')
        return openid
        
    except Exception as e:
        return None
   

def generate_short_pwd(length=6):
    # 可选字符：数字+大小写字母（也可只保留数字）
    chars = string.digits + string.ascii_letters
    # 随机选择6个字符拼接
    return ''.join(random.choice(chars) for _ in range(length))       


@login_bp.route('/api/check-login', methods=['POST'])
def check_login():
    try:
        # 1. 接收小程序传递的token
        req_data = request.get_json() or {}
        token = req_data.get('token')
        
        # 2. 参数校验：无token直接返回失败
        if not token:
            return json_response(code=201, msg='缺少登录凭证（token）', data={})
        
        # 3. 验证JWT令牌
        user_id = verify_jwt(token)
        if not user_id:
            return json_response(code=202, msg='登录凭证无效/已过期，请重新登录', data={})
   
        
        # 4. 验证用户是否存在（兜底：防止JWT有效但用户被删除）
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username FROM user WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return json_response(code=203, msg='用户不存在，请重新登录', data={})

        
        # 5. 登录态有效 → 生成新token（刷新令牌，延长有效期）
        new_token = generate_jwt(user_id, username= user['username'])
        
        # 6. 返回成功结果
        return json_response(code=0, msg='登录状态验证成功', data={'token': new_token})
    
    # 全局异常捕获
    except Exception as e:
        print(f"接口异常：{str(e)}")
        return json_response(code=204, msg='服务器内部错误，请稍后重试', data={})
    
# ========== 可选：新增用户接口（用于测试） ==========
@login_bp.route('/api/register', methods=['POST'])
def register():
    """新增用户（密码自动加密）"""
    try:
        req_data = request.get_json() or {}
        username = req_data.get('username')
        password = req_data.get('password')

        if not username or not password:
            return json_response(code=205, msg='用户名和密码不能为空', data={})


        # 加密密码
        password_hash = hash_password(password)

        # 插入数据库
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO user (username, password) VALUES (?, ?)',
                (username, password_hash)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return json_response(code=206, msg='用户名已存在', data={})

        finally:
            cursor.close()
            conn.close()

        return json_response(code=0, msg='注册成功', data={})

    except Exception as e:
        print(f"注册接口异常：{str(e)}")
        return json_response(code=207, msg='服务器内部错误', data={})
        
        

@login_bp.route('/login', methods=['POST'])
def login_api():
    """用户登录接口：验证用户名+加密密码，返回JWT"""
    try:
        # 1. 接收前端参数
        req_data = request.get_json() or {}
        username = req_data.get('username')
        password = req_data.get('password')

        # 2. 参数校验
        if not username or not password:
            return json_response(code=208, msg='用户名和密码不能为空', data={})
              

        # 3. 查询用户（通过用户名）
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, password FROM user WHERE username = ?', (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        # 4. 验证用户和密码
        if not user:
            # 用户名不存在
            return json_response(code=209, msg='用户名或密码错误', data={})
        
        # 验证密码（明文 vs 加密）
        if not verify_password(password, user['password']):
            return json_response(code=210, msg='用户名或密码错误', data={})

        # 5. 生成JWT令牌
        token = generate_jwt(user['id'], username)

        # 6. 返回成功结果
        return json_response(code=0, msg='登录成功', data={
            'token': token,
            'username': username  # 可选：返回用户名给前端
        })

    except Exception as e:
        print(f"登录接口异常：{str(e)}")
        return json_response(code=211, msg='服务器内部错误', data={})


@login_bp.route('/wx-login', methods=['POST'])
def wx_login_api():
    """用户登录接口：验证用户名+加密密码，返回JWT"""
    try:
        # 1. 接收前端参数
        req_data = request.get_json() or {}
        wx_code = req_data.get('code')

        # 2. 参数校验
        if not wx_code :
            return json_response(code=213, msg='微信登录错误', data={})
              
        username = get_wx_openid(wx_code)
        if not username:
            return json_response(code=214, msg='微信登录错误', data={}) 
        
        
        # 3. 直接注册
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 查询user表，检查用户是否存在
        cursor.execute("SELECT id, username FROM user WHERE username = ?", (username,))
        existing_user = cursor.fetchone()


        if existing_user:
            # 用户已存在，使用现有用户信息
            user_id = existing_user[0]
            username = existing_user[1]
        else:
            # 用户不存在，插入新用户
            try:
                cursor.execute(
                    'INSERT INTO user (username, password) VALUES (?, ?)',
                    (username, generate_short_pwd())
                )
                user_id = cursor.lastrowid
                conn.commit()
                
            except Exception as e:
                conn.rollback()
                return json_response(code=215, msg='微信登录失败', data={}) 
            
            finally:
                cursor.close()
                conn.close()

        token = generate_jwt(user_id, username)

        # 6. 返回成功结果
        return json_response(code=0, msg='登录成功', data={
            'token': token,
            'username': username  # 可选：返回用户名给前端
        })

    except Exception as e:
        print(f"登录接口异常：{str(e)}")
        return json_response(code=211, msg='服务器内部错误', data={})

@login_bp.route('/logout', methods=['POST'])
def logout():
    """登出接口：JWT无服务端存储，仅做兜底验证"""
    try:
        # 1. 接收前端token（可选：验证token是否有效）
        req_data = request.get_json() or {}
        token = req_data.get('token')

        # 2. 验证token（仅日志记录，不影响登出）
        if token:
            user_id = verify_jwt(token)
            if user_id:
                print(f"用户{user_id}登出成功")

        # 3. 返回成功（前端需自行删除本地token）
        return json_response(code=200, msg='登出成功，请清除本地token', data={})
    
    except Exception as e:
        print(f"登出接口异常：{str(e)}")
        return json_response(code=212, msg='服务器内部错误', data={})
    

@login_bp.route('/ping')
def ping():
    """测试接口：用于测试接口是否正常"""
    return json_response(code=0, msg='pong', data={})