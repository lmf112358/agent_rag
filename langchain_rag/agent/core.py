"""
Agent核心模块
基于LangGraph实现Agent状态机和ReAct Pattern
支持Human-in-the-Loop容错机制
"""

from typing import TypedDict, Annotated, Sequence, Literal, Optional, Dict, Any, List, Union, Callable
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.tools import BaseTool, Tool
from langchain.graph import StateGraph, END
from pydantic import BaseModel, Field
from enum import Enum
import operator


class AgentState(TypedDict):
    """Agent状态定义"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    current_query: str
    intent: Optional[str]
    selected_tools: Optional[List[str]]
    tool_results: Optional[Dict[str, Any]]
    confidence: Optional[float]
    needs_human_review: bool
    review_reason: Optional[str]
    iteration_count: int
    final_answer: Optional[str]


class Intent(str, Enum):
    """意图识别枚举"""
    KNOWLEDGE_QUERY = "knowledge_query"
    QUOTE_VALIDATION = "quote_validation"
    COMPLIANCE_CHECK = "compliance_check"
    GENERAL_CHAT = "general_chat"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """置信度等级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ToolExecutionResult(BaseModel):
    """工具执行结果"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HumanReviewRequest(BaseModel):
    """人工审核请求"""
    reason: str
    context: Dict[str, Any]
    options: List[str] = ["采纳AI建议", "修正后采纳", "完全人工重做"]
    priority: Literal["low", "medium", "high"] = "medium"


class AgenticRAGAgent:
    """Agentic RAG Agent - 基于LangGraph"""

    def __init__(
        self,
        llm: Any,
        tools: List[BaseTool],
        max_iterations: int = 10,
        confidence_threshold: float = 0.75,
    ):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools}
        self.max_iterations = max_iterations
        self.confidence_threshold = confidence_threshold
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """构建状态图"""
        graph = StateGraph(AgentState)

        graph.add_node("intent_recognition", self._intent_recognition_node)
        graph.add_node("route_to_tools", self._route_to_tools_node)
        graph.add_node("execute_tool", self._execute_tool_node)
        graph.add_node("evaluate_result", self._evaluate_result_node)
        graph.add_node("generate_response", self._generate_response_node)
        graph.add_node("human_review", self._human_review_node)

        graph.set_entry_point("intent_recognition")

        graph.add_edge("intent_recognition", "route_to_tools")
        graph.add_edge("route_to_tools", "execute_tool")
        graph.add_edge("execute_tool", "evaluate_result")

        graph.add_conditional_edges(
            "evaluate_result",
            self._should_continue_or_review,
            {
                "continue": "generate_response",
                "retry": "execute_tool",
                "human_review": "human_review",
            }
        )

        graph.add_edge("generate_response", END)
        graph.add_edge("human_review", END)

        return graph.compile()

    def _intent_recognition_node(self, state: AgentState) -> AgentState:
        """意图识别节点"""
        query = state["current_query"]

        intent_prompt = f"""请分析用户查询的意图，从以下类别中选择最匹配的:

1. knowledge_query: 需要查询企业知识库的问题
2. quote_validation: 需要复核投标报价是否合理
3. compliance_check: 需要检查投标方案是否符合规范
4. general_chat: 一般性对话或问候
5. unknown: 无法确定意图

用户查询: {query}

请直接输出意图类别(只需英文类别名，不要其他内容):"""

        response = self.llm.invoke([HumanMessage(content=intent_prompt)])
        intent = response.content.strip().lower()

        if intent not in [e.value for e in Intent]:
            intent = Intent.UNKNOWN

        state["intent"] = intent
        return state

    def _route_to_tools_node(self, state: AgentState) -> AgentState:
        """根据意图选择工具"""
        intent = state.get("intent", Intent.UNKNOWN)

        tool_mapping = {
            Intent.KNOWLEDGE_QUERY: ["knowledge_retriever"],
            Intent.QUOTE_VALIDATION: ["quote_validator"],
            Intent.COMPLIANCE_CHECK: ["compliance_checker"],
            Intent.GENERAL_CHAT: [],
            Intent.UNKNOWN: ["knowledge_retriever"],
        }

        selected = tool_mapping.get(intent, ["knowledge_retriever"])
        state["selected_tools"] = selected
        return state

    def _execute_tool_node(self, state: AgentState) -> AgentState:
        """执行工具"""
        query = state["current_query"]
        selected_tools = state.get("selected_tools", [])
        tool_results = {}

        for tool_name in selected_tools:
            if tool_name in self.tools:
                try:
                    tool = self.tools[tool_name]
                    result = tool.invoke(query)
                    tool_results[tool_name] = ToolExecutionResult(
                        success=True,
                        result=result,
                        confidence=0.85,
                    )
                except Exception as e:
                    tool_results[tool_name] = ToolExecutionResult(
                        success=False,
                        error=str(e),
                        confidence=0.0,
                    )

        state["tool_results"] = tool_results
        return state

    def _evaluate_result_node(self, state: AgentState) -> AgentState:
        """评估结果"""
        tool_results = state.get("tool_results", {})

        if not tool_results:
            state["confidence"] = 0.0
            state["needs_human_review"] = True
            state["review_reason"] = "没有获取到任何结果"
            return state

        confidences = [r.confidence for r in tool_results.values() if r.success]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        state["confidence"] = avg_confidence

        if avg_confidence >= self.confidence_threshold:
            state["needs_human_review"] = False
        else:
            state["needs_human_review"] = True
            state["review_reason"] = f"置信度({avg_confidence:.2f})低于阈值({self.confidence_threshold})"

        iteration = state.get("iteration_count", 0)
        if iteration >= self.max_iterations:
            state["needs_human_review"] = True
            state["review_reason"] = "已达到最大迭代次数"

        return state

    def _should_continue_or_review(
        self, state: AgentState
    ) -> Literal["continue", "retry", "human_review"]:
        """判断下一步"""
        if state.get("needs_human_review", False):
            return "human_review"

        tool_results = state.get("tool_results", {})
        all_success = all(r.success for r in tool_results.values()) if tool_results else False

        if all_success and state.get("confidence", 0) >= self.confidence_threshold:
            return "continue"

        iteration = state.get("iteration_count", 0)
        if iteration < self.max_iterations:
            return "retry"

        return "human_review"

    def _generate_response_node(self, state: AgentState) -> AgentState:
        """生成最终响应"""
        query = state["current_query"]
        tool_results = state.get("tool_results", {})
        intent = state.get("intent")

        context_parts = []
        for tool_name, result in tool_results.items():
            if result.success and result.result:
                context_parts.append(f"[{tool_name}]: {result.result}")

        context = "\n\n".join(context_parts)

        system_prompt = f"""你是一个专业的工业暖通空调领域AI助手。基于检索到的信息回答用户问题。

