from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/frontai"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # API
    api_prefix: str = "/api/v2"
    debug: bool = False
    
    # CORS
    cors_origins: list[str] = ["*"]
    
    # JWT (必须在生产环境通过环境变量设置)
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 60  # 1小时
    jwt_refresh_expire_days: int = 7  # 7天
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
