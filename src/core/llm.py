"""
LLM provider factory for creating configured language model instances.

This module provides a unified interface for creating LLM instances from different
providers (Ollama, Anthropic) with automatic fallback handling.
"""

from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama

from core.config import LLMProviderConfig


def create_llm(
    provider_config: LLMProviderConfig,
    temperature: float = 0,
):
    """
    Create an LLM instance based on the provider.

    Args:
        model: Model name (defaults based on provider)
        provider: LLM provider ("ollama" or "anthropic")
        anthropic_api_key: Anthropic API key (required for anthropic provider)
        ollama_base_url: Ollama server URL
        temperature: Model temperature (0-1)

    Returns:
        LLM instance

    Raises:
        ValueError: If unsupported provider or missing required config
        Exception: If Ollama unavailable and no Anthropic fallback
    """
    if provider_config.llm_provider == "ollama":
        model_name = provider_config.model_name or "qwen3:8b"
        return ChatOllama(
            model=model_name,
            base_url=provider_config.ollama_base_url,
            temperature=temperature,
        )

    if provider_config.llm_provider == "anthropic":
        if not provider_config.anthropic_api_key:
            raise ValueError("Anthropic API key required for anthropic provider")
        model_name = provider_config.model_name or "claude-3-opus-20240229"
        return ChatAnthropic(
            temperature=temperature,
            model_name=model_name,
            timeout=None,
            stop=["Concluded"],
        )

    raise ValueError(f"Unsupported provider: {provider_config.llm_provider}")
