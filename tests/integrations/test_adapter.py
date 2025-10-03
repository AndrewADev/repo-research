"""
Unit tests for GitHub adapter functions.

Tests data transformation and parsing functions without requiring network access.
"""

from datetime import datetime

from integrations.github.adapter import parse_repository_data
from integrations.github.models import RepositoryRecord


class TestParseRepositoryData:
    """Test cases for parse_repository_data function."""

    def test_parse_repository_data_complete(self):
        """Test parsing repository dictionary with all fields."""
        repo_dict = {
            "name": "owner/repo",
            "description": "Test repo",
            "stars": 100,
            "forks": 20,
            "language": "Python",
            "url": "https://github.com/owner/repo",
            "updated_at": datetime(2024, 1, 1),
            "created_at": datetime(2023, 1, 1),
            "pushed_at": datetime(2024, 1, 2),
            "topics": ["ai", "ml"],
            "open_issues": 5,
            "size": 1024,
            "archived": False,
            "fork": False,
            "private": False,
            "license": "MIT",
        }

        result = parse_repository_data(repo_dict)

        assert isinstance(result, RepositoryRecord)
        assert result.name == "owner/repo"
        assert result.description == "Test repo"
        assert result.stars == 100
        assert result.forks == 20
        assert result.language == "Python"
        assert result.url == "https://github.com/owner/repo"
        assert result.updated_at == datetime(2024, 1, 1)
        assert result.created_at == datetime(2023, 1, 1)
        assert result.pushed_at == datetime(2024, 1, 2)
        assert result.topics == ["ai", "ml"]
        assert result.open_issues == 5
        assert result.size == 1024
        assert result.archived is False
        assert result.fork is False
        assert result.private is False
        assert result.license == "MIT"

    def test_parse_repository_data_minimal(self):
        """Test parsing repository dictionary with only required fields."""
        repo_dict = {
            "name": "owner/repo",
            "stars": 50,
            "url": "https://github.com/owner/repo",
        }

        result = parse_repository_data(repo_dict)

        assert isinstance(result, RepositoryRecord)
        assert result.name == "owner/repo"
        assert result.stars == 50
        assert result.url == "https://github.com/owner/repo"
        # Check defaults for optional fields
        assert result.description is None
        assert result.forks == 0
        assert result.language is None
        assert result.topics == []
        assert result.open_issues == 0
        assert result.archived is False
        assert result.fork is False
        assert result.private is False
        assert result.license is None

    def test_parse_repository_data_missing_optional_fields(self):
        """Test parsing repository dictionary with missing optional fields."""
        repo_dict = {
            "name": "test/repo",
            "stars": 25,
            "url": "https://github.com/test/repo",
            # Explicitly missing: description, language, license, updated_at, etc.
        }

        result = parse_repository_data(repo_dict)

        assert result.name == "test/repo"
        assert result.stars == 25
        assert result.description is None
        assert result.language is None
        assert result.updated_at is None
        assert result.created_at is None
        assert result.pushed_at is None

    def test_parse_repository_data_with_empty_topics(self):
        """Test parsing repository with empty topics list."""
        repo_dict = {
            "name": "owner/repo",
            "stars": 10,
            "url": "https://github.com/owner/repo",
            "topics": [],
        }

        result = parse_repository_data(repo_dict)

        assert result.topics == []

    def test_parse_repository_data_archived_fork(self):
        """Test parsing archived fork repository."""
        repo_dict = {
            "name": "fork/repo",
            "stars": 5,
            "url": "https://github.com/fork/repo",
            "archived": True,
            "fork": True,
            "private": True,
        }

        result = parse_repository_data(repo_dict)

        assert result.archived is True
        assert result.fork is True
        assert result.private is True

    def test_parse_repository_data_zero_counts(self):
        """Test parsing repository with zero stars, forks, and issues."""
        repo_dict = {
            "name": "new/repo",
            "stars": 0,
            "forks": 0,
            "open_issues": 0,
            "url": "https://github.com/new/repo",
        }

        result = parse_repository_data(repo_dict)

        assert result.stars == 0
        assert result.forks == 0
        assert result.open_issues == 0

    def test_parse_repository_data_with_size(self):
        """Test parsing repository with size in KB."""
        repo_dict = {
            "name": "big/repo",
            "stars": 100,
            "url": "https://github.com/big/repo",
            "size": 50000,  # 50MB
        }

        result = parse_repository_data(repo_dict)

        assert result.size == 50000

    def test_parse_repository_data_multiple_topics(self):
        """Test parsing repository with multiple topics."""
        repo_dict = {
            "name": "cool/repo",
            "stars": 200,
            "url": "https://github.com/cool/repo",
            "topics": ["python", "machine-learning", "data-science", "ai", "nlp"],
        }

        result = parse_repository_data(repo_dict)

        assert len(result.topics) == 5
        assert "python" in result.topics
        assert "machine-learning" in result.topics
        assert "nlp" in result.topics
