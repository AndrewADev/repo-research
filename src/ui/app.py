"""Gradio UI application for GitHub Agent."""

import uuid
from collections.abc import Iterator

import gradio as gr
from dotenv import load_dotenv

from core.config import get_resolved_model_name
from core.prompts import topic_prompt
from github_agent.main import close_agent_resources, create_configured_agent
from storage import ConversationStore
from ui.components import get_conversation_history, load_conversation_details


def stream_topic_search(topics: str, language: str | None) -> Iterator[str]:
    """Execute topic search and stream results.

    Args:
        topics: Comma-separated topics to search
        language: Optional programming language filter

    Yields:
        Streaming response chunks
    """
    if not topics.strip():
        yield "Please enter at least one topic."
        return

    # Combine topics and language
    search_query = topics.strip()
    if language and language != "Any":
        search_query = f"{search_query},{language}"

    # Generate thread ID
    thread_id = str(uuid.uuid4())

    with ConversationStore() as store:
        resolved_model = get_resolved_model_name(None)
        store.create_conversation(
            thread_id,
            "topics",
            f"UI Search: {search_query}",
            model_name=resolved_model,
        )

    # Create agent and run search (memory is created internally)
    agent = create_configured_agent(model_name_override=None, memory=None)
    try:
        # Configure thread
        config = {"configurable": {"thread_id": thread_id}}

        # Format prompt
        call_args = {"topics": search_query}
        if isinstance(topic_prompt.template, object) and hasattr(
            topic_prompt.template, "format"
        ):
            formatted_prompt = topic_prompt.template.format(**call_args)
        else:
            formatted_prompt = str(topic_prompt.template)

        # Stream events
        events = agent.stream(
            {"messages": [("user", formatted_prompt)]}, config, stream_mode="values"
        )

        full_response = []
        for event in events:
            if "messages" in event:
                last_message = event["messages"][-1]
                if hasattr(last_message, "content"):
                    content = last_message.content
                    full_response.append(content)
                    yield "\n\n".join(full_response)

        # Add thread ID at the end
        final_output = "\n\n".join(full_response)
        final_output += f"\n\n---\n💾 **Thread ID:** `{thread_id}`"
        yield final_output

    except Exception as e:
        yield f"Error during search: {str(e)}"
    finally:
        close_agent_resources(agent)


def create_topics_tab() -> gr.Blocks:
    """Create the Topics Search tab interface.

    Returns:
        Gradio Blocks component for topics tab
    """
    with gr.Blocks() as topics_tab:
        gr.Markdown("## 🔍 Search GitHub Repositories by Topics")
        gr.Markdown(
            "Search for recently active GitHub repositories by topics and "
            "programming language."
        )

        with gr.Row():
            with gr.Column(scale=3):
                topics_input = gr.Textbox(
                    label="Topics",
                    placeholder="e.g., machine-learning, ai, transformers",
                    info="Enter comma-separated topics",
                )
            with gr.Column(scale=1):
                language_dropdown = gr.Dropdown(
                    choices=[
                        "Any",
                        "Python",
                        "JavaScript",
                        "TypeScript",
                        "Go",
                        "Rust",
                        "Java",
                        "C++",
                        "C",
                        "Ruby",
                        "PHP",
                    ],
                    value="Any",
                    label="Language",
                    info="Filter by programming language",
                )

        search_button = gr.Button("Search", variant="primary")

        output_box = gr.Markdown(label="Results")

        search_button.click(
            fn=stream_topic_search,
            inputs=[topics_input, language_dropdown],
            outputs=output_box,
        )

    return topics_tab


def create_history_tab() -> gr.Blocks:
    """Create the Conversation History tab interface.

    Returns:
        Gradio Blocks component for history tab
    """
    with gr.Blocks() as history_tab:
        gr.Markdown("## 📚 Conversation History")
        gr.Markdown("View and browse your conversation history.")

        with gr.Row():
            limit_slider = gr.Slider(
                minimum=5,
                maximum=100,
                value=20,
                step=5,
                label="Number of conversations to show",
            )
            refresh_button = gr.Button("Refresh", variant="secondary")

        conversations_table = gr.Dataframe(
            headers=[
                "Thread ID",
                "Command",
                "Summary",
                "Model",
                "Created",
                "Messages",
            ],
            datatype=["str", "str", "str", "str", "str", "number"],
            label="Recent Conversations",
            interactive=False,
            wrap=True,
        )

        gr.Markdown("### Conversation Details")
        gr.Markdown("Click on a row above to view the full conversation.")

        conversation_viewer = gr.HTML(label="Conversation")

        # State to track selected thread
        selected_thread = gr.State(None)

        # Load initial data
        conversations_table.value = get_conversation_history(20)

        # Refresh handler
        def refresh_conversations(limit: int):
            return get_conversation_history(limit)

        refresh_button.click(
            fn=refresh_conversations, inputs=limit_slider, outputs=conversations_table
        )

        limit_slider.change(
            fn=refresh_conversations, inputs=limit_slider, outputs=conversations_table
        )

        # Selection handler
        conversations_table.select(
            fn=load_conversation_details,
            inputs=selected_thread,
            outputs=conversation_viewer,
        )

    return history_tab


def launch_ui(
    share: bool = False,
    server_name: str = "127.0.0.1",
    server_port: int = 7860,
):
    """Launch the Gradio UI application.

    Args:
        share: Whether to create a public share link
        server_name: Server hostname/IP
        server_port: Server port number
    """
    with gr.Blocks(title="GitHub Agent", theme=gr.themes.Soft()) as app:
        gr.Markdown("# 🤖 GitHub Agent")
        gr.Markdown(
            "Analyze GitHub repositories using AI-powered workflows. "
            "Powered by LangGraph and configurable LLM providers."
        )

        with gr.Tabs():
            create_topics_tab()
            create_history_tab()

    app.launch(share=share, server_name=server_name, server_port=server_port)


if __name__ == "__main__":
    # Only load when running main Gradio entry point directly
    load_dotenv()
    launch_ui()
