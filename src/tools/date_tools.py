"""
Date utility tools for AI agents.

This module provides simple date manipulation tools that are useful for
GitHub search queries and other time-based operations.
"""

from datetime import datetime, timedelta

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class DateOffsetInput(BaseModel):
    """Input schema for date offset tool."""

    days: int = Field(..., description="Number of days ago to calculate", ge=0)


class CurrentDateTool(BaseTool):
    """Tool to get the current date in YYYY-MM-DD format."""

    name: str = "get_current_date"
    description: str = """
    Get the current date in YYYY-MM-DD format.
    Useful for creating date filters in searches or understanding current time context.
    """

    def _run(self) -> str:
        """Get the current date."""
        return datetime.now().strftime("%Y-%m-%d")


class DateOffsetTool(BaseTool):
    """Tool to get a date X days ago in YYYY-MM-DD format."""

    name: str = "get_date_days_ago"
    description: str = """
    Get a date X days ago in YYYY-MM-DD format.
    Useful for creating relative date filters like "repos updated in last 30 days".
    """
    args_schema: type[BaseModel] = DateOffsetInput

    def _run(self, days: int) -> str:
        """Get date X days ago."""
        target_date = datetime.now() - timedelta(days=days)
        return target_date.strftime("%Y-%m-%d")
