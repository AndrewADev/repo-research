# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- Install dependencies: `uv sync`
- Install with dev dependencies: `uv sync --dev`
- Create .env file with required tokens:
  ```
  GITHUB_TOKEN=your_github_personal_access_token
  # LLM Provider Configuration (defaults to ollama)
  LLM_PROVIDER=ollama  # or "anthropic" or "huggingface"
  # Ollama Configuration (optional, defaults shown)
  OLLAMA_BASE_URL=http://localhost:11434
  # Anthropic Configuration (required if using anthropic provider or as fallback)
  ANTHROPIC_API_KEY=your_anthropic_api_key
  # HuggingFace Configuration (required if using huggingface provider)
  HUGGINGFACE_API_KEY=your_huggingface_api_token
  ```

### LLM Provider Setup

#### Ollama (Default)
1. Install Ollama: https://ollama.ai/
2. Pull a model: `ollama pull qwen3:8b` (or your preferred model -- making sure it supports tool calling)
3. Start Ollama service: `ollama serve`
4. The tool will automatically use Ollama with fallback to Anthropic if configured

#### Anthropic Claude
1. Get API key from https://console.anthropic.com/
2. Set `LLM_PROVIDER=anthropic` in .env or use as fallback when Ollama unavailable

#### HuggingFace Inference API
1. Get API token from https://huggingface.co/settings/tokens (free tier available)
2. Set `LLM_PROVIDER=huggingface` in .env
3. Default model: `Qwen/Qwen2.5-7B-Instruct`
4. Free serverless API with rate limits

### Pre-commit Hooks
- Install prek: `pip install prek` (or `uv tool install prek`)
- Install hooks: `prek install`
- Run hooks manually: `prek run --all-files`
- The project uses comprehensive pre-commit hooks including:
  - Ruff linting and formatting
  - File hygiene checks (trailing whitespace, end-of-file fixes)
  - Syntax validation for YAML, JSON, TOML
  - Python AST validation and debug statement detection
  - Security checks for secrets and private keys

### Running the Application
- Execute main analysis: `uv run github-agent`
- Available commands: `uv run github-agent --help`

#### Analysis Commands
- `uv run github-agent diagnostics` - Diagnose setup issues
- `uv run github-agent analyze` - Run comprehensive starred repository analysis
- `uv run github-agent topics "ai,machine-learning"` - Search repositories by topics
- All analysis commands support `--thread-id` flag to resume existing conversations

#### Conversation Management Commands
- `uv run github-agent history` - List recent conversation history (up to 20 by default)
  - Use `--limit` or `-n` to change number displayed: `uv run github-agent history -n 50`
- `uv run github-agent show <thread-id>` - Display full transcript of a conversation
- `uv run github-agent resume <thread-id>` - Resume and continue an existing conversation interactively
  - Interactive mode allows multi-turn conversations
  - Type 'exit' or 'quit' to end the session

#### Conversation Persistence
- All conversations are automatically saved to `~/.github-agent/conversations.db`
- Each command execution generates a unique thread ID displayed at completion
- Use thread IDs to resume conversations or view history
- The application runs predefined GitHub analysis workflows using LangGraph with full state persistence

## Architecture Overview

This is a GitHub analysis tool built with LangGraph, configurable LLM providers (Ollama/Anthropic/HuggingFace), and the GitHub API. The system follows a modular architecture with clear separation of concerns:

### Code Style and Type Safety

**IMPORTANT: This project strongly emphasizes type safety and strongly-typed Python.**

When working with this codebase, you MUST:

- **Use type hints everywhere**: All functions, methods, and variables should have explicit type annotations
- **Leverage Pydantic models**: Use `pydantic.BaseModel` for all data structures, especially:
  - API inputs/outputs
  - Configuration objects
  - Tool parameters and results
  - Internal data transfer objects
- **Avoid dictionaries and untyped data**: Replace plain `dict` types with Pydantic models or `TypedDict`
- **Enable strict type checking**: The codebase should be compatible with `mypy --strict`
- **Validate data at boundaries**: Use Pydantic's validation at all external interfaces (API calls, user input, file I/O)

Benefits of this approach:
- Catches bugs at development time rather than runtime
- Provides excellent IDE autocomplete and inline documentation
- Makes refactoring safer and more confident
- Self-documenting code through type annotations
- Automatic data validation and serialization via Pydantic

Example of preferred style:
```python
from pydantic import BaseModel, Field

class RepositoryAnalysis(BaseModel):
    repo_name: str = Field(..., description="Full repository name (owner/repo)")
    stars: int = Field(ge=0, description="Number of stars")
    topics: list[str] = Field(default_factory=list)

def analyze_repository(repo: RepositoryAnalysis) -> dict[str, Any]:
    # Type-safe, validated input
    ...
```

Avoid untyped patterns like:
```python
def analyze_repository(repo):  # No type hints
    data = {}  # Untyped dict
    ...
```

### Core Components

1. **src/github_agent/main.py** - Entry point that orchestrates the GitHub analysis workflow
   - Creates and configures the LangGraph execution graph
   - Defines analysis prompts for repository analysis
   - Handles streaming responses and conversation flow
   - Provides CLI interface via Typer
   - Manages thread IDs and conversation persistence

