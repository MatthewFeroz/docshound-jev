from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    github_token: str | None = None
    github_write_token: str | None = None

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    nvidia_api_key: SecretStr | None = None
    nvidia_embed_enabled: bool = False
    nvidia_embed_model: str = "nvidia/nemotron-3-embed-1b"
    nvidia_embed_url: str = "https://integrate.api.nvidia.com/v1/embeddings"
    nvidia_embed_max_passages: int = Field(default=2048, ge=1, le=4096)
    nvidia_embed_timeout_seconds: float = Field(default=120, gt=0, le=120)
    nvidia_rerank_enabled: bool = False
    nvidia_rerank_model: str = "nvidia/llama-nemotron-rerank-vl-1b-v2"
    nvidia_rerank_url: str = (
        "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking"
    )
    nvidia_rerank_candidates: int = Field(default=40, ge=3, le=100)
    nvidia_rerank_timeout_seconds: float = Field(default=15, gt=0, le=60)


@lru_cache
def get_settings() -> Settings:
    return Settings()
