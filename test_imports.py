#!/usr/bin/env python3
"""
测试脚本 - 验证所有模块导入是否正确
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """测试所有模块导入"""
    modules = [
        # 核心模块
        "langchain_rag.llm.qwen",
        "langchain_rag.vectorstore.qdrant",
        "langchain_rag.rag.retrieval",
        "langchain_rag.agent.core",
        "langchain_rag.tools.agent_tools",
        "langchain_rag.document.processor",
        "langchain_rag.config.settings",
        
        # 后端模块
        "backend.config.settings",
        "backend.services.rag_service",
        "backend.services.agent_service",
        "backend.services.memory_service",
        "backend.api.routes",
        "backend.main",
    ]

    print("开始测试模块导入...")
    print("=" * 60)

    success_count = 0
    failure_count = 0

    for module in modules:
        try:
            __import__(module)
            print(f"[OK] 成功导入: {module}")
            success_count += 1
        except Exception as e:
            print(f"[FAIL] 导入失败: {module}")
            print(f"   错误: {e}")
            failure_count += 1
        print("-" * 60)

    print("=" * 60)
    print(f"测试完成: 成功 {success_count}, 失败 {failure_count}")

    if failure_count == 0:
        print("所有模块导入成功!")
        return True
    else:
        print("存在导入失败的模块")
        return False


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
