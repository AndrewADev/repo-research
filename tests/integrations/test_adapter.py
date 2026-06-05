"""
Unit tests for GitHub adapter functions.

Tests data transformation and parsing functions without requiring network access.
"""

import json
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from integrations.github.adapter import (
    RepositorySearchByTopicTool,
    RepositorySearchTool,
    StarredRepositoriesTool,
    normalize_tool_message_ids,
    parse_repository_data,
    result_analysis_condition,
)
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


class TestResultAnalysisCondition:
    """Branching logic that decides whether to run diagnostics after a tool call."""

    def _state(self, content: str, message_cls=ToolMessage):
        if message_cls is ToolMessage:
            msg = ToolMessage(content=content, tool_call_id="call_1")
        else:
            msg = AIMessage(content=content)
        return {"messages": [msg]}

    def test_real_error_payload_triggers_diagnostics(self):
        payload = json.dumps({"error": "GitHub API returned 401"})
        assert result_analysis_condition(self._state(payload)) == "run_diagnostics"

    def test_description_containing_word_errors_does_not_trigger(self):
        """Regression: description containing 'errors' must not trip diagnostics."""
        payload = json.dumps(
            {
                "results": [
                    {
                        "name": "hyperdxio/hyperdx",
                        "description": (
                            "An observability platform unifying session replays, "
                            "logs, metrics, traces and errors powered by ClickHouse."
                        ),
                    }
                ],
                "search_metadata": {"has_results": True, "total_found": 1},
            }
        )
        assert result_analysis_condition(self._state(payload)) == "continue"

    def test_topic_containing_error_monitoring_does_not_trigger(self):
        payload = json.dumps(
            {
                "results": [{"name": "foo/bar", "topics": ["error-monitoring"]}],
                "search_metadata": {"has_results": True, "total_found": 1},
            }
        )
        assert result_analysis_condition(self._state(payload)) == "continue"

    def test_no_results_payload_routes_to_no_results_handler(self):
        payload = json.dumps(
            {"results": [], "search_metadata": {"has_results": False, "total_found": 0}}
        )
        assert result_analysis_condition(self._state(payload)) == "handle_no_results"

    def test_empty_state_returns_continue(self):
        assert result_analysis_condition({"messages": []}) == "continue"


def _ai_with_tool_call(tc_id: str, name: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": {}, "id": tc_id, "type": "tool_call"},
        ],
    )


class TestNormalizeToolMessageIds:
    """Defensive scrubbing of tool_call_id mismatches before LLM invocation."""

    def test_matching_ids_pass_through_unchanged(self):
        history = [
            _ai_with_tool_call("call_abc", "get_starred_repositories"),
            ToolMessage(
                content="{}",
                tool_call_id="call_abc",
                name="get_starred_repositories",
            ),
        ]
        result = normalize_tool_message_ids(history)
        assert result == history
        # Same object identity — pass-through, no copy
        assert result[1] is history[1]

    def test_orphan_rewritten_to_preceding_tool_call_id(self, caplog):
        """Regression: tool emits its own prefixed id instead of receiving one."""
        history = [
            _ai_with_tool_call("call_abc", "get_starred_repositories"),
            ToolMessage(
                content='{"results": []}',
                tool_call_id="get_starred_repositories-deadbeef",
                name="get_starred_repositories",
            ),
        ]
        with caplog.at_level("WARNING"):
            result = normalize_tool_message_ids(history)
        assert result[1].tool_call_id == "call_abc"
        assert result[1].content == '{"results": []}'
        # Original message is not mutated
        assert history[1].tool_call_id == "get_starred_repositories-deadbeef"
        assert any("Rewriting" in r.message for r in caplog.records)

    def test_unpairable_orphan_dropped_with_warning(self, caplog):
        history = [
            _ai_with_tool_call("call_abc", "get_starred_repositories"),
            ToolMessage(
                content="answers call_abc",
                tool_call_id="call_abc",
                name="get_starred_repositories",
            ),
            ToolMessage(
                content="orphan",
                tool_call_id="totally_unrelated",
                name="search_repositories",  # different name → no pair candidate
            ),
        ]
        with caplog.at_level("WARNING"):
            result = normalize_tool_message_ids(history)
        # Orphan dropped; the legitimate pair survives.
        assert len(result) == 2
        assert result[1].tool_call_id == "call_abc"
        assert any("Dropping orphan" in r.message for r in caplog.records)

    def test_unconsumed_tool_call_warns(self, caplog):
        """AIMessage tool_call with no matching ToolMessage response warns."""
        history = [
            _ai_with_tool_call("call_unanswered", "get_starred_repositories"),
            # No ToolMessage follows.
        ]
        with caplog.at_level("WARNING"):
            normalize_tool_message_ids(history)
        assert any(
            "no corresponding ToolMessage response" in r.message for r in caplog.records
        )

    def test_multiple_tool_calls_pair_by_position(self):
        ai = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_starred_repositories",
                    "args": {},
                    "id": "call_1",
                    "type": "tool_call",
                },
                {
                    "name": "get_starred_repositories",
                    "args": {},
                    "id": "call_2",
                    "type": "tool_call",
                },
            ],
        )
        history = [
            ai,
            ToolMessage(
                content="first",
                tool_call_id="wrong_a",
                name="get_starred_repositories",
            ),
            ToolMessage(
                content="second",
                tool_call_id="wrong_b",
                name="get_starred_repositories",
            ),
        ]
        result = normalize_tool_message_ids(history)
        assert result[1].tool_call_id == "call_1"
        assert result[2].tool_call_id == "call_2"

    def test_already_consumed_call_not_double_assigned(self):
        """If first ToolMessage takes call_1 by id, second can't claim it again."""
        ai = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_starred_repositories",
                    "args": {},
                    "id": "call_1",
                    "type": "tool_call",
                },
            ],
        )
        history = [
            ai,
            ToolMessage(
                content="legit",
                tool_call_id="call_1",
                name="get_starred_repositories",
            ),
            ToolMessage(
                content="orphan",
                tool_call_id="wrong",
                name="get_starred_repositories",
            ),
        ]
        result = normalize_tool_message_ids(history)
        # First ToolMessage matches by id and is kept; second has no
        # unconsumed candidate to pair with, so it's dropped.
        assert len(result) == 2
        assert result[1].content == "legit"
        assert result[1].tool_call_id == "call_1"

    def test_non_tool_messages_pass_through(self):
        history = [
            HumanMessage(content="hi"),
            AIMessage(content="hello"),
        ]
        result = normalize_tool_message_ids(history)
        assert result == history


