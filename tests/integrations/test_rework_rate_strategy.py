"""
Unit tests for ReworkRateStrategy.

Tests the rework rate calculation strategy that categorizes changes
based on the 21-day window and tracks new work, rework, refactor,
and helping others.
"""

from datetime import datetime, timedelta

import pytest

from integrations.github.churn_strategies import ReworkRateStrategy
from integrations.github.models import CommitChangeRecord, ReworkCategoryBreakdown


class TestReworkRateStrategy:
    """Test cases for ReworkRateStrategy."""

    def test_empty_commit_history(self):
        """Test that empty commit history returns zero rework."""
        strategy = ReworkRateStrategy()

        rework_pct, breakdown = strategy.calculate_churn(
            commit_history=[],
        )

        assert rework_pct == 0.0
        assert breakdown.new_work_lines == 0
        assert breakdown.rework_lines == 0
        assert breakdown.refactor_lines == 0
        assert breakdown.helping_others_lines == 0

    def test_none_commit_history(self):
        """Test that None commit history returns zero rework."""
        strategy = ReworkRateStrategy()

        rework_pct, breakdown = strategy.calculate_churn(
            commit_history=None,
        )

        assert rework_pct == 0.0
        assert breakdown.total_lines == 0

    def test_only_additions_are_new_work(self):
        """Test that additions without deletions are categorized as new work."""
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        commits = [
            CommitChangeRecord(
                commit_sha="abc123",
                commit_date=base_date,
                author_login="alice",
                additions=100,
                deletions=0,
                total_lines_changed=100,
            ),
            CommitChangeRecord(
                commit_sha="def456",
                commit_date=base_date + timedelta(days=5),
                author_login="bob",
                additions=50,
                deletions=0,
                total_lines_changed=50,
            ),
        ]

        strategy = ReworkRateStrategy()
        rework_pct, breakdown = strategy.calculate_churn(
            commit_history=commits,
        )

        assert breakdown.new_work_lines == 150
        assert breakdown.rework_lines == 0
        assert breakdown.refactor_lines == 0
        assert breakdown.helping_others_lines == 0
        assert rework_pct == 0.0

    def test_deletion_within_21_days_is_rework(self):
        """Test that deletions within 21 days are categorized as rework."""
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        commits = [
            # Alice adds 100 lines
            CommitChangeRecord(
                commit_sha="abc123",
                commit_date=base_date,
                author_login="alice",
                additions=100,
                deletions=0,
                total_lines_changed=100,
            ),
            # Alice deletes 50 lines 10 days later (within 21-day window)
            CommitChangeRecord(
                commit_sha="def456",
                commit_date=base_date + timedelta(days=10),
                author_login="alice",
                additions=0,
                deletions=50,
                total_lines_changed=50,
            ),
        ]

        strategy = ReworkRateStrategy()
        rework_pct, breakdown = strategy.calculate_churn(
            commit_history=commits,
        )

        assert breakdown.new_work_lines == 100
        assert breakdown.rework_lines == 50
        assert breakdown.refactor_lines == 0
        assert breakdown.helping_others_lines == 0
        # (50 rework) / (100 new + 50 rework) * 100 = 33.33%
        assert rework_pct == pytest.approx(33.333333333333336, rel=1e-9)

    def test_deletion_after_21_days_is_refactor(self):
        """Test that deletions after 21 days are categorized as refactor."""
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        commits = [
            # Alice adds 100 lines
            CommitChangeRecord(
                commit_sha="abc123",
                commit_date=base_date,
                author_login="alice",
                additions=100,
                deletions=0,
                total_lines_changed=100,
            ),
            # Alice deletes 50 lines 30 days later (outside 21-day window)
            CommitChangeRecord(
                commit_sha="def456",
                commit_date=base_date + timedelta(days=30),
                author_login="alice",
                additions=0,
                deletions=50,
                total_lines_changed=50,
            ),
        ]

        strategy = ReworkRateStrategy()
        rework_pct, breakdown = strategy.calculate_churn(
            commit_history=commits,
        )

        assert breakdown.new_work_lines == 100
        assert breakdown.rework_lines == 0
        assert breakdown.refactor_lines == 50
        assert breakdown.helping_others_lines == 0
        # No rework, so 0%
        assert rework_pct == 0.0

    def test_helping_others_detection(self):
        """Test that changes to someone else's recent code are categorized
        as helping others."""
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        commits = [
            # Alice adds 100 lines
            CommitChangeRecord(
                commit_sha="abc123",
                commit_date=base_date,
                author_login="alice",
                additions=100,
                deletions=0,
                total_lines_changed=100,
            ),
            # Bob deletes 30 lines 15 days later
            # (within 21-day window, different author)
            CommitChangeRecord(
                commit_sha="def456",
                commit_date=base_date + timedelta(days=15),
                author_login="bob",
                additions=0,
                deletions=30,
                total_lines_changed=30,
            ),
        ]

        strategy = ReworkRateStrategy()
        rework_pct, breakdown = strategy.calculate_churn(
            commit_history=commits,
        )

        assert breakdown.new_work_lines == 100
        assert breakdown.rework_lines == 0
        assert breakdown.helping_others_lines == 30
        assert breakdown.refactor_lines == 0
        # helping_others is not counted in rework percentage
        assert rework_pct == 0.0

    def test_exactly_21_days_is_rework(self):
        """Test that deletions exactly 21 days later are still rework."""
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        commits = [
            CommitChangeRecord(
                commit_sha="abc123",
                commit_date=base_date,
                author_login="alice",
                additions=100,
                deletions=0,
                total_lines_changed=100,
            ),
            # Exactly 21 days later
            CommitChangeRecord(
                commit_sha="def456",
                commit_date=base_date + timedelta(days=21),
                author_login="alice",
                additions=0,
                deletions=40,
                total_lines_changed=40,
            ),
        ]

        strategy = ReworkRateStrategy()
        rework_pct, breakdown = strategy.calculate_churn(
            commit_history=commits,
        )

        assert breakdown.rework_lines == 40
        # (40 rework) / (100 new + 40 rework) * 100 = 28.57%
        assert rework_pct == pytest.approx(28.571428571428573, rel=1e-9)

    def test_22_days_is_refactor(self):
        """Test that deletions at 22 days are refactor, not rework."""
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        commits = [
            CommitChangeRecord(
                commit_sha="abc123",
                commit_date=base_date,
                author_login="alice",
                additions=100,
                deletions=0,
                total_lines_changed=100,
            ),
            # 22 days later (just outside window)
            CommitChangeRecord(
                commit_sha="def456",
                commit_date=base_date + timedelta(days=22),
                author_login="alice",
                additions=0,
                deletions=40,
                total_lines_changed=40,
            ),
        ]

        strategy = ReworkRateStrategy()
        rework_pct, breakdown = strategy.calculate_churn(
            commit_history=commits,
        )

        assert breakdown.rework_lines == 0
        assert breakdown.refactor_lines == 40
        assert rework_pct == 0.0

    def test_complex_scenario_with_all_categories(self):
        """
        Test a complex scenario with all four categories.

        Note: Without line-level Git blame tracking, we can't know which
        specific lines are being deleted. The strategy uses a simplified model:
        - If the author has added code within 21 days, deletions are "own rework"
        - Otherwise, if ANY author added code within 21 days, it's "helping others"
        - Otherwise, it's "refactor"
        """
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        commits = [
            # Day 0: Alice adds 100 lines (new work)
            CommitChangeRecord(
                commit_sha="commit1",
                commit_date=base_date,
                author_login="alice",
                additions=100,
                deletions=0,
                total_lines_changed=100,
            ),
            # Day 5: Bob adds 50 lines (new work)
            CommitChangeRecord(
                commit_sha="commit2",
                commit_date=base_date + timedelta(days=5),
                author_login="bob",
                additions=50,
                deletions=0,
                total_lines_changed=50,
            ),
            # Day 10: Alice deletes 20 lines
            # (rework - within 21 days of her own code from day 0)
            CommitChangeRecord(
                commit_sha="commit3",
                commit_date=base_date + timedelta(days=10),
                author_login="alice",
                additions=0,
                deletions=20,
                total_lines_changed=20,
            ),
            # Day 15: Alice deletes 10 lines
            # (also rework - she still has code from day 0 within window)
            CommitChangeRecord(
                commit_sha="commit4",
                commit_date=base_date + timedelta(days=15),
                author_login="alice",
                additions=0,
                deletions=10,
                total_lines_changed=10,
            ),
            # Day 25: Bob deletes 5 lines
            # (own rework - Bob has code from day 5, 20 days ago)
            CommitChangeRecord(
                commit_sha="commit4b",
                commit_date=base_date + timedelta(days=25),
                author_login="bob",
                additions=0,
                deletions=5,
                total_lines_changed=5,
            ),
            # Day 20: Charlie deletes 3 lines (helping others - Bob has
            # code from day 5 (15 days), Alice from day 0 (20 days))
            CommitChangeRecord(
                commit_sha="commit4c",
                commit_date=base_date + timedelta(days=20),
                author_login="charlie",
                additions=0,
                deletions=3,
                total_lines_changed=3,
            ),
            # Day 40: Alice adds 30 more lines (new work)
            CommitChangeRecord(
                commit_sha="commit5",
                commit_date=base_date + timedelta(days=40),
                author_login="alice",
                additions=30,
                deletions=0,
                total_lines_changed=30,
            ),
            # Day 50: Alice deletes 15 lines
            # (rework - within 21 days of her day 40 addition)
            CommitChangeRecord(
                commit_sha="commit6",
                commit_date=base_date + timedelta(days=50),
                author_login="alice",
                additions=0,
                deletions=15,
                total_lines_changed=15,
            ),
            # Day 70: Alice deletes 8 lines (refactor - all code is now >21 days old)
            CommitChangeRecord(
                commit_sha="commit7",
                commit_date=base_date + timedelta(days=70),
                author_login="alice",
                additions=0,
                deletions=8,
                total_lines_changed=8,
            ),
        ]

        strategy = ReworkRateStrategy()
        rework_pct, breakdown = strategy.calculate_churn(
            commit_history=commits,
        )

        # Check categorization
        assert breakdown.new_work_lines == 180  # 100 + 50 + 30
        assert (
            breakdown.rework_lines == 50
        )  # Day 10 (20) + Day 15 (10) + Day 25 (5) + Day 50 (15)
        assert (
            breakdown.helping_others_lines == 3
        )  # Day 20 (Charlie deleting recent code)
        assert breakdown.refactor_lines == 8  # Day 70 deletion

        # Total = 180 + 50 + 3 + 8 = 241
        assert breakdown.total_lines == 241

        # Rework percentage = 50 / 241 * 100 ≈ 20.75%
        assert rework_pct == pytest.approx(20.746887966804977, rel=1e-9)

    def test_rework_window_constant(self):
        """Test that the REWORK_WINDOW_DAYS constant is 21."""
        strategy = ReworkRateStrategy()
        assert strategy.REWORK_WINDOW_DAYS == 21

    def test_category_breakdown_properties(self):
        """Test CategoryBreakdown model properties work correctly."""
        breakdown = ReworkCategoryBreakdown(
            new_work_lines=100,
            rework_lines=20,
            refactor_lines=10,
            helping_others_lines=5,
        )

        assert breakdown.total_lines == 135
        assert breakdown.rework_percentage == pytest.approx(
            14.814814814814815, rel=1e-9
        )

    def test_unsorted_commits_are_handled(self):
        """Test that commits are sorted chronologically even if provided
        out of order."""
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        # Provide commits out of chronological order
        commits = [
            # This commit is from day 10 but listed first
            CommitChangeRecord(
                commit_sha="def456",
                commit_date=base_date + timedelta(days=10),
                author_login="alice",
                additions=0,
                deletions=20,
                total_lines_changed=20,
            ),
            # This commit is from day 0 but listed second
            CommitChangeRecord(
                commit_sha="abc123",
                commit_date=base_date,
                author_login="alice",
                additions=100,
                deletions=0,
                total_lines_changed=100,
            ),
        ]

        strategy = ReworkRateStrategy()
        rework_pct, breakdown = strategy.calculate_churn(
            commit_history=commits,
        )

        # Should still detect rework because commits are sorted internally
        assert breakdown.rework_lines == 20
