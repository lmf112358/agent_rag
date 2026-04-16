"""
pytest 配置与 Fixtures
"""
import pytest
import os
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def sample_text():
    """示例文本 fixture"""
    return "这是一段用于测试的示例文本。空调系统设计需要遵循相关规范。"


@pytest.fixture(scope="session")
def sample_documents():
    """示例文档列表 fixture"""
    from langchain_core.documents import Document

    return [
        Document(
            page_content="空调系统设计规范：制冷性能系数(COP)不应低于6.0。",
            metadata={"source": "design_spec.txt", "category": "规范"},
        ),
        Document(
            page_content="设备选型要求：综合部分负荷值(IPLV)不应低于5.0。",
            metadata={"source": "equipment_spec.txt", "category": "选型"},
        ),
    ]


@pytest.fixture(scope="session")
def mock_embeddings():
    """Mock 嵌入向量 fixture"""
    from langchain_core.embeddings import Embeddings

    class MockEmbeddings(Embeddings):
        def embed_documents(self, texts):
            return [[0.1] * 1536 for _ in texts]

        def embed_query(self, text):
            return [0.1] * 1536

    return MockEmbeddings()
