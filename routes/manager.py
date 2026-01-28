from flask import Blueprint, render_template, jsonify, request, send_file, current_app, g
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shutil
from datetime import datetime
from werkzeug.utils import secure_filename
from . import login_required
from utils.storage import StorageManager
from error_code.JsonError import json_response

# 创建蓝图
manager_bp = Blueprint('manager', __name__)


@manager_bp.route('/manager/list/')
@login_required
def list_models():
    # 可以获取其他用户信息
    username = g.username
    
    data_dir = current_app.config.get('DATA_DIR', 'data')
    sm = StorageManager(data_dir)
    try:
        models = sm.list_models(username)
        return json_response(code=0, msg='获取模型列表成功', data={
            'models': [{ 'path': m['relpath'], 'url': m['url']} for m in models]
            }
        )  

    except Exception as e:
        current_app.logger.error(f"列出模型失败: {str(e)}", exc_info=True)
        return json_response(code=301, success=False, msg='获取模型列表失败', data={})





@manager_bp.route('/manager/delete/<path:model_name>', methods=['POST'])
@login_required
def delete_model(model_name):
    """删除指定的3D模型"""
    user_name = g.username
    
    data_dir = current_app.config.get('DATA_DIR', 'data')
    model_path = os.path.abspath(os.path.join(data_dir, user_name, model_name))
    user_dir = os.path.abspath(os.path.join(data_dir, user_name))

    sm = StorageManager(data_dir)

    # 防止路径穿越
    if not model_path.startswith(user_dir + os.sep) and os.path.basename(model_path) != model_name:
        return json_response(code=306, msg='非法的文件路径', data={}), 400

    if os.path.isfile(model_path):
        # If it's a file, remove its containing folder (so image folder + models)
        folder = os.path.dirname(model_path)
        try:
            if os.path.isdir(folder):
                # remove the entire folder containing this file
                shutil.rmtree(folder)
                # remove any indexed models under this folder
                try:
                    models = sm.list_models(user_name)
                    prefix = os.path.relpath(folder, user_dir).replace('\\', '/')
                    if not prefix.endswith('/'):
                        prefix = prefix + '/'
                    for m in models:
                        if m['relpath'].startswith(prefix):
                            sm.remove_model(user_name, m['relpath'])
                except Exception:
                    current_app.logger.exception('从索引移除模型失败')
                return json_response(code=0, msg='模型所在文件夹已删除', data={})
            else:
                # containing folder does not exist (file likely missing) — ensure xml record removed
                try:
                    sm.remove_model(user_name, model_name)
                except Exception:
                    current_app.logger.exception('从索引移除模型失败')
                return json_response(code=0, msg='模型文件不存在，已从索引移除记录', data={})
                
        except Exception as e:
            current_app.logger.exception('删除文件/文件夹失败')
            return json_response(code=307, msg='服务器内部错误', data={})

    elif os.path.isdir(model_path):
        try:
            shutil.rmtree(model_path)
            # remove any indexed models under this folder
            try:
                models = sm.list_models(user_name)
                prefix = model_name.rstrip('/') + '/'
                for m in models:
                    if m['relpath'].startswith(prefix):
                        sm.remove_model(user_name, m['relpath'])
            except Exception:
                current_app.logger.exception('从索引移除模型失败')
            return json_response(code=0, msg='模型删除成功', data={})
            
        except Exception as e:
            current_app.logger.exception('删除目录失败')
            return json_response(code=308, msg='服务器内部错误', data={})
    else:
        return json_response(code=309, msg='模型不存在', data={}), 404


@manager_bp.route('/manager/rename', methods=['POST'])
@login_required
def rename_model():
    """重命名用户模型文件。接受 JSON 或表单：{ old_name, new_name }"""
    user_name = g.username
    
    data = request.get_json(silent=True) or request.form
    old_name = data.get('old_name')
    new_name = data.get('new_name')

    if not old_name or not new_name:
        return json_response(code=310, msg='参数缺失', data={}), 400

    data_dir = current_app.config.get('DATA_DIR', 'data')
    sm = StorageManager(data_dir)
    try:
        # old_name is relpath; new_name is base name without extension
        new_rel = sm.rename_model(user_name, old_name, new_name)
        return json_response(code=0, msg='重命名成功', data={'new_name': new_rel})
        
    except FileNotFoundError:
        return json_response(code=310, msg='源文件不存在', data={}), 404

    except FileExistsError:
        return json_response(code=311, msg='目标文件已存在', data={}), 409

    except ValueError:
        return json_response(code=312, msg='非法的源文件路径', data={}), 400
    
    except Exception as e:
        current_app.logger.exception('重命名失败')
        return json_response(code=313, msg='服务器内部错误', data={}), 500