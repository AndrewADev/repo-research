import typer
from dotenv import load_dotenv

from core.config import get_config
from core.models import TemplatedPrompt, ThreadedPrompt
from core.prompts import comprehensive_analysis, run_diagnostic, topic_prompt
from integrations.github.agent import create_graph

# Load environment variables
load_dotenv()

# Configure the execution
config = {"configurable": {"thread_id": "example_chat"}}

app = typer.Typer(rich_markup_mode="rich")


def create_configured_graph(model_name_override: str | None = None):
    """Create a graph with the specified model configuration.

    Args:
        model_name_override: CLI-provided model name that overrides settings.

    Returns:
        Configured LangGraph instance
    """
    if model_name_override is not None:
        provider_config = get_config(model_name=model_name_override)
    else:
        provider_config = get_config()

    return create_graph(
        provider_config,
    )


def run_prompt(prompt: ThreadedPrompt, graph):
    # Run the analysis
    try:
        # Initialize with our first message
        events = graph.stream(
            {"messages": [("user", prompt.prompt)]}, config, stream_mode="values"
        )

        # Track if we hit a stop condition
        should_stop = False
        stop_reason = None

        # Print each event as it occurs
        for event in events:
            if "messages" in event:
                last_message = event["messages"][-1]
                print(f"Step output: {last_message.content}\n")

                # Check for various stop conditions
                if hasattr(last_message, "content"):
                    content = last_message.content
                    if "Execution Stopped Due to Diagnostics" in content:
                        should_stop = True
                        stop_reason = "diagnostics"
                    elif "Task Concluded" in content:
                        should_stop = True
                        stop_reason = "no_results"

    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        should_stop = True
        stop_reason = "exception"

    # Only run follow-ups if we didn't stop
    if not should_stop:
        for follow_up in prompt.follow_ups:
            events = graph.stream(
                {"messages": [("user", follow_up)]}, config, stream_mode="values"
            )

            for event in events:
                if "messages" in event:
                    last_message = event["messages"][-1]
                    print(f"Follow-up response: {last_message.content}\n")
    else:
        if stop_reason == "diagnostics":
            print("⚠️ Skipping follow-up prompts due to diagnostic stop condition.")
        elif stop_reason == "no_results":
            print("✅ Task completed - no results found.")
        elif stop_reason == "exception":
            print("❌ Skipping follow-up prompts due to error.")


def run_templated_prompt(prompt: TemplatedPrompt, user_args: list[str], graph):
    call_args = {}

    # Handle the case where we have multiple user args but only one template key
    # (e.g., multiple topics passed as comma-separated list)
    if len(prompt.keys) == 1 and len(user_args) > 1:
        # Join all arguments with commas for the single key
        key = prompt.keys[0]
        call_args[key] = ", ".join(user_args)
    else:
        # Original 1:1 mapping for multiple keys
        for i, key in enumerate(prompt.keys):
            if i < len(user_args):
                call_args[key] = user_args[i]
            else:
                call_args[key] = ""  # Default to empty string if not enough args

    # Format the template with the provided arguments
    formatted_prompt = prompt.template.format(**call_args)

    # Run the formatted prompt through the graph
    try:
        events = graph.stream(
            {"messages": [("user", formatted_prompt)]}, config, stream_mode="values"
        )

        for event in events:
            if "messages" in event:
                last_message = event["messages"][-1]
                print(f"Response: {last_message.content}\n")

    except Exception as e:
        print(f"Error during templated prompt execution: {str(e)}")


@app.command()
def diagnostics(
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
):
    """Diagnose issues with the setup"""
    graph = create_configured_graph(model_name)
    run_prompt(run_diagnostic, graph)


@app.command()
def analyze(
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
):
    """Run comprehensive analysis of starred repositories"""
    graph = create_configured_graph(model_name)
    run_prompt(comprehensive_analysis, graph)


@app.command()
def topics(
    topics_raw: str,
    model_name: str = typer.Option(
        None, "--model-name", help="Override the model name for this command"
    ),
):
    """Search for repositories related to specific topics/with specific labels"""
    graph = create_configured_graph(model_name)
    parsed_topics = topics_raw.split(",")

    run_templated_prompt(topic_prompt, parsed_topics, graph)


if __name__ == "__main__":
    app()
