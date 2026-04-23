# Custom Judging Criteria Feature

## Overview
This feature allows users to provide custom judging criteria via the CLI, with the default criteria being creativity, aesthetics, and complexity.

## Changes Made

### 1. Configuration (`src/config.py`)
- Added `JUDGING_CRITERIA` field to the `Config` class with default value `"creativity,aesthetics,complexity"`
- Added `judging_criteria` property that parses the comma-separated string into a list

### 2. SVG Judge (`src/svg_judge.py`)
- Updated `Judgment` dataclass to use dynamic `scores` dictionary instead of fixed `creativity_score`, `aesthetics_score`, `complexity_score` fields
- Added `criteria_used` field to track which criteria were used for each judgment
- Updated `judge_svg()` method to:
  - Build prompts dynamically based on configured criteria
  - Extract scores for each criterion from the LLM response
  - Pass criteria to the Judgment constructor
- Updated `aggregate_judgments()` method to aggregate scores dynamically for each criterion

### 3. Main CLI (`main.py`)
- Added `--criteria` / `-c` option to the `run` command
- Updated `get_config()` to accept and pass `judging_criteria` parameter
- Updated `_run_impl()` to accept and pass `judging_criteria` parameter
- Updated console output to display criteria being used
- Updated leaderboard table to display columns for each criterion dynamically

### 4. HTML Report Generator (`src/html_generator.py`)
- Updated `generate_benchmark_html()` to accept and pass `criteria` parameter
- Updated `_build_html()` to accept `criteria_display` parameter
- Added CSS for `.criteria-display` class to show criteria in the header
- Added HTML element to display criteria in the report header

## Usage

### Default Criteria (creativity, aesthetics, complexity)
```bash
python main.py run --models "llama3,mistral" --themes "abstract,landscape"
```

### Custom Criteria
```bash
python main.py run --models "llama3,mistral" --criteria "color_harmony,composition,technical_quality"
```

### Available Built-in Criteria
- `creativity` - How original and innovative is the design?
- `aesthetics` - How visually pleasing and well-composed is the SVG?
- `complexity` - How sophisticated and detailed is the artwork?
- `color_harmony` - How well do the colors work together?
- `composition` - How balanced and well-structured is the composition?
- `technical_quality` - How technically sound is the SVG code?

Users can define any custom criteria by simply listing them in the `--criteria` option.

## Backward Compatibility
The feature is fully backward compatible. If no `--criteria` is provided, the system uses the default criteria (creativity, aesthetics, complexity).

## Testing
The implementation has been tested with:
1. Default criteria (no --criteria flag)
2. Custom criteria (with --criteria flag)
3. CLI help displays the criteria option correctly
