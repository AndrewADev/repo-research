"""
Unit tests for export utilities.

Tests the markdown export functionality for hotspot analysis.
"""

from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage

from export.formats import markdown as md
from export.models import ExportMetadata
from integrations.github.models import FileHotspot, HotspotAnalysisResult


class TestExportMetadata:
    """Test cases for ExportMetadata model."""

    def test_sanitized_repo_name(self):
        """Test that slashes in repo names are replaced with hyphens."""
        metadata = ExportMetadata(
            repo_name="owner/repo",
            analysis_date=datetime(2025, 10, 18, 14, 30),
            latest_commit_sha="abc123",  # pragma: allowlist secret
        )

        assert metadata.sanitized_repo_name == "owner-repo"

    def test_short_sha(self):
        """Test that SHA is truncated to 7 characters."""
        metadata = ExportMetadata(
            repo_name="owner/repo",
            analysis_date=datetime(2025, 10, 18, 14, 30),
            latest_commit_sha="abc123d",  # pragma: allowlist secret
        )

        assert metadata.short_sha == "abc123d"
        assert len(metadata.short_sha) == 7

    def test_none_sha_omitted(self):
        """Test that SHA is truncated to 7 characters."""
        metadata = ExportMetadata(
            repo_name="owner/repo",
            analysis_date=datetime(2025, 10, 18, 14, 30),
            latest_commit_sha=None,  # pragma: allowlist secret
        )

        assert metadata.filename == "owner-repo_18-10-2025-1430.md"

    def test_filename_generation(self):
        """Test correct filename format: repo-name_sha_DD-MM-YYYY-HHmm.md"""
        metadata = ExportMetadata(
            repo_name="anthropics/claude",
            analysis_date=datetime(2025, 10, 18, 14, 30),
            latest_commit_sha="a1b2c3d",  # pragma: allowlist secret
        )

        # Format is: repo-name_sha_DD-MM-YYYY-HHmm.md
        expected = "anthropics-claude_a1b2c3d_18-10-2025-1430.md"
        assert metadata.filename == expected

    def test_filepath_generation(self):
        """Test full filepath includes output directory."""
        metadata = ExportMetadata(
            repo_name="owner/repo",
            analysis_date=datetime(2025, 10, 18, 14, 30),
            latest_commit_sha="abc123",  # pragma: allowlist secret
            output_dir=Path("/tmp/outputs"),
        )

        expected_path = Path("/tmp/outputs/owner-repo_abc123_18-10-2025-1430.md")
        assert metadata.filepath == expected_path


class TestMarkdownExporter:
    """Test cases for markdown export functions."""

    def test_format_empty_hotspot_table(self):
        """Test formatting when no hotspots are found."""
        result = md.format_hotspot_table([])

        assert "_No hotspots found matching the criteria._" in result

    def test_format_hotspot_table_single_entry(self):
        """Test formatting a single hotspot into markdown table."""
        hotspot = FileHotspot(
            file_path="src/main.py",
            change_count=5,
            total_additions=100,
            total_deletions=50,
            churn_score=25.5,
            unique_authors=2,
            first_changed=datetime(2025, 1, 1),
            last_changed=datetime(2025, 10, 18),
        )

        result = md.format_hotspot_table([hotspot])

        # Verify table structure
        assert "| File Path |" in result
        assert "| Changes |" in result
        assert "| Churn Score |" in result

        # Verify data
        assert "`src/main.py`" in result
        assert "| 5 |" in result
        assert "| 100 |" in result
        assert "| 50 |" in result
        assert "| 25.50 |" in result  # Float formatted to 2 decimals
        assert "| 2 |" in result
        assert "2025-01-01" in result
        assert "2025-10-18" in result

    def test_format_hotspot_table_integer_churn_score(self):
        """Test formatting hotspot with integer churn score."""
        hotspot = FileHotspot(
            file_path="test.py",
            change_count=3,
            total_additions=20,
            total_deletions=10,
            churn_score=42,  # Integer churn score
            unique_authors=1,
        )

        result = md.format_hotspot_table([hotspot])

        assert "| 42 |" in result  # Integer rendered as-is

    def test_format_analysis_summary(self):
        """Test formatting analysis summary section."""
        result_data = HotspotAnalysisResult(
            hotspots=[],
            analysis_period_days=90,
            total_commits_analyzed=150,
            total_files_changed=45,
            date_range_start=datetime(2025, 7, 20),
            date_range_end=datetime(2025, 10, 18),
            path_filter="src/integrations",
        )

        summary = md.format_analysis_summary(result_data, strategy="activity")

        assert "**Analysis Period:** 90 days" in summary
        assert "2025-07-20" in summary
        assert "2025-10-18" in summary
        assert "**Total Commits Analyzed:** 150" in summary
        assert "**Total Files Changed:** 45" in summary
        assert "**Strategy:** activity" in summary
        assert "**Path Filter:** `src/integrations`" in summary

    def test_format_analysis_summary_no_path_filter(self):
        """Test summary when no path filter is applied."""
        result_data = HotspotAnalysisResult(
            hotspots=[],
            analysis_period_days=30,
            total_commits_analyzed=50,
            total_files_changed=10,
            date_range_start=datetime(2025, 9, 18),
            date_range_end=datetime(2025, 10, 18),
            path_filter=None,
        )

        summary = md.format_analysis_summary(result_data)

        assert "**Path Filter:**" not in summary

    def test_generate_markdown_report_complete(self):
        """Test generating a complete markdown report."""
        metadata = ExportMetadata(
            repo_name="test/repo",
            analysis_date=datetime(2025, 10, 18, 14, 30),
            latest_commit_sha="abc123de",  # pragma: allowlist secret
        )

        report = md.generate_markdown_report(
            metadata=metadata,
            analysis_message=AIMessage(content="Analysis complete"),
            strategy="activity",
            days=90,
            max_commits=200,
            min_changes=3,
            path_filter=None,
        )

        # Verify all major sections are present
        assert "# Hotspot Analysis: test/repo" in report
        assert "**Analysis Date:** 18-10-2025 14:30" in report
        assert "**Commit SHA:** abc123de" in report
        assert "## Parameters" in report
        assert "- **Days:** 90" in report
        assert "- **Max Commits:** 200" in report
        assert "- **Min Changes:** 3" in report
        assert "- **Path Filter:** All files" in report
        assert "## Analysis & Insights" in report
        assert "Analysis complete" in report
        assert "_Report generated by repo-research" in report

    def test_export_to_file_creates_directory(self, tmp_path):
        """Test that export creates output directory if it doesn't exist."""
        output_dir = tmp_path / "new_outputs"
        filepath = output_dir / "test_export.md"

        assert not output_dir.exists()

        md.write_to_file("# Test Content", filepath)

        assert output_dir.exists()
        assert filepath.exists()
        assert filepath.read_text() == "# Test Content"

    def test_export_to_file_writes_content(self, tmp_path):
        """Test that export correctly writes markdown content."""
        filepath = tmp_path / "export.md"
        content = "# Test Report\n\nThis is a test."

        md.write_to_file(content, filepath)

        assert filepath.exists()
        assert filepath.read_text() == content
