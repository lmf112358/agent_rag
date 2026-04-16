@echo off
REM Agentic RAG - FastAPI 后端启动脚本 (Windows)
REM 激活 conda 环境后运行: start.bat

echo ========================================
echo Agentic RAG Backend Startup (Windows)
echo ========================================

REM 检查 Python 是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please activate your conda environment first.
    echo Example: conda activate agent_rag
    pause
    exit /b 1
)

REM 检查 .env 文件
if not exist "langchain_rag\.env" (
    if exist "langchain_rag\.env.example" (
        echo [INFO] Copying .env.example to .env
        copy "langchain_rag\.env.example" "langchain_rag\.env"
    ) else (
        echo [WARN] .env file not found! Please create one from .env.example
    )
)

REM 设置 PYTHONPATH
set PYTHONPATH=%CD%;%CD%\langchain_rag;%PYTHONPATH%
echo [INFO] PYTHONPATH set to: %PYTHONPATH%

REM 启动 Uvicorn
echo.
echo ========================================
echo Starting FastAPI server with Uvicorn...
echo API Docs: http://localhost:8000/docs
echo ========================================
echo.

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
