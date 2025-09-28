"""
LLM provider factory for creating configured language model instances.

This module provides a unified interface for creating LLM instances from different
providers (Ollama, Anthropic) with automatic fallback handling.
"""

from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama


def create_llm(
    provider: str = "ollama",
    anthropic_api_key: str | None = None,
    ollama_base_url: str = "http://localhost:11434",
    model: str | None = None,
    temperature: float = 0,
):
    """
    Create an LLM instance based on the provider.

    Args:
        provider: LLM provider ("ollama" or "anthropic")
        anthropic_api_key: Anthropic API key (required for anthropic provider)
        ollama_base_url: Ollama server URL
        model: Model name (defaults based on provider)
        temperature: Model temperature (0-1)

    Returns:
        LLM instance

    Raises:
        ValueError: If unsupported provider or missing required config
        Exception: If Ollama unavailable and no Anthropic fallback
    """
    if provider == "ollama":
        # Use a model with better tool calling support
        default_model = model or "qwen3:8b"
        try:
            return ChatOllama(
                model=default_model,
                base_url=ollama_base_url,
                temperature=temperature,
            )
        except Exception as e:
            if anthropic_api_key:
                print(f"Warning: Ollama unavailable ({e}), falling back to Anthropic")
                provider = "anthropic"
            else:
                raise Exception(
                    f"Ollama unavailable and no Anthropic API key provided: {e}"
                ) from e

    if provider == "anthropic":
        if not anthropic_api_key:
            raise ValueError("Anthropic API key required for anthropic provider")
        default_model = model or "claude-3-opus-20240229"
        return ChatAnthropic(
            temperature=temperature,
            model=default_model,
            anthropic_api_key=anthropic_api_key,
            max_tokens=4096,
        )

    raise ValueError(f"Unsupported provider: {provider}")
