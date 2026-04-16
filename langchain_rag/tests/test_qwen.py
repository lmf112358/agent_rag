"""
Qwen LLM 模块测试
"""
import pytest
from unittest.mock import MagicMock, patch

from langchain_rag.llm.qwen import ChatQwen, QwenChatModel


class TestChatQwen:
    """测试 ChatQwen 类"""

    def test_initialization(self):
        """测试基本初始化"""
        chat = ChatQwen(
            model_name="qwen-plus",
            api_key="test-key",
            temperature=0.5,
        )

        assert chat.model_name == "qwen-plus"
        assert chat.api_key == "test-key"
        assert chat.temperature == 0.5

    def test_llm_type_property(self):
        """测试 _llm_type 属性"""
        chat = ChatQwen()
        assert chat._llm_type == "qwen"

    def test_identifying_params(self):
        """测试识别参数"""
        chat = ChatQwen(model_name="qwen-max", temperature=0.8)
        params = chat._identifying_params

        assert "model_name" in params
        assert params["model_name"] == "qwen-max"
        assert params["temperature"] == 0.8

    @patch("langchain_rag.llm.qwen.Generation")
    def test_convert_messages(self, mock_generation):
        """测试消息格式转换"""
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

        chat = ChatQwen(api_key="test-key")

        messages = [
            SystemMessage(content="系统提示"),
            HumanMessage(content="用户问题"),
            AIMessage(content="AI回答"),
        ]

        dashscope_msgs = chat._convert_to_dashscope_format(messages)

        assert len(dashscope_msgs) == 3
        assert dashscope_msgs[0]["role"] == "system"
        assert dashscope_msgs[1]["role"] == "user"
        assert dashscope_msgs[2]["role"] == "assistant"

    def test_bind_tools_returns_new_instance(self):
        """测试 bind_tools 返回新实例（不修改原对象）"""
        from langchain_core.tools import tool

        @tool
        def test_tool(query: str) -> str:
            """测试工具"""
            return "result"

        chat_original = ChatQwen(api_key="test-key")
        chat_with_tools = chat_original.bind_tools([test_tool])

        assert chat_original is not chat_with_tools
        assert chat_original._tools is None
        assert chat_with_tools._tools is not None


class TestQwenChatModel:
    """测试 QwenChatModel 工厂类"""

    def test_get_instance_creates_singleton(self):
        """测试单例模式"""
        QwenChatModel.reset_instance()

        instance1 = QwenChatModel.get_instance(api_key="test-key")
        instance2 = QwenChatModel.get_instance()

        assert instance1 is instance2

    def test_reset_instance(self):
        """测试重置单例"""
        QwenChatModel.reset_instance()

        instance1 = QwenChatModel.get_instance(api_key="test-key")
        QwenChatModel.reset_instance()
        instance2 = QwenChatModel.get_instance(api_key="test-key")

        assert instance1 is not instance2
