"""
Gunicorn 生产配置
使用方式: gunicorn -c gunicorn_conf.py backend.main:app
"""
import os
import multiprocessing

# 监听地址
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Worker 数量: (2 * CPU核数) + 1
workers = int(os.getenv("GUNICORN_WORKERS", (2 * multiprocessing.cpu_count()) + 1))

# Worker 类 (使用 UvicornWorker 处理 ASGI)
worker_class = "uvicorn.workers.UvicornWorker"

# 每个 Worker 的最大连接数
worker_connections = int(os.getenv("GUNICORN_MAX_CONNECTIONS", 1000))

# 超时时间 (秒)
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))

# Keep-Alive 时间 (秒)
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))

# 预加载应用代码
preload_app = os.getenv("GUNICORN_PRELOAD", "true").lower() in ("true", "1", "yes")

# 日志
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# 进程名称
proc_name = "agentic-rag-backend"


def on_starting(server):
    """Server 启动钩子"""
    server.log.info("Agentic RAG Backend starting...")


def when_ready(server):
    """Server 就绪钩子"""
    server.log.info(f"Agentic RAG Backend ready on {bind}")
    server.log.info(f"Workers: {workers}")


def on_exit(server):
    """Server 退出钩子"""
    server.log.info("Agentic RAG Backend shutting down...")
