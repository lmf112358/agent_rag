"""
Agentic RAG - 迪奥技术AI总工程师工具体系
核心配置模块
"""
import os
import re
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# 定位 .env 文件（优先使用 langchain_rag/.env）
PROJECT_ROOT = Path(__file__).parent.parent
ENV_PATH = PROJECT_ROOT / "langchain_rag" / ".env"
if not ENV_PATH.exists():
    ENV_PATH = PROJECT_ROOT / ".env"


def load_env_to_os(env_file: Path):
    """手动加载 .env 文件到 os.environ（让 os.getenv 也能拿到值）"""
    if not env_file.exists():
        return

    print(f"[config] Loading env from: {env_file}")
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([A-Z_]+)\s*=\s*(.*)$", line)
            if match:
                key = match.group(1)
                value = match.group(2).strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = value


# 先加载 .env 到 os.environ
load_env_to_os(ENV_PATH)

# 全局 DASHSCOPE_API_KEY 回退
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")


class LLMConfig(BaseSettings):
    """LLM配置"""
    model_config = SettingsConfigDict(env_prefix="LLM_")

    provider: Literal["qwen", "openai", "anthropic"] = "qwen"
    model_name: str = "qwen-plus"
    api_key: str = Field(default="", description="API Key")
    api_base: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="API Base URL")
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 120

    @property
    def effective_api_key(self) -> str:
        """获取有效 API Key（优先自身配置，回退到 DASHSCOPE_API_KEY）"""
        return self.api_key or DASHSCOPE_API_KEY


class EmbeddingConfig(BaseSettings):
    """Embedding配置"""
    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")

    provider: Literal["qwen", "openai", "local"] = "qwen"
    model_name: str = "text-embedding-v3"
    api_key: str = Field(default="", description="API Key")
    api_base: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="API Base URL")
    dimension: int = 1536

    @property
    def effective_api_key(self) -> str:
        """获取有效 API Key（优先自身配置，回退到 DASHSCOPE_API_KEY）"""
        return self.api_key or DASHSCOPE_API_KEY


class VectorStoreConfig(BaseSettings):
    """向量存储配置"""
    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    provider: Literal["qdrant", "chroma", "milvus"] = "qdrant"
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "agent_rag_knowledge"
    vector_dim: int = 1536
    distance: Literal["COSINE", "EUCLID", "DOT", "MANHATTAN"] = "COSINE"
    api_key: str = Field(default="", description="Qdrant API Key (可选)")


class RAGConfig(BaseSettings):
    """RAG配置"""
    model_config = SettingsConfigDict(env_prefix="RAG_")

    chunk_size: int = 512
    chunk_overlap: int = 100
    retrieval_top_k: int = 10
    rerank_top_k: int = 5
    min_relevance_score: float = 0.75


class AgentConfig(BaseSettings):
    """Agent配置"""
    model_config = SettingsConfigDict(env_prefix="AGENT_")

    max_iterations: int = 10
    max_execution_time: int = 120
    confidence_threshold: float = 0.75
    fallback_to_human: bool = True
    human_trigger_conditions: list[str] = [
        "max_iterations_exceeded",
        "low_confidence",
        "tool_execution_failed_3_times",
        "涉及金额大于500万元",
    ]


class Config(BaseSettings):
    """主配置"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else None,
        env_nested_delimiter="__",
        extra="ignore",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vectorstore: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)


config = Config()
