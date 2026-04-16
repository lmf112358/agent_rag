"""
简单检查 QdrantClient 用法
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.environ["PYTHONPATH"] = str(project_root) + os.pathsep + str(project_root / "langchain_rag")

print("=" * 60)
print("检查 QdrantClient 用法")
print("=" * 60)

try:
    from langchain_rag.config.settings import config

    print(f"\n[1] 导入 qdrant_client...")
    import qdrant_client
    print(f"    qdrant_client 版本: {qdrant_client.__version__}")

    print(f"\n[2] 导入 QdrantClient...")
    from qdrant_client import QdrantClient

    print(f"\n[3] 创建客户端...")
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

    print(f"\n[4] QdrantClient 公开方法:")
    methods = [m for m in dir(client) if not m.startswith('_')]
    for m in sorted(methods):
        print(f"    - {m}")

    print(f"\n[5] 尝试列出集合...")
    collections = client.get_collections()
    print(f"    集合列表: {collections}")

    print(f"\n[6] 尝试获取集合信息...")
    try:
        info = client.get_collection(config.vectorstore.collection_name)
        print(f"    成功!")
        print(f"    info 类型: {type(info)}")
        print(f"    info 属性: {[a for a in dir(info) if not a.startswith('_')]}")
    except Exception as e:
        print(f"    失败: {e}")

    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)

except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()
