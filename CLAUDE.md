# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- Install dependencies: `pipenv install`
- Activate virtual environment: `pipenv shell`
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

### Running the Application
- Execute main analysis: `python main.py`
- The application runs predefined GitHub analysis workflows using LangGraph

## Architecture Overview

This is a GitHub analysis tool built with LangGraph, configurable LLM providers (Ollama/Anthropic), and the GitHub API. The system follows a modular architecture with clear separation of concerns:

### Core Components

1. **main.py** - Entry point that orchestrates the GitHub analysis workflow
   - Creates and configures the LangGraph execution graph
   - Defines analysis prompts for repository analysis
   - Handles streaming responses and conversation flow

2. **tools/github_tools.py** - Core GitHub API integration
   - `GitHubTools` class provides authenticated GitHub API access
   - Methods for repository search, starred repos, and activity analysis
   - Built-in rate limiting and error handling
   - Supports both authenticated user and public user operations

3. **tools/github_adapter.py** - LangGraph integration layer
   - Defines Pydantic schemas for tool input validation
   - `StarredRepositoriesTool`, `RepositorySearchTool`, `RepositoryActivityTool`
   - Creates and configures the LangGraph state machine
   - Supports multiple LLM providers (Ollama, Anthropic) with automatic fallback
   - Integrates LLMs with GitHub tools using proper tool binding

### Key Design Patterns

- **Tool Lifecycle Management**: Uses `@with_github_tools` decorator to ensure proper resource cleanup
- **State Management**: LangGraph manages conversation state and tool execution flow
- **Error Handling**: Comprehensive error handling with JSON responses for tool failures
- **Rate Limiting**: Built-in GitHub API rate limit handling with automatic backoff

### Dependencies

The project uses Pipenv for dependency management with these key libraries:
- `pygithub` - GitHub API client
- `langchain`, `langchain-anthropic`, `langchain-ollama` - LLM framework and provider integrations
- `langgraph` - State graph execution framework
- `python-dotenv` - Environment variable management
- `pydantic` - Data validation and serialization

### Workflow Architecture

The application follows a conversational AI pattern where:
1. User provides analysis prompt
2. LangGraph orchestrates tool calls based on LLM reasoning (Ollama or Anthropic)
3. GitHub tools execute API calls with proper authentication
4. Results are processed and fed back to the LLM for synthesis
5. Final analysis is streamed back to the user

This architecture enables complex multi-step GitHub analysis workflows while maintaining conversation context and tool state. The flexible LLM provider system allows users to choose between local Ollama models for privacy or cloud-based Anthropic models for performance.