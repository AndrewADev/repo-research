"""Gradio UI application for Repo Research."""

import gradio as gr
from dotenv import load_dotenv

from ui.components import get_conversation_history, load_conversation_details
from ui.handlers import FavoritesHandler, RepositoryDisplayHandler, SearchHandler


def create_topics_tab(favorites_state):
    """Create the Topics Search tab interface.

    Args:
        favorites_state: Shared BrowserState for favorites
    """
    with gr.Tab("🔍 Topic Search"):
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

        # Hidden state to store extracted repositories
        extracted_repos = gr.State([])

        gr.Markdown("### Found Repositories")
        gr.Markdown("Click 'Save' to bookmark repositories to your favorites list.")

        repos_display = gr.Dataframe(
            headers=["Repository", "Stars", "Language", "Description", "Actions"],
            datatype=["str", "number", "str", "str", "str"],
            label="Extracted Repositories",
            interactive=False,
            visible=False,
        )

        with gr.Row():
            save_repo_input = gr.Textbox(
                label="Save Repository by Name",
                placeholder="owner/repo",
                scale=3,
            )
            save_button = gr.Button("💾 Save", variant="primary", scale=1)

        save_status = gr.Markdown(visible=False)

        # Wire up event handlers
        search_button.click(
            fn=SearchHandler.search_with_extraction,
            inputs=[topics_input, language_dropdown, favorites_state],
            outputs=[output_box, extracted_repos, favorites_state],
        )

        extracted_repos.change(
            fn=RepositoryDisplayHandler.format_repos_for_table,
            inputs=extracted_repos,
            outputs=repos_display,
        )

        def handle_save(repo_name, repos, favorites):
            updated_fav, msg, show = FavoritesHandler.save_repository(
                repo_name, repos, favorites
            )
            return updated_fav, gr.update(value=msg, visible=show)

        save_button.click(
            fn=handle_save,
            inputs=[save_repo_input, extracted_repos, favorites_state],
            outputs=[favorites_state, save_status],
        )


def create_saved_repos_tab(favorites_state):
    """Create the Saved Repositories tab interface.

    Args:
        favorites_state: Shared BrowserState for favorites
    """
    with gr.Tab("⭐ Saved Repositories"):
        gr.Markdown("## ⭐ Saved Repositories")
        gr.Markdown(
            "Your bookmarked repositories are stored locally in your browser. "
            "They will persist across sessions on this device "
            "(unless you clear site data)."
        )

        with gr.Row():
            refresh_button = gr.Button("🔄 Refresh", variant="secondary")
            export_button = gr.Button("📥 Export CSV", variant="secondary")

        repos_table = gr.Dataframe(
            headers=[
                "Repository",
                "URL",
                "Stars",
                "Language",
                "Topics",
                "Description",
                "Saved At",
            ],
            datatype=["str", "str", "number", "str", "str", "str", "str"],
            label="Saved Repositories",
            interactive=False,
            wrap=True,
        )

        with gr.Row():
            remove_input = gr.Textbox(
                label="Remove Repository",
                placeholder="Enter full name (e.g., owner/repo)",
                scale=3,
            )
            remove_button = gr.Button("🗑️ Remove", variant="stop", scale=1)

        export_output = gr.File(label="Downloaded CSV", visible=False)

        # Wire up event handlers
        refresh_button.click(
            fn=FavoritesHandler.refresh_table,
            inputs=favorites_state,
            outputs=repos_table,
        )

        remove_button.click(
            fn=FavoritesHandler.remove_repository,
            inputs=[remove_input, favorites_state],
            outputs=[favorites_state, repos_table, remove_input],
        )

        export_button.click(
            fn=FavoritesHandler.export_to_csv,
            inputs=favorites_state,
            outputs=export_output,
        )

        # Initialize table on app load by setting select event on the tab itself
        # This will be triggered when the parent Tabs component loads


def create_history_tab():
    """Create the Conversation History tab interface."""
    with gr.Tab("📚 History"):
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

        # Refresh handler
        def refresh_conversations(limit: int):
            return get_conversation_history(limit)

        # Load initial data using refresh handler
        refresh_button.click(
            fn=refresh_conversations, inputs=limit_slider, outputs=conversations_table
        )

        limit_slider.change(
            fn=refresh_conversations, inputs=limit_slider, outputs=conversations_table
        )

        # Selection handler - load_conversation_details expects SelectData event
        def handle_row_select(evt: gr.SelectData):
            return load_conversation_details(None, evt)

        conversations_table.select(
            fn=handle_row_select,
            outputs=conversation_viewer,
        )


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
    # One-time migration: copy favorites from the legacy localStorage key to the
    # new one on first page load if the new key is empty. Runs before BrowserState
    # reads its value.
    favorites_migration_js = """
    () => {
        const NEW_KEY = 'repo_research_favorites_v1';
        const OLD_KEY = 'github_agent_favorites_v1';
        try {
            if (!localStorage.getItem(NEW_KEY) && localStorage.getItem(OLD_KEY)) {
                localStorage.setItem(NEW_KEY, localStorage.getItem(OLD_KEY));
            }
        } catch (e) { /* localStorage unavailable; ignore */ }
    }
    """

    with gr.Blocks(
        title="Repo Research", theme=gr.themes.Soft(), js=favorites_migration_js
    ) as app:
        gr.Markdown("# 🔍 Repo Research")
        gr.Markdown(
            "Analyze GitHub repositories using AI-powered workflows. "
            "Powered by LangGraph and configurable LLM providers."
        )

        # Shared browser state for favorites across tabs
        # BrowserState persists in browser localStorage with explicit storage_key
        # This ensures data persists across both page refreshes AND server restarts
        # Note: If you see localStorage errors, clear your browser's site data
        favorites_state = gr.BrowserState(
            default_value={"saved_repos": []}, storage_key="repo_research_favorites_v1"
        )

        with gr.Tabs():
            create_topics_tab(favorites_state)
            create_saved_repos_tab(favorites_state)
            create_history_tab()

    app.launch(share=share, server_name=server_name, server_port=server_port)


if __name__ == "__main__":
    # Only load when running main Gradio entry point directly
    load_dotenv()
    launch_ui()
