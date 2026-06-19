"""Configuration.

Default runs fully offline: LLM_MODE=mock uses a deterministic planner (no Ollama,
no API key), so the app and tests run anywhere. Switch to a real model with:
  LLM_MODE=ollama   (local Llama 3 via Ollama)   or
  LLM_MODE=gemini   (Google Gemini, needs GOOGLE_API_KEY)
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_mode: str = Field("mock", alias="LLM_MODE")           # mock | ollama | gemini
    db_path: str = Field("data/copilot.db", alias="DB_PATH")
    max_retries: int = Field(2, alias="MAX_RETRIES")          # self-correction attempts
    row_limit: int = Field(100, alias="ROW_LIMIT")            # cap rows returned

    ollama_model: str = Field("llama3", alias="OLLAMA_MODEL")
    gemini_model: str = Field("gemini-1.5-flash", alias="GEMINI_MODEL")
    google_api_key: str | None = Field(None, alias="GOOGLE_API_KEY")


settings = Settings()