class TestToolCallIdInjection:
    """End-to-end: invoking a tool via the ToolCall dict shape must propagate
    ``tool_call_id`` into ``_run`` so the emitted ``ToolMessage`` carries the
    same id as the originating ``AIMessage.tool_calls[]``.

    """

    def _invoke_with_id(self, tool, args: dict, call_id: str):
        return tool.invoke(
            {"args": args, "id": call_id, "name": tool.name, "type": "tool_call"}
        )

    def _tool_message_from_result(self, result):
        # StarredRepositoriesTool / RepositorySearchTool / RepositorySearchByTopicTool
        # all return a Command whose update contains messages=[ToolMessage].
        assert isinstance(result, Command), f"expected Command, got {type(result)}"
        messages = result.update["messages"]
        assert len(messages) == 1
        return messages[0]

    def test_starred_repositories_tool_propagates_id(self, mocker):
        # Mock the GitHubTools class instantiated by @with_github_tools.
        mock_gh = mocker.MagicMock()
        mock_gh.get_starred_repositories.return_value = []
        mocker.patch("integrations.github.adapter.GitHubTools", return_value=mock_gh)

        tool = StarredRepositoriesTool()
        result = self._invoke_with_id(tool, {"limit": 1}, "call_from_model_abc")

        msg = self._tool_message_from_result(result)
        assert msg.tool_call_id == "call_from_model_abc", (
            f"expected propagation; got {msg.tool_call_id!r}. The "
            "_injected_args_keys override on StarredRepositoriesTool is "
            "likely missing or returns the wrong key."
        )

    def test_repository_search_tool_propagates_id(self, mocker):
        mock_gh = mocker.MagicMock()
        mock_gh.search_repositories.return_value = []
        mocker.patch("integrations.github.adapter.GitHubTools", return_value=mock_gh)

        tool = RepositorySearchTool()
        result = self._invoke_with_id(
            tool, {"query": "python", "limit": 1}, "call_search_xyz"
        )

        msg = self._tool_message_from_result(result)
        assert msg.tool_call_id == "call_search_xyz"

    def test_repository_search_by_topic_tool_propagates_id(self, mocker):
        mock_gh = mocker.MagicMock()
        mock_gh.search_repositories_by_topic.return_value = []
        mocker.patch("integrations.github.adapter.GitHubTools", return_value=mock_gh)

        tool = RepositorySearchByTopicTool()
        result = self._invoke_with_id(tool, {"topics": ["python"]}, "call_topic_qrs")

        msg = self._tool_message_from_result(result)
        assert msg.tool_call_id == "call_topic_qrs"
