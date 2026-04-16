"""
LLM模块 - 通义千问(Qwen)集成
使用LangChain统一接口，支持DashScope API 与 Function Calling
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage,
)
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.tools import BaseTool
from typing import Optional, List, Dict, Any, Union, Iterator
import os
from dashscope import Generation
from dashscope.common.error import AuthenticationError, InvalidParameter

from langchain_rag.config.settings import config


class ChatQwen(BaseChatModel):
    """通义千问LangChain集成类，支持Function Calling"""

    model_name: str = "qwen-plus"
    api_key: Optional[str] = None
    api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 120
    top_p: float = 0.8
    top_k: int = 50
    repetition_penalty: float = 1.0

    # Function Calling 相关
    _tools: Optional[List[Dict[str, Any]]] = None

    model_config = {"arbitrary_types_allowed": True}

    @property
    def _llm_type(self) -> str:
        return "qwen"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> ChatResult:
        """生成回复，支持Function Calling"""
        if self.api_key is None:
            self.api_key = os.getenv("DASHSCOPE_API_KEY", "")

        if not self.api_key:
            raise ValueError(
                "API key not found. Please set DASHSCOPE_API_KEY environment variable "
                "or pass api_key to ChatQwen"
            )

        dashscope_messages = self._convert_to_dashscope_format(messages)

        gen_kwargs = {
            "model": self.model_name,
            "api_key": self.api_key,
            "messages": dashscope_messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repetition_penalty": self.repetition_penalty,
            "max_tokens": self.max_tokens,
            "result_format": "message",
        }

        if stop:
            gen_kwargs["stop"] = stop

        # Function Calling 支持
        tools = kwargs.get("tools", self._tools)
        if tools:
            gen_kwargs["tools"] = self._format_tools(tools)
            if "tool_choice" in kwargs:
                gen_kwargs["tool_choice"] = kwargs["tool_choice"]

        try:
            response = Generation.call(**gen_kwargs)
        except AuthenticationError:
            raise ValueError("Invalid API key. Please check your DASHSCOPE_API_KEY")
        except InvalidParameter as e:
            raise ValueError(f"Invalid parameter: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to call DashScope API: {str(e)}")

        if response.status_code != 200:
            raise RuntimeError(
                f"DashScope API error: {response.code} - {response.message}"
            )

        output = response.output
        choice = output.choices[0]
        message = choice.message

        # 解析工具调用（DashScope response 是字典式对象）
        tool_calls = None
        try:
            if "tool_calls" in message and message["tool_calls"]:
                tool_calls = self._parse_tool_calls(message["tool_calls"])
        except (KeyError, TypeError):
            pass

        # 获取 content（安全访问）
        content = ""
        try:
            if "content" in message:
                content = message["content"]
        except (KeyError, TypeError):
            pass

        # 只有有 tool_calls 时才传递这个参数
        ai_message_kwargs = {"content": content}
        if tool_calls:
            ai_message_kwargs["tool_calls"] = tool_calls

        ai_message = AIMessage(**ai_message_kwargs)

        generation = ChatGeneration(message=ai_message)
        return ChatResult(generations=[generation])

    def _convert_to_dashscope_format(
        self, messages: List[BaseMessage]
    ) -> List[Dict[str, Any]]:
        """将LangChain消息格式转换为DashScope格式（支持工具消息）"""
        result = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                msg_dict: Dict[str, Any] = {"role": "assistant"}
                if msg.content:
                    msg_dict["content"] = msg.content
                if msg.tool_calls:
                    msg_dict["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": tc.args,
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                result.append(msg_dict)
            elif isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            elif isinstance(msg, ToolMessage):
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })
            else:
                result.append({"role": "user", "content": str(msg.content)})
        return result

    def _format_tools(
        self, tools: Union[List[BaseTool], List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """格式化工具定义供DashScope使用"""
        formatted = []
        for tool in tools:
            if isinstance(tool, BaseTool):
                # 从 BaseTool 转换
                formatted.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.args_schema.model_json_schema(),
                    },
                })
            else:
                # 已经是字典格式
                formatted.append(tool)
        return formatted

    def _parse_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Any]:
        """解析工具调用为LangChain格式"""
        from langchain_core.messages.tool import ToolCall

        calls = []
        for tc in tool_calls:
            calls.append(ToolCall(
                id=tc.get("id", ""),
                name=tc.get("function", {}).get("name", ""),
                args=tc.get("function", {}).get("arguments", {}),
            ))
        return calls

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """返回识别参数"""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }

    def bind_tools(
        self,
        tools: Union[List[BaseTool], List[Dict[str, Any]]],
        **kwargs: Any,
    ) -> "ChatQwen":
        """绑定工具（用于Function Calling）"""
        # 创建新实例避免修改原对象
        new_instance = self.__class__(**self.__dict__)
        new_instance._tools = tools
        return new_instance


class QwenChatModel:
    """Qwen聊天模型工厂类"""

    _instance: Optional[ChatQwen] = None

    @classmethod
    def get_instance(
        cls,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ChatQwen:
        """获取单例实例"""
        if cls._instance is None:
            cfg = config.llm
            cls._instance = ChatQwen(
                model_name=model_name or cfg.model_name,
                api_key=api_key or cfg.api_key or os.getenv("DASHSCOPE_API_KEY", ""),
                api_base=cfg.api_base,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置实例（用于切换模型）"""
        cls._instance = None


def get_qwen_chat(
    model_name: str = "qwen-plus",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> ChatQwen:
    """快捷函数：获取Qwen聊天实例"""
    return QwenChatModel.get_instance(
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def get_qwen_with_tools(tools: List[Dict[str, Any]]) -> ChatQwen:
    """快捷函数：获取支持工具调用的Qwen实例"""
    chat = get_qwen_chat()
    return chat.bind_tools(tools)
