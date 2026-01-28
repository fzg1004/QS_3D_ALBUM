#!/bin/bash
set -e  # 错误时退出，增强稳定性


# ========== 通用日志函数（核心封装） ==========
# 功能：1. 输出内容到控制台  2. 写入指定日志文件（自动带时间戳）
# 参数1：要打印/写入的日志内容
# 参数2：日志文件路径（可选，默认使用 SERVICE_LOG）
log_print() {
    # 定义时间戳格式（和你原格式一致）
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    # 日志内容（带时间戳）
    local log_content="[$timestamp] $1"
    # 日志文件（优先用传入的第二个参数，否则用全局变量 SERVICE_LOG）
    local log_file=${2:-${SERVICE_LOG}}

    # 1. 输出到控制台（stdout）
    echo -e "${log_content}"
    # 2. 写入日志文件（追加模式）
    if [ -n "${log_file}" ]; then
        # 确保日志目录存在
        mkdir -p $(dirname ${log_file}) || true
        echo -e "${log_content}" >> ${log_file}
    fi
}


# ========== 核心开关：是否使用Conda虚拟环境（true/false） ==========
USE_CONDA="false"  # false=不使用Conda，true=使用Conda

# ========== 基础配置（根据实际情况修改） ==========
# Conda配置（仅USE_CONDA=true时生效）
CONDA_ENV_NAME="QS3D_Album"                          # 你的Conda环境名
CONDA_SH_PATH="/usr/local/anaconda3/etc/profile.d/conda.sh"  # conda.sh路径



# 项目&服务配置（通用）
PROJECT_DIR="/home/fzg/QS_3D_ALBUM"  # 项目目录
HOST="0.0.0.0"                                 # 外部可访问
PORT="8090"                                   # 服务端口
WORKERS="4"                                    # 工作进程数
TIMEOUT="100"                                  # 超时时间



# Gunicorn路径（自动适配：Conda环境/系统路径）
# - USE_CONDA=true: 用Conda环境内的gunicorn
# - USE_CONDA=false: 用系统gunicorn（需提前安装）
GUNICORN_PATH=""
if [ "${USE_CONDA}" = "true" ]; then
    GUNICORN_PATH="/usr/local/anaconda3/envs/${CONDA_ENV_NAME}/bin/gunicorn"
else
    GUNICORN_PATH="$(which gunicorn)"  # 系统gunicorn路径
fi


# 日志配置（通用）
SCRIPT_DIR=$(cd $(dirname $0); pwd)
LOG_DIR="${SCRIPT_DIR}/logs"
SERVICE_LOG="${LOG_DIR}/flask_service.log"     # 监控日志
ACCESS_LOG="${LOG_DIR}/flask_access.log"       # 访问日志
ERROR_LOG="${LOG_DIR}/flask_error.log"         # 错误日志


# 进程唯一标识（避免误判）
SERVICE_TAG="QS_3D_ALBUM_8090"                # 自定义标签

# ========== 初始化准备 ==========
# 创建日志目录
mkdir -p ${LOG_DIR} || { echo "创建日志目录失败"; exit 1; }
# 写入启动日志
log_print "服务启动脚本初始化（USE_CONDA=${USE_CONDA}）..." 



# 校验Gunicorn路径
if [ ! -x "${GUNICORN_PATH}" ] && [ "${USE_CONDA}" = "false" ]; then
    log_print "ERROR: 系统未安装gunicorn，请执行 pip install gunicorn"
    exit 1
elif [ ! -x "${GUNICORN_PATH}" ] && [ "${USE_CONDA}" = "true" ]; then
    log_print "ERROR: Conda环境内未找到gunicorn（路径：${GUNICORN_PATH}）"
    exit 1
fi



# ========== 核心函数定义 ==========
# 函数1：激活环境（仅USE_CONDA=true时执行）
activate_env() {
    if [ "${USE_CONDA}" = "true" ]; then
        # 检查conda.sh是否存在
        if [ ! -f ${CONDA_SH_PATH} ]; then
            log_print "ERROR: Conda脚本不存在 ${CONDA_SH_PATH}"
            exit 1
        fi
        # 加载Conda并激活环境
        source ${CONDA_SH_PATH}
        conda activate ${CONDA_ENV_NAME} || {
            log_print "ERROR: 激活Conda环境失败"
            exit 1
        }
        log_print "Conda环境激活成功（${CONDA_ENV_NAME}）"
    fi
}



# 函数2：退出环境（仅USE_CONDA=true时执行）
deactivate_env() {
    if [ "${USE_CONDA}" = "true" ]; then
        conda deactivate
        log_print "Conda环境已退出"
    fi
}



