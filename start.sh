#!/bin/bash
# Agentic RAG - FastAPI 后端启动脚本 (Linux / macOS)
# 使用方式:
#   ./start.sh          # 开发模式 (带 reload)
#   ./start.sh prod     # 生产模式 (gunicorn + uvicorn workers)

set -e

echo "========================================"
echo "Agentic RAG Backend Startup"
echo "========================================"

# 检查 Python 是否可用
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python not found! Please activate your conda environment first."
    echo "Example: conda activate agent_rag"
    exit 1
fi

PYTHON_CMD=python
if ! command -v python &> /dev/null; then
    PYTHON_CMD=python3
fi

# 检查 .env 文件
if [ ! -f "langchain_rag/.env" ]; then
    if [ -f "langchain_rag/.env.example" ]; then
        echo "[INFO] Copying .env.example to .env"
        cp langchain_rag/.env.example langchain_rag/.env
    else
        echo "[WARN] .env file not found! Please create one from .env.example"
    fi
fi

# 设置 PYTHONPATH
export PYTHONPATH="$(pwd):$(pwd)/langchain_rag:$PYTHONPATH"
echo "[INFO] PYTHONPATH set to: $PYTHONPATH"

MODE=${1:-dev}

cd backend

if [ "$MODE" = "prod" ]; then
    # 生产模式: gunicorn + uvicorn workers
    echo ""
    echo "========================================"
    echo "Starting in PRODUCTION mode with Gunicorn..."
    echo "========================================"
    echo ""

    if ! command -v gunicorn &> /dev/null; then
        echo "[INFO] Installing gunicorn..."
        $PYTHON_CMD -m pip install gunicorn
    fi

    WORKERS=${WORKERS:-4}
    echo "[INFO] Using $WORKERS workers"

    exec gunicorn main:app \
        --workers $WORKERS \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:8000 \
        --access-logfile - \
        --error-logfile -
else
    # 开发模式: uvicorn --reload
    echo ""
    echo "========================================"
    echo "Starting in DEVELOPMENT mode with Uvicorn..."
    echo "API Docs: http://localhost:8000/docs"
    echo "========================================"
    echo ""

    exec $PYTHON_CMD -m uvicorn main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload
fi
