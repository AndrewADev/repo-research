"""
Unit tests for tool utility functions.

Tests utility functions without requiring network access.
"""

from tools.utils import generate_tool_call_id


class TestGenerateToolCallId:
    """Test cases for generate_tool_call_id function."""

    def test_generate_tool_call_id_custom_prefix(self):
        """Test tool call ID generation with custom prefix."""
        custom_id = generate_tool_call_id("custom")

        assert custom_id.startswith("custom-")
        assert len(custom_id) > len("custom-")

    def test_generate_tool_call_id_empty_prefix(self):
        """Test tool call ID generation with empty prefix."""
        tool_id = generate_tool_call_id("")

        assert tool_id.startswith("-")
        # Should still have ID component
        assert len(tool_id) > 10

    def test_generate_tool_call_id_uniqueness(self):
        """Test that generated IDs are unique."""
        id1 = generate_tool_call_id()
        id2 = generate_tool_call_id()
        id3 = generate_tool_call_id()

        # All IDs should be different
        assert id1 != id2
        assert id2 != id3
        assert id1 != id3

    def test_generate_tool_call_id_special_prefix(self):
        """Test tool call ID generation with special characters in prefix."""
        special_id = generate_tool_call_id("tool:call:id")

        assert special_id.startswith("tool:call:id-")
        assert len(special_id) > len("tool:call:id-")

    def test_generate_tool_call_id_none_prefix(self):
        """Test tool call ID generation with None prefix."""
        # Should use default prefix
        tool_id = generate_tool_call_id(None)

        assert tool_id.startswith("None-")

    def test_generate_tool_call_id_multiple_calls_different_prefixes(self):
        """Test generating IDs with different prefixes."""
        id1 = generate_tool_call_id("prefix1")
        id2 = generate_tool_call_id("prefix2")

        assert id1.startswith("prefix1-")
        assert id2.startswith("prefix2-")
        # Even with different prefixes, UUIDs should differ
        assert id1.split("-", 1)[1] != id2.split("-", 1)[1]

    def test_generate_tool_call_id_consistency_with_same_prefix(self):
        """Test that same prefix doesn't generate same ID."""
        id1 = generate_tool_call_id("same-prefix")
        id2 = generate_tool_call_id("same-prefix")

        # Both should have same prefix
        assert id1.startswith("same-prefix-")
        assert id2.startswith("same-prefix-")
        # But IDs should be different (different UUIDs)
        assert id1 != id2

    def test_generate_tool_call_id_no_collision_stress_test(self):
        """Stress test: generate many IDs and ensure no collisions."""
        ids = {generate_tool_call_id("stress") for _ in range(1000)}

        # All 1000 IDs should be unique
        assert len(ids) == 1000
