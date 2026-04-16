"""
配置检查脚本
运行方式: python check_config.py
"""
import os
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 60)
print("Agentic RAG - 配置检查")
print("=" * 60)

# 1. 检查 .env 文件
print("\n[1/5] 检查配置文件...")
env_path = project_root / "langchain_rag" / ".env"
env_path_alt = project_root / ".env"

if env_path.exists():
    print(f"  OK: .env 文件存在 ({env_path})")
elif env_path_alt.exists():
    print(f"  OK: .env 文件存在 ({env_path_alt})")
    env_path = env_path_alt
else:
    print("  WARN: .env 文件不存在，正在从 .env.example 创建...")
    example_path = project_root / "langchain_rag" / ".env.example"
    if example_path.exists():
        import shutil
        shutil.copy(example_path, project_root / "langchain_rag" / ".env")
        print(f"  OK: 已从 {example_path} 复制")
        env_path = project_root / "langchain_rag" / ".env"
    else:
        print("  ERROR: 找不到 .env.example")

# 2. 检查环境变量
print("\n[2/5] 检查关键环境变量...")
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        env_content = f.read()

    has_dashscope = "DASHSCOPE_API_KEY" in env_content and "sk-" in env_content
    has_qdrant = "QDRANT_HOST" in env_content

    if has_dashscope:
        print("  OK: DASHSCOPE_API_KEY 已配置")
    else:
        print("  ERROR: DASHSCOPE_API_KEY 未配置或格式不正确")
        print("         请在 .env 中设置: DASHSCOPE_API_KEY=sk-你的APIKey")

    if has_qdrant:
        print("  OK: QDRANT_HOST 已配置")
    else:
        print("  WARN: QDRANT_HOST 未配置，将使用默认 localhost:6333")

# 3. 测试配置加载
print("\n[3/5] 测试配置模块加载...")
try:
    from langchain_rag.config.settings import config

    print(f"  OK: 配置加载成功")
    print(f"    - LLM Model: {config.llm.model_name}")
    print(f"    - Qdrant: {config.vectorstore.host}:{config.vectorstore.port}")
    print(f"    - Collection: {config.vectorstore.collection_name}")
    if config.vectorstore.api_key:
        print(f"    - Qdrant API Key: 已设置")
except Exception as e:
    print(f"  ERROR: 配置加载失败: {e}")
    sys.exit(1)

# 4. 测试关键模块导入
print("\n[4/5] 测试关键模块导入...")
modules_to_check = [
    ("langchain_rag.llm.qwen", "ChatQwen"),
    ("langchain_rag.vectorstore.qdrant", "QdrantVectorStoreFactory"),
    ("langchain_rag.rag.retrieval", "AdvancedRAGChain"),
    ("backend.services.rag_service", "RAGService"),
    ("backend.services.agent_service", "AgentService"),
]

all_ok = True
for module_name, class_name in modules_to_check:
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        print(f"  OK: {module_name}.{class_name}")
    except Exception as e:
        print(f"  ERROR: {module_name}.{class_name} - {e}")
        all_ok = False

# 5. 检查依赖
print("\n[5/5] 检查关键依赖...")
deps = [
    ("langchain", "langchain"),
    ("langchain_core", "langchain-core"),
    ("langgraph", "langgraph"),
    ("dashscope", "dashscope"),
    ("qdrant_client", "qdrant-client"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
]

for pkg_name, display_name in deps:
    try:
        __import__(pkg_name)
        print(f"  OK: {display_name}")
    except ImportError:
        print(f"  ERROR: {display_name} 未安装")
        all_ok = False

print("\n" + "=" * 60)
if all_ok:
    print("检查完成！配置基本正常，可以尝试启动服务。")
    print("\n启动方式:")
    print("  Windows: start.bat")
    print("  Linux/macOS: ./start.sh")
else:
    print("检查完成！存在错误，请先修复上述问题。")
print("=" * 60)
