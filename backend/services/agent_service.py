"""
Agent服务
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

from langchain_rag.agent.core import AgenticRAGAgent, ReActAgent
from langchain_rag.tools.agent_tools import get_all_tools
from langchain_rag.llm.qwen import get_qwen_chat
from langchain_rag.vectorstore.qdrant import QdrantVectorStoreFactory
from langchain_rag.config.settings import config
from backend.services.memory_service import MemoryService


class AgentService:
    """Agent服务 - 使用配置初始化，带优雅降级"""

    _instance: Optional["AgentService"] = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._error = None
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        print("[AgentService] 正在初始化...")
        try:
            # 从配置初始化
            self.llm = get_qwen_chat()

            print(f"[AgentService] 连接 Qdrant: {config.vectorstore.host}:{config.vectorstore.port}")
            self.vectorstore = QdrantVectorStoreFactory.create(
                collection_name=config.vectorstore.collection_name,
                vector_dim=config.vectorstore.vector_dim,
            )

            # 测试连接
            info = self.vectorstore.get_collection_info()
            if "error" in info:
                print(f"[AgentService] Qdrant 集合警告: {info['error']}")
            else:
                print(f"[AgentService] Qdrant 连接正常: {info}")

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
                max_iterations=config.agent.max_iterations,
                confidence_threshold=config.agent.confidence_threshold,
            )
            self._initialized = True
            print("[AgentService] 初始化完成")
        except Exception as e:
            self._error = str(e)
            print(f"[AgentService] 初始化失败: {self._error}")
            print(traceback.format_exc())

    def invoke(
        self,
        query: str,
        session_id: Optional[str] = None,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """调用Agent"""
        if not self._initialized:
            return {
                "answer": f"服务初始化失败: {self._error}\n\n请检查 Qdrant 连接配置（langchain_rag/.env）。",
                "intent": None,
                "confidence": 0.0,
                "needs_human_review": True,
                "review_reason": "服务初始化失败",
                "tool_results": None,
                "session_id": session_id
            }

        try:
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
        except Exception as e:
            print(f"[AgentService] 调用错误: {e}")
            print(traceback.format_exc())
            return {
                "answer": f"Agent 调用失败: {str(e)}",
                "intent": None,
                "confidence": 0.0,
                "needs_human_review": True,
                "review_reason": "调用异常",
                "tool_results": None,
                "session_id": session_id
            }

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出可用工具"""
        if not self._initialized:
            return []

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
        if not self._initialized:
            return {
                "answer": f"服务初始化失败: {self._error}",
                "iterations": 0,
                "history": [],
                "session_id": session_id
            }

        try:
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
        except Exception as e:
            print(f"[AgentService] ReAct 调用错误: {e}")
            print(traceback.format_exc())
            return {
                "answer": f"ReAct 调用失败: {str(e)}",
                "iterations": 0,
                "history": [],
                "session_id": session_id
            }
