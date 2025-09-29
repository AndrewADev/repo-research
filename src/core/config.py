from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["ollama", "anthropic"]


class LLMProviderConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    llm_provider: LLMProvider = "ollama"
    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Model selection priority: CLI flag > Environment variable > Provider defaults
    model_name: str | None = None


def get_config(**kwargs):
    return LLMProviderConfig(**kwargs)
