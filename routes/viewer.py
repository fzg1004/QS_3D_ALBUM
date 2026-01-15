from flask import Blueprint, render_template, jsonify, send_from_directory, send_file, current_app, g
import os
from . import login_required
from utils.storage import StorageManager
from error_code.JsonError import json_response

# 创建查看器蓝图
viewer_bp = Blueprint('viewer', __name__)


def get_user_model_dir(username):
    data_dir = current_app.config.get('DATA_DIR', 'data')
    sm = StorageManager(data_dir)
    return sm.ensure_user(username)




@viewer_bp.route('/viewer')
@login_required
def viewer_page():
    """3D查看器主页面"""
    return render_template('viewer.html')


@viewer_bp.route('/viewer/<path:filename>')
@login_required
def serve_model(filename):
    
    username = g.username
    
    print(filename);
    
    data_dir = current_app.config.get('DATA_DIR', 'data')
    sm = StorageManager(data_dir)
    models_dir = sm.ensure_user(username)

    try:
        # 规范化路径，防止路径穿越攻击
        user_file_path = sm.get_full_path(username, filename)

        # Ensure requested file is inside the user's models directory
        if not user_file_path.startswith(models_dir + os.sep) and os.path.basename(user_file_path) != filename:
            current_app.logger.warning(f"Attempt to access file outside user dir: {user_file_path}")
            return json_response(code=302, msg='非法的文件路径', data={}), 400

        if os.path.isfile(user_file_path):
            # 返回文件内容（send_file 会处理 mime-type）
            current_app.logger.info(f"Serving model file: {user_file_path}")
            return send_file(user_file_path)
        
        else:
            return json_response(code=303, msg='模型文件不存在', data={}), 404
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        current_app.logger.error('Error serving model file: %s', tb)
        if current_app.debug:
            return json_response(code=304, msg='服务器内部错误', data={'error': str(e), 'trace': tb}), 500
        else:
            return json_response(code=305, msg='服务器内部错误', data={}), 500
            