意图类型: {intent}
检索结果:
{context}

要求:
1. 准确、专业地回答问题
2. 引用相关数据来源
3. 如有不一致，明确指出
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]

        response = self.llm.invoke(messages)
        state["final_answer"] = response.content
        return state

    def _human_review_node(self, state: AgentState) -> AgentState:
        """人工审核节点"""
        review_reason = state.get("review_reason", "需要人工审核")
        tool_results = state.get("tool_results", {})

        context = {
            "original_query": state["current_query"],
            "intent": state.get("intent"),
            "tool_results": {
                name: {
                    "success": r.success,
                    "result": r.result if r.success else None,
                    "error": r.error if not r.success else None,
                }
                for name, r in tool_results.items()
            },
            "confidence": state.get("confidence"),
        }

        review_request = HumanReviewRequest(
            reason=review_reason,
            context=context,
        )

        state["final_answer"] = f"【需要人工审核】\n原因: {review_reason}\n\n请人工介入处理。"
        return state

    def invoke(self, query: str) -> Dict[str, Any]:
        """执行Agent"""
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query)],
            "current_query": query,
            "intent": None,
            "selected_tools": None,
            "tool_results": None,
            "confidence": None,
            "needs_human_review": False,
            "review_reason": None,
            "iteration_count": 0,
            "final_answer": None,
        }

        result = self.graph.invoke(initial_state)

        return {
            "answer": result.get("final_answer", ""),
            "intent": result.get("intent"),
            "confidence": result.get("confidence"),
            "needs_human_review": result.get("needs_human_review", False),
            "review_reason": result.get("review_reason"),
            "tool_results": result.get("tool_results"),
        }


class ReActAgent:
    """ReAct (Reasoning + Acting) Agent - 简化版"""

    def __init__(
        self,
        llm: Any,
        tools: List[BaseTool],
        max_iterations: int = 5,
    ):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools}
        self.max_iterations = max_iterations

    def run(self, query: str) -> Dict[str, Any]:
        """运行ReAct循环"""
        history = []
        current_query = query
        iterations = 0

        while iterations < self.max_iterations:
            iterations += 1

            thought_prompt = f"""你是一个AI助手，正在分析用户问题。

当前问题: {current_query}

请分析:
1. 用户真正想问的是什么?
2. 需要调用什么工具来解决问题?
3. 是否有足够信息直接回答?

历史步骤:
{chr(10).join(history) if history else '无'}

直接输出你的分析(中文，简洁):"""

            thought = self.llm.invoke([HumanMessage(content=thought_prompt)])
            history.append(f"思考: {thought.content}")

            action_prompt = f"""基于以上分析，你需要执行什么动作?

可用工具:
{chr(10).join([f'- {name}: {tool.description}' for name, tool in self.tools.items()])}

如果需要调用工具，请按以下JSON格式输出(只需JSON，不要其他内容):
{{"action": "工具名称", "input": "输入参数"}}

如果可以直接回答，请输出:
{{"action": "final_answer", "input": "你的回答"}}
"""

            action_response = self.llm.invoke([HumanMessage(content=action_prompt)])

            try:
                import json
                action_json = json.loads(action_response.content.strip())

                if action_json.get("action") == "final_answer":
                    return {
                        "answer": action_json.get("input", ""),
                        "iterations": iterations,
                        "history": history,
                    }

                tool_name = action_json.get("action")
                tool_input = action_json.get("input", "")

                if tool_name in self.tools:
                    tool_result = self.tools[tool_name].invoke(tool_input)
                    history.append(f"行动: 调用{tool_name}, 结果: {str(tool_result)[:200]}")
                    current_query = f"基于之前的工具结果: {tool_result}\n\n用户原问题: {query}"
                else:
                    history.append(f"错误: 工具{tool_name}不存在")
                    break

            except json.JSONDecodeError:
                history.append(f"解析错误: {action_response.content}")
                break

        return {
            "answer": "抱歉，我无法在有限步骤内完成回答，已转人工处理。",
            "iterations": iterations,
            "history": history,
        }
