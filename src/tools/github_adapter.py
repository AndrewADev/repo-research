"""
LangChain GitHub Tools Integration with Anthropic's Claude and Pydantic schemas.

This module integrates GitHub tools with LangGraph's framework, using proper Pydantic
models for input validation and schema generation.

"""

import json
from functools import wraps

from langchain.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel

from tools.github_models import (
    ActivityAnalysisInput,
    GitHubToolState,
    RateLimitInput,
    RepositoryLabelsInput,
    RepositorySearchByTopicInput,
    SearchRepoInput,
    StarredRepoInput,
    TokenValidationInput,
)

from .date_tools import CurrentDateTool, DateOffsetTool
from .github_tools import GitHubTools


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
    args_schema: type[BaseModel] = StarredRepoInput

    @with_github_tools
    def _run(
        self,
        username: str | None = None,
        sort_by: str = "stars",
        github_tools: GitHubTools | None = None,
    ) -> str:
        """Execute the starred repositories tool."""
        try:
            repos = github_tools.get_starred_repositories(username, sort_by)

            # Enhanced response with metadata
            response = {
                "results": repos,
                "search_metadata": {
                    "username": username or "authenticated_user",
                    "sort_by": sort_by,
                    "total_found": len(repos),
                    "has_results": len(repos) > 0,
                },
            }

            # Add specific messaging for no results
            if len(repos) == 0:
                user_display = username or "the authenticated user"
                response["search_metadata"]["suggestion"] = (
                    f"No starred repositories found for {user_display}. "
                    "Consider: 1) Verifying the username is correct, "
                    "2) Checking if the user has any starred repositories, "
                    "3) Trying a different user, or 4) Asking for alternative analysis."
                )

            return json.dumps(response, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


class RepositorySearchTool(BaseTool):
    name: str = "search_repositories"
    description: str = """
    Search for GitHub repositories matching specific criteria.
    Useful for finding repositories based on language, stars, topics, etc.
    """
    args_schema: type[BaseModel] = SearchRepoInput

    @with_github_tools
    def _run(
        self,
        query: str,
        sort: str = "stars",
        limit: int = 10,
        github_tools: GitHubTools | None = None,
    ) -> str:
        """Execute the repository search tool."""
        try:
            results = github_tools.search_repositories(query, sort, limit)

            # Enhanced response with search metadata
            response = {
                "results": results,
                "search_metadata": {
                    "query": query,
                    "total_found": len(results),
                    "has_results": len(results) > 0,
                },
            }

            # Add specific messaging for no results
            if len(results) == 0:
                response["search_metadata"]["suggestion"] = (
                    "No repositories found for this query. Consider: "
                    "1) Broadening search terms, 2) Checking spelling, "
                    "3) Using different keywords, or "
                    "4) Asking the user for alternative search criteria."
                )

            return json.dumps(response, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


# @tool(args_schema=ActivityAnalysisInput)
class RepositoryActivityTool(BaseTool):
    name: str = "analyze_repository_activity"
    description: str = """
    Analyze recent activity in a GitHub repository.
    Useful for understanding how active and maintained a repository is.
    """
    args_schema: type[BaseModel] = ActivityAnalysisInput

    @with_github_tools
    def _run(self, repo_full_name: str, github_tools: GitHubTools | None = None) -> str:
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
    args_schema: type[BaseModel] = RateLimitInput

    @with_github_tools
    def _run(self, github_tools: GitHubTools | None = None) -> str:
        """Execute the rate limit check tool."""
        try:
            status = github_tools.check_rate_limit_status()
            return json.dumps(status, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


class TokenValidationTool(BaseTool):
    name: str = "validate_github_token"
    description: str = """
    Validate the GitHub token and return detailed information about its capabilities.
    Checks if the token is valid, what permissions it has, and provides rate
    limit status. Useful for debugging authentication issues and understanding
    token scope.
    """
    args_schema: type[BaseModel] = TokenValidationInput

    @with_github_tools
    def _run(self, github_tools: GitHubTools | None = None) -> str:
        """Execute the token validation tool."""
        try:
            validation_result = github_tools.validate_token()
            return json.dumps(validation_result, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


class RepositoryLabelsTool(BaseTool):
    name: str = "get_repository_labels"
    description: str = """
    Retrieve all labels from a specific GitHub repository.
    Useful for understanding the labeling system and organization of
    issues/PRs in a repository.

    Returns label names, colors, descriptions, and URLs.
    """
    args_schema: type[BaseModel] = RepositoryLabelsInput

    @with_github_tools
    def _run(self, repo_full_name: str, github_tools: GitHubTools | None = None) -> str:
        """Execute the repository labels tool."""
        try:
            labels = github_tools.get_repository_labels(repo_full_name)
            return json.dumps(labels, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


class RepositorySearchByTopicTool(BaseTool):
    name: str = "search_repositories_by_topic"
    description: str = """
    Search for GitHub repositories that have specific topics assigned.
    Useful for discovering repositories by technology, category, or purpose.
    Returns repositories with their topics and matches the specified topic criteria.
    """
    args_schema: type[BaseModel] = RepositorySearchByTopicInput

    @with_github_tools
    def _run(self, github_tools: GitHubTools | None = None, **kwargs) -> str:
        """Execute the repository search by topic tool."""
        try:
            from tools.github_models import RepositorySearchByTopicInput

            # Create the search parameters model from the kwargs
            search_params = RepositorySearchByTopicInput(**kwargs)

            results = github_tools.search_repositories_by_topic(search_params)

            # Enhanced response with search metadata
            response = {
                "results": results,
                "search_metadata": {
                    "topics_searched": search_params.topics,
                    "total_found": len(results),
                    "has_results": len(results) > 0,
                    "search_parameters": {
                        "language": search_params.language,
                        "min_stars": search_params.min_stars,
                        "sort": search_params.sort,
                    },
                },
            }

            # Add specific messaging for no results
            if len(results) == 0:
                response["search_metadata"]["suggestion"] = (
                    f"No repositories found with topics {search_params.topics}. "
                    "Consider: 1) Trying broader or different topics, "
                    "2) Relaxing filters (stars, language), "
                    "3) Checking topic spelling, or "
                    "4) Asking the user for alternative topics to search."
                )

            return json.dumps(response, default=str, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


def result_analysis_condition(state: GitHubToolState) -> str:
    """Analyze tool results for errors and no-results scenarios."""
    messages = state.get("messages", [])
    if not messages:
        return "continue"

    last_message = messages[-1]
    if hasattr(last_message, "content") and last_message.content:
        content = last_message.content.lower()

        # Check for explicit errors first
        if "error" in content:
            return "run_diagnostics"

        # Check for no-results scenarios
        no_results_indicators = [
            '"has_results": false',
            '"total_found": 0',
            "no repositories found",
            "no results",
            "consider: 1) broadening search terms",
        ]

        if any(indicator in content for indicator in no_results_indicators):
            return "handle_no_results"

    return "continue"


def handle_no_results_node(state: GitHubToolState):
    """Handle no-results scenarios by automatically concluding gracefully."""
    no_results_message = AIMessage(
        content=(
            "🔍 **No Results Found - Task Concluded**\n\n"
            "The search didn't return any repositories matching the criteria. "
            "This could indicate:\n\n"
            "- The specific combination of topics/filters is very rare\n"
            "- The search terms might need adjustment\n"
            "- The desired repositories may not exist or be publicly available\n\n"
            "To try a different search, please run the command again with "
            "different topics or search criteria."
        )
    )

    return {"messages": [no_results_message], "task_concluded": True}


def run_diagnostics_node(state: GitHubToolState):
    """Run the existing diagnostic workflow."""
    from core.prompts import run_diagnostic

    diagnostic_message = AIMessage(
        content=(
            "🔍 **Error Detected - Running Diagnostics**\n\n"
            f"{run_diagnostic.prompt}"
            "Are we able to continue our task?"
        )
    )

    return {"messages": [diagnostic_message], "diagnostic_ran": True}


def can_continue_condition(state: GitHubToolState) -> str:
    """Check if we can continue after diagnostics based on LLM response."""
    messages = state.get("messages", [])
    if not messages:
        return "continue"

    # Look for the LLM's response to the diagnostic prompt
    # Check if the latest message indicates we should stop
    last_message = messages[-1]
    if hasattr(last_message, "content") and last_message.content:
        content = last_message.content.lower()

        # Look for negative responses to "Are we able to continue our task?"
        stop_indicators = [
            "no",
            "not able",
            "cannot continue",
            "unable to continue",
            "should stop",
            "cannot proceed",
            "not possible",
            "blocked",
            "failed",
            "critical error",
            "cannot resolve",
        ]

        if any(indicator in content for indicator in stop_indicators):
            return "stop"

    return "continue"


def diagnostic_stop_node(state: GitHubToolState):
    """Node that provides a clear stop message for main.py to detect."""
    stop_message = AIMessage(
        content=(
            "⚠️ **Execution Stopped Due to Diagnostics**\n\n"
            "Diagnostics indicate we cannot continue."
            "Stopping execution to prevent further issues."
        )
    )

    return {"messages": [stop_message], "execution_stopped": True}


def _create_llm(
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


def create_graph(
    provider: str = "ollama",
    anthropic_api_key: str | None = None,
    ollama_base_url: str = "http://localhost:11434",
    model: str | None = None,
    temperature: float = 0,
    max_steps: int = 5,
):
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
    graph = StateGraph(GitHubToolState)

    # Initialize our LLM
    llm = _create_llm(
        provider=provider,
        anthropic_api_key=anthropic_api_key,
        ollama_base_url=ollama_base_url,
        model=model,
        temperature=temperature,
    )

    # Create our tools list
    tools = [
        StarredRepositoriesTool(),
        RepositorySearchTool(),
        RepositoryActivityTool(),
        RateLimitCheckTool(),
        TokenValidationTool(),
        RepositoryLabelsTool(),
        RepositorySearchByTopicTool(),
        CurrentDateTool(),
        DateOffsetTool(),
    ]

    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(tools)

    # Define the chatbot node - this handles the core conversation
    def chatbot(state: GitHubToolState):
        # Increment step counter
        steps = state.get("step_count", 0) + 1

        # Generate LLM response
        response = llm_with_tools.invoke(state["messages"])

        return {"messages": [response], "step_count": steps}

    # Create a tools node to handle tool execution
    tool_node = ToolNode(tools=tools)

    # Add nodes to graph
    graph.add_node("chatbot", chatbot)
    graph.add_node("tools", tool_node)
    graph.add_node("run_diagnostics", run_diagnostics_node)
    graph.add_node("diagnostic_stop", diagnostic_stop_node)
    graph.add_node("handle_no_results", handle_no_results_node)

    # Add conditional edges from chatbot
    graph.add_conditional_edges(
        "chatbot",
        tools_condition,
        {
            "tools": "tools",  # If tools needed, go to tools node
            END: END,  # Otherwise end
        },
    )

    # Enhanced tools conditional logic to handle errors and no-results
    graph.add_conditional_edges(
        "tools",
        result_analysis_condition,
        {
            "run_diagnostics": "run_diagnostics",
            "handle_no_results": "handle_no_results",
            "continue": "chatbot",  # Normal flow continues to chatbot
        },
    )

    # Add conditional edge from diagnostics (check if we can continue)
    graph.add_conditional_edges(
        "run_diagnostics",
        can_continue_condition,
        {"continue": "chatbot", "stop": "diagnostic_stop"},
    )

    # No-results handler automatically ends the task
    graph.add_edge("handle_no_results", END)
    graph.add_edge("diagnostic_stop", END)
    graph.add_edge(START, "chatbot")

    # Set up checkpointing
    memory = MemorySaver()

    # Compile and return the graph
    return graph.compile(checkpointer=memory)
