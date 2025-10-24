"""Tests for prompt execution flow (run_templated_prompt and run_prompt)."""

import uuid

from langchain_core.prompts import PromptTemplate

from core.models import TemplatedPrompt
from github_agent.main import run_templated_prompt


class TestRunTemplatedPrompt:
    """Tests for run_templated_prompt argument mapping and execution."""

    def test_special_characters_in_values(self, mocker):
        """Test that special characters in argument values are handled correctly."""
        prompt = TemplatedPrompt(
            template=PromptTemplate.from_template("Query: {query}"),
            keys=["query"],
        )

        mock_graph = mocker.MagicMock()
        mock_message = mocker.MagicMock()
        mock_message.content = "Mock response"
        mock_graph.stream.return_value = [{"messages": [mock_message]}]

        thread_id = str(uuid.uuid4())

        # Test with special characters
        special_values = [
            "search \"quotes\" and 'apostrophes'",
            "newlines\nand\ttabs",
            "unicode: 万歳 🎉",
            "symbols: @#$%^&*()",
        ]

        for value in special_values:
            run_templated_prompt(prompt, [value], mock_graph, thread_id)

            # Verify the value was passed through correctly
            call_args = mock_graph.stream.call_args
            state = call_args[0][0]
            actual_content = state["messages"][0].content
            assert value in actual_content

    def test_graph_exception_handling(self, mocker, capsys):
        """Test that exceptions during graph execution are caught and reported."""
        prompt = TemplatedPrompt(
            template=PromptTemplate.from_template("Test: {key}"),
            keys=["key"],
        )

        mock_graph = mocker.MagicMock()
        mock_graph.stream.side_effect = RuntimeError("Graph execution failed")

        thread_id = str(uuid.uuid4())

        # Should not raise exception, should print error
        run_templated_prompt(prompt, ["value"], mock_graph, thread_id)

        # Verify error was printed
        captured = capsys.readouterr()
        assert "Error during prompt execution" in captured.out
        assert "Graph execution failed" in captured.out
