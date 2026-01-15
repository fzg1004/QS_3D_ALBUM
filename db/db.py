import sqlite3

from config import Config 

# SQLite数据库路径
DB_PATH = Config.DATA_DIR / 'user.db'


# ========== 工具函数 ==========
def get_db_connection():
    """获取SQLite连接，返回字典格式结果"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化用户表（首次运行自动创建）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # 仅存储用户基础信息，不存JWT（JWT自身带签名和过期）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()
    
init_db()