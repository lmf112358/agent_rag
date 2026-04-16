"""
RAG服务
"""
import os
import sys
import traceback
from pathlib import Path

# 确保项目根目录在路径中
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from typing import Dict, Any, Optional, List
from langchain_core.documents import Document

from langchain_rag.rag.retrieval import AdvancedRAGChain
from langchain_rag.vectorstore.qdrant import QdrantVectorStoreFactory
from langchain_rag.llm.qwen import get_qwen_chat
from langchain_rag.config.settings import config


class RAGService:
    """RAG服务 - 使用配置初始化，带优雅降级"""

    _instance: Optional["RAGService"] = None

    def __new__(cls):
        """单例模式，避免每次请求都初始化连接"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._error = None
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        print("[RAGService] 正在初始化...")
        try:
            # 从配置初始化各组件
            self.llm = get_qwen_chat()

            # 使用工厂创建 vectorstore（从 config 读取）
            print(f"[RAGService] 连接 Qdrant: {config.vectorstore.host}:{config.vectorstore.port}")
            self.vectorstore = QdrantVectorStoreFactory.create(
                collection_name=config.vectorstore.collection_name,
                vector_dim=config.vectorstore.vector_dim,
            )

            # 测试连接（获取集合信息）
            info = self.vectorstore.get_collection_info()
            if "error" in info:
                print(f"[RAGService] Qdrant 集合警告: {info['error']}")
            else:
                print(f"[RAGService] Qdrant 连接正常: {info}")

            # 创建 RAG 链
            self.advanced_rag = AdvancedRAGChain(
                vectorstore=self.vectorstore,
                llm=self.llm,
                retrieval_top_k=config.rag.retrieval_top_k,
                rerank_top_k=config.rag.rerank_top_k,
            )

            self._initialized = True
            print("[RAGService] 初始化完成")
        except Exception as e:
            self._error = str(e)
            print(f"[RAGService] 初始化失败: {self._error}")
            print(traceback.format_exc())

    def query(
        self,
        query: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行RAG查询"""
        if not self._initialized:
            return {
                "answer": f"服务初始化失败: {self._error}\n\n请检查 Qdrant 连接配置（langchain_rag/.env）。",
                "sources": [],
                "confidence": 0.0,
                "session_id": session_id
            }

        try:
            result = self.advanced_rag.invoke(
                query,
                return_context=True
            )

            # 安全获取 context 文档
            context_docs = result.get("context", []) or result.get("source_documents", [])

            return {
                "answer": result.get("answer", ""),
                "sources": [
                    {
                        "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                        "metadata": doc.metadata
                    }
                    for doc in context_docs
                ],
                "confidence": result.get("confidence", 0.0),
                "session_id": session_id
            }
        except Exception as e:
            print(f"[RAGService] 查询错误: {e}")
            print(traceback.format_exc())
            return {
                "answer": f"查询执行失败: {str(e)}",
                "sources": [],
                "confidence": 0.0,
                "session_id": session_id
            }
