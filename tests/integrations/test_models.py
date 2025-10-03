"""
Unit tests for GitHub integration models.

Tests state management and reducer functions without requiring network access.
"""

from src.integrations.github.models import RepositoryRecord, add_repositories


class TestRepositoryRecord:
    """Test cases for RepositoryRecord model."""

    def test_repository_record_creation_minimal(self):
        """Test creating RepositoryRecord with only required fields."""
        repo = RepositoryRecord(
            name="user/project", stars=50, url="https://github.com/user/project"
        )  # pyright: ignore[reportCallIssue]

        assert repo.name == "user/project"
        assert repo.stars == 50
        assert repo.url == "https://github.com/user/project"
        # Check defaults
        assert repo.description is None
        assert repo.forks == 0
        assert repo.topics == []
        assert repo.archived is False


class TestAddRepositoriesReducer:
    """Test cases for add_repositories reducer function."""

    def test_add_repositories_with_none_existing(self):
        """Test adding repositories when existing list is None."""
        repo1 = RepositoryRecord(
            name="repo1", stars=100, url="https://github.com/owner/repo1"
        )  # pyright: ignore[reportCallIssue]

        result = add_repositories(None, [repo1])

        assert len(result) == 1
        assert result[0].name == "repo1"
        assert result[0].stars == 100

    def test_add_repositories_with_existing(self):
        """Test adding repositories to existing list."""
        repo1 = RepositoryRecord(
            name="repo1", stars=100, url="https://github.com/owner/repo1"
        )  # pyright: ignore[reportCallIssue]
        repo2 = RepositoryRecord(
            name="repo2", stars=200, url="https://github.com/owner/repo2"
        )  # pyright: ignore[reportCallIssue]

        result = add_repositories([repo1], [repo2])

        assert len(result) == 2
        assert result[0].name == "repo1"
        assert result[1].name == "repo2"
        assert result[0].stars == 100
        assert result[1].stars == 200

    def test_add_repositories_with_empty_new_list(self):
        """Test adding empty list to existing repositories."""
        repo1 = RepositoryRecord(
            name="repo1", stars=100, url="https://github.com/owner/repo1"
        )  # pyright: ignore[reportCallIssue]

        result = add_repositories([repo1], [])

        assert len(result) == 1
        assert result[0].name == "repo1"

    def test_add_repositories_multiple_new_repos(self):
        """Test adding multiple new repositories at once."""
        existing = [
            RepositoryRecord(
                name="repo1", stars=100, url="https://github.com/owner/repo1"
            )  # pyright: ignore[reportCallIssue]
        ]
        new_repos = [
            RepositoryRecord(
                name="repo2", stars=200, url="https://github.com/owner/repo2"
            ),  # pyright: ignore[reportCallIssue]
            RepositoryRecord(
                name="repo3", stars=300, url="https://github.com/owner/repo3"
            ),  # pyright: ignore[reportCallIssue]
        ]

        result = add_repositories(existing, new_repos)

        assert len(result) == 3
        assert result[0].name == "repo1"
        assert result[1].name == "repo2"
        assert result[2].name == "repo3"

    def test_add_repositories_empty_existing(self):
        """Test adding to empty existing list."""
        new_repos = [
            RepositoryRecord(
                name="repo1", stars=100, url="https://github.com/owner/repo1"
            ),  # pyright: ignore[reportCallIssue]
            RepositoryRecord(
                name="repo2", stars=200, url="https://github.com/owner/repo2"
            ),  # pyright: ignore[reportCallIssue]
        ]

        result = add_repositories([], new_repos)

        assert len(result) == 2
        assert result[0].name == "repo1"
        assert result[1].name == "repo2"

    def test_add_repositories_preserves_order(self):
        """Test that add_repositories preserves insertion order."""
        repo1 = RepositoryRecord(
            name="a-repo", stars=10, url="https://github.com/owner/a-repo"
        )  # pyright: ignore[reportCallIssue]
        repo2 = RepositoryRecord(
            name="b-repo", stars=20, url="https://github.com/owner/b-repo"
        )  # pyright: ignore[reportCallIssue]
        repo3 = RepositoryRecord(
            name="c-repo", stars=30, url="https://github.com/owner/c-repo"
        )  # pyright: ignore[reportCallIssue]

        result = add_repositories([repo1], [repo2, repo3])

        assert result[0].name == "a-repo"
        assert result[1].name == "b-repo"
        assert result[2].name == "c-repo"

    def test_add_repositories_allows_duplicates(self):
        """Test that add_repositories allows duplicate repository names."""
        repo1 = RepositoryRecord(
            name="same-repo", stars=100, url="https://github.com/owner/same-repo"
        )  # pyright: ignore[reportCallIssue]
        repo2 = RepositoryRecord(
            name="same-repo", stars=100, url="https://github.com/owner/same-repo"
        )  # pyright: ignore[reportCallIssue]

        result = add_repositories([repo1], [repo2])

        # Should allow duplicates (no deduplication)
        assert len(result) == 2
        assert result[0].name == "same-repo"
        assert result[1].name == "same-repo"

    def test_add_repositories_preserves_repo_properties(self):
        """Test that all repository properties are preserved through reducer."""
        existing = [
            RepositoryRecord(
                name="existing",
                description="Existing repo",
                stars=50,
                forks=10,
                language="JavaScript",
                url="https://github.com/owner/existing",
                topics=["web"],
                archived=False,
            )  # pyright: ignore[reportCallIssue]
        ]
        new_repos = [
            RepositoryRecord(
                name="new",
                description="New repo",
                stars=100,
                forks=20,
                language="Python",
                url="https://github.com/owner/new",
                topics=["ai", "ml"],
                archived=True,
            )  # pyright: ignore[reportCallIssue]
        ]

        result = add_repositories(existing, new_repos)

        assert result[0].description == "Existing repo"
        assert result[0].language == "JavaScript"
        assert result[0].topics == ["web"]
        assert result[0].archived is False

        assert result[1].description == "New repo"
        assert result[1].language == "Python"
        assert result[1].topics == ["ai", "ml"]
        assert result[1].archived is True

    def test_add_repositories_with_none_and_empty_list(self):
        """Test edge case with None existing and empty new list."""
        result = add_repositories(None, [])

        assert result == []

    def test_add_repositories_sequential_additions(self):
        """Test sequential additions to build up repository list."""
        repo1 = RepositoryRecord(
            name="repo1", stars=10, url="https://github.com/owner/repo1"
        )  # pyright: ignore[reportCallIssue]
        repo2 = RepositoryRecord(
            name="repo2", stars=20, url="https://github.com/owner/repo2"
        )  # pyright: ignore[reportCallIssue]
        repo3 = RepositoryRecord(
            name="repo3", stars=30, url="https://github.com/owner/repo3"
        )  # pyright: ignore[reportCallIssue]

        # Simulate sequential state updates
        result1 = add_repositories(None, [repo1])
        result2 = add_repositories(result1, [repo2])
        result3 = add_repositories(result2, [repo3])

        assert len(result3) == 3
        assert result3[0].name == "repo1"
        assert result3[1].name == "repo2"
        assert result3[2].name == "repo3"
