import subprocess
import sys
import json
from pathlib import Path
import logging
import time
import os

# 导入你的Config配置（确保Config里包含修正后的conda和环境配置）
from config import Config

logger = logging.getLogger(__name__)

class ImageModelTrainer:
    """高斯溅射模型训练器（适配conda虚拟环境+环境变量）"""
    
    def __init__(self):
        # 从Config加载核心配置
        self.gs_repo_path = Config.GAUSSIAN_REPO_PATH  # 修正配置名（对应之前的GAUSSIAN_REPO_PATH）
        self.conda_base = Config.CONDA_BASE  # conda根目录 /usr/local/anaconda3
        self.gs_env = Config.GAUSSIAN_ENV  # 虚拟环境名 gaussian-splatting

    def _build_conda_command(self, cmd_list):
        """构建带conda激活+环境变量的完整命令"""
        # 1. 拼接环境变量export命令
        #env_commands = [f"export {k}='{v}'" for k, v in self.gs_exports.items()]
        # 2. Conda激活命令（系统级conda）
        activate_cmd = f"source {self.conda_base}/etc/profile.d/conda.sh && conda activate {self.gs_env}"
        # 3. 切换到项目目录
        cd_cmd = f"cd {self.gs_repo_path}"
        # 4. 拼接最终命令（用&&保证前一步成功才执行后一步）
        #full_cmd = " && ".join(env_commands + [activate_cmd, cd_cmd] + [" ".join(cmd_list)])
        full_cmd = " && ".join([activate_cmd, cd_cmd] + [" ".join(cmd_list)])
        return full_cmd

    def train(self, input_dir, output_dir):
        """训练高斯溅射模型（适配conda环境+环境变量）"""
        try:
           
            # 校验输入路径
            colmap_path = Path(input_dir).absolute()
            if not colmap_path.exists():
                raise ValueError(f"图片路径不存在: {input_dir}")
            
            # 确定输出目录
            if output_dir is None:
                output_dir = input_dir.parent
                
            output_dir = Path(output_dir).absolute()
            output_dir.mkdir(exist_ok=True)
            
            # (可选) 如果存在训练脚本可使用，否则直接调用 `sharp predict` CLI
            # 不再将训练脚本的存在性作为必须条件，允许直接使用系统中安装的 `sharp` 命令
                   
            
            # 构建基础训练命令（使用 sharp CLI）
            # 使用独立的词元避免在 shell 中出现解析问题
            base_train_cmd = [
                "sharp", "predict",
                '-i', str(input_dir),
                '-o', str(output_dir),
            ]
            
            # 构建带conda激活和环境变量的完整命令
            full_train_cmd = self._build_conda_command(base_train_cmd)
            logger.info(f"开始重建模型（conda环境）: {full_train_cmd}")
            
            # 运行训练（必须用shell=True执行bash命令）
            process = subprocess.Popen(
                full_train_cmd,
                shell=True,  # 关键：执行bash命令（conda激活需要）
                executable="/bin/bash",  # 核心新增：指定bash执行
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 将stderr重定向到stdout，统一捕获
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=self.gs_repo_path,  # 工作目录设为高斯溅射项目根目录
                env=os.environ.copy()  # 继承当前环境变量
            )
            
            # 实时监控训练输出
            training_log = []
            start_time = time.time()
            logger.info(f"启动重建，输出目录: {output_dir}")
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    output_strip = output.strip()
                    training_log.append(output_strip)
                    logger.info(f"重建日志 [{time.strftime('%H:%M:%S')}]: {output_strip}")
            
            # 等待进程结束并获取返回码
            return_code = process.wait()
            elapsed_time = time.time() - start_time
            logger.info(f"重建进程结束，返回码: {return_code}，耗时: {elapsed_time:.2f}秒")
            
            # 检查重建是否成功
            if return_code != 0:
                error_msg = f"重建进程返回非0码: {return_code}，最后10行日志: {training_log[-10:]}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
           

            return {
                'success': True,
                'output_dir': str(output_dir.absolute()),
                'log': training_log[-10:],  # 返回最后10行日志
                'elapsed_time': round(elapsed_time, 2),
                'message': '模型重建完成'
            }
            
        except Exception as e:
            error_msg = f"重建失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'log': training_log[-10:] if 'training_log' in locals() else []
            }