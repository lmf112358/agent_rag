"""
配置文件
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    model_config = SettingsConfigDict(env_prefix="DB_", extra="ignore")

    url: str = "sqlite:///./agent_rag.db"
    echo: bool = False


class RedisSettings(BaseSettings):
    """Redis配置"""
    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""


class MemorySettings(BaseSettings):
    """记忆配置"""
    model_config = SettingsConfigDict(env_prefix="MEMORY_", extra="ignore")

    max_session_length: int = 50  # 每个会话最大消息数
    session_ttl: int = 3600  # 会话过期时间（秒）
    memory_type: str = "redis"  # redis或inmemory


class APISettings(BaseSettings):
    """API配置"""
    model_config = SettingsConfigDict(env_prefix="API_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list = ["*"]


class Settings(BaseSettings):
    """总配置"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    api: APISettings = Field(default_factory=APISettings)


settings = Settings()
