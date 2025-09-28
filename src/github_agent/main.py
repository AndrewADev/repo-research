import os

import typer
from dotenv import load_dotenv

from core.models import TemplatedPrompt, ThreadedPrompt
from core.prompts import comprehensive_analysis, run_diagnostic, topic_prompt
from tools.github_adapter import create_graph

# Load environment variables
load_dotenv()

# Configure LLM provider
provider = os.getenv("LLM_PROVIDER", "ollama")  # Default to ollama
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
model_name = os.getenv("MODEL_NAME", None)

# Create the graph
graph = create_graph(
    provider=provider,
    anthropic_api_key=anthropic_api_key,
    ollama_base_url=ollama_base_url,
    model=model_name,
)

# Configure the execution
config = {"configurable": {"thread_id": "example_chat"}}

# analysis_prompt = """
# I need a comprehensive analysis of the most popular AI framework repositories.
# 1. First, find the top 5 AI framework repositories with more than 10000 stars
# 2. For each of these repositories, analyze their recent activity
# 3. Provide a summary of which framework seems to be most actively maintained
# """

app = typer.Typer(rich_markup_mode="rich")


def run_prompt(prompt: ThreadedPrompt):
    # Run the analysis
    try:
        # Initialize with our first message
        events = graph.stream(
            {"messages": [("user", prompt.prompt)]}, config, stream_mode="values"
        )

        # Track if we hit a diagnostic stop condition
        diagnostic_stopped = False

        # Print each event as it occurs
        for event in events:
            if "messages" in event:
                last_message = event["messages"][-1]
                print(f"Step output: {last_message.content}\n")

                # Check if this was a diagnostic stop message
                if (
                    hasattr(last_message, "content")
                    and "Execution Stopped Due to Diagnostics" in last_message.content
                ):
                    diagnostic_stopped = True

    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        diagnostic_stopped = True

    # Only run follow-ups if we didn't stop due to diagnostics
    if not diagnostic_stopped:
        for follow_up in prompt.follow_ups:
            events = graph.stream(
                {"messages": [("user", follow_up)]}, config, stream_mode="values"
            )

            for event in events:
                if "messages" in event:
                    last_message = event["messages"][-1]
                    print(f"Follow-up response: {last_message.content}\n")
    else:
        print("⚠️ Skipping follow-up prompts due to diagnostic stop condition.")


def run_templated_prompt(prompt: TemplatedPrompt, user_args: list[str]):
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
def diagnostics():
    """Diagnose issues with the setup"""
    run_prompt(run_diagnostic)


@app.command()
def analyze():
    """Run comprehensive analysis of starred repositories"""
    run_prompt(comprehensive_analysis)


@app.command()
def topics(topics_raw: str):
    """Search for repositories related to specific topics/with specific labels"""

    parsed_topics = topics_raw.split(",")

    run_templated_prompt(topic_prompt, parsed_topics)


if __name__ == "__main__":
    app()
