from flask import Blueprint, jsonify, request, session, redirect, url_for
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.tools import *

from db.db import *
from error_code.JsonError import json_response

# 创建登录蓝图
login_bp = Blueprint('login', __name__)


       
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

@login_bp.route('/logout')
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