from functools import lru_cache

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neis_api_key: str = Field(min_length=1)
    neis_base_url: HttpUrl = HttpUrl("https://open.neis.go.kr/hub")
    neis_timeout_seconds: float = Field(default=5, gt=0, le=30)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
