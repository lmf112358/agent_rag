"""
LLM模块 - 通义千问(Qwen)集成
使用LangChain统一接口，支持DashScope API
"""

from langchain.callbacks.manager import CallbackManager
from langchain.chat_models.base import BaseChatModel
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.schema import ChatResult, ChatGeneration
from typing import Optional, List, Dict, Any, Literal, Union
import os
from dashscope import Generation
from dashscope.common.error import AuthenticationError, InvalidParameter

from config.settings import config


class ChatQwen(BaseChatModel):
    """通义千问LangChain集成类"""

    model_name: str = "qwen-plus"
    api_key: Optional[str] = None
    api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 120
    top_p: float = 0.8
    top_k: int = 50
    repetition_penalty: float = 1.0
    callback_manager: Optional[CallbackManager] = None

    class Config:
        arbitrary_types_allowed = True

    def _llm_type(self) -> str:
        return "qwen"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> ChatResult:
        """生成回复"""
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
        content = output.choices[0].message.content

        ai_message = AIMessage(content=content)

        generation = ChatGeneration(message=ai_message)
        return ChatResult(generations=[generation])

    def _convert_to_dashscope_format(
        self, messages: List[BaseMessage]
    ) -> List[Dict[str, str]]:
        """将LangChain消息格式转换为DashScope格式"""
        result = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                result.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            else:
                result.append({"role": "user", "content": str(msg.content)})
        return result

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """返回识别参数"""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }

    def bind_tools(self, tools: List[Dict[str, Any]], **kwargs) -> "ChatQwen":
        """绑定工具（用于Function Calling）"""
        return self


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
