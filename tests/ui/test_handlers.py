"""Tests for UI handlers (business logic).

Note: These tests focus on logic that doesn't require LLM calls.
Tests for SearchHandler.execute_topic_search() are excluded as they require
a live LangGraph agent and LLM connection.
"""

import pytest

from ui.handlers import FavoritesHandler, RepositoryDisplayHandler


class TestFavoritesHandler:
    """Tests for FavoritesHandler methods."""

    @pytest.fixture
    def search_result_repos(self):
        """Create sample repo search results (as json, since coming from Gradio UI)."""
        return [
            {
                "full_name": "langchain-ai/langgraph",
                "url": "https://github.com/langchain-ai/langgraph",
                "stars": 12500,
                "language": "Python",
                "topics": ["ai"],
                "description": "Build stateful agents",
            },
            {
                "full_name": "openai/gpt-4",
                "url": "https://github.com/openai/gpt-4",
                "stars": 50000,
                "language": "Python",
                "topics": ["llm"],
                "description": "GPT-4",
            },
        ]

    @pytest.fixture
    def favorites(self, search_result_repos):
        """Create sample favorites dict."""
        return {"saved_repos": [search_result_repos[0]]}

    def test_save_repository_found_in_list(self, search_result_repos, favorites):
        """Test saving a repository that exists in available list."""
        updated_fav, msg, show = FavoritesHandler.save_repository(
            "openai/gpt-4", search_result_repos, favorites
        )

        assert show is True
        assert "✅" in msg
        assert "openai/gpt-4" in msg
        assert len(updated_fav["saved_repos"]) == 2

    def test_save_repository_case_insensitive(self, search_result_repos, favorites):
        """Test that repository matching is case-insensitive."""
        updated_fav, msg, show = FavoritesHandler.save_repository(
            "OPENAI/GPT-4", search_result_repos, favorites
        )

        assert show is True
        assert "✅" in msg
        assert len(updated_fav["saved_repos"]) == 2

    def test_save_repository_not_in_list_creates_minimal(
        self, search_result_repos, favorites
    ):
        """Test saving a repository not in list creates minimal entry."""
        updated_fav, msg, show = FavoritesHandler.save_repository(
            "new/repo", search_result_repos, favorites
        )

        assert show is True
        assert "✅" in msg
        assert len(updated_fav["saved_repos"]) == 2
        # Find the new repo
        new_repo = [
            r for r in updated_fav["saved_repos"] if r["full_name"] == "new/repo"
        ][0]
        assert new_repo["stars"] == 0
        assert new_repo["url"] == "https://github.com/new/repo"

    def test_save_repository_invalid_name(self, search_result_repos, favorites):
        """Test saving repository with invalid name (no slash)."""
        updated_fav, msg, show = FavoritesHandler.save_repository(
            "invalidname", search_result_repos, favorites
        )

        assert show is True
        assert "❌" in msg
        assert "not found" in msg
        assert len(updated_fav["saved_repos"]) == 1  # Unchanged

    def test_save_repository_empty_name(self, search_result_repos, favorites):
        """Test saving repository with empty name."""
        updated_fav, msg, show = FavoritesHandler.save_repository(
            "", search_result_repos, favorites
        )

        assert show is True
        assert "⚠️" in msg
        assert "enter a repository name" in msg
        assert updated_fav == favorites  # Unchanged

    def test_save_repository_whitespace_name(self, search_result_repos, favorites):
        """Test saving repository with whitespace name."""
        updated_fav, msg, show = FavoritesHandler.save_repository(
            "   ", search_result_repos, favorites
        )

        assert show is True
        assert "⚠️" in msg
        assert updated_fav == favorites  # Unchanged

    def test_remove_repository(self, favorites):
        """Test removing a repository."""
        updated_fav, table, cleared_input = FavoritesHandler.remove_repository(
            "langchain-ai/langgraph", favorites
        )

        assert len(updated_fav["saved_repos"]) == 0
        assert cleared_input == ""
        assert table == []

    def test_remove_repository_not_found(self, favorites):
        """Test removing a repository that doesn't exist."""
        updated_fav, table, cleared_input = FavoritesHandler.remove_repository(
            "nonexistent/repo", favorites
        )

        assert len(updated_fav["saved_repos"]) == 1  # Unchanged
        assert cleared_input == ""

    def test_refresh_table_with_data(self, favorites):
        """Test refreshing table with data."""
        table = FavoritesHandler.refresh_table(favorites)

        assert len(table) == 1
        assert table[0][0] == "langchain-ai/langgraph"

    def test_refresh_table_empty(self):
        """Test refreshing table with empty favorites."""
        table = FavoritesHandler.refresh_table(None)
        assert table == []

        table = FavoritesHandler.refresh_table({"saved_repos": []})
        assert table == []

    def test_export_to_csv_creates_file(self, favorites):
        """Test that export creates a CSV file."""
        import os

        result = FavoritesHandler.export_to_csv(favorites)

        # Result is a Gradio update dict with value and visible keys
        assert result is not None
        assert isinstance(result, dict)
        assert "value" in result
        assert "visible" in result

        file_path = result["value"]
        assert os.path.exists(file_path)
        assert file_path.endswith(".csv")

        # Clean up
        os.remove(file_path)

    def test_export_to_csv_contains_data(self, favorites):
        """Test that exported CSV contains repository data."""
        import os

        result = FavoritesHandler.export_to_csv(favorites)
        file_path = result["value"]

        with open(file_path) as f:
            content = f.read()

        assert "langchain-ai/langgraph" in content
        assert "full_name" in content  # Header

        # Clean up
        os.remove(file_path)


