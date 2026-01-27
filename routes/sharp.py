from flask import Blueprint, render_template, jsonify, request, session, current_app, g, send_file
import os
import sys
import urllib.parse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import threading
import time
import shutil
from datetime import datetime
from werkzeug.utils import secure_filename
from . import login_required
from config import Config
from trainer_image import ImageModelTrainer
from convert import convert as ply_convert
from pathlib import Path
from utils.storage import StorageManager
from error_code.JsonError import json_response

# 创建蓝图
sharp_bp = Blueprint('sharp', __name__)

# 存储任务状态的全局字典
sharp_tasks = {}

class TaskStatus:
    """任务状态跟踪"""
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    TRAINING = "training"
    COMPLETED = "completed"
    FAILED = "failed"

def update_task_status(task_id, status, message="", progress=0, result=None):
    """更新任务状态"""
    if task_id not in sharp_tasks:
        sharp_tasks[task_id] = {
            "status": status,
            "message": message,
            "progress": progress,
            "result": result,
            "created_at": time.time(),
            "updated_at": time.time()
        }
    else:
        sharp_tasks[task_id].update({
            "status": status,
            "message": message,
            "progress": progress,
            "result": result,
            "updated_at": time.time()
        })

# 允许的扩展名


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_IMAGE_EXTENSIONS

