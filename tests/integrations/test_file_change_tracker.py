"""
Unit tests for FileChangeTracker class.

Tests the file change tracking logic independently of GitHub API calls.
"""

from datetime import datetime, timedelta

from integrations.github.churn_strategies import (
    ReworkRateStrategy,
    TotalActivityChurnStrategy,
)
from integrations.github.hotspot_tracker import FileChangeTracker


class TestFileChangeTracker:
    """Test cases for FileChangeTracker."""

    def test_empty_tracker(self):
        """Test newly initialized tracker has no data."""
        tracker = FileChangeTracker()

        hotspots = tracker.get_hotspots(min_changes=1)
        assert hotspots == []
        assert tracker.total_files_changed == 0

    def test_single_file_single_change(self):
        """Test tracking a single change to one file."""
        tracker = FileChangeTracker(strategy=TotalActivityChurnStrategy())
        now = datetime.now()

        tracker.record_file_change(
            file_path="test.py",
            additions=10,
            deletions=5,
            author_login="user1",
            commit_date=now,
            commit_sha="abc123",
        )

        # Set baseline (file had 100 lines)
        tracker.set_baseline_loc("test.py", 100)

        hotspots = tracker.get_hotspots(min_changes=1)
        assert len(hotspots) == 1
        assert hotspots[0].file_path == "test.py"
        assert hotspots[0].change_count == 1
        assert hotspots[0].total_additions == 10
        assert hotspots[0].total_deletions == 5
        assert hotspots[0].churn_score == 15.0  # (10 + 5) / 100 * 100 = 15%
        assert hotspots[0].unique_authors == 1
        assert tracker.total_files_changed == 1

    def test_multiple_changes_same_file(self):
        """Test aggregating multiple changes to the same file."""
        tracker = FileChangeTracker(strategy=TotalActivityChurnStrategy())
        now = datetime.now()

        # Record 3 changes to the same file
        for i in range(3):
            tracker.record_file_change(
                file_path="main.py",
                additions=20,
                deletions=10,
                author_login="user1",
                commit_date=now - timedelta(days=i),
                commit_sha=f"commit{i}",
            )

        # Set baseline (file had 300 lines)
        tracker.set_baseline_loc("main.py", 300)

        hotspots = tracker.get_hotspots(min_changes=1)
        assert len(hotspots) == 1
        assert hotspots[0].file_path == "main.py"
        assert hotspots[0].change_count == 3
        assert hotspots[0].total_additions == 60  # 20 * 3
        assert hotspots[0].total_deletions == 30  # 10 * 3
        assert hotspots[0].churn_score == 30.0  # (60 + 30) / 300 * 100 = 30%
        assert tracker.total_files_changed == 1

    def test_multiple_files(self):
        """Test tracking changes to multiple files."""
        tracker = FileChangeTracker()
        now = datetime.now()

        tracker.record_file_change(
            file_path="file1.py",
            additions=10,
            deletions=5,
            author_login="user1",
            commit_date=now,
        )
        tracker.record_file_change(
            file_path="file2.py",
            additions=20,
            deletions=10,
            author_login="user1",
            commit_date=now,
        )

        hotspots = tracker.get_hotspots(min_changes=1)
        assert len(hotspots) == 2
        assert tracker.total_files_changed == 2

    def test_min_changes_filter(self):
        """Test that min_changes filter excludes files below threshold."""
        tracker = FileChangeTracker()
        now = datetime.now()

        # File with 5 changes
        for _ in range(5):
            tracker.record_file_change(
                file_path="frequent.py",
                additions=5,
                deletions=3,
                author_login="user1",
                commit_date=now,
            )

        # File with 2 changes
        for _ in range(2):
            tracker.record_file_change(
                file_path="infrequent.py",
                additions=5,
                deletions=3,
                author_login="user1",
                commit_date=now,
            )

        # Get hotspots with min_changes=3
        hotspots = tracker.get_hotspots(min_changes=3)

        # Only frequent.py should be included
        assert len(hotspots) == 1
        assert hotspots[0].file_path == "frequent.py"
        assert tracker.total_files_changed == 2  # Both files tracked

    def test_sorting_by_churn_score(self):
        """Test that hotspots are sorted by churn score descending."""
        tracker = FileChangeTracker(strategy=TotalActivityChurnStrategy())
        now = datetime.now()

        # High frequency, low magnitude
        for i in range(5):
            tracker.record_file_change(
                file_path="file1.py",
                additions=5,
                deletions=5,
                author_login="user1",
                commit_date=now,
                commit_sha=f"commit1_{i}",
            )

        # Low frequency, high magnitude
        for i in range(3):
            tracker.record_file_change(
                file_path="file2.py",
                additions=50,
                deletions=50,
                author_login="user1",
                commit_date=now,
                commit_sha=f"commit2_{i}",
            )

        # Set baselines to create different churn percentages
        tracker.set_baseline_loc("file1.py", 1000)  # (5+5)*5 / 1000 = 5%
        tracker.set_baseline_loc("file2.py", 100)  # (50+50)*3 / 100 = 300%

        hotspots = tracker.get_hotspots(min_changes=1)

        # file2 should be first (higher churn percentage)
        assert hotspots[0].file_path == "file2.py"
        assert hotspots[0].churn_score == 300.0
        assert hotspots[1].file_path == "file1.py"
        assert hotspots[1].churn_score == 5.0

    def test_unique_authors_tracking(self):
        """Test tracking unique authors for a file."""
        tracker = FileChangeTracker()
        now = datetime.now()

        # Three changes by different authors
        tracker.record_file_change(
            file_path="shared.py",
            additions=10,
            deletions=5,
            author_login="user1",
            commit_date=now,
        )
        tracker.record_file_change(
            file_path="shared.py",
            additions=20,
            deletions=10,
            author_login="user2",
            commit_date=now,
        )
        tracker.record_file_change(
            file_path="shared.py",
            additions=15,
            deletions=8,
            author_login="user1",  # Duplicate author
            commit_date=now,
        )

        hotspots = tracker.get_hotspots(min_changes=1)
        assert hotspots[0].unique_authors == 2  # user1 and user2

    def test_author_none_handling(self):
        """Test handling commits with no author."""
        tracker = FileChangeTracker()
        now = datetime.now()

        tracker.record_file_change(
            file_path="test.py",
            additions=10,
            deletions=5,
            author_login=None,  # No author
            commit_date=now,
        )

        hotspots = tracker.get_hotspots(min_changes=1)
        assert hotspots[0].unique_authors == 0

    def test_date_tracking(self):
        """Test that first_changed and last_changed dates are tracked."""
        tracker = FileChangeTracker()
        now = datetime.now()
        dates = [
            now - timedelta(days=30),  # First
            now - timedelta(days=20),  # Middle
            now - timedelta(days=10),  # Last
        ]

        for date in dates:
            tracker.record_file_change(
                file_path="tracked.py",
                additions=5,
                deletions=3,
                author_login="user1",
                commit_date=date,
            )

        hotspots = tracker.get_hotspots(min_changes=1)
        assert hotspots[0].first_changed == dates[0]
        assert hotspots[0].last_changed == dates[2]

    def test_activity_churn_strategy(self):
        """Test TotalActivityChurnStrategy with baseline LOC."""
        activity_tracker = FileChangeTracker(strategy=TotalActivityChurnStrategy())
        now = datetime.now()

        # Record changes
        activity_tracker.record_file_change(
            file_path="test.py",
            additions=100,
            deletions=50,
            author_login="user1",
            commit_date=now,
            commit_sha="abc123",
        )

        # Set baseline LOC (file had 1000 lines at start of period)
        activity_tracker.set_baseline_loc("test.py", 1000)

        hotspots = activity_tracker.get_hotspots(min_changes=1)

        # Activity churn: (100 + 50) / 1000 * 100 = 15%
        assert hotspots[0].churn_score == 15.0
        assert hotspots[0].activity_churn_percentage == 15.0
        assert hotspots[0].baseline_loc == 1000

    def test_activity_churn_without_baseline(self):
        """Test TotalActivityChurnStrategy without baseline returns 0."""
        activity_tracker = FileChangeTracker(strategy=TotalActivityChurnStrategy())
        now = datetime.now()

        # Record changes but don't set baseline
        activity_tracker.record_file_change(
            file_path="test.py",
            additions=100,
            deletions=50,
            author_login="user1",
            commit_date=now,
            commit_sha="abc123",
        )

        hotspots = activity_tracker.get_hotspots(min_changes=1)

        # Without baseline, should return 0
        assert hotspots[0].churn_score == 0.0
        assert hotspots[0].activity_churn_percentage == 0.0
        assert hotspots[0].baseline_loc is None

    def test_rework_rate_strategy(self):
        """Test ReworkRateStrategy with commit history."""
        rework_tracker = FileChangeTracker(strategy=ReworkRateStrategy())
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        # Day 0: Add 100 lines
        rework_tracker.record_file_change(
            file_path="test.py",
            additions=100,
            deletions=0,
            author_login="user1",
            commit_date=base_date,
            commit_sha="commit1",
        )

        # Day 10: Delete 30 lines (rework - within 21 days)
        rework_tracker.record_file_change(
            file_path="test.py",
            additions=0,
            deletions=30,
            author_login="user1",
            commit_date=base_date + timedelta(days=10),
            commit_sha="commit2",
        )

        hotspots = rework_tracker.get_hotspots(min_changes=1)

        # Rework percentage: 30 / (100 + 30) * 100 ≈ 23.08%
        assert hotspots[0].churn_score > 23.0
        assert hotspots[0].churn_score < 24.0
        assert hotspots[0].rework_percentage is not None
        assert hotspots[0].category_breakdown is not None
        assert hotspots[0].category_breakdown.new_work_lines == 100
        assert hotspots[0].category_breakdown.rework_lines == 30
        assert hotspots[0].category_breakdown.refactor_lines == 0
        assert hotspots[0].category_breakdown.helping_others_lines == 0

    def test_rework_rate_with_refactor(self):
        """Test ReworkRateStrategy distinguishes rework from refactor."""
        rework_tracker = FileChangeTracker(strategy=ReworkRateStrategy())
        base_date = datetime(2025, 1, 1, 12, 0, 0)

        # Day 0: Add 100 lines
        rework_tracker.record_file_change(
            file_path="test.py",
            additions=100,
            deletions=0,
            author_login="user1",
            commit_date=base_date,
            commit_sha="commit1",
        )

        # Day 30: Delete 20 lines (refactor - outside 21-day window)
        rework_tracker.record_file_change(
            file_path="test.py",
            additions=0,
            deletions=20,
            author_login="user1",
            commit_date=base_date + timedelta(days=30),
            commit_sha="commit2",
        )

        hotspots = rework_tracker.get_hotspots(min_changes=1)

        # No rework, only refactor
        assert hotspots[0].churn_score == 0.0
        assert hotspots[0].category_breakdown.new_work_lines == 100
        assert hotspots[0].category_breakdown.rework_lines == 0
        assert hotspots[0].category_breakdown.refactor_lines == 20

    def test_strategy_comparison(self):
        """Compare results using both activity and rework strategies."""
        activity_tracker = FileChangeTracker(strategy=TotalActivityChurnStrategy())
        rework_tracker = FileChangeTracker(strategy=ReworkRateStrategy())

        base_date = datetime(2025, 1, 1, 12, 0, 0)

        # Record identical changes to both trackers
        for tracker in [activity_tracker, rework_tracker]:
            # Day 0: user1 adds 100 lines
            tracker.record_file_change(
                file_path="test.py",
                additions=100,
                deletions=0,
                author_login="user1",
                commit_date=base_date,
                commit_sha="commit1",
            )
            # Day 5: user2 adds 50 lines
            tracker.record_file_change(
                file_path="test.py",
                additions=50,
                deletions=0,
                author_login="user2",
                commit_date=base_date + timedelta(days=5),
                commit_sha="commit2",
            )

        # Set baseline for activity tracker
        activity_tracker.set_baseline_loc("test.py", 1000)

        activity_hotspots = activity_tracker.get_hotspots(min_changes=1)
        rework_hotspots = rework_tracker.get_hotspots(min_changes=1)

        # Activity: (150 + 0) / 1000 * 100 = 15%
        assert activity_hotspots[0].churn_score == 15.0

        # Rework: 0% (no deletions, only additions = new work)
        assert rework_hotspots[0].churn_score == 0.0
