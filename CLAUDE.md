# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

A GitHub analysis tool built with LangGraph and a configurable LLM provider (Ollama / Anthropic / HuggingFace). It runs predefined analysis workflows over GitHub data with full conversation persistence via SQLite checkpointing.

## Environment

- Install: `uv sync` (add `--dev` for dev tools)
- Required env: `GITHUB_TOKEN`. Provider config (`LLM_PROVIDER`, `ANTHROPIC_API_KEY`, etc.) — see the `llm-provider-setup` skill.
- CLI: `uv run github-agent --help` lists all commands and flags. Don't duplicate that surface here.
- Conversations persist to `~/.github-agent/conversations.db`; each run prints a thread ID usable with `resume` / `show`.

## Code Style and Type Safety

**This project strongly emphasizes type safety.** When writing code here you MUST:

- Use explicit type hints on all functions, methods, and variables.
- Model data with `pydantic.BaseModel` (or `TypedDict`) — not raw `dict`. This applies to API I/O, tool params/results, config, and internal DTOs.
- Stay compatible with `mypy --strict`.
- Validate at system boundaries (external APIs, user input, file I/O) using Pydantic.

```python
from pydantic import BaseModel, Field

class RepositoryAnalysis(BaseModel):
    repo_name: str = Field(..., description="Full repository name (owner/repo)")
    stars: int = Field(ge=0)
    topics: list[str] = Field(default_factory=list)
```

## Core Components

1. **`src/github_agent/main.py`** — Typer CLI entry point; builds the LangGraph, defines analysis prompts, streams responses, manages thread IDs.
2. **`src/storage/conversations.py`** — `ConversationStore`, SQLite-backed conversation history with thread management.
3. **`src/integrations/github/`** — GitHub integration:
   - `github_client.py` — **custom** HTTP client (not PyGithub) for type safety and reduced deps.
   - `tools.py` — `GitHubTools` class wrapping the client.
   - `adapter.py` — LangGraph integration layer with Pydantic schemas.
   - `agent.py` — LangGraph state machine config.
   - `models.py` — Pydantic input models.
   - `churn_strategies.py`, `hotspot_tracker.py` — hotspot analysis (see `hotspot-analysis` skill).
4. **`src/core/`** — `models.py` (Prompt types), `prompts.py` (workflow prompts: `starred_pulse`, `topic_prompt`, `hotspot_analysis`, `run_diagnostic`), `config.py`, `llm.py`.
5. **`src/ui/`** — Gradio web UI (`app.py`, `components.py`, `handlers.py`).

## Key Design Patterns

- **Tool lifecycle**: `@with_github_tools` decorator ensures cleanup.
- **State**: LangGraph manages conversation/tool state with SQLite checkpointing.
- **Threads**: every run gets a unique thread ID; resumable via CLI.
- **Strategy pattern**: pluggable churn calculations for hotspot analysis.
- **Rate limiting**: GitHub client handles backoff on rate limit responses.

## Workflow

User prompt → LangGraph orchestrates LLM reasoning + tool calls → GitHub tools execute → results fed back to LLM for synthesis → streamed to user and persisted. Thread IDs let users resume multi-session investigations.

## Tests

Live under `tests/`, mirroring `src/` layout. Run with `uv run pytest`.
