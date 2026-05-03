# Tournament Feature Design

**Date:** 2026-05-03
**Status:** Approved

## Overview

Add a `tournament` CLI subcommand to latent-space-dance-off that runs a single-elimination tournament where LLM models compete in free-for-all rounds. In each round, all surviving models generate SVGs from a theme selected by an "audience" judge LLM. A round judge ranks all models and the worst is eliminated. The tournament ends when one champion remains.

## Architecture

A new `tournament` subcommand in `main.py` that orchestrates the tournament flow. Three new modules in `src/`:

- **`tournament.py`** — Core `Tournament` class managing bracket state, rounds, and results
- **`theme_selector.py`** — Uses a judge LLM to pick a theme each round from a pool
- **`round_judge.py`** — Evaluates SVGs from all surviving models, eliminates the worst

These follow the existing pattern (like `svg_generator.py`, `svg_judge.py`) and reuse `ModelManager`, `SVGGenerator`, and `Config`.

## Components & Data Flow

### `Tournament` class (`src/tournament.py`)

- `__init__(models: dict[str, client], config: Config)` — accepts model name→client dict and config
- `run() -> TournamentResult` — orchestrates the full tournament loop
- Tracks `survivors` (list of model names), `rounds` (list of RoundResult), `champion` (str)
- Each round: picks theme → generates SVGs → judges → eliminates worst

### `ThemeSelector` (`src/theme_selector.py`)

- `select_theme(pool: list[str], round_num: int, history: list[str]) -> str`
- Sends a prompt to a judge LLM with the theme pool, round number, and past themes to avoid repetition
- Returns selected theme string

### `RoundJudge` (`src/round_judge.py`)

- `judge_round(survivors: list[str], theme: str, svg_map: dict[str, list[str]], num_svg_per_model: int = 2) -> str`
- Receives all SVG code paths from surviving models for the theme
- Sends all SVGs to a judge LLM with a tournament-specific prompt: "Pick the winner, rank all models"
- Returns the model name to eliminate (lowest ranked)

### Data flow per round

```
ThemeSelector.select_theme() → theme
  → SVGGenerator.generate_svg() for each survivor × 2 passes
  → RoundJudge.judge_round() → model_to_eliminate
    → remove from survivors
```

Each round's results (theme, all scores, eliminated model) are stored in a `RoundResult` dataclass.

## CLI Interface

### Command

```bash
python main.py tournament --models llama3,gemma2,mistral [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--models` | (required) | Comma-separated model names |
| `--theme-pool` | `abstract,landscape,portrait,object,scene` | Available themes for the audience-judge to pick from |
| `--judges` | `1` | Number of judge models (1 for theme selection + round judging) |
| `--output` | `./output` | Output directory |
| `--svg-per-model` | `2` | SVGs each model generates per round |
| `--ollama-host` | `http://localhost:11434` | Ollama host |

### Terminal Output Per Round

- Round number and theme (revealed by audience-judge)
- Progress bar for SVG generation (reuses existing Rich progress pattern)
- ASCII art preview of each model's best SVG
- Judge's ranking and eliminated model highlighted in red
- Live bracket visualization showing survivors vs eliminated

### HTML Report

Extends existing `benchmark_report.html` with:
- Tournament bracket visualization
- Per-round breakdown with themes, rankings, and SVGs
- Champion highlight

## Error Handling & Edge Cases

### Error handling
- Model generation failure → model gets lowest possible score, most likely eliminated
- Judge LLM failure → fallback to random elimination for that round, logged as warning
- Theme pool exhaustion → if pool size <= eliminated count, cycle through remaining themes or allow repeats

### Edge cases
- 2 models remaining → final round, clear winner declared
- Tie in judging → judge LLM prompted to break ties; if still tied, first-alphabetical eliminated
- All SVGs fail in a round → random elimination, all remaining models advance

## Storage

### Output structure

```
output/
└── <run_id>/
    ├── tournament.json           # Full tournament state (rounds, results, champion)
    ├── assets/
    │   └── <round>_<model>_pass{N}.svg
    └── tournament_report.html    # HTML tournament report
```

### Data classes (`src/tournament.py`)

```python
@dataclass
class RoundResult:
    round_num: int
    theme: str
    rankings: list[tuple[str, float]]  # (model_name, score)
    eliminated: str
    svg_results: list[SVGResult]

@dataclass
class TournamentResult:
    run_id: str
    timestamp: str
    models: list[str]
    rounds: list[RoundResult]
    champion: str
```

Mirrors the existing `BenchmarkRecord`/`LeaderboardEntry` pattern.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/tournament.py` | New | Core Tournament class, RoundResult, TournamentResult |
| `src/theme_selector.py` | New | Audience-judge theme selection |
| `src/round_judge.py` | New | Free-for-all round judging |
| `main.py` | Modify | Add `tournament` subcommand |
| `src/html_generator.py` | Modify | Add tournament report template support |
| `README.md` | Modify | Document tournament command |
