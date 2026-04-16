"""
检查 QdrantClient 实际可用的方法
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_rag.config.settings import config

print("=" * 60)
print("检查 QdrantClient 可用方法")
print("=" * 60)

try:
    from qdrant_client import QdrantClient

    print(f"\nQdrant host: {config.vectorstore.host}")
    print(f"Qdrant port: {config.vectorstore.port}")

    # 创建 client
    if config.vectorstore.host.startswith("http://") or config.vectorstore.host.startswith("https://"):
        client = QdrantClient(
            url=config.vectorstore.host,
            api_key=config.vectorstore.api_key or None,
        )
    else:
        client = QdrantClient(
            host=config.vectorstore.host,
            port=config.vectorstore.port,
            api_key=config.vectorstore.api_key or None,
        )

    print("\nQdrantClient 方法列表:")
    for attr in sorted(dir(client)):
        if not attr.startswith("_"):
            print(f"  - {attr}")

    print("\n尝试获取集合信息:")
    try:
        info = client.get_collection(config.vectorstore.collection_name)
        print(f"  成功! info 类型: {type(info)}")
        print(f"  info 属性: {[a for a in dir(info) if not a.startswith('_')]}")
    except Exception as e:
        print(f"  获取集合信息失败: {e}")

except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()
