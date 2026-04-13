"""
启动脚本 - 快速启动整个系统
"""

import subprocess
import os
import time
import sys

def start_backend():
    """启动后端服务"""
    print("\n启动后端服务...")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    return backend_process

def start_frontend():
    """启动前端服务"""
    print("\n启动前端服务...")
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
    frontend_process = subprocess.Popen(
        ["python", "-m", "http.server", "3000"],
        cwd=frontend_dir
    )
    return frontend_process

def main():
    """主函数"""
    print("=" * 60)
    print("Agentic RAG 系统启动脚本")
    print("=" * 60)

    # 启动后端
    backend_process = start_backend()
    
    # 等待后端启动
    print("\n等待后端服务启动...")
    time.sleep(3)

    # 启动前端
    frontend_process = start_frontend()

    print("\n" + "=" * 60)
    print("系统已启动:")
    print("- 后端API: http://localhost:8000")
    print("- 前端界面: http://localhost:3000")
    print("- API文档: http://localhost:8000/docs")
    print("=" * 60)

    try:
        # 保持脚本运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        backend_process.terminate()
        frontend_process.terminate()
        print("服务已停止")

if __name__ == "__main__":
    main()
