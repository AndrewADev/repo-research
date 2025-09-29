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
  LLM_PROVIDER=ollama  # or "anthropic"
  # Ollama Configuration (optional, defaults shown)
  OLLAMA_BASE_URL=http://localhost:11434
  # Anthropic Configuration (required if using anthropic provider or as fallback)
  ANTHROPIC_API_KEY=your_anthropic_api_key
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

This is a GitHub analysis tool built with LangGraph, configurable LLM providers (Ollama/Anthropic), and the GitHub API. The system follows a modular architecture with clear separation of concerns:

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
   - Supports multiple LLM providers (Ollama, Anthropic) with automatic fallback

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

### Dependencies

The project uses uv for dependency management with these key libraries:
- `pygithub` - GitHub API client
- `langchain`, `langchain-anthropic`, `langchain-ollama` - LLM framework and provider integrations
- `langgraph` - State graph execution framework
- `python-dotenv` - Environment variable management
- `pydantic` - Data validation and serialization

### Workflow Architecture

The application follows a conversational AI pattern where:
1. User provides analysis prompt or resumes existing conversation
2. Thread ID is generated (new) or validated (resume)
3. LangGraph orchestrates tool calls based on LLM reasoning (Ollama or Anthropic)
4. GitHub tools execute API calls with proper authentication
5. Results are processed and fed back to the LLM for synthesis
6. Responses are streamed to the user and persisted to SQLite
7. Thread ID is displayed for future reference or resumption

This architecture enables complex multi-step GitHub analysis workflows while maintaining conversation context, tool state, and full conversation history. The flexible LLM provider system allows users to choose between local Ollama models for privacy or cloud-based Anthropic models for performance. Conversation persistence ensures users can review past analyses and continue multi-session investigations.

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