# 函数3：启动服务（通用）
start_service() {
    # 激活环境（按需）
    activate_env

    # 切换到项目目录
    cd ${PROJECT_DIR} || {
        log_print "ERROR: 项目目录不存在 ${PROJECT_DIR}"
        exit 1
    }

    # 启动Gunicorn（后台运行+标签）
    log_print "启动服务... 监听 ${HOST}:${PORT}，Gunicorn路径：${GUNICORN_PATH}"
    ${GUNICORN_PATH} \
        --workers ${WORKERS} \
        --bind ${HOST}:${PORT} \
        --timeout ${TIMEOUT} \
        --access-logfile ${ACCESS_LOG} \
        --error-logfile ${ERROR_LOG} \
        --daemon \
        --name ${SERVICE_TAG} \
        "main:create_app()"

    # 验证启动结果
    if [ $? -eq 0 ]; then
        log_print "服务启动成功！进程标签：${SERVICE_TAG}"
    else
        log_print "ERROR: 服务启动失败"
        exit 1
    fi

    # 退出环境（按需）
    deactivate_env
}

# 函数4：检查进程是否存活（通用）
check_process() {
    PID=$(ps -ef | grep "gunicorn: master process \[${SERVICE_TAG}\]" | grep -v grep | awk '{print $2}')
    if [ -n "${PID}" ]; then
        return 0  # 进程存活
    else
        return 1  # 进程崩溃
    fi
}

# 函数5：停止服务（精准判断进程+分层清理，无残留）
stop_service() {
    # ========== 第一步：精准判断进程是否存在（多维度验证） ==========
    # 维度1：通过端口查找进程PID（最核心）
    PORT_PID=$(lsof -i :${PORT} | grep gunicorn | grep -v grep | awk '{print $2}')
    # 维度2：通过Gunicorn路径+启动文件查找所有关联PID（兜底）
    CMD_PIDS=$(ps -ef | grep "${GUNICORN_PATH}" | grep "main:create_app()" | grep -v grep | awk '{print $2}')

     # ===== 新增核心判断：两者都为空则直接退出 =====
    if [ -z "${PORT_PID}" ] && [ -z "${CMD_PIDS}" ]; then
        return 0  # 直接退出函数，不执行后续逻辑
    fi

    # 合并去重所有PID
    ALL_PIDS=$(echo -e "${PORT_PID}\n${CMD_PIDS}" | sort -u | grep -v "^$")

    # 核心判断：无进程则直接返回，避免无效操作
    if [ -z "${ALL_PIDS}" ]; then
        log_print "提示：服务未运行（端口${PORT}无进程，无关联Gunicorn进程）"
        return 0  # 无进程，正常退出函数
    fi

    # ========== 第二步：分层清理进程（先主后子，彻底无残留） ==========
    log_print "发现运行中的进程，PID列表：${ALL_PIDS}"

    # 1. 逐个杀死所有关联PID（强制杀）
    for pid in ${ALL_PIDS}; do
        if kill -9 ${pid} > /dev/null 2>&1; then
            log_print "成功杀死进程 PID: ${pid}"
        else
            log_print "警告：进程 ${pid} 已不存在或无权限杀死"
        fi
    done

    # 2. 等待2秒，让进程彻底退出
    sleep 2

    # 3. 终极兜底：强制释放端口（杀死所有占用该端口的进程，无论是不是gunicorn）
    if fuser -k -n tcp ${PORT} > /dev/null 2>&1; then
        log_print "强制释放端口 ${PORT} 完成"
    fi

    # ========== 第三步：验证清理结果（最终确认） ==========
    # 再次检查端口和进程
    AFTER_PORT_PID=$(lsof -i :${PORT} | grep gunicorn | grep -v grep | awk '{print $2}')
    AFTER_CMD_PIDS=$(ps -ef | grep "${GUNICORN_PATH}" | grep "main:create_app()" | grep -v grep | awk '{print $2}')
    AFTER_ALL_PIDS=$(echo -e "${AFTER_PORT_PID}\n${AFTER_CMD_PIDS}" | sort -u | grep -v "^$")

    if [ -z "${AFTER_ALL_PIDS}" ]; then
        log_print "成功：服务已彻底停止，端口${PORT}无残留进程"
    else
        log_print "警告：仍有残留进程 PID: ${AFTER_ALL_PIDS}，请手动清理"
    fi

}

# ========== 主逻辑：参数控制（启动/停止/监控） ==========
case "$1" in
    start)
        # 先停止残留进程，再启动
        stop_service
        start_service
        ;;
    stop)
        stop_service
        ;;
    monitor)
        log_print "启动服务监控（崩溃自动重启）..."
        # 先确保服务已启动
        if ! check_process; then
            log_print "服务未运行，先启动..."
            start_service
        fi
        # 循环监控（每5秒检查一次）
        while true; do
            if ! check_process; then
                # 进程崩溃，记录日志并重启
                log_print "ERROR: 服务崩溃！开始重启..."
                start_service
                sleep 10  # 重启后等待10秒，避免频繁重启
            fi
            sleep 5  # 每5秒检查一次
        done
        ;;
    *)
        echo "用法: $0 {start|stop|monitor}"
        echo "  start   - 启动服务（单次）"
        echo "  stop    - 停止服务"
        echo "  monitor - 启动服务并监控，崩溃自动重启"
        exit 1
        ;;
esac

exit 0