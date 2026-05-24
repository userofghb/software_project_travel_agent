from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = Field(default="Smart Travel Assistant API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    secret_key: str = Field(default="change-me", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    database_url: str = Field(
        default="mysql+pymysql://root:root@127.0.0.1:3306/travel_agent?charset=utf8mb4",
        alias="DATABASE_URL",
    )
    agent_provider_mode: str = Field(default="auto", alias="AGENT_PROVIDER_MODE")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    amap_api_key: str = Field(default="", alias="AMAP_API_KEY")
    amap_route_mode: str = Field(default="auto", alias="AMAP_ROUTE_MODE")
    provider_timeout_seconds: float = Field(default=8.0, alias="PROVIDER_TIMEOUT_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
