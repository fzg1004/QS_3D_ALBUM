import os
from pathlib import Path

class Config:
    # 基础配置
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = BASE_DIR / "logs"
    STATIC_DIR = BASE_DIR / "static"
    TEMPLATE_DIR = BASE_DIR / "templates"
    SSL_DIR = BASE_DIR / "key"

    #https证书相关
    SSL_CERT_FILE = SSL_DIR / "jumeijiacn.com_bundle.crt"
    SSL_KEY_FILE = SSL_DIR / "jumeijiacn.com.key"

    #小程序登录相关
    APPID = "wxacab755fe2f98821"
    APPSECRET = "89a32aeebfe95ed226b32b23ed41db43"

    # JWT配置
    JWT_SECRET_KEY = "your-jwt-secret-key-change-this"
    JWT_EXPIRE_SECONDS = 1296000
    
    # 服务器配置
    HOST = "0.0.0.0"; #"www.jumeijiacn.com"
    PORT = 8090;# 443
    
    CLOUD_SERVER = "https://www.jumeijiacn.com";

    DEBUG = True
    
    USE_GPU_SERVER = False  #启用GPU服务器进行模型转换
    
    # 文件上传配置
    MAX_VIDEO_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
    UPLOAD_VIDEO_CHUNK_SIZE = 8192
    
    MAX_IMAGE__CONTENT_LENGTH = 30 * 1024 * 1024  # 500MB
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'jfif'}
    
    Target_File = "train.ply"
    
    # ==================== Conda 环境基础配置 ====================
    # Conda根路径（可通过 `conda info --base` 命令获取）
    CONDA_BASE = Path("/usr/local/anaconda3")  # 替换为你的conda根目录
   

    # ==================== 高斯泼溅项目配置 ====================
    # 高斯泼溅项目仓库路径
    GAUSSIAN_REPO_PATH = Path("/home/fzg25/project/ml-sharp")
    #虚拟环境名
    GAUSSIAN_ENV = "sharp"
    

    
    # 用户会话配置
    SECRET_KEY = "your-secret-key-change-this"
    
    @classmethod
    def init_dirs(cls):
        """初始化必要的目录"""
        dirs = [cls.DATA_DIR, cls.LOG_DIR, cls.STATIC_DIR, cls.TEMPLATE_DIR]
        for dir_path in dirs:
            dir_path.mkdir(exist_ok=True)
    
    @classmethod
    def get_user_dir(cls, username):
        """获取用户目录"""
        user_dir = cls.DATA_DIR / username
        user_dir.mkdir(exist_ok=True)
        return user_dir
    
    @classmethod
    def get_video_dir(cls, username, filename):
        """获取视频文件目录"""
        video_dir = cls.get_user_dir(username) / filename
        video_dir.mkdir(exist_ok=True)
        return video_dir

config = Config()