"""
LangGraph agent for GitHub analysis workflow.

This module creates and configures the LangGraph state machine that orchestrates
GitHub analysis tasks using the configured LLM provider and GitHub tools.
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from core.config import LLMProviderConfig
from core.llm import create_llm
from tools.date_tools import CurrentDateTool, DateOffsetTool

from .adapter import (
    QueryIssuesTool,
    RateLimitCheckTool,
    RepositoryActivityTool,
    RepositoryLabelsTool,
    RepositorySearchByTopicTool,
    RepositorySearchTool,
    StarredRepositoriesTool,
    TokenValidationTool,
    can_continue_condition,
    diagnostic_stop_node,
    handle_no_results_node,
    result_analysis_condition,
    run_diagnostics_node,
)
from .models import GitHubToolState


def create_graph(
    provider_config: LLMProviderConfig,
    memory: BaseCheckpointSaver | None = None,
    temperature: float = 0,
    db_path: str | None = None,
):
    """
    Create a LangGraph for GitHub analysis with configurable LLM provider.

    Args:
        provider_config: Configuration for model provider
        temperature: Model temperature (0-1)
        db_path: Path to SQLite database for conversation persistence.
            Defaults to ~/.github-agent/conversations.db

    Returns:
        Tuple of (compiled_graph, sqlite_connection) - caller must close connection
    """
    # Initialize our graph builder
    graph = StateGraph(GitHubToolState)

    # Initialize our LLM
    llm = create_llm(
        provider_config,
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
        QueryIssuesTool(),
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

    # Create a tools node wrapper that sets current_predicate
    # NOTE: This is done here due to returning JSON strings instead of state
    # in the tools
    base_tool_node = ToolNode(tools=tools)

    def tool_node_with_predicate(state: GitHubToolState):
        """Wrap tool execution to set current_predicate based on tool being called."""
        # Determine predicate from the last message's tool calls
        messages = state.get("messages", [])
        current_predicate = None

        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                tool_name = last_message.tool_calls[0].get("name", "")
                # Map tool names to entity predicates
                predicate_map = {
                    "get_starred_repositories": "repositories",
                    "search_repositories": "repositories",
                    "search_repositories_by_topic": "repositories",
                    "query_issues": "issues",
                }
                current_predicate = predicate_map.get(tool_name)

        # Execute the base tool node
        result = base_tool_node.invoke(state)

        # Add current_predicate to the result
        if current_predicate:
            result["current_predicate"] = current_predicate

        return result

    # Add nodes to graph
    graph.add_node("chatbot", chatbot)
    graph.add_node("tools", tool_node_with_predicate)
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

    # Set up checkpointing with SqliteSaver
    if db_path is None:
        home_dir = Path.home()
        storage_dir = home_dir / ".github-agent"
        storage_dir.mkdir(exist_ok=True)
        db_path = str(storage_dir / "conversations.db")

    # Create persistent SQLite connection for checkpointing
    if not memory:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        memory = SqliteSaver(conn)

    # Compile and return the graph
    return graph.compile(checkpointer=memory, name="GitHubAgent")
