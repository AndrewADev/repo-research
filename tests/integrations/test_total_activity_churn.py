"""
Unit tests for TotalActivityChurnStrategy.

Tests the total activity churn calculation strategy that measures
code volatility as a percentage of initial codebase size.
"""

from datetime import datetime

import pytest

from integrations.github.churn_strategies import TotalActivityChurnStrategy
from integrations.github.models import CommitChangeRecord


def create_commit_history(additions: int, deletions: int) -> list[CommitChangeRecord]:
    """Helper to create commit history with given additions/deletions."""
    base_date = datetime(2025, 1, 1, 12, 0, 0)
    return [
        CommitChangeRecord(
            commit_sha="abc123",
            commit_date=base_date,
            author_login="alice",
            additions=additions,
            deletions=deletions,
            total_lines_changed=additions + deletions,
        )
    ]


class TestTotalActivityChurnStrategy:
    """Test cases for TotalActivityChurnStrategy."""

    @pytest.mark.parametrize(
        "additions,deletions,baseline_loc,expected_percentage",
        [
            # Example from the requirements: 4000 added, 1600 deleted, 20000 baseline
            # (4000 + 1600) / 20000 * 100 = 28%
            (4000, 1600, 20000, 28.0),
            # Simple case: 100 changes on 1000 LOC baseline = 10%
            (50, 50, 1000, 10.0),
            # High churn: 200 changes on 100 LOC baseline = 200%
            (100, 100, 100, 200.0),
            # Low churn: 10 changes on 10000 LOC baseline = 0.1%
            (5, 5, 10000, 0.1),
            # Only additions
            (1000, 0, 5000, 20.0),
            # Only deletions
            (0, 500, 2000, 25.0),
            # Zero changes
            (0, 0, 1000, 0.0),
        ],
    )
    def test_activity_churn_calculations(
        self,
        additions: int,
        deletions: int,
        baseline_loc: int,
        expected_percentage: float,
    ):
        """Test activity churn percentage calculations with various inputs."""
        strategy = TotalActivityChurnStrategy()
        commit_history = create_commit_history(additions, deletions)

        result = strategy.calculate_churn(
            commit_history=commit_history,
            baseline_loc=baseline_loc,
        )

        assert result == pytest.approx(expected_percentage, rel=1e-9)

    def test_zero_baseline_returns_zero(self):
        """Test that zero baseline LOC returns 0% churn."""
        strategy = TotalActivityChurnStrategy()
        commit_history = create_commit_history(100, 50)

        result = strategy.calculate_churn(
            commit_history=commit_history,
            baseline_loc=0,
        )

        assert result == 0.0

    def test_none_baseline_returns_zero(self):
        """Test that None baseline LOC returns 0% churn."""
        strategy = TotalActivityChurnStrategy()
        commit_history = create_commit_history(100, 50)

        result = strategy.calculate_churn(
            commit_history=commit_history,
            baseline_loc=None,
        )

        assert result == 0.0

    def test_multiple_commits_aggregated(self):
        """Test that multiple commits are properly aggregated."""
        strategy = TotalActivityChurnStrategy()
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        # Create multiple commits with different additions/deletions
        commit_history = [
            CommitChangeRecord(
                commit_sha="commit1",
                commit_date=base_date,
                author_login="alice",
                additions=60,
                deletions=30,
                total_lines_changed=90,
            ),
            CommitChangeRecord(
                commit_sha="commit2",
                commit_date=base_date,
                author_login="bob",
                additions=40,
                deletions=20,
                total_lines_changed=60,
            ),
        ]

        # Total: 60+40=100 additions, 30+20=50 deletions
        result = strategy.calculate_churn(
            commit_history=commit_history,
            baseline_loc=1000,
        )

        # (100 + 50) / 1000 * 100 = 15%
        assert result == 15.0

    def test_high_churn_percentage(self):
        """Test that churn can exceed 100% for very volatile files."""
        strategy = TotalActivityChurnStrategy()
        commit_history = create_commit_history(500, 500)

        # File had 100 lines, but we added 500 and deleted 500
        result = strategy.calculate_churn(
            commit_history=commit_history,
            baseline_loc=100,
        )

        # (500 + 500) / 100 * 100 = 1000%
        assert result == 1000.0

    def test_fractional_percentage(self):
        """Test that strategy handles fractional percentages correctly."""
        strategy = TotalActivityChurnStrategy()
        commit_history = create_commit_history(4, 3)

        # 7 changes on 30 LOC baseline
        result = strategy.calculate_churn(
            commit_history=commit_history,
            baseline_loc=30,
        )

        # (4 + 3) / 30 * 100 = 23.333...%
        assert result == pytest.approx(23.333333333333332, rel=1e-9)
