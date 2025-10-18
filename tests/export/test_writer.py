"""
Unit tests for export writer.

Tests the export writer for hotspot analysis including
conversation extraction and message formatting.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from export.writer import export_hotspot_analysis


class TestExportHotspotAnalysis:
    """Test cases for export_hotspot_analysis writer."""

    def test_export_raises_on_missing_conversation(self, tmp_path):
        """Test that export raises ValueError when conversation not found."""
        mock_store = MagicMock()
        mock_store.get_conversation.return_value = None

        with pytest.raises(ValueError, match="Could not retrieve conversation"):
            export_hotspot_analysis(
                store=mock_store,
                thread_id="nonexistent",
                repo="test/repo",
                days=90,
                max_commits=200,
                min_changes=3,
                path_filter=None,
            )

    def test_export_with_valid_conversation(self):
        """Test successful export with markdown hotspot analysis."""
        # Create mock conversation with markdown table hotspot analysis
        mock_conversation = {
            "thread_id": "test-thread-123",
            "command": "hotspots",
            "messages": [
                {
                    "role": "user",
                    "content": "Analyze hotspots for the repo",
                    "created_at": "2025-10-18 14:00:00",
                },
                {
                    "role": "assistant",
                    "content": """**Maintenance Hotspot Analysis**

| File | Changes | Additions | Deletions | Churn % |
|------|---------|-----------|-----------|---------|
| src/main.py | 5 | 100 | 50 | 15% |
| src/utils.py | 3 | 50 | 25 | 8% |

These files show the highest churn and maintenance burden.""",
                    "created_at": "2025-10-18 14:01:00",
                },
            ],
        }

        mock_store = MagicMock()
        mock_store.get_conversation.return_value = mock_conversation

        # Execute export
        filepath = export_hotspot_analysis(
            store=mock_store,
            thread_id="test-thread-123",
            repo="test/repo",
            days=90,
            max_commits=200,
            min_changes=3,
            path_filter=None,
            strategy="activity",
        )

        # Verify file was created
        exported_file = Path(filepath)
        assert exported_file.exists()

        # Read and verify content
        content = exported_file.read_text()
        assert "# Hotspot Analysis: test/repo" in content
        assert "src/main.py" in content
        assert "Maintenance Hotspot Analysis" in content

        # Clean up
        exported_file.unlink()

    def test_export_without_hotspot_data(self, capsys):
        """Test export when conversation lacks hotspot data."""
        # Mock conversation without hotspot data
        mock_conversation = {
            "thread_id": "test-thread-456",
            "command": "hotspots",
            "messages": [
                {
                    "role": "user",
                    "content": "Analyze hotspots",
                    "created_at": "2025-10-18 14:00:00",
                },
                {
                    "role": "assistant",
                    "content": "I couldn't complete the analysis.",
                    "created_at": "2025-10-18 14:01:00",
                },
            ],
        }

        mock_store = MagicMock()
        mock_store.get_conversation.return_value = mock_conversation

        # Execute export
        filepath = export_hotspot_analysis(
            store=mock_store,
            thread_id="test-thread-456",
            repo="test/repo",
            days=90,
            max_commits=200,
            min_changes=3,
            path_filter=None,
        )

        # Verify warning was printed
        captured = capsys.readouterr()
        assert "doesn't appear to contain hotspot analysis" in captured.out

        # Verify file was still created (with conversation only)
        exported_file = Path(filepath)
        assert exported_file.exists()
        content = exported_file.read_text()
        assert "# Hotspot Analysis: test/repo" in content

        # Clean up
        exported_file.unlink()
