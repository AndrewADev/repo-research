"""
LangGraph agent for GitHub analysis workflow.

This module creates and configures the LangGraph state machine that orchestrates
GitHub analysis tasks using the configured LLM provider and GitHub tools.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from core.llm import create_llm
from tools.date_tools import CurrentDateTool, DateOffsetTool

from .adapter import (
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
    provider: str = "ollama",
    anthropic_api_key: str | None = None,
    ollama_base_url: str = "http://localhost:11434",
    model: str | None = None,
    temperature: float = 0,
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
    llm = create_llm(
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
