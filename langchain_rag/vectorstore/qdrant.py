"""
Qdrant向量存储封装
支持通义千问Embedding，提供高效的向量检索能力
"""

from typing import List, Optional, Dict, Any, Tuple
from langchain.schema import Document, BaseRetriever
from langchain.callbacks.manager import CallbackManagerForRetrieverRun
from langchain.vectorstores.base import VectorStore
from langchain.embeddings.base import Embeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
import os
import json

from config.settings import config


class DashScopeEmbeddings(Embeddings):
    """通义千问文本嵌入封装"""

    def __init__(
        self,
        model_name: str = "text-embedding-v3",
        api_key: Optional[str] = None,
    ):
        try:
            from dashscope import TextEmbedding
        except ImportError:
            raise ImportError(
                "dashscope package is required. Install it: pip install dashscope"
            )

        self.model_name = model_name
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        if not self.api_key:
            raise ValueError("API key is required. Set DASHSCOPE_API_KEY environment variable.")
        self.client = None

    def _get_client(self):
        if self.client is None:
            from dashscope import TextEmbedding
            self.client = TextEmbedding(model=self.model_name, api_key=self.api_key)
        return self.client

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文档"""
        client = self._get_client()
        results = []
        for text in texts:
            response = client.call(text)
            if response.status_code != 200:
                raise ValueError(f"Embedding API error: {response.code} - {response.message}")
            embedding = response.output['embeddings'][0]['embedding']
            results.append(embedding)
        return results

    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        return self.embed_documents([text])[0]

    def __call__(self, text: str) -> List[float]:
        """支持直接调用"""
        return self.embed_query(text)


class QdrantVectorStore(VectorStore):
    """Qdrant向量存储封装类"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "agent_rag_knowledge",
        vector_dim: int = 1536,
        distance: str = "Cosine",
        api_key: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
    ):
        self.client = QdrantClient(
            host=host,
            port=port,
            api_key=api_key or config.vectorstore.qdrant_api_key or None,
        )
        self.collection_name = collection_name
        self.vector_dim = vector_dim
        self.distance = models.Distance[distance].value if isinstance(distance, str) else distance
        self.embeddings = embeddings

    def __del__(self):
        """清理资源"""
        if hasattr(self, 'client'):
            del self.client

    @classmethod
    def from_documents(
        cls,
        documents: List[Document],
        embeddings: Embeddings,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "agent_rag_knowledge",
        vector_dim: Optional[int] = None,
        distance: str = "Cosine",
        api_key: Optional[str] = None,
        batch_size: int = 100,
    ) -> "QdrantVectorStore":
        """从文档列表创建向量存储"""
        vector_dim = vector_dim or len(embeddings.embed_query("test"))
        instance = cls(
            host=host,
            port=port,
            collection_name=collection_name,
            vector_dim=vector_dim,
            distance=distance,
            api_key=api_key,
            embeddings=embeddings,
        )

        instance._create_collection_if_not_exists(vector_dim, distance)
        instance.add_documents(documents, batch_size=batch_size)
        return instance

    def _create_collection_if_not_exists(self, vector_dim: int, distance: str):
        """创建集合（如果不存在）"""
        try:
            self.client.get_collection(self.collection_name)
        except (UnexpectedResponse, Exception):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_dim,
                    distance=models.Distance[distance],
                ),
            )

    def add_documents(
        self,
        documents: List[Document],
        ids: Optional[List[str]] = None,
        batch_size: int = 100,
    ) -> List[str]:
        """添加文档到向量存储"""
        if not documents:
            return []

        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        embeddings = self.embeddings.embed_documents(texts)

        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]

        for i in range(0, len(documents), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]

            points = [
                models.PointStruct(
                    id=batch_ids[idx],
                    vector=batch_embeddings[idx],
                    payload={
                        "page_content": batch_texts[idx],
                        "metadata": batch_metadatas[idx],
                    },
                )
                for idx in range(len(batch_texts))
            ]

            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

        return ids

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Document]:
        """相似度搜索"""
        query_embedding = self.embeddings.embed_query(query)

        search_params = models.SearchParams(
            hnsw_algorithm=models.HnswSearchParams(ef=128)
        )

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=k,
            query_filter=self._convert_filter(filter) if filter else None,
            search_params=search_params,
            score_threshold=score_threshold,
        )

        return [
            Document(
                page_content=hit.payload["page_content"],
                metadata=hit.payload["metadata"],
            )
            for hit in results
        ]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        """带分数的相似度搜索"""
        query_embedding = self.embeddings.embed_query(query)

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=k,
            query_filter=self._convert_filter(filter) if filter else None,
            with_vectors=False,
        )

        return [
            (
                Document(
                    page_content=hit.payload["page_content"],
                    metadata=hit.payload["metadata"],
                ),
                hit.score,
            )
            for hit in results
        ]

    def similarity_search_by_vector(
        self,
        embedding: List[float],
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """通过向量搜索"""
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=embedding,
            limit=k,
            query_filter=self._convert_filter(filter) if filter else None,
        )

        return [
            Document(
                page_content=hit.payload["page_content"],
                metadata=hit.payload["metadata"],
            )
            for hit in results
        ]

    def _convert_filter(self, filter_dict: Dict[str, Any]) -> models.Filter:
        """转换过滤条件"""
        must_conditions = []
        for key, value in filter_dict.items():
            if isinstance(value, list):
                should_conditions = [
                    models.FieldCondition(
                        key=f"metadata.{key}",
                        match=models.MatchValue(value=v),
                    )
                    for v in value
                ]
                must_conditions.append(models.Filter(should=should_conditions))
            else:
                must_conditions.append(
                    models.FieldCondition(
                        key=f"metadata.{key}",
                        match=models.MatchValue(value=value),
                    )
                )
        return models.Filter(must=must_conditions) if must_conditions else None

    def delete_collection(self):
        """删除集合"""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass

    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
            }
        except Exception as e:
            return {"error": str(e)}

    @property
    def retriever(self) -> "QdrantRetriever":
        """获取检索器"""
        return QdrantRetriever(vectorstore=self)


