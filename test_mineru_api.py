"""
测试MinerU官方API连接
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载.env文件
from dotenv import load_dotenv
load_dotenv("langchain_rag/.env")

print("=" * 60)
print("MinerU API 连接测试")
print("=" * 60)

# 读取配置
mineru_api_base = os.getenv("MINERU_API_BASE", "https://mineru.net")
mineru_api_key = os.getenv("MINERU_API_KEY", "")

print(f"\nAPI Base: {mineru_api_base}")
print(f"API Key: {'*' * len(mineru_api_key) if mineru_api_key else '未设置'}")
print(f"Is Cloud API: {bool(mineru_api_key)}")

# 测试初始化
from langchain_rag.document.mineru_client import MinerUClient

try:
    client = MinerUClient(
        api_base=mineru_api_base,
        api_key=mineru_api_key,
        timeout=300,
    )
    print("\nMinerUClient 初始化成功!")

    # 健康检查
    if client.health_check():
        print("健康检查: 通过")
    else:
        print("健康检查: 未通过 (云端API跳过此检查)")

    print(f"模型版本: {client.model_version}")
    print(f"轮询间隔: {client.poll_interval}s")
    print(f"最大轮询次数: {client.max_polls}")

    # 测试PDF文件路径
    test_pdf = "data/samples/tender/tender_sample.pdf"
    if os.path.exists(test_pdf):
        print(f"\n测试文件: {test_pdf}")
        print("文件存在，可以测试到“申请上传链接 + PUT上传”阶段。")
        print("\n注意: 当前还缺少 batch_id 对应的官方结果查询接口文档。")
        print("补全文档后即可完成完整解析链路。")
    else:
        print(f"\n警告: 测试文件不存在: {test_pdf}")

except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
