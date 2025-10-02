from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["ollama", "anthropic", "huggingface"]


class LLMProviderConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    llm_provider: LLMProvider = "ollama"
    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    huggingface_api_key: str | None = None

    # Model selection priority: CLI flag > Environment variable > Provider defaults
    model_name: str | None = None

    def get_model_or_default(self):
        if self.model_name:
            return self.model_name
        elif self.llm_provider == "ollama":
            return "qwen3:8b"
        elif self.llm_provider == "huggingface":
            return "Qwen/Qwen2.5-7B-Instruct"
        else:  # anthropic
            return "claude-3-opus-20240229"


def get_config(**kwargs):
    return LLMProviderConfig(**kwargs)


def get_resolved_model_name(model_name_override: str | None = None) -> str:
    """Get the actual model name that will be used.

    Args:
        model_name_override: CLI-provided model name that overrides settings.

    Returns:
        The resolved model name
    """
    if model_name_override is not None:
        provider_config = get_config(model_name=model_name_override)
    else:
        provider_config = get_config()

    # Return the same defaults as create_llm
    return provider_config.get_model_or_default()
