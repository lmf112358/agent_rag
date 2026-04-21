"""
测试环境变量配置是否正确加载
"""
import os
import sys

# 加载 .env 文件
from dotenv import load_dotenv

# 尝试加载不同位置的 .env
env_paths = [
    "langchain_rag/.env",
    "./langchain_rag/.env",
    "../langchain_rag/.env",
]

loaded = False
for path in env_paths:
    if os.path.exists(path):
        print(f"找到 .env 文件: {path}")
        load_dotenv(path)
        loaded = True
        break

if not loaded:
    print("警告: 未找到 .env 文件，将使用环境变量")
    load_dotenv()  # 尝试加载默认位置的 .env

print("\n" + "="*60)
print("环境变量配置检查")
print("="*60)

# 检查 MinerU 配置
mineru_base = os.getenv("MINERU_API_BASE", "未设置")
mineru_key = os.getenv("MINERU_API_KEY", "未设置")

print(f"\nMinerU 配置:")
print(f"  MINERU_API_BASE: {mineru_base}")
print(f"  MINERU_API_KEY: {'*' * len(mineru_key) if mineru_key != '未设置' else '未设置'}")

# 检查 DashScope 配置
dashscope_key = os.getenv("DASHSCOPE_API_KEY", "未设置")
print(f"\nDashScope 配置:")
print(f"  DASHSCOPE_API_KEY: {'*' * 10 + '...' if dashscope_key != '未设置' else '未设置'}")

# 检查 Qdrant 配置
qdrant_host = os.getenv("QDRANT_HOST", "未设置")
qdrant_port = os.getenv("QDRANT_PORT", "6333")
print(f"\nQdrant 配置:")
print(f"  QDRANT_HOST: {qdrant_host}")
print(f"  QDRANT_PORT: {qdrant_port}")

# 测试 MinerUClient 初始化
print("\n" + "="*60)
print("测试 MinerUClient 初始化")
print("="*60)

try:
    from langchain_rag.document.mineru_client import MinerUClient

    # 从环境变量读取配置
    mineru_api_base = os.getenv("MINERU_API_BASE", "http://localhost:8008")
    mineru_api_key = os.getenv("MINERU_API_KEY", "")

    # 测试从环境变量读取配置
    client = MinerUClient(
        api_base=mineru_api_base,
        api_key=mineru_api_key,
    )
    print(f"\nMinerUClient 初始化成功!")
    print(f"  API Base: {client.api_base}")
    print(f"  Is Cloud API: {client.is_cloud_api}")
    print(f"  API Key 已设置: {'是' if client.api_key else '否'}")

except Exception as e:
    print(f"\nMinerUClient 初始化失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("配置检查完成")
print("="*60)
