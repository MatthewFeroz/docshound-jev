from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            Path(__file__).resolve().parents[2] / ".env",
            Path(__file__).resolve().parents[1] / ".env",
        ),
        extra="ignore",
    )

    app_env: str = "development"

    github_token: str | None = None

    merge_gateway_api_key: str | None = None
    merge_gateway_base_url: str = "https://api-gateway.merge.dev/v1/openai"
    merge_gateway_primary_model: str = "google/gemini-3.7-flash"
    merge_gateway_fallback_model: str = "openai/gpt-5.6-luna"

    # Backwards compatibility for installations that call OpenAI directly.
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    docshound_db_path: str | None = None
    docshound_demo_scenario: str | None = None

    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"

    github_write_token: str | None = None
    repo_docs_max_files: int = Field(default=200, ge=1, le=500)
    repo_docs_max_file_bytes: int = Field(default=150_000, ge=1000, le=1_000_000)
    repo_docs_timeout_seconds: float = Field(default=90, gt=0, le=120)
    nvidia_api_key: SecretStr | None = None
    nvidia_embed_enabled: bool = False
    nvidia_embed_model: str = "nvidia/nemotron-3-embed-1b"
    nvidia_embed_url: str = "https://integrate.api.nvidia.com/v1/embeddings"
    nvidia_embed_max_passages: int = Field(default=2048, ge=1, le=4096)
    nvidia_embed_timeout_seconds: float = Field(default=120, gt=0, le=120)
    nvidia_rerank_enabled: bool = False
    nvidia_rerank_model: str = "nvidia/llama-nemotron-rerank-vl-1b-v2"
    nvidia_rerank_url: str = "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking"
    nvidia_rerank_candidates: int = Field(default=40, ge=3, le=100)
    nvidia_rerank_timeout_seconds: float = Field(default=15, gt=0, le=60)

    @property
    def allowed_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
