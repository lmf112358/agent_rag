"""
Agentic RAG - 迪奥技术AI总工程师工具体系
核心配置模块
"""

from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field


class LLMConfig(BaseSettings):
    """LLM配置"""
    provider: Literal["qwen", "openai", "anthropic"] = "qwen"
    model_name: str = "qwen-plus"
    api_key: str = Field(default="", description="API Key")
    api_base: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="API Base URL")
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 120


class EmbeddingConfig(BaseSettings):
    """Embedding配置"""
    provider: Literal["qwen", "openai", "local"] = "qwen"
    model_name: str = "text-embedding-v3"
    api_key: str = Field(default="", description="API Key")
    api_base: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="API Base URL")
    dimension: int = 1536


class VectorStoreConfig(BaseSettings):
    """向量存储配置"""
    provider: Literal["qdrant", "chroma", "milvus"] = "qdrant"
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "agent_rag_knowledge"
    vector_dim: int = 1536
    distance: Literal["Cosine", "Euclidean", "Dot"] = "Cosine"
    qdrant_api_key: str = Field(default="", description="Qdrant API Key (可选)")


class RAGConfig(BaseSettings):
    """RAG配置"""
    chunk_size: int = 512
    chunk_overlap: int = 100
    retrieval_top_k: int = 10
    rerank_top_k: int = 5
    min_relevance_score: float = 0.75


class AgentConfig(BaseSettings):
    """Agent配置"""
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
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vectorstore: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"


config = Config()
