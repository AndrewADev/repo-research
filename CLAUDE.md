# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- Install dependencies: `pipenv install`
- Activate virtual environment: `pipenv shell`
- Create .env file with required tokens:
  ```
  GITHUB_TOKEN=your_github_personal_access_token
  ANTHROPIC_API_KEY=your_anthropic_api_key
  ```

### Running the Application
- Execute main analysis: `python main.py`
- The application runs predefined GitHub analysis workflows using LangGraph

## Architecture Overview

This is a GitHub analysis tool built with LangGraph, Anthropic's Claude, and the GitHub API. The system follows a modular architecture with clear separation of concerns:

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
   - Integrates Claude LLM with GitHub tools using proper tool binding

### Key Design Patterns

- **Tool Lifecycle Management**: Uses `@with_github_tools` decorator to ensure proper resource cleanup
- **State Management**: LangGraph manages conversation state and tool execution flow
- **Error Handling**: Comprehensive error handling with JSON responses for tool failures
- **Rate Limiting**: Built-in GitHub API rate limit handling with automatic backoff

### Dependencies

The project uses Pipenv for dependency management with these key libraries:
- `pygithub` - GitHub API client
- `langchain` & `langchain-anthropic` - LLM framework and Claude integration
- `langgraph` - State graph execution framework
- `python-dotenv` - Environment variable management
- `pydantic` - Data validation and serialization

### Workflow Architecture

The application follows a conversational AI pattern where:
1. User provides analysis prompt
2. LangGraph orchestrates tool calls based on Claude's reasoning
3. GitHub tools execute API calls with proper authentication
4. Results are processed and fed back to Claude for synthesis
5. Final analysis is streamed back to the user

This architecture enables complex multi-step GitHub analysis workflows while maintaining conversation context and tool state.