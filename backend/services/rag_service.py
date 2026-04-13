"""
RAG服务
"""

from typing import Dict, Any, Optional, List
from langchain_rag.rag.retrieval import AdvancedRAGChain, ConversationalRAGChain
from langchain_rag.vectorstore.qdrant import QdrantVectorStore, DashScopeEmbeddings
from langchain_rag.llm.qwen import get_qwen_chat


class RAGService:
    """RAG服务"""

    def __init__(self):
        self.llm = get_qwen_chat()
        self.embeddings = DashScopeEmbeddings()
        self.vectorstore = QdrantVectorStore(
            host="localhost",
            port=6333,
            collection_name="agent_rag_knowledge",
            embeddings=self.embeddings
        )
        self.advanced_rag = AdvancedRAGChain(
            vectorstore=self.vectorstore,
            llm=self.llm
        )
        self.conv_rag = ConversationalRAGChain(
            vectorstore=self.vectorstore,
            llm=self.llm
        )

    def query(
        self,
        query: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行RAG查询"""
        result = self.advanced_rag.invoke(
            query,
            return_context=True
        )

        return {
            "answer": result.get("answer", ""),
            "sources": [
                {
                    "content": doc.page_content[:200] + "...",
                    "metadata": doc.metadata
                }
                for doc in result.get("context", [])
            ],
            "confidence": result.get("confidence", 0.0),
            "session_id": session_id
        }

    def conversational_query(
        self,
        query: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """对话式查询"""
        result = self.conv_rag.invoke(query)

        return {
            "answer": result.get("answer", ""),
            "sources": [
                {
                    "content": doc.page_content[:200] + "...",
                    "metadata": doc.metadata
                }
                for doc in result.get("source_documents", [])
            ],
            "session_id": session_id
        }