2. **src/storage/** - Conversation persistence layer
   - `conversations.py` - SQLite-based conversation storage
   - `ConversationStore` class for managing conversation history
   - Stores messages with roles, content, and metadata
   - Supports conversation queries and thread management

3. **src/integrations/github/** - GitHub API integration
   - `tools.py` - Core GitHub API integration with `GitHubTools` class
   - `adapter.py` - LangGraph integration layer with Pydantic schemas
   - `agent.py` - LangGraph state machine configuration
   - `models.py` - Pydantic models for tool input validation
   - `churn_strategies.py` - Pluggable strategies for calculating code churn
   - `hotspot_tracker.py` - Tracks file changes for hotspot analysis
   - Supports multiple LLM providers (Ollama, Anthropic, HuggingFace)

4. **src/core/** - Core application models and prompts
   - `models.py` - Pydantic models for templated and threaded prompts
   - `prompts.py` - Predefined analysis prompts and workflows
   - `config.py` - Configuration management for LLM providers
   - `llm.py` - LLM initialization and setup

### Key Design Patterns

- **Tool Lifecycle Management**: Uses `@with_github_tools` decorator to ensure proper resource cleanup
- **State Management**: LangGraph manages conversation state and tool execution flow with checkpointing
- **Conversation Persistence**: SQLite storage for conversation history with thread-based organization
- **Thread Management**: Unique thread IDs for each conversation with resume capability
- **Error Handling**: Comprehensive error handling with JSON responses for tool failures
- **Rate Limiting**: Built-in GitHub API rate limit handling with automatic backoff
- **Strategy Pattern**: Pluggable churn calculation strategies for flexible code analysis

### Hotspot Analysis Feature

The tool includes commit hotspot analysis to identify files with high maintenance burden:

**Churn Calculation Strategies:**

1. **Total Activity Churn** (default: `strategy="activity"`)
   - Formula: `(additions + deletions) / baseline_loc × 100`
   - Measures total code volatility as percentage of initial codebase
   - Requires baseline LOC at start of analysis period
   - Example: 4,000 added + 1,600 deleted / 20,000 baseline = 28% churn

2. **Rework Rate** (`strategy="rework"`)
   - Measures code rewritten within 21-day window
   - Categorizes changes as:
     - **New Work**: Newly added code
     - **Rework**: Code deleted/rewritten within 21 days by same author
     - **Refactor**: Code modified after 21 days
     - **Helping Others**: Changes to someone else's recent code within 21 days
   - Formula: `(rework_lines) / (total_lines) × 100`
   - Returns detailed category breakdown

**Key Implementation Details:**
- Chronological commit processing for temporal analysis
- Baseline LOC fetched from Git tree at analysis period start
- Same-commit additions and deletions are NOT considered rework
- Only changes in subsequent commits (days_diff > 0) count as rework
- Fixed 21-day window for rework detection (industry standard)

### Dependencies

The project uses uv for dependency management with these key libraries:
- `pygithub` - GitHub API client
- `langchain`, `langchain-anthropic`, `langchain-ollama`, `langchain-huggingface` - LLM framework and provider integrations
- `langgraph` - State graph execution framework
- `python-dotenv` - Environment variable management
- `pydantic` - Data validation and serialization

### Workflow Architecture

The application follows a conversational AI pattern where:
1. User provides analysis prompt or resumes existing conversation
2. Thread ID is generated (new) or validated (resume)
3. LangGraph orchestrates tool calls based on LLM reasoning (Ollama, Anthropic, or HuggingFace)
4. GitHub tools execute API calls with proper authentication
5. Results are processed and fed back to the LLM for synthesis
6. Responses are streamed to the user and persisted to SQLite
7. Thread ID is displayed for future reference or resumption

This architecture enables complex multi-step GitHub analysis workflows while maintaining conversation context, tool state, and full conversation history. The flexible LLM provider system allows users to choose between local Ollama models for privacy, cloud-based Anthropic models for performance, or HuggingFace's free Inference API for access to open-source models. Conversation persistence ensures users can review past analyses and continue multi-session investigations.

### Development Tools

The project includes modern development tooling:
- **uv**: Fast Python package manager for dependency management
- **ruff**: Integrated linting, formatting, and import sorting
- **prek**: Pre-commit hook manager (drop-in replacement for pre-commit)
- **pyproject.toml**: Modern Python project configuration
- **pre-commit hooks**: Comprehensive code quality and security checks

Available development commands:
- `uv sync --dev` - Install all dependencies including dev tools
- `uv run ruff check` - Run linting checks
- `uv run ruff format` - Format code
- `uv run ruff check --fix` - Auto-fix linting issues
- `prek install` - Install pre-commit hooks
- `prek run --all-files` - Run all pre-commit hooks manually

### Testing

The project uses pytest for comprehensive test coverage:

**Running Tests:**
- `uv run pytest` - Run all tests
- `uv run pytest tests/integrations/` - Run integration tests only
- `uv run pytest tests/integrations/test_hotspot_analysis.py -v` - Run specific test file with verbose output
- `uv run pytest -k "rework"` - Run tests matching keyword
- `uv run pytest --tb=short` - Run with shorter traceback format

**Test Organization:**
- `tests/core/` - Core functionality tests
- `tests/integrations/` - GitHub API and tool integration tests
- `tests/storage/` - Conversation persistence tests
- `tests/tools/` - Utility tool tests
- `tests/ui/` - User interface tests
- `tests/main/` - CLI and main entry point tests

**Key Test Files:**
- `test_hotspot_analysis.py` - Commit hotspot analysis integration tests
- `test_rework_rate_strategy.py` - Rework rate calculation tests
- `test_total_activity_churn.py` - Activity churn calculation tests
- `test_file_change_tracker.py` - File change tracking tests
