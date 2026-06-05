---
name: hotspot-analysis
description: Reference for the hotspot/churn analysis feature — churn formulas (Total Activity vs. Rework Rate), the 21-day rework window, change categorization (New Work / Rework / Refactor / Helping Others), and implementation invariants. Load when working on src/integrations/github/churn_strategies.py, hotspot_tracker.py, related tests, the `hotspots` CLI command, or when the user asks about churn/rework formulas.
---

# Hotspot Analysis

Commit hotspot analysis identifies files with high maintenance burden by computing per-file churn over a time window.

CLI entry point: `uv run github-agent hotspots <owner/repo>` with `--path`, `--strategy` (`activity` or `rework`), `--since`, `--until`, `--export-md`.

## Churn Calculation Strategies

Strategies are pluggable — implementations live in `src/integrations/github/churn_strategies.py`. File change tracking lives in `src/integrations/github/hotspot_tracker.py`.

### 1. Total Activity Churn (default: `strategy="activity"`)

- Formula: `(additions + deletions) / baseline_loc × 100`
- Measures total code volatility as percentage of initial codebase
- Requires baseline LOC at start of analysis period
- Example: 4,000 added + 1,600 deleted / 20,000 baseline = 28% churn

### 2. Rework Rate (`strategy="rework"`)

- Measures code rewritten within a 21-day window
- Categorizes changes as:
  - **New Work**: Newly added code
  - **Rework**: Code deleted/rewritten within 21 days by same author
  - **Refactor**: Code modified after 21 days
  - **Helping Others**: Changes to someone else's recent code within 21 days
- Formula: `(rework_lines) / (total_lines) × 100`
- Returns detailed category breakdown

## Implementation Invariants

- Chronological commit processing for temporal analysis
- Baseline LOC fetched from Git tree at analysis period start
- Same-commit additions and deletions are **not** considered rework
- Only changes in subsequent commits (`days_diff > 0`) count as rework
- Fixed 21-day window for rework detection (industry standard)

## Related Tests

- `tests/integrations/test_hotspot_analysis.py`
- `tests/integrations/test_rework_rate_strategy.py`
- `tests/integrations/test_total_activity_churn.py`
- `tests/integrations/test_file_change_tracker.py`
