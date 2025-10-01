from integrations.github.models import RepositorySearchByTopicInput
from integrations.github.tools import build_repository_search_query


class TestBuildRepositorySearchQuery:
    """Test cases for build_repository_search_query function."""

    def test_basic_topics_only(self):
        """Test query building with only topics."""
        params = RepositorySearchByTopicInput(
            topics=["python", "machine-learning"], min_stars=None
        )
        query = build_repository_search_query(params)
        assert query == "topic:python topic:machine-learning"

    def test_topics_with_language_and_license(self):
        """Test query building with topics, language, and license filters."""
        params = RepositorySearchByTopicInput(
            topics=["web", "api"], language="javascript", license="mit"
        )
        query = build_repository_search_query(params)
        assert "topic:web topic:api" in query
        assert "language:javascript" in query
        assert "license:mit" in query

    def test_star_range_filters(self):
        """Test query building with star count filters."""
        # Min and max stars
        params = RepositorySearchByTopicInput(
            topics=["ai"], min_stars=100, max_stars=1000
        )
        query = build_repository_search_query(params)
        assert "topic:ai" in query
        assert "stars:100..1000" in query

        # Only min stars
        params = RepositorySearchByTopicInput(topics=["ai"], min_stars=500)
        query = build_repository_search_query(params)
        assert "stars:>=500" in query

        # Only max stars
        params = RepositorySearchByTopicInput(
            topics=["ai"], min_stars=None, max_stars=200
        )
        query = build_repository_search_query(params)
        assert "stars:<=200" in query

    def test_fork_range_filters(self):
        """Test query building with fork count filters."""
        # Min and max forks
        params = RepositorySearchByTopicInput(
            topics=["devops"], min_forks=10, max_forks=50
        )
        query = build_repository_search_query(params)
        assert "forks:10..50" in query

        # Only min forks
        params = RepositorySearchByTopicInput(topics=["devops"], min_forks=25)
        query = build_repository_search_query(params)
        assert "forks:>=25" in query

    def test_date_filters(self):
        """Test query building with date filters."""
        params = RepositorySearchByTopicInput(
            topics=["blockchain"],
            created_after="2023-01-01",
            created_before="2023-12-31",
            updated_after="2024-01-01",
            pushed_after="2024-06-01",
            pushed_before="2024-12-31",
        )
        query = build_repository_search_query(params)
        assert "created:2023-01-01..2023-12-31" in query
        assert "updated:>=2024-01-01" in query
        assert "pushed:2024-06-01..2024-12-31" in query

    def test_size_filters(self):
        """Test query building with repository size filters."""
        params = RepositorySearchByTopicInput(
            topics=["microservices"], size_min_kb=100, size_max_kb=5000
        )
        query = build_repository_search_query(params)
        assert "size:100..5000" in query

    def test_boolean_filters(self):
        """Test query building with boolean filters."""
        params = RepositorySearchByTopicInput(
            topics=["template"],
            archived=False,
            template=True,
            fork=False,
            is_public=True,
        )
        query = build_repository_search_query(params)
        assert "archived:false" in query
        assert "template:true" in query
        assert "fork:false" in query
        assert "is:public" in query

    def test_comprehensive_query(self):
        """Test query building with multiple filter types combined."""
        params = RepositorySearchByTopicInput(
            topics=["data-science", "analytics"],
            language="python",
            license="apache-2.0",
            min_stars=50,
            max_stars=500,
            created_after="2022-01-01",
            updated_after="2024-01-01",
            archived=False,
            is_public=True,
        )
        query = build_repository_search_query(params)

        # Verify all components are present
        assert "topic:data-science topic:analytics" in query
        assert "language:python" in query
        assert "license:apache-2.0" in query
        assert "stars:50..500" in query
        assert "created:>=2022-01-01" in query
        assert "updated:>=2024-01-01" in query
        assert "archived:false" in query
        assert "is:public" in query

    def test_private_repository_filter(self):
        """Test query building with private repository filter."""
        params = RepositorySearchByTopicInput(topics=["internal"], is_public=False)
        query = build_repository_search_query(params)
        assert "is:private" in query