def generate_unique_filename(original_filename, username):
    """生成唯一的文件名"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ext = original_filename.rsplit('.', 1)[1].lower()
    unique_id = str(uuid.uuid4())[:8]
    return f"{username}_{timestamp}_{unique_id}.{ext}"

def get_user_image_dir(username):
    """获取用户图片目录"""
    data_dir = current_app.config.get('DATA_DIR', 'data')
    user_dir = os.path.join(data_dir, username, 'sharp_images')
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


@sharp_bp.route('/sharp')
@login_required
def sharp_page():
    """显示sharp页面
    username = session.get('username', 'Guest')
    return render_template('sharp.html', username=username)
    """
    return json_response(code=0, msg='sharp', data={})


@sharp_bp.route('/sharp/ping')
def sharping():
    return json_response(code=0, msg='sharp pong', data={})



@sharp_bp.route('/sharp/images', methods=['POST'])
@login_required
def upload_image():
     # 可以获取其他用户信息
    username = g.username

    if 'image' not in request.files:
        return json_response(code=401, msg='未找到上传的文件'), 400

    file = request.files['image']
    if file.filename == '':
        return json_response(code=402, msg='未选择文件'), 400
    
    if not allowed_file(file.filename):
        return json_response(code=403, msg='不支持的文件类型'), 400
    
    original_name = request.form.get('originalName', '')

    try:
        
        # create task
        task_id = str(uuid.uuid4())
        update_task_status(task_id, TaskStatus.UPLOADING, "正在上传文件......", 0)
        
        
        # save uploaded image into its own folder (username/<image_folder>/image.jpg)
        data_dir = current_app.config.get('DATA_DIR', 'data')
        sm = StorageManager(data_dir)
        rel_folder, filename_saved, save_path = sm.save_image(username, file, original_name)
        update_task_status(task_id, TaskStatus.PROCESSING, "正在处理图片...", 10)
       

        # start background processing thread
        t = threading.Thread(target=_run_sharp_task, args=(task_id, data_dir, save_path, username, rel_folder), daemon=True)
        t.start()
        
        #从状态字典中获取任务结果
        task = sharp_tasks.get(task_id)
        if not task:
            return json_response(code=405, msg='任务不存在'), 404
    
        result = task.get('result')
        return json_response(code=0, msg='上传成功', data={'taskId': task_id, "result": result})
    
    except Exception as e:
        current_app.logger.exception('上传图像失败')
        return json_response(code=404, msg='服务器错误: ' + str(e)), 500


def _run_sharp_task(task_id, data_dir,image_path, username, rel_folder):
    
    if Config.USE_GPU_SERVER : 
        update_task_status(task_id, TaskStatus.TRAINING, "正在重建...", 80)
    
        trainer = ImageModelTrainer()
        sm = StorageManager(data_dir)
        # image_path is the saved image file; sharp predict expects an input directory
        image_dir = os.path.dirname(image_path)
        # output directory should be the same image folder so generated ply sits alongside the image
        user_dir = os.path.join(data_dir, username)
        out_dir = os.path.join(user_dir, rel_folder)
        os.makedirs(out_dir, exist_ok=True)

        # call trainer with input directory and output directory
        training_result = trainer.train(image_dir, out_dir)
        if not training_result.get('success'):
            update_task_status(task_id, TaskStatus.FAILED, f"重建失败: {training_result.get('message')}", training_result.get('log', []))
            return

        update_task_status(task_id, TaskStatus.PROCESSING, "正在处理数据...", 10)
        out_dir = training_result.get('output_dir')

        # 查找输出目录中的 ply / ply.gz / splat 文件
        result_file = None
        try:
            for fname in os.listdir(out_dir):
                if fname.lower().endswith(('.ply', '.splat')):
                    result_file = fname
                    break
        except Exception:
            result_file = None

        if result_file:
            # 1) attempt conversion using convert.py (if available)
            try:
                teaser_full = os.path.join(out_dir, result_file)
                # determine output filename: base + _convert + ext
                base, ext = os.path.splitext(result_file)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                converted_name = f"{base}_{timestamp}{ext}"
                converted_full = os.path.join(out_dir, converted_name)
                #target_full = os.path.join(data_dir, Config.Target_File)

                print(f"input file : {teaser_full}")
                print(f"output file: {converted_full}")
                ply_convert(Path(teaser_full), Path(converted_full))
                
                # remove intermediate teaser file
                try:
                    os.remove(teaser_full)
                except Exception:
                    current_app.logger.exception('删除中间文件失败')
                
                # 尝试将转换后的文件重命名为与输出文件夹同名（保留扩展名），避免覆盖已有文件
                try:
                    folder_name = os.path.basename(out_dir.rstrip(os.sep))
                    new_name = f"{folder_name}{ext}"
                    new_full = os.path.join(out_dir, new_name)

                    if os.path.abspath(converted_full) != os.path.abspath(new_full):
                        # 若目标名已存在，则在其后追加时间戳以避免覆盖
                        if os.path.exists(new_full):
                            ts2 = datetime.now().strftime('%Y%m%d_%H%M%S')
                            new_name = f"{folder_name}_{ts2}{ext}"
                            new_full = os.path.join(out_dir, new_name)
                        os.replace(converted_full, new_full)
                        converted_name = new_name
                        converted_full = new_full
                except Exception:
                    current_app.logger.exception('重命名转换文件失败')

                # register converted file (use final converted_name)
                rel_converted = os.path.join(rel_folder, converted_name).replace('\\', '/')
                try:
                    sm.add_model(username, rel_converted)
                except Exception:
                    current_app.logger.exception('注册转换后模型失败')

                
                encoded_filename = urllib.parse.quote(rel_converted, safe='')
                viewer_link = f"{Config.CLOUD_SERVER}/viewer?model={encoded_filename}"
                update_task_status(task_id, TaskStatus.COMPLETED, "已完成", 100, result=viewer_link)


                
            except Exception as e:
                # conversion failed; still register original result and finish
                current_app.logger.exception('PLY 转换失败')
                rel = os.path.join(rel_folder, result_file).replace('\\', '/')
                update_task_status(task_id, TaskStatus.COMPLETED, f"完成（转换失败: {e}", 100, result=rel)
        else:
            # 若没有找到直接的模型文件，仍返回输出目录供人工查看
            update_task_status(task_id, TaskStatus.COMPLETED, "完成（未找到明确的模型文件，输出在目录）", 100, result=os.path.basename(out_dir))
    
    else:
        
        update_task_status(task_id, TaskStatus.TRAINING, "正在重建...", 20)
        time.sleep(10)
        
        update_task_status(task_id, TaskStatus.PROCESSING, "正在处理数据...", 50)
        time.sleep(10)
        
        # 原始文件名（带路径）
        original_filename = "20160915_IMG_0078/20160915_IMG_0078.ply"

        # 编码：整体编码，保留路径结构的同时处理特殊字符
        encoded_filename = urllib.parse.quote(original_filename, safe='')
        
        viewer_link = f"{Config.CLOUD_SERVER}/viewer?model={encoded_filename}"
        update_task_status(task_id, TaskStatus.COMPLETED, "已完成", 100, viewer_link)
        print(viewer_link)
  

@sharp_bp.route('/sharp/status/<task_id>')
@login_required
def sharp_status(task_id):
    task = sharp_tasks.get(task_id)
    if not task:
        return json_response(code=405, msg='任务不存在'), 404
    
    task_status = task.get('status')
    if task_status in ['completed', 'failed']:
        del sharp_tasks[task_id]  # 删除指定id的任务

    return json_response(code=0, msg='获取任务状态成功', data={'task': {
        'status': task.get('status'),
        'progress': task.get('progress', 0),
        'message': task.get('message', ''),
        'result': task.get('result')
    }})



@sharp_bp.route('/sharp/<path:filename>')
@login_required
def serve_model(filename):
    
    username = g.username
    decoded_filename = urllib.parse.unquote(filename)

    data_dir = current_app.config.get('DATA_DIR', 'data')
    sm = StorageManager(data_dir)
    models_dir = sm.ensure_user(username)

    try:
        # 规范化路径，防止路径穿越攻击
        user_file_path = sm.get_full_path(username, decoded_filename)
        print(user_file_path)

        # Ensure requested file is inside the user's models directory
        if not user_file_path.startswith(models_dir + os.sep) and os.path.basename(user_file_path) != decoded_filename:
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
            
            
