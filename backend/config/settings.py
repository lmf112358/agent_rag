"""
后端配置
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    url: str = "sqlite:///./agent_rag.db"
    echo: bool = False


class RedisSettings(BaseSettings):
    """Redis配置"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""


class MemorySettings(BaseSettings):
    """记忆配置"""
    max_session_length: int = 50  # 每个会话最大消息数
    session_ttl: int = 3600  # 会话过期时间（秒）
    memory_type: str = "redis"  # redis或inmemory


class APISettings(BaseSettings):
    """API配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list = ["*"]


class Settings(BaseSettings):
    """主配置"""
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    api: APISettings = Field(default_factory=APISettings)

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"


settings = Settings()
