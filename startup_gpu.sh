#!/bin/bash

# ========== 1. 脚本基础配置（核心优化：日志目录自动创建） ==========
# 获取脚本所在绝对路径（无论在哪执行，路径都准确）
SCRIPT_DIR=$(cd $(dirname $0); pwd)
# 日志目录：脚本目录下的 logs 文件夹
LOG_DIR="${SCRIPT_DIR}/logs"
# 自动创建logs文件夹（-p：无则建，有则不报错）
mkdir -p ${LOG_DIR} || { echo "ERROR: 创建日志目录失败 ${LOG_DIR}"; exit 1; }

# ========== 2. Conda 环境配置 ==========
CONDA_ENV_NAME="QS3D_Album"  # 替换为实际环境名（如 py313）
# Conda启动脚本路径（根据实际安装路径调整，执行 find / -name conda.sh 可查找）
CONDA_SH_PATH="/usr/local/anaconda3/etc/profile.d/conda.sh" 

# 检查Conda脚本是否存在
if [ ! -f ${CONDA_SH_PATH} ]; then
    echo "ERROR: Conda启动脚本不存在 ${CONDA_SH_PATH}"
    exit 1
fi

# 加载Conda环境变量 + 激活指定虚拟环境
source ${CONDA_SH_PATH}
conda activate ${CONDA_ENV_NAME} || { echo "ERROR: 激活Conda环境 ${CONDA_ENV_NAME} 失败"; exit 1; }

# ========== 3. Gunicorn 核心配置（核心优化：外部可访问） ==========
PROJECT_DIR="/home/fzg25/project/QS_3D_ALBUM"  # 你的项目目录
# 关键改：0.0.0.0 监听服务器所有网卡（外部可访问），替代 127.0.0.1
HOST="0.0.0.0"  
PORT="21000"     # 保持端口不变（需确保服务器防火墙开放21000端口）
WORKERS="4"
TIMEOUT="300"

# 切换到项目目录
cd $PROJECT_DIR || { echo "ERROR: 项目目录不存在 ${PROJECT_DIR}"; exit 1; }

# ========== 4. 启动Gunicorn（日志路径+外部访问） ==========
# 激活环境后直接用gunicorn（无需绝对路径）
gunicorn \
  --workers $WORKERS \
  --bind ${HOST}:${PORT} \          # 0.0.0.0:21000 外部可访问
  --timeout $TIMEOUT \
  --access-logfile "${LOG_DIR}/flask_access.log" \  # 脚本目录/logs/下
  --error-logfile "${LOG_DIR}/flask_error.log" \    # 脚本目录/logs/下
  --daemon \  # 可选：后台运行（不加则前台运行，终端关闭则进程终止）
  "main:create_app()"  # 工厂函数启动格式（必须加引号）

# 验证启动结果
if [ $? -eq 0 ]; then
    echo "SUCCESS: Gunicorn启动成功！监听地址：${HOST}:${PORT}，日志目录：${LOG_DIR}"
else
    echo "ERROR: Gunicorn启动失败！"
    exit 1
fi

# 可选：退出Conda环境（脚本结束后自动退出，非必需）
#conda deactivate
