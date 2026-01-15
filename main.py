import mimetypes
from flask import Flask, logging
from flask_cors import CORS
import os
import logging

import jwt
from config import Config
from pathlib import Path

# 配置MIME类型
mimetypes.add_type('application/wasm', '.wasm')
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/javascript', '.mjs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_DIR / 'app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
    
def create_app():
    
    # 初始化配置
    Config.init_dirs()    
    
    """创建Flask应用工厂函数"""
    # 初始化Flask应用
    app = Flask(__name__, 
                static_folder='static',
                template_folder='templates')
    
    # 基础配置
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    app.config['ROOT_DIR'] = Config.BASE_DIR
    app.config['STATIC_DIR'] = Config.STATIC_DIR
    app.config['TEMPLATES_DIR'] = Config.TEMPLATE_DIR
    app.config['DATA_DIR'] = Config.DATA_DIR
    app.config['LOG_DIR'] = Config.LOG_DIR
    
    
    # 启用CORS
    CORS(app)
    
    # 导入并注册路由
    from routes.login import login_bp
    from routes.viewer import viewer_bp
    from routes.sharp import sharp_bp
    from routes.manager import manager_bp
    
    app.register_blueprint(viewer_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(sharp_bp)
    app.register_blueprint(manager_bp)
    
    return app


def main():
    """应用主入口"""
    app = create_app()
    
    print("=" * 50)
    print("Flask PLY 3D可视化服务器已启动！")
    print(f"访问地址：http://localhost:8090")
    print(f"静态文件目录：{app.config['STATIC_DIR']}")
    print(f"模板文件目录：{app.config['TEMPLATES_DIR']}")
    print("=" * 50)
    
    '''
    import jwt
    print(f"Module: {jwt}")
    print(f"Module file: {jwt.__file__}")
    print(f"Attributes: {dir(jwt)}")
    '''
    # 启动Flask服务
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
    
    

if __name__ == '__main__':
    main()