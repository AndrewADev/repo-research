"""Tests for favorites/saved repositories functionality."""

from datetime import UTC, datetime

import pytest

from ui.favorites import FavoritesState, SavedRepository


@pytest.fixture
def sample_repo():
    """Create a sample SavedRepository."""
    return SavedRepository(
        full_name="langchain-ai/langgraph",
        url="https://github.com/langchain-ai/langgraph",
        stars=12500,
        language="Python",
        topics=["ai", "agents", "langgraph"],
        description="Build stateful agents with LangGraph",
        saved_at=datetime(2025, 10, 2, 14, 30, 0, tzinfo=UTC),
    )


@pytest.fixture
def another_repo():
    """Create another sample SavedRepository."""
    return SavedRepository(
        full_name="openai/gpt-4",
        url="https://github.com/openai/gpt-4",
        stars=50000,
        language="Python",
        topics=["llm", "ai"],
        description="GPT-4 model",
        saved_at=datetime(2025, 10, 2, 15, 0, 0, tzinfo=UTC),
    )


def test_add_repository_to_empty_favorites(sample_repo):
    """Test adding a repository to empty favorites."""
    state = FavoritesState()

    was_added = state.add_repository(sample_repo)

    assert was_added is True
    assert len(state.saved_repos) == 1
    assert state.saved_repos[0].full_name == "langchain-ai/langgraph"


def test_add_repository_to_existing_favorites(sample_repo, another_repo):
    """Test adding a repository to existing favorites."""
    state = FavoritesState(saved_repos=[sample_repo])

    was_added = state.add_repository(another_repo)

    assert was_added is True
    assert len(state.saved_repos) == 2
    # New repo should be first (prepended)
    assert state.saved_repos[0].full_name == "openai/gpt-4"
    assert state.saved_repos[1].full_name == "langchain-ai/langgraph"


def test_add_duplicate_repository(sample_repo):
    """Test that adding duplicate repository doesn't create duplicates."""
    state = FavoritesState(saved_repos=[sample_repo])

    was_added = state.add_repository(sample_repo)

    assert was_added is False
    assert len(state.saved_repos) == 1
    assert state.saved_repos[0].full_name == "langchain-ai/langgraph"


def test_remove_repository(sample_repo, another_repo):
    """Test removing a repository from favorites."""
    state = FavoritesState(saved_repos=[sample_repo, another_repo])

    was_removed = state.remove_repository("langchain-ai/langgraph")

    assert was_removed is True
    assert len(state.saved_repos) == 1
    assert state.saved_repos[0].full_name == "openai/gpt-4"


def test_remove_nonexistent_repository(sample_repo):
    """Test removing a repository that doesn't exist."""
    state = FavoritesState(saved_repos=[sample_repo])

    was_removed = state.remove_repository("nonexistent/repo")

    assert was_removed is False
    assert len(state.saved_repos) == 1
    assert state.saved_repos[0].full_name == "langchain-ai/langgraph"


def test_remove_from_empty_favorites():
    """Test removing from empty favorites."""
    state = FavoritesState()

    was_removed = state.remove_repository("any/repo")

    assert was_removed is False
    assert len(state.saved_repos) == 0


def test_is_repository_saved(sample_repo):
    """Test checking if repository is saved."""
    state = FavoritesState(saved_repos=[sample_repo])

    assert state.is_repository_saved("langchain-ai/langgraph") is True
    assert state.is_repository_saved("other/repo") is False

    empty_state = FavoritesState()
    assert empty_state.is_repository_saved("any/repo") is False


def test_get_saved_repos_table_empty():
    """Test getting table data from empty favorites."""
    state = FavoritesState()
    result = state.get_table_data()
    assert result == []


def test_get_saved_repos_table_with_data(sample_repo):
    """Test getting table data with repositories."""
    state = FavoritesState(saved_repos=[sample_repo])

    result = state.get_table_data()

    assert len(result) == 1
    assert result[0][0] == "langchain-ai/langgraph"  # full_name
    assert result[0][1] == "https://github.com/langchain-ai/langgraph"  # url
    assert result[0][2] == 12500  # stars
    assert result[0][3] == "Python"  # language
    assert result[0][4] == "ai, agents, langgraph"  # topics
    assert "Build stateful" in result[0][5]  # description
    assert result[0][6] == "2025-10-02T14:30:00"  # saved_at (trimmed)


def test_get_saved_repos_table_truncates_long_description():
    """Test that long descriptions are truncated."""
    repo = SavedRepository(
        full_name="test/repo",
        url="https://github.com/test/repo",
        stars=100,
        language="Go",
        topics=[],
        description="A" * 150,  # 150 character description
        saved_at=datetime(2025, 10, 2, 14, 30, 0, tzinfo=UTC),
    )
    state = FavoritesState(saved_repos=[repo])

    result = state.get_table_data()

    assert len(result[0][5]) == 100  # Truncated to 100 chars


def test_get_saved_repos_table_limits_topics():
    """Test that topics are limited to 5."""
    repo = SavedRepository(
        full_name="test/repo",
        url="https://github.com/test/repo",
        stars=100,
        language="JavaScript",
        topics=[
            "topic1",
            "topic2",
            "topic3",
            "topic4",
            "topic5",
            "topic6",
            "topic7",
        ],
        description="Test",
        saved_at=datetime(2025, 10, 2, 14, 30, 0, tzinfo=UTC),
    )
    state = FavoritesState(saved_repos=[repo])

    result = state.get_table_data()

    topics_str = result[0][4]
    topics_list = topics_str.split(", ")
    assert len(topics_list) == 5


def test_export_favorites_csv_empty():
    """Test exporting empty favorites."""
    state = FavoritesState()
    result = state.export_csv()

    assert "full_name,url,stars,language,topics,description,saved_at" in result
    assert result.count("\n") == 0  # Only header (no trailing newline)


def test_export_favorites_csv_with_data(sample_repo):
    """Test exporting favorites with data."""
    state = FavoritesState(saved_repos=[sample_repo])

    result = state.export_csv()

    lines = result.strip().split("\n")
    assert len(lines) == 2  # Header + 1 data row
    assert "langchain-ai/langgraph" in lines[1]
    assert "12500" in lines[1]
    assert "Python" in lines[1]


def test_export_favorites_csv_handles_special_characters():
    """Test that CSV export handles commas and quotes in descriptions."""
    repo = SavedRepository(
        full_name="test/repo",
        url="https://github.com/test/repo",
        stars=100,
        language="Python",
        topics=["ai", "ml"],
        description='A test, with "quotes" and, commas',
        saved_at=datetime(2025, 10, 2, 14, 30, 0, tzinfo=UTC),
    )
    state = FavoritesState(saved_repos=[repo])

    result = state.export_csv()

    # Description should be quoted and commas should be replaced with semicolons
    assert "quotes" in result


def test_export_favorites_csv_handles_newlines():
    """Test that CSV export handles newlines in descriptions."""
    repo = SavedRepository(
        full_name="test/repo",
        url="https://github.com/test/repo",
        stars=100,
        language="Python",
        topics=[],
        description="Line 1\nLine 2\nLine 3",
        saved_at=datetime(2025, 10, 2, 14, 30, 0, tzinfo=UTC),
    )
    state = FavoritesState(saved_repos=[repo])

    result = state.export_csv()

    # Newlines should be replaced with spaces
    assert "\n\n" not in result.split("\n")[1]  # No double newlines in data row
