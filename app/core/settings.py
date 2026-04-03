import json

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DocuMind"
    version: str = "0.1.0"
    debug: bool = False

    app_env: str = "dev"
    log_level: str = "INFO"
    cors_allow_origins: list[str] | str = Field(default_factory=list)
    api_request_timeout_seconds: int = 60
    enable_request_id: bool = True

    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "DOCUMIND_OPENAI_API_KEY"),
    )
    gemini_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "DOCUMIND_GEMINI_API_KEY"),
    )
    anthropic_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "DOCUMIND_ANTHROPIC_API_KEY"),
    )
    ollama_base_url: str = "http://localhost:11434"
    ollama_http_timeout_seconds: float = Field(default=120.0, gt=0)
    ollama_keep_alive: str = "5m"
    ollama_deepseek_ocr_model: str = "deepseek-ocr:3b"
    ollama_glm_ocr_model: str = "glm-ocr"
    llm_default_max_output_tokens: int = Field(default=1024, gt=0)
    http_timeout_seconds: float = Field(default=10.0, gt=0)

    # -- Milvus (vector store) --
    vector_store_backend: str = "memory"  # "memory" or "milvus"
    milvus_uri: str = "http://localhost:19530"
    milvus_collection_name: str = "documind_chunks"
    milvus_token: str = ""
    milvus_vector_dim: int = Field(default=768, gt=0)

    # -- Redis (job queue) --
    job_queue_backend: str = "memory"  # "memory" or "redis"
    redis_url: str = "redis://localhost:6379/0"

    # -- Auth --
    auth_enabled: bool = False
    auth_secret_key: str = "change-me-in-production"
    auth_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = Field(default=30, gt=0)
    auth_admin_username: str = "admin"
    auth_admin_password: str = "admin"

    model_config = SettingsConfigDict(
        env_prefix="DOCUMIND_",
        env_file=".env",
        extra="ignore",
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _normalize_cors_allow_origins(cls, value: list[str] | str | None) -> list[str]:
        if value is None:
            return []

        if isinstance(value, list):
            return [origin.strip() for origin in value if isinstance(origin, str) and origin.strip()]

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []

            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [origin.strip() for origin in parsed if isinstance(origin, str) and origin.strip()]

            return [origin.strip() for origin in stripped.split(",") if origin.strip()]

        return []


settings = Settings()