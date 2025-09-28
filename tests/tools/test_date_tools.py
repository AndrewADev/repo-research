"""
Tests for date utility tools.

This module tests the CurrentDateTool and DateOffsetTool to ensure they
return correct date formats and handle various edge cases properly.
"""

import re
from datetime import datetime, timedelta

import pytest

from src.tools.date_tools import CurrentDateTool, DateOffsetInput, DateOffsetTool


class TestCurrentDateTool:
    """Tests for CurrentDateTool."""

    def test_tool_description(self):
        """Test that the tool has a meaningful name and description."""
        tool = CurrentDateTool()
        assert tool.name == "get_current_date"
        assert "current date" in tool.description.lower()
        assert "yyyy-mm-dd" in tool.description.lower()

    def test_returns_current_date(self):
        """Test that the tool returns today's date."""
        tool = CurrentDateTool()
        result = tool._run()

        # Check format (YYYY-MM-DD)
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        assert re.match(date_pattern, result), f"Date format incorrect: {result}"

        # Check it's actually today's date
        expected_date = datetime.now().strftime("%Y-%m-%d")
        assert result == expected_date

    def test_returns_mocked_date(self, mocker):
        """Test with a mocked datetime to ensure consistent behavior."""
        # Mock datetime.now() to return a specific date
        mock_datetime = mocker.patch("src.tools.date_tools.datetime")
        mock_datetime.now.return_value = datetime(2023, 6, 15, 10, 30, 0)
        mock_datetime.strftime = datetime.strftime

        tool = CurrentDateTool()
        result = tool._run()

        assert result == "2023-06-15"

    def test_format_consistency(self):
        """Test that the date format is always consistent."""
        tool = CurrentDateTool()

        # Run multiple times to ensure consistency
        results = [tool._run() for _ in range(3)]

        # All results should be identical (assuming tests run quickly)
        assert len(set(results)) <= 2  # Allow for date change during test

        # All results should match the pattern
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        for result in results:
            assert re.match(date_pattern, result)


class TestDateOffsetTool:
    """Tests for DateOffsetTool."""

    def test_tool_description(self):
        """Test that the tool has a meaningful name and description."""
        tool = DateOffsetTool()
        assert tool.name == "get_date_days_ago"
        assert "days ago" in tool.description.lower()
        assert "yyyy-mm-dd" in tool.description.lower()

    def test_zero_days_ago(self):
        """Test that 0 days ago returns today's date."""
        tool = DateOffsetTool()
        result = tool._run(0)

        expected_date = datetime.now().strftime("%Y-%m-%d")
        assert result == expected_date

    def test_one_day_ago(self):
        """Test that 1 day ago returns yesterday's date."""
        tool = DateOffsetTool()
        result = tool._run(1)

        expected_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected_date

    def test_with_mocked_date(self, mocker):
        """Test with a mocked datetime for consistent results."""
        # Mock datetime.now() to return June 15, 2023
        base_date = datetime(2023, 6, 15, 10, 30, 0)
        mock_datetime = mocker.patch("src.tools.date_tools.datetime")
        mock_datetime.now.return_value = base_date
        mock_datetime.strftime = datetime.strftime

        tool = DateOffsetTool()

        # Test various day offsets
        assert tool._run(0) == "2023-06-15"  # Same day
        assert tool._run(1) == "2023-06-14"  # 1 day ago
        assert tool._run(7) == "2023-06-08"  # 1 week ago
        assert tool._run(30) == "2023-05-16"  # 30 days ago

    def test_format_consistency(self):
        """Test that the date format is always consistent."""
        tool = DateOffsetTool()

        # Test different day offsets
        test_days = [0, 1, 7, 30, 365]
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"

        for days in test_days:
            result = tool._run(days)
            assert re.match(date_pattern, result), (
                f"Date format incorrect for {days} days: {result}"
            )

    def test_large_day_offset(self):
        """Test with a large day offset (e.g., 1 year)."""
        tool = DateOffsetTool()
        result = tool._run(365)

        # Should still return a valid date format
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        assert re.match(date_pattern, result)

        # Should be approximately 1 year ago
        expected_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        assert result == expected_date

    def test_cross_year_boundary(self, mocker):
        """Test that dates crossing year boundaries work correctly."""
        # Test with a date that would cross into the previous year
        mock_datetime = mocker.patch("src.tools.date_tools.datetime")
        # Set current date to January 15, 2023
        mock_datetime.now.return_value = datetime(2023, 1, 15, 10, 30, 0)
        mock_datetime.strftime = datetime.strftime

        tool = DateOffsetTool()
        result = tool._run(30)  # 30 days ago from Jan 15 = Dec 16, 2022

        expected_date = (datetime(2023, 1, 15) - timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )
        assert result == expected_date
        assert result == "2022-12-16"


class TestDateOffsetInput:
    """Tests for DateOffsetInput validation."""

    def test_valid_input(self):
        """Test that valid inputs are accepted."""
        valid_inputs = [0, 1, 7, 30, 365, 1000]

        for days in valid_inputs:
            input_obj = DateOffsetInput(days=days)
            assert input_obj.days == days

    def test_negative_input_validation(self):
        """Test that negative inputs are rejected."""
        with pytest.raises(ValueError):
            DateOffsetInput(days=-1)

    def test_input_description(self):
        """Test that the input field has proper description."""
        field_info = DateOffsetInput.model_fields["days"]
        assert "days ago" in field_info.description.lower()


class TestDateToolsIntegration:
    """Integration tests for date tools working together."""

    def test_current_date_vs_zero_offset(self):
        """Test that current date tool matches zero offset tool."""
        current_tool = CurrentDateTool()
        offset_tool = DateOffsetTool()

        current_result = current_tool._run()
        offset_result = offset_tool._run(0)

        assert current_result == offset_result

    def test_date_sequence(self):
        """Test that a sequence of dates makes logical sense."""
        tool = DateOffsetTool()

        today = tool._run(0)
        yesterday = tool._run(1)
        week_ago = tool._run(7)

        # Convert to datetime objects for comparison
        today_dt = datetime.strptime(today, "%Y-%m-%d")
        yesterday_dt = datetime.strptime(yesterday, "%Y-%m-%d")
        week_ago_dt = datetime.strptime(week_ago, "%Y-%m-%d")

        # Verify the sequence is logical
        assert today_dt > yesterday_dt
        assert yesterday_dt > week_ago_dt
        assert (today_dt - yesterday_dt).days == 1
        assert (today_dt - week_ago_dt).days == 7