class TestRepositoryDisplayHandler:
    """Tests for RepositoryDisplayHandler methods."""

    @pytest.fixture
    def sample_repos(self):
        """Create sample repository list (as json, since coming from Gradio UI)."""
        return [
            {
                "full_name": "repo1/test",
                "stars": 100,
                "language": "Python",
                "description": "Short description",
            },
            {
                "full_name": "repo2/test",
                "stars": 200,
                "language": "Go",
                "description": "A" * 100,  # Exactly 80 chars + "..."
            },
        ]

    def test_format_repos_for_table_with_data(self, sample_repos):
        """Test formatting repositories for table display."""
        result = RepositoryDisplayHandler.format_repos_for_table(sample_repos)

        assert result["visible"] is True
        assert "value" in result
        assert len(result["value"]) == 2
        assert result["value"][0][0] == "repo1/test"
        assert result["value"][0][1] == 100
        assert result["value"][1][2] == "Go"

    def test_format_repos_for_table_empty(self):
        """Test formatting empty repository list."""
        result = RepositoryDisplayHandler.format_repos_for_table([])

        assert result["visible"] is False
        assert "value" not in result

    def test_format_repos_for_table_truncates_description(self):
        """Test that long descriptions are truncated."""
        repos = [
            {
                "full_name": "test/repo",
                "stars": 50,
                "language": "Rust",
                "description": "A" * 150,  # Long description
            }
        ]

        result = RepositoryDisplayHandler.format_repos_for_table(repos)

        description = result["value"][0][3]
        assert len(description) <= 83  # 80 + "..."
        assert description.endswith("...")

    def test_format_repos_for_table_short_description(self):
        """Test that short descriptions are not truncated."""
        repos = [
            {
                "full_name": "test/repo",
                "stars": 50,
                "language": "JavaScript",
                "description": "Short",
            }
        ]

        result = RepositoryDisplayHandler.format_repos_for_table(repos)

        description = result["value"][0][3]
        assert description == "Short"
        assert not description.endswith("...")

    def test_format_repos_for_table_includes_action_hint(self, sample_repos):
        """Test that action column includes helpful text."""
        result = RepositoryDisplayHandler.format_repos_for_table(sample_repos)

        action_text = result["value"][0][4]
        assert "save" in action_text.lower()
        assert "➡️" in action_text
