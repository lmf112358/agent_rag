"""
向量存储模块测试
"""
import pytest
from unittest.mock import MagicMock, patch

from langchain_rag.vectorstore.qdrant import (
    DashScopeEmbeddings,
    QdrantVectorStore,
    QdrantRetriever,
    QdrantVectorStoreFactory,
)


class TestDashScopeEmbeddings:
    """测试 DashScopeEmbeddings 类"""

    def test_initialization(self):
        """测试基本初始化（不实际调用 API）"""
        # patch 内部导入位置
        with patch("langchain_rag.vectorstore.qdrant.DashScopeEmbeddings._get_client"):
            embeddings = DashScopeEmbeddings(
                model_name="text-embedding-v3",
                api_key="test-key",
            )
            assert embeddings.model_name == "text-embedding-v3"
            assert embeddings.api_key == "test-key"

    def test_embed_query_delegates(self):
        """测试 embed_query 委托给 embed_documents"""
        # patch 内部导入位置
        with patch("langchain_rag.vectorstore.qdrant.DashScopeEmbeddings._get_client"):
            embeddings = DashScopeEmbeddings(api_key="test-key")
            # 不实际调用，只验证方法存在
            assert hasattr(embeddings, "embed_query")
            assert hasattr(embeddings, "embed_documents")
            assert hasattr(embeddings, "__call__")


class TestQdrantVectorStore:
    """测试 QdrantVectorStore 类（mock 客户端）"""

    @pytest.fixture
    def mock_client(self):
        """Mock Qdrant 客户端 fixture"""
        with patch("langchain_rag.vectorstore.qdrant.QdrantClient") as mock:
            yield mock.return_value

    @pytest.fixture
    def vectorstore(self, mock_client, mock_embeddings):
        """Mock 向量存储 fixture"""
        vs = QdrantVectorStore(
            host="localhost",
            port=6333,
            collection_name="test_collection",
            vector_dim=1536,
            embeddings=mock_embeddings,
        )
        vs.client = mock_client
        return vs

    def test_initialization(self, mock_embeddings):
        """测试基本初始化"""
        with patch("langchain_rag.vectorstore.qdrant.QdrantClient"):
            vs = QdrantVectorStore(
                host="localhost",
                port=6333,
                collection_name="test",
                vector_dim=1536,
                embeddings=mock_embeddings,
            )
            assert vs.collection_name == "test"
            assert vs.vector_dim == 1536

    def test_add_texts(self, vectorstore, mock_client):
        """测试添加文本"""
        texts = ["文本1", "文本2"]
        ids = vectorstore.add_texts(texts)

        assert len(ids) == 2
        # 验证 upsert 被调用
        assert mock_client.upsert.called

    def test_similarity_search(self, vectorstore, mock_client):
        """测试相似度搜索（mock 返回）"""
        # 模拟搜索结果
        mock_hit = MagicMock()
        mock_hit.payload = {
            "page_content": "搜索结果内容",
            "metadata": {"source": "test"},
        }
        mock_client.search.return_value = [mock_hit]

        docs = vectorstore.similarity_search("查询", k=3)

        assert len(docs) == 1
        assert mock_client.search.called

    def test_retriever_property(self, vectorstore):
        """测试 retriever 属性"""
        retriever = vectorstore.retriever
        assert isinstance(retriever, QdrantRetriever)

    def test_convert_filter(self, vectorstore):
        """测试过滤条件转换"""
        filter_dict = {"category": ["规范", "选型"], "source": "test.txt"}
        qdrant_filter = vectorstore._convert_filter(filter_dict)

        assert qdrant_filter is not None


class TestQdrantRetriever:
    """测试 QdrantRetriever 类"""

    @pytest.fixture
    def mock_vectorstore(self):
        """Mock 向量存储 fixture"""
        vs = MagicMock(spec=QdrantVectorStore)
        vs.similarity_search.return_value = []
        return vs

    def test_get_relevant_documents(self, mock_vectorstore):
        """测试获取相关文档"""
        retriever = QdrantRetriever(
            vectorstore=mock_vectorstore,
            k=5,
        )

        docs = retriever._get_relevant_documents(
            "查询",
            run_manager=MagicMock(),
        )

        assert mock_vectorstore.similarity_search.called


class TestQdrantVectorStoreFactory:
    """测试工厂类（不实际连接）"""

    def test_create_returns_instance(self, mock_embeddings):
        """测试 create 返回向量存储实例"""
        with patch("langchain_rag.vectorstore.qdrant.QdrantClient"):
            vs = QdrantVectorStoreFactory.create(
                collection_name="test_factory",
                embeddings=mock_embeddings,
            )
            assert isinstance(vs, QdrantVectorStore)
