"""
Qdrant向量存储封装
支持通义千问Embedding，提供高效的向量检索能力
"""

from typing import Iterable, List, Optional, Dict, Any, Tuple
import uuid
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks.manager import CallbackManagerForRetrieverRun
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
import os

from langchain_rag.config.settings import config


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

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文档"""
        from dashscope import TextEmbedding

        results = []
        for text in texts:
            response = TextEmbedding.call(
                model=self.model_name,
                input=text,
                api_key=self.api_key,
            )
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
        distance: str = "COSINE",
        api_key: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
    ):
        # 支持带 https:// 或 http:// 的完整 URL
        if host.startswith("http://") or host.startswith("https://"):
            self.client = QdrantClient(
                url=host,
                api_key=api_key or config.vectorstore.api_key or None,
            )
        else:
            self.client = QdrantClient(
                host=host,
                port=port,
                api_key=api_key or config.vectorstore.api_key or None,
            )
        self.collection_name = collection_name
        self.vector_dim = vector_dim
        # Distance 枚举使用全大写 (COSINE/EUCLID/DOT/MANHATTAN)
        if isinstance(distance, str):
            # 支持多种写法: Cosine/cosine/COSINE -> COSINE
            dist_upper = distance.upper()
            if dist_upper in ["COSINE", "EUCLIDEAN"]:
                dist_upper = "COSINE"
            self.distance = models.Distance[dist_upper].value
        else:
            self.distance = distance
        # 使用内部变量存储 embeddings，覆盖基类的只读 property
        self._embeddings = embeddings

    @property
    def embeddings(self) -> Optional[Embeddings]:
        """获取 embeddings（覆盖基类只读 property）"""
        return self._embeddings

    def __del__(self):
        """清理资源"""
        if hasattr(self, 'client'):
            del self.client

    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "agent_rag_knowledge",
        vector_dim: Optional[int] = None,
        distance: str = "Cosine",
        api_key: Optional[str] = None,
        batch_size: int = 100,
        **kwargs: Any,
    ) -> "QdrantVectorStore":
        """从文本列表创建向量存储（VectorStore 抽象方法实现）"""
        vector_dim = vector_dim or len(embedding.embed_query("test"))
        instance = cls(
            host=host,
            port=port,
            collection_name=collection_name,
            vector_dim=vector_dim,
            distance=distance,
            api_key=api_key,
            embeddings=embedding,
        )
        instance._create_collection_if_not_exists(vector_dim, distance)
        instance.add_texts(texts, metadatas=metadatas, batch_size=batch_size)
        return instance

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
        **kwargs: Any,
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
        collection_exists = False
        try:
            self.client.get_collection(self.collection_name)
            collection_exists = True
        except Exception:
            # 集合不存在，需要创建
            pass

        if not collection_exists:
            # Distance 枚举使用全大写 (COSINE/EUCLID/DOT/MANHATTAN)
            if isinstance(distance, str):
                dist_upper = distance.upper()
                if dist_upper in ["COSINE", "EUCLIDEAN"]:
                    dist_upper = "COSINE"
                dist_enum = models.Distance[dist_upper]
            else:
                dist_enum = distance

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_dim,
                    distance=dist_enum,
                ),
            )

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        batch_size: int = 100,
        **kwargs: Any,
    ) -> List[str]:
        """将文本列表嵌入并写入 Qdrant（VectorStore 抽象方法实现）"""
        texts_list = list(texts)
        if not texts_list:
            return []

        if metadatas is None:
            metadatas = [{} for _ in texts_list]
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts_list]

        embeddings_list = self.embeddings.embed_documents(texts_list)

        for i in range(0, len(texts_list), batch_size):
            batch_slice = slice(i, i + batch_size)
            points = [
                models.PointStruct(
                    id=ids[i + j],
                    vector=embeddings_list[i + j],
                    payload={
                        "page_content": texts_list[i + j],
                        "metadata": metadatas[i + j],
                    },
                )
                for j in range(len(texts_list[batch_slice]))
            ]
            self.client.upsert(collection_name=self.collection_name, points=points)

        return ids

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
        return self.add_texts(texts, metadatas=metadatas, ids=ids, batch_size=batch_size)

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Document]:
        """相似度搜索（兼容不同版本的 QdrantClient）"""
        query_embedding = self.embeddings.embed_query(query)

        results = []

        # 尝试多种可能的搜索方法
        if hasattr(self.client, "search"):
            # 新版本 API
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=k,
            )
        elif hasattr(self.client, "query_points"):
            # 旧版本 API
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=k,
            ).points
        elif hasattr(self.client, "http") and hasattr(self.client.http, "points_api"):
            # 直接用底层 API
            from qdrant_client.http import models
            results = self.client.http.points_api.search_points(
                collection_name=self.collection_name,
                search_request=models.SearchRequest(
                    vector=query_embedding,
                    limit=k,
                    with_payload=True,
                ),
            ).result

        docs = []
        for hit in results:
            # 兼容不同的返回结构
            payload = {}
            if hasattr(hit, "payload"):
                payload = hit.payload or {}
            elif isinstance(hit, dict) and "payload" in hit:
                payload = hit["payload"] or {}

            page_content = payload.get("page_content", "")
            metadata = payload.get("metadata", {})
            docs.append(Document(page_content=page_content, metadata=metadata))
        return docs

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
            result = {
                "name": self.collection_name,
                "status": info.status if hasattr(info, "status") else "unknown",
            }
            # 安全访问可能不存在的字段
            if hasattr(info, "vectors_count"):
                result["vectors_count"] = info.vectors_count
            if hasattr(info, "points_count"):
                result["points_count"] = info.points_count
            if hasattr(info, "config") and hasattr(info.config, "params"):
                result["vector_size"] = info.config.params.vectors.size
            return result
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
        cfg = config.vectorstore
        vectorstore._create_collection_if_not_exists(
            vector_dim=vectorstore.vector_dim,
            distance=cfg.distance if cfg else "COSINE",
        )
        vectorstore.add_documents(documents, batch_size=batch_size)
        return vectorstore
