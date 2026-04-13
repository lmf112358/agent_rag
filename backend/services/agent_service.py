"""
Agent服务
"""

from typing import Dict, Any, Optional, List
from langchain_rag.agent.core import AgenticRAGAgent, ReActAgent
from langchain_rag.tools.agent_tools import get_all_tools
from langchain_rag.llm.qwen import get_qwen_chat
from langchain_rag.vectorstore.qdrant import QdrantVectorStore, DashScopeEmbeddings
from backend.services.memory_service import MemoryService


class AgentService:
    """Agent服务"""

    def __init__(self):
        self.llm = get_qwen_chat()
        self.embeddings = DashScopeEmbeddings()
        self.vectorstore = QdrantVectorStore(
            host="localhost",
            port=6333,
            collection_name="agent_rag_knowledge",
            embeddings=self.embeddings
        )
        self.tools = get_all_tools(
            vectorstore=self.vectorstore,
            llm=self.llm,
            historical_prices={
                "冷水机组": 500000,
                "冷却塔": 80000,
                "风机盘管": 3500,
            },
            supplier_whitelist=["格力", "美的", "麦克维尔", "开利"],
        )
        self.memory_service = MemoryService()
        self.agent = AgenticRAGAgent(
            llm=self.llm,
            tools=self.tools,
            max_iterations=5,
            confidence_threshold=0.75,
        )

    def invoke(
        self,
        query: str,
        session_id: Optional[str] = None,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """调用Agent"""
        # 调用Agent
        result = self.agent.invoke(query)
        
        # 保存到记忆
        if session_id:
            self.memory_service.add_message(session_id, "user", query)
            self.memory_service.add_message(session_id, "assistant", result.get("answer", ""))
        
        return {
            "answer": result.get("answer", ""),
            "intent": result.get("intent"),
            "confidence": result.get("confidence"),
            "needs_human_review": result.get("needs_human_review", False),
            "review_reason": result.get("review_reason"),
            "tool_results": result.get("tool_results"),
            "session_id": session_id
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出可用工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in self.tools
        ]

    def react_invoke(
        self,
        query: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """使用ReAct模式调用"""
        react_agent = ReActAgent(
            llm=self.llm,
            tools=self.tools,
            max_iterations=3,
        )
        
        result = react_agent.run(query)
        
        # 保存到记忆
        if session_id:
            self.memory_service.add_message(session_id, "user", query)
            self.memory_service.add_message(session_id, "assistant", result.get("answer", ""))
        
        return {
            "answer": result.get("answer", ""),
            "iterations": result.get("iterations"),
            "history": result.get("history"),
            "session_id": session_id
        }
