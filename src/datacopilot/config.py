"""Application configuration.

Settings are read from environment variables (or a ``.env`` file) and validated at
startup, so a misconfiguration fails fast and loudly instead of surfacing as a
confusing runtime error deep in a request.

Default runs fully offline: ``LLM_MODE=mock`` uses a deterministic planner (no
Ollama, no API key), so the app, tests and CI run anywhere. Switch to a real model:
    LLM_MODE=ollama   (local Llama 3 via Ollama)   or
    LLM_MODE=gemini   (Google Gemini, needs GOOGLE_API_KEY)
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LlmMode = Literal["mock", "ollama", "gemini"]
AppEnv = Literal["dev", "staging", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False
    )

    # --- runtime / observability -------------------------------------------
    app_env: AppEnv = Field("dev", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_json: bool = Field(False, alias="LOG_JSON")
    cors_origins: str = Field("*", alias="CORS_ORIGINS")  # comma-separated

    # --- copilot behaviour --------------------------------------------------
    llm_mode: LlmMode = Field("mock", alias="LLM_MODE")
    db_path: str = Field("data/copilot.db", alias="DB_PATH")
    max_retries: int = Field(2, ge=0, le=5, alias="MAX_RETRIES")   # self-correction
    row_limit: int = Field(100, ge=1, le=10_000, alias="ROW_LIMIT")
    query_timeout_s: float = Field(5.0, gt=0, le=60, alias="QUERY_TIMEOUT_S")

    # --- model backends -----------------------------------------------------
    ollama_model: str = Field("llama3", alias="OLLAMA_MODEL")
    gemini_model: str = Field("gemini-1.5-flash", alias="GEMINI_MODEL")
    google_api_key: str | None = Field(None, alias="GOOGLE_API_KEY")

    @model_validator(mode="after")
    def _validate_backend(self) -> Settings:
        if self.llm_mode == "gemini" and not self.google_api_key:
            raise ValueError("LLM_MODE=gemini requires GOOGLE_API_KEY to be set")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
