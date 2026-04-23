# Sync Issues (Unresolved Only)

## SYNC-1: src/ranking.py Structural Issues
- **Severity**: HIGH
- **Files**: src/ranking.py
- **Problem**: 
  1. Duplicate `Config` class definition (lines 90 and 95)
  2. Unused imports: `uuid` and `os`
  3. Missing unit tests
- **Fix**: 
  1. Remove nested `Config` class (line 90) or consolidate
  2. Remove unused imports (`uuid`, `os`)
  3. Create `tests/test_ranking.py` with unit tests for all functions
- **Status**: pending

## SYNC-2: Missing Unit Tests for ranking.py
- **Severity**: HIGH
- **Files**: tests/test_ranking.py
- **Problem**: No test file exists for src/ranking.py module
- **Fix**: Create comprehensive unit tests covering:
  - `aggregate_all_judgments`
  - `calculate_final_ranking`
  - `generate_leaderboard`
  - `save_leaderboard`
  - `load_leaderboard`
  - `export_to_csv`
  - `get_top_models`
  - `get_model_stats`
- **Status**: pending