class QdrantRetriever(BaseRetriever):
    """Qdrant检索器，用于LangChain Chain集成"""

    vectorstore: QdrantVectorStore
    k: int = 5
    filter: Optional[Dict[str, Any]] = None
    score_threshold: Optional[float] = None
    callback_manager: Optional[CallbackManagerForRetrieverRun] = None

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        """获取相关文档"""
        if self.score_threshold:
            return self.vectorstore.similarity_search(
                query,
                k=self.k,
                filter=self.filter,
                score_threshold=self.score_threshold,
            )
        return self.vectorstore.similarity_search(
            query,
            k=self.k,
            filter=self.filter,
        )


class QdrantVectorStoreFactory:
    """Qdrant向量存储工厂类"""

    _instance: Optional[QdrantVectorStore] = None

    @classmethod
    def create(
        cls,
        collection_name: str = "agent_rag_knowledge",
        embeddings: Optional[Embeddings] = None,
        vector_dim: int = 1536,
    ) -> QdrantVectorStore:
        """创建或获取向量存储实例"""
        cfg = config.vectorstore

        if embeddings is None:
            embeddings = DashScopeEmbeddings(
                model_name=config.embedding.model_name,
                api_key=config.embedding.api_key or os.getenv("DASHSCOPE_API_KEY", ""),
            )

        return QdrantVectorStore(
            host=cfg.host,
            port=cfg.port,
            collection_name=collection_name,
            vector_dim=vector_dim,
            distance=cfg.distance,
            embeddings=embeddings,
        )

    @classmethod
    def create_from_documents(
        cls,
        documents: List[Document],
        collection_name: str = "agent_rag_knowledge",
        embeddings: Optional[Embeddings] = None,
        batch_size: int = 100,
    ) -> QdrantVectorStore:
        """从文档创建向量存储"""
        vectorstore = cls.create(
            collection_name=collection_name,
            embeddings=embeddings,
        )
        vectorstore._create_collection_if_not_exists(
            vector_dim=vectorstore.vector_dim,
            distance=cfg.distance if (cfg := config.vectorstore) else "Cosine",
        )
        vectorstore.add_documents(documents, batch_size=batch_size)
        return vectorstore
