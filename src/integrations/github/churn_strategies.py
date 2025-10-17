"""
Churn calculation strategies for hotspot analysis.

Provides different algorithms for calculating churn scores, which help identify
files with high maintenance burden.
"""

from datetime import datetime
from typing import Protocol

from .models import CommitChangeRecord, ReworkCategoryBreakdown


class ChurnCalculationStrategy(Protocol):
    """
    Protocol for churn calculation strategies.

    Churn score quantifies the maintenance burden of a file by combining
    how often it changes with how much it changes.
    """

    def calculate_churn(
        self,
        commit_history: list[CommitChangeRecord],
    ) -> int:
        """
        Calculate churn score for a file.

        Args:
            commit_history: Chronological list of commits affecting this file

        Returns:
            Churn score (higher indicates more maintenance burden)
        """
        ...


class TotalActivityChurnStrategy:
    """
    Total Activity Churn: (additions + deletions) / baseline_loc × 100.

    Measures total code volatility as a percentage of the initial codebase size.
    This approach is useful for understanding overall code activity relative to
    the file size at the start of the analysis period.
    """

    def calculate_churn(
        self,
        commit_history: list[CommitChangeRecord],
        baseline_loc: int | None = None,
    ) -> float:
        """
        Calculate total activity churn percentage.

        Args:
            commit_history: Chronological list of commits affecting this file
            baseline_loc: Lines of code at start of analysis period

        Returns:
            Activity churn percentage. Returns 0.0 if baseline_loc is None or 0.
        """
        if baseline_loc is None or baseline_loc == 0:
            return 0.0

        # Calculate total additions and deletions from commit history
        additions = sum(commit.additions for commit in commit_history)
        deletions = sum(commit.deletions for commit in commit_history)

        total_activity = additions + deletions
        return (total_activity / baseline_loc) * 100


class ReworkRateStrategy:
    """
    Rework Rate: Measures code rewritten within 21 days of merging.

    Categorizes changes as:
    - New Work: Newly added code (not replacing existing code)
    - Churn/Rework: Code deleted or rewritten within 21 days of merging
    - Refactor: Code modified after 21 days (excluded from churn)
    - Helping Others: Changes to someone else's recent code within 21 days

    Formula: (rework_lines) / (total_lines_committed) * 100
    """

    REWORK_WINDOW_DAYS = 21

    def calculate_churn(
        self,
        commit_history: list[CommitChangeRecord] | None = None,
    ) -> tuple[float, ReworkCategoryBreakdown]:
        """
        Calculate rework rate and categorize changes.

        Args:
            commit_history: Chronological list of commits affecting this file

        Returns:
            Tuple of (rework_percentage, category_breakdown)
        """
        if not commit_history or len(commit_history) == 0:
            return 0.0, ReworkCategoryBreakdown()

        breakdown = ReworkCategoryBreakdown()

        # Sort commits chronologically
        sorted_commits = sorted(commit_history, key=lambda c: c.commit_date)

        # Track which authors introduced code and when
        # Maps author -> list of (commit_date, lines_added)
        author_code_timeline: dict[str, list[tuple[datetime, int]]] = {}

        for commit in sorted_commits:
            author = commit.author_login or "unknown"
            commit_date = commit.commit_date

            # Categorize additions
            if commit.additions > 0:
                # All additions are new work in this simplified model
                # (More sophisticated analysis would track line-level changes)
                breakdown.new_work_lines += commit.additions

                # Track when this author added code
                if author not in author_code_timeline:
                    author_code_timeline[author] = []
                author_code_timeline[author].append((commit_date, commit.additions))

            # Categorize deletions
            if commit.deletions > 0:
                # Check if this is rework, helping others, or refactor
                is_own_rework = False
                is_helping_others = False

                # Check if the current author added code within 21 days
                # Note: days_diff > 0 excludes same-commit additions (not rework)
                if author in author_code_timeline:
                    for add_date, _ in author_code_timeline[author]:
                        days_diff = (commit_date - add_date).days
                        if 0 < days_diff <= self.REWORK_WINDOW_DAYS:
                            is_own_rework = True
                            break

                # Check if ANY other author added code within 21 days
                # Note: days_diff > 0 excludes same-commit additions (not helping)
                if not is_own_rework:
                    for other_author, timeline in author_code_timeline.items():
                        if other_author == author:
                            continue
                        for add_date, _ in timeline:
                            days_diff = (commit_date - add_date).days
                            if 0 < days_diff <= self.REWORK_WINDOW_DAYS:
                                is_helping_others = True
                                break
                        if is_helping_others:
                            break

                # Categorize the deletion
                if is_helping_others:
                    breakdown.helping_others_lines += commit.deletions
                elif is_own_rework:
                    breakdown.rework_lines += commit.deletions
                else:
                    breakdown.refactor_lines += commit.deletions

        # Calculate rework percentage
        rework_percentage = breakdown.rework_percentage

        return rework_percentage, breakdown


# Default strategy used by the system
DEFAULT_STRATEGY = TotalActivityChurnStrategy()
