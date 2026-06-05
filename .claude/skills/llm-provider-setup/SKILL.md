---
name: llm-provider-setup
description: Setup and configuration reference for the three supported LLM providers (Ollama, Anthropic, HuggingFace) — required env vars, default models, and provider-specific gotchas. Load when configuring providers, debugging provider/auth errors, onboarding a new environment, or working on src/core/config.py / src/core/llm.py.
---

# LLM Provider Setup

The project supports three LLM providers via `LLM_PROVIDER` in `.env`. Provider wiring lives in `src/core/config.py` and `src/core/llm.py`.

## Env vars

```
LLM_PROVIDER=ollama  # or "anthropic" or "huggingface"

# Ollama (defaults shown)
OLLAMA_BASE_URL=http://localhost:11434

# Anthropic (required for anthropic provider or as Ollama fallback)
ANTHROPIC_API_KEY=...

# HuggingFace (required for huggingface provider)
HUGGINGFACE_API_KEY=...
```

## Ollama (default)

1. Install Ollama: https://ollama.ai/
2. Pull a tool-calling-capable model: `ollama pull qwen3:8b`
3. Start the service: `ollama serve`
4. The tool automatically falls back to Anthropic if Ollama is unreachable and `ANTHROPIC_API_KEY` is set.

Gotcha: the chosen model **must** support tool calling — many small models do not.

## Anthropic Claude

1. Get an API key from https://console.anthropic.com/
2. Set `LLM_PROVIDER=anthropic` (or leave as Ollama and let it fall back).

## HuggingFace Inference API

1. Get a token from https://huggingface.co/settings/tokens (free tier available).
2. Set `LLM_PROVIDER=huggingface`.
3. Default model: `Qwen/Qwen2.5-7B-Instruct`.
4. Free serverless tier has rate limits.

## Diagnostics

Run `uv run github-agent diagnostics` to surface provider/auth issues before running an analysis.
