from flask import Blueprint, render_template, jsonify, send_from_directory, send_file, current_app, g
import os
from . import login_required
from utils.storage import StorageManager
from error_code.JsonError import json_response
import urllib.parse

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



