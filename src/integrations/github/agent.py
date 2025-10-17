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
from langgraph.prebuilt import tools_condition
from langgraph.types import Command

from core.config import LLMProviderConfig
from core.llm import create_llm
from tools.date_tools import CurrentDateTool, DateOffsetTool
from tools.utils import generate_tool_call_id

from .adapter import (
    CommitHotspotAnalysisTool,
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
        CommitHotspotAnalysisTool(),
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

    # Create tools-by-name mapping for custom tool node
    tools_by_name = {tool.name: tool for tool in tools}

    def call_tools(state: GitHubToolState):
        """
        Custom tool node that handles Command returns from tools.

        Executes tools and processes Command objects to update state properly.
        For tools that return strings, wraps them in ToolMessages.
        Also sets current_predicate for contextual error messages.
        """
        from langchain_core.messages import ToolMessage

        messages = state.get("messages", [])
        if not messages:
            return {}

        last_message = messages[-1]
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {}

        # Determine predicate from tool calls
        tool_calls = last_message.tool_calls
        current_predicate = None

        if tool_calls:
            tool_name = tool_calls[0].get("name", "")
            # Map tool names to entity predicates
            predicate_map = {
                "get_starred_repositories": "repositories",
                "search_repositories": "repositories",
                "search_repositories_by_topic": "repositories",
                "query_issues": "issues",
            }
            current_predicate = predicate_map.get(tool_name)

        # Execute tools and collect results
        commands = []
        tool_messages = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_call_id = tool_call.get("id", generate_tool_call_id())
            tool = tools_by_name.get(tool_name)

            if tool:
                try:
                    # Prepare tool input with injected parameters
                    tool_input = tool_call.get("args", {}).copy()

                    # Invoke the tool with the prepared input
                    result = tool.run(tool_input, tool_call_id=tool_call_id)

                    # If tool returns Command, collect it
                    if isinstance(result, Command):
                        commands.append(result)
                    else:
                        # Tool returned string - wrap in ToolMessage
                        tool_message = ToolMessage(
                            content=str(result),
                            tool_call_id=tool_call_id,
                            name=tool_name,
                        )
                        tool_messages.append(tool_message)
                except Exception as e:
                    # Handle tool execution errors
                    error_message = ToolMessage(
                        content=f"Error executing {tool_name}: {str(e)}",
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )
                    tool_messages.append(error_message)

        # Build state update
        state_update = {}

        # Add tool messages if any
        if tool_messages:
            state_update["messages"] = tool_messages

        # Add current_predicate if determined
        if current_predicate:
            state_update["current_predicate"] = current_predicate

        # If we have Commands, merge the first Command with our state_update
        # and return all Commands
        if commands:
            if state_update:
                # Merge state_update into first Command
                if commands[0].update is None:
                    commands[0] = Command(update=state_update)
                else:
                    commands[0].update.update(state_update)
            return commands

        # No Commands - return state update dict
        return state_update if state_update else {}

    # Add nodes to graph
    graph.add_node("chatbot", chatbot)
    graph.add_node("tools", call_tools)
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
