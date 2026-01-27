import mimetypes
from flask import Flask, logging
from flask_cors import CORS
import os
import logging

import jwt
from config import Config
from pathlib import Path
import ssl

# 配置MIME类型
mimetypes.add_type('application/wasm', '.wasm')
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/javascript', '.mjs')


# 1. 先检查并创建日志目录（核心新增逻辑）
log_dir = Config.LOG_DIR
# 兼容 Path 对象和字符串路径两种情况
if isinstance(log_dir, Path):
    log_dir_path = log_dir
else:
    log_dir_path = Path(log_dir)

# 检查目录是否存在，不存在则创建（mode=0o755 保证目录权限）
if not log_dir_path.exists():
    log_dir_path.mkdir(parents=True, exist_ok=True, mode=0o755)
    logging.warning(f"日志目录不存在，已自动创建：{log_dir_path.absolute()}")
    
    
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_DIR / 'app.log', encoding='utf-8'),
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
    if not Config.USE_GPU_SERVER : #* 启用业务服务器 */
        
        from routes.login import login_bp
        from routes.viewer import viewer_bp
        app.register_blueprint(viewer_bp)
        app.register_blueprint(login_bp)
        
    else :  #* 启用 GPU 服务*/
        from routes.manager import manager_bp
        from routes.sharp import sharp_bp
        
        app.register_blueprint(sharp_bp)
        app.register_blueprint(manager_bp)
    
    
    return app


def main():
    """应用主入口"""
    app = create_app()
    
    print("=" * 50)
    print("Flask PLY 3D可视化服务器已启动！")
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
    #app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG, ssl_context=(Config.SSL_CERT_FILE, Config.SSL_KEY_FILE))
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
    
    

if __name__ == '__main__':
    main()