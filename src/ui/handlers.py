"""Business logic handlers for UI operations.

This module contains the non-UI business logic that powers the Gradio interface.
Separates concerns: UI components in app.py, business logic here.
"""

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from core.config import get_resolved_model_name
from core.prompts import topic_prompt
from integrations.github.agent import close_agent_resources, create_configured_agent
from integrations.github.models import RepositoryRecord
from storage import ConversationStore, default_db_path
from ui.favorites import FavoritesState, SavedRepository


def convert_repository_record_to_dict(repo: RepositoryRecord) -> dict:
    """Convert a RepositoryRecord from state to UI dict format.

    Args:
        repo: RepositoryRecord object from graph state

    Returns:
        Dictionary with UI-expected keys
    """
    return {
        "full_name": repo.name,
        "url": repo.url,
        "stars": repo.stars,
        "language": repo.language or "",
        "topics": repo.topics,
        "description": repo.description or "",
    }


class SearchHandler:
    """Handle repository search operations."""

    @staticmethod
    async def search_with_extraction(
        topics: str, language: str | None, favorites: dict
    ) -> AsyncIterator[tuple[str, list[dict], dict]]:
        """Stream repository search results into the Gradio UI."""
        if not topics.strip():
            yield "Please enter at least one topic.", [], favorites
            return

        search_query = topics.strip()
        language_filter = language if language and language != "Any" else ""
        filters_text = f"Language: {language_filter}" if language_filter else ""

        thread_id = str(uuid.uuid4())

        with ConversationStore() as store:
            store.create_conversation(
                thread_id,
                "topics",
                f"UI Search: {search_query}",
                model_name=get_resolved_model_name(None),
            )

        agent = create_configured_agent(model_name_override=None, memory=None)
        try:
            config = {"configurable": {"thread_id": thread_id}}
            formatted_prompt = topic_prompt.template.format(
                topics=search_query,
                sort="stars",
                limit="10",
                language=language_filter,
                license="",
                min_stars="10",
                max_stars="",
                pushed_after="",
                archived="",
                fork="",
                filters_text=filters_text,
            )
            input_state = {"messages": [HumanMessage(formatted_prompt)]}

            full_response: list[str] = []
            final_state: dict | None = None

            async with AsyncSqliteSaver.from_conn_string(default_db_path()) as saver:
                agent.checkpointer = saver
                try:
                    async for event in agent.astream(
                        input_state, config, stream_mode="values"
                    ):
                        final_state = event
                        last_message = event.get("messages", [None])[-1]
                        content = getattr(last_message, "content", None)
                        if isinstance(content, str) and content:
                            full_response.append(content)
                            yield "\n\n".join(full_response), [], favorites
                finally:
                    agent.checkpointer = None

            final_output = "\n\n".join(full_response)
            final_output += f"\n\n---\n💾 **Thread ID:** `{thread_id}`"

            repos: list[dict] = []
            if final_state and "tracked_repositories" in final_state:
                repos = [
                    convert_repository_record_to_dict(repo)
                    for repo in final_state["tracked_repositories"]
                ]

            yield final_output, repos, favorites

        except Exception as e:
            yield f"Error during search: {str(e)}", [], favorites
        finally:
            close_agent_resources(agent)


class FavoritesHandler:
    """Handle favorites/saved repositories operations."""

    @staticmethod
    def save_repository(
        repo_name: str, available_repos: list[dict], favorites: dict
    ) -> tuple[dict, str, bool]:
        """Save a repository to favorites.

        Args:
            repo_name: Full repository name (owner/repo)
            available_repos: List of repositories from recent search
            favorites: Current favorites state

        Returns:
            Tuple of (updated_favorites, status_message, show_status)
        """
        if not repo_name.strip():
            return favorites, "⚠️ Please enter a repository name", True

        # Convert dict to FavoritesState
        state = FavoritesState.model_validate(favorites or {})

        # Find repository in available list
        repo_to_save = None
        for repo in available_repos:
            if repo["full_name"].lower() == repo_name.lower():
                repo_to_save = repo
                break

        if not repo_to_save:
            # Try to create minimal repo entry
            if "/" in repo_name:
                repo_to_save = {
                    "full_name": repo_name,
                    "url": f"https://github.com/{repo_name}",
                    "stars": 0,
                    "language": "",
                    "topics": [],
                    "description": "",
                }
            else:
                return (
                    favorites,
                    f"❌ Repository '{repo_name}' not found in results",
                    True,
                )

        # Convert dict to SavedRepository
        saved_repo = SavedRepository(
            full_name=repo_to_save["full_name"],
            url=repo_to_save["url"],
            stars=repo_to_save["stars"],
            language=repo_to_save.get("language", ""),
            topics=repo_to_save.get("topics", []),
            description=repo_to_save.get("description", ""),
            saved_at=datetime.now(UTC),
        )

        state.add_repository(saved_repo)
        return state.model_dump(mode="json"), f"✅ Saved {repo_name}", True

    @staticmethod
    def remove_repository(
        full_name: str, favorites: dict
    ) -> tuple[dict, list[list], str]:
        """Remove a repository from favorites.

        Args:
            full_name: Full repository name (owner/repo)
            favorites: Current favorites state

        Returns:
            Tuple of (updated_favorites, updated_table_data, cleared_input)
        """
        state = FavoritesState.model_validate(favorites or {})
        state.remove_repository(full_name)
        updated_favorites = state.model_dump(mode="json")
        updated_table = state.get_table_data()
        return updated_favorites, updated_table, ""

    @staticmethod
    def refresh_table(favorites: dict) -> list[list]:
        """Refresh the favorites table display.

        Args:
            favorites: Current favorites state

        Returns:
            Table data for Gradio Dataframe
        """
        state = FavoritesState.model_validate(favorites or {})
        return state.get_table_data()

    @staticmethod
    def export_to_csv(favorites: dict) -> dict:
        """Export favorites to CSV file.

        Args:
            favorites: Current favorites state

        Returns:
            Gradio update dict with file path and visibility
        """
        import gradio as gr

        state = FavoritesState.model_validate(favorites or {})
        csv_content = state.export_csv()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, prefix="github_agent_favorites_"
        ) as f:
            f.write(csv_content)
            file_path = f.name

        return gr.update(value=file_path, visible=True)


class RepositoryDisplayHandler:
    """Handle repository display formatting."""

    @staticmethod
    def format_repos_for_table(repos: list[dict]) -> dict:
        """Format repository list for Gradio table display.

        Args:
            repos: List of repository dictionaries

        Returns:
            Gradio update dict for Dataframe component
        """
        if not repos:
            return {"visible": False}

        display_data = [
            [
                r["full_name"],
                r["stars"],
                r["language"],
                (
                    r["description"][:80] + "..."
                    if len(r["description"]) > 80
                    else r["description"]
                ),
                "➡️ Use form below to save",
            ]
            for r in repos
        ]
        return {"value": display_data, "visible": True}
