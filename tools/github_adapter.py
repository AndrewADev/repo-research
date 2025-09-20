"""
LangChain GitHub Tools Integration with Anthropic's Claude and Pydantic schemas.

This module integrates GitHub tools with LangGraph's framework, using proper Pydantic
models for input validation and schema generation.

"""

from langchain.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from typing import Optional, Literal, Type
from .github_tools import GitHubTools
import json
from functools import wraps
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

# Define input schemas for our tools
class StarredRepoInput(BaseModel):
    """Input schema for starred repositories tool."""
    username: Optional[str] = Field(
        None, 
        description="GitHub username. If not provided, uses authenticated user"
    )
    sort_by: Literal["stars", "recent", "issues"] = Field(
        "stars",
        description="How to sort the results"
    )

class SearchRepoInput(BaseModel):
    """Input schema for repository search tool."""
    query: str = Field(
        ...,  # ... means required
        description="Search query string (e.g., 'language:python stars:>1000')"
    )
    sort: Literal["stars", "forks", "updated"] = Field(
        "stars",
        description="How to sort the results"
    )
    limit: int = Field(
        10,
        description="Maximum number of results to return",
        ge=1,
        le=100
    )

class ActivityAnalysisInput(BaseModel):
    """Input schema for repository activity analysis tool."""
    repo_full_name: str = Field(
        ...,
        description="Full repository name (e.g., 'username/repo')"
    )

class RateLimitInput(BaseModel):
    """Input schema for rate limit check tool."""
    pass

# Define our graph state
class State(TypedDict):
    """The state of our GitHub analysis graph."""
    # Messages have the type "list". The add_messages function defines how 
    # this state key should be updated (appending messages rather than overwriting)
    messages: Annotated[list, add_messages]
    # Track how many steps we've taken to limit long-running operations
    step_count: int

def with_github_tools(func):
    """Decorator to handle GitHub tool lifecycle."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        github_tools = GitHubTools()
        try:
            return func(*args, **kwargs, github_tools=github_tools)
        finally:
            github_tools.close()
    return wrapper

class StarredRepositoriesTool(BaseTool):
    name: str = "get_starred_repositories"
    description: str = """
    Retrieve and analyze repositories starred by a GitHub user.
    Useful for discovering popular repositories and understanding a user's interests.
    """
    args_schema: Type[BaseModel] = StarredRepoInput
    
    @with_github_tools
    def _run(self, username: Optional[str] = None, 
             sort_by: str = "stars", 
             github_tools: Optional[GitHubTools] = None) -> str:
        """Execute the starred repositories tool."""
        try:
            repos = github_tools.get_starred_repositories(username, sort_by)
            return json.dumps(repos, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

class RepositorySearchTool(BaseTool):
    name: str = "search_repositories"
    description: str = """
    Search for GitHub repositories matching specific criteria.
    Useful for finding repositories based on language, stars, topics, etc.
    """
    args_schema: Type[BaseModel] = SearchRepoInput
    
    @with_github_tools
    def _run(self, query: str, sort: str = "stars", 
             limit: int = 10, 
             github_tools: Optional[GitHubTools] = None) -> str:
        """Execute the repository search tool."""
        try:
            results = github_tools.search_repositories(query, sort, limit)
            return json.dumps(results, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

# @tool(args_schema=ActivityAnalysisInput)
class RepositoryActivityTool(BaseTool):
    name: str = "analyze_repository_activity"
    description: str = """
    Analyze recent activity in a GitHub repository.
    Useful for understanding how active and maintained a repository is.
    """
    args_schema: Type[BaseModel] = ActivityAnalysisInput

    @with_github_tools
    def _run(self, repo_full_name: str,
             github_tools: Optional[GitHubTools] = None) -> str:
        """Execute the repository activity analysis tool."""
        try:
            activity = github_tools.analyze_repository_activity(repo_full_name)
            return json.dumps(activity, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

class RateLimitCheckTool(BaseTool):
    name: str = "check_rate_limit_status"
    description: str = """
    Check the current GitHub API rate limit status for the configured token.
    Shows remaining requests and reset times for core API, search API, and GraphQL API.
    Useful for understanding API quota usage and planning API calls.
    """
    args_schema: Type[BaseModel] = RateLimitInput

    @with_github_tools
    def _run(self, github_tools: Optional[GitHubTools] = None) -> str:
        """Execute the rate limit check tool."""
        try:
            status = github_tools.check_rate_limit_status()
            return json.dumps(status, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

def _create_llm(provider: str = "ollama",
               anthropic_api_key: Optional[str] = None,
               ollama_base_url: str = "http://localhost:11434",
               model: Optional[str] = None,
               temperature: float = 0):
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
                raise Exception(f"Ollama unavailable and no Anthropic API key provided: {e}")

    if provider == "anthropic":
        if not anthropic_api_key:
            raise ValueError("Anthropic API key required for anthropic provider")
        default_model = model or "claude-3-opus-20240229"
        return ChatAnthropic(
            temperature=temperature,
            model=default_model,
            anthropic_api_key=anthropic_api_key,
            max_tokens=4096
        )

    raise ValueError(f"Unsupported provider: {provider}")

def create_graph(provider: str = "ollama",
                anthropic_api_key: Optional[str] = None,
                ollama_base_url: str = "http://localhost:11434",
                model: Optional[str] = None,
                temperature: float = 0,
                max_steps: int = 5):
    """
    Create a LangGraph for GitHub analysis with configurable LLM provider.

    Args:
        provider: LLM provider ("ollama" or "anthropic")
        anthropic_api_key: Anthropic API key (required for anthropic provider)
        ollama_base_url: Ollama server URL
        model: Model name (defaults based on provider)
        temperature: Model temperature (0-1)
        max_steps: Maximum number of steps before forcibly ending

    Returns:
        Compiled LangGraph ready for execution
    """
    # Initialize our graph builder
    graph = StateGraph(State)
    
    # Initialize our LLM
    llm = _create_llm(
        provider=provider,
        anthropic_api_key=anthropic_api_key,
        ollama_base_url=ollama_base_url,
        model=model,
        temperature=temperature
    )
    
    # Create our tools list
    tools = [
        StarredRepositoriesTool(),
        RepositorySearchTool(),
        RepositoryActivityTool(),
        RateLimitCheckTool()
    ]
    
    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Define the chatbot node - this handles the core conversation
    def chatbot(state: State):
        # Increment step counter
        steps = state.get("step_count", 0) + 1
        
        # Generate LLM response
        response = llm_with_tools.invoke(state["messages"])
        
        return {
            "messages": [response],
            "step_count": steps
        }
    
    # Create a tools node to handle tool execution
    tool_node = ToolNode(tools=tools)
    
    # Add nodes to graph
    graph.add_node("chatbot", chatbot)
    graph.add_node("tools", tool_node)
    
    # Add conditional edges
    graph.add_conditional_edges(
        "chatbot",
        tools_condition,
        {
            "tools": "tools",  # If tools needed, go to tools node
            "__end__": "__end__"  # Otherwise end
        }
    )
    
    # Add remaining edges
    graph.add_edge("tools", "chatbot")
    graph.add_edge(START, "chatbot")
    
    # Set up checkpointing
    memory = MemorySaver()
    
    # Compile and return the graph
    return graph.compile(
        checkpointer=memory
    )
