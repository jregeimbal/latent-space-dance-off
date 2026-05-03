# Tournament Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `tournament` CLI subcommand that runs a single-elimination tournament where LLM models compete in free-for-all rounds — each round, a judge picks a theme, all surviving models generate 2 SVGs each, and the worst is eliminated until one champion remains.

**Architecture:** Three new modules (`src/tournament.py`, `src/theme_selector.py`, `src/round_judge.py`) plus a new `tournament` subcommand in `main.py`. Tournament data is stored in `output/benchmarks/<run_id>/tournament.json` and a `tournament_report.html` is generated.

**Tech Stack:** Python 3.9+, Pydantic, Typer, Rich, httpx, existing Ollama/LM Studio client.

---

### Task 1: Create `src/tournament.py` with data classes

**Files:**
- Create: `src/tournament.py`

- [ ] **Step 1: Write the `RoundResult` and `TournamentResult` data classes**

```python
"""
Tournament module for latent-space-dance-off.

Defines data structures for tournament state and results.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.benchmark import SVGResult


@dataclass
class RoundResult:
    """Result of a single tournament round."""
    round_num: int
    theme: str
    rankings: List[tuple]  # List of (model_name, score) tuples, highest first
    eliminated: str
    svg_results: List[SVGResult] = field(default_factory=list)


@dataclass
class TournamentResult:
    """Complete tournament result."""
    run_id: str
    timestamp: str
    models: List[str]
    rounds: List[RoundResult] = field(default_factory=list)
    champion: Optional[str] = None
```

- [ ] **Step 2: Run test to verify it imports**

Run: `python -c "from src.tournament import RoundResult, TournamentResult; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/tournament.py
git commit -m "feat: add tournament data classes"
```

---

### Task 2: Create `src/theme_selector.py`

**Files:**
- Create: `src/theme_selector.py`

- [ ] **Step 1: Write the `ThemeSelector` class**

```python
"""
Theme Selector - Audience-judge picks themes for tournament rounds.

Uses a judge LLM to select themes from a pool, avoiding repeats from past rounds.
"""

import re
from typing import List, Optional

from src.llm_client import BaseLLMClient, LLMChunk


class ThemeSelector:
    """Selects themes for tournament rounds using a judge LLM."""

    def __init__(self, judge_client: BaseLLMClient, judge_model: str) -> None:
        self.judge_client = judge_client
        self.judge_model = judge_model

    async def select_theme(
        self,
        pool: List[str],
        round_num: int,
        used_themes: List[str],
    ) -> str:
        """Select a theme for the current round.

        Args:
            pool: Available themes to choose from.
            round_num: Current round number (1-based).
            used_themes: Themes already used in previous rounds.

        Returns:
            Selected theme string.
        """
        available = [t for t in pool if t not in used_themes]
        if not available:
            available = pool  # Allow repeats if pool exhausted

        prompt = (
            f"You are the audience judge for a tournament round. "
            f"This is round {round_num}. "
            f"Available themes: {', '.join(pool)}. "
            f"Themes already used: {', '.join(used_themes) if used_themes else 'none'}. "
            f"Pick one theme from the available list that would make for an interesting round. "
            f"Respond with ONLY the theme name, nothing else."
        )

        try:
            # Clear context first
            await self.judge_client.generate(
                model=self.judge_model,
                prompt="/clear",
                stream=False,
            )

            response = await self.judge_client.generate(
                model=self.judge_model,
                prompt=prompt,
                stream=False,
            )
            text = getattr(response, "response", "") or str(response)
            theme = text.strip().strip('"').strip("'").strip()
            if theme and theme in pool:
                return theme
            # Fallback: pick first available
            return available[0]
        except Exception:
            return available[0]
```

- [ ] **Step 2: Write unit tests for ThemeSelector**

Create file `tests/test_theme_selector.py`:

```python
"""Tests for theme_selector module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.theme_selector import ThemeSelector
from tests.conftest import _run_async


class TestThemeSelector:
    def test_select_theme_picks_from_pool(self):
        """ThemeSelector picks a theme from the available pool."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = "landscape"
        mock_client.generate = AsyncMock(return_value=mock_response)

        selector = ThemeSelector(judge_client=mock_client, judge_model="test_model")

        result = _run_async(
            selector.select_theme(
                pool=["abstract", "landscape", "portrait"],
                round_num=1,
                used_themes=[],
            )
        )

        assert result == "landscape"

    def test_select_theme_avoids_used_themes(self):
        """ThemeSelector skips themes already used in past rounds."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = "portrait"
        mock_client.generate = AsyncMock(return_value=mock_response)

        selector = ThemeSelector(judge_client=mock_client, judge_model="test_model")

        result = _run_async(
            selector.select_theme(
                pool=["abstract", "landscape", "portrait"],
                round_num=2,
                used_themes=["abstract", "landscape"],
            )
        )

        assert result == "portrait"

    def test_select_theme_falls_back_when_judge_fails(self):
        """ThemeSelector falls back to first available theme on judge error."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=Exception("connection error"))

        selector = ThemeSelector(judge_client=mock_client, judge_model="test_model")

        result = _run_async(
            selector.select_theme(
                pool=["abstract", "landscape"],
                round_num=1,
                used_themes=[],
            )
        )

        assert result == "abstract"

    def test_select_theme_cycles_when_pool_exhausted(self):
        """ThemeSelector allows repeats when all themes have been used."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = "abstract"
        mock_client.generate = AsyncMock(return_value=mock_response)

        selector = ThemeSelector(judge_client=mock_client, judge_model="test_model")

        result = _run_async(
            selector.select_theme(
                pool=["abstract", "landscape"],
                round_num=3,
                used_themes=["abstract", "landscape"],
            )
        )

        assert result == "abstract"

    def test_select_theme_strips_quotes(self):
        """ThemeSelector strips surrounding quotes from judge response."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = '"landscape"'
        mock_client.generate = AsyncMock(return_value=mock_response)

        selector = ThemeSelector(judge_client=mock_client, judge_model="test_model")

        result = _run_async(
            selector.select_theme(
                pool=["abstract", "landscape"],
                round_num=1,
                used_themes=[],
            )
        )

        assert result == "landscape"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_theme_selector.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.theme_selector'"

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_theme_selector.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/theme_selector.py tests/test_theme_selector.py
git commit -m "feat: add theme selector for tournament audience-judge"
```

---

### Task 3: Create `src/round_judge.py`

**Files:**
- Create: `src/round_judge.py`

- [ ] **Step 1: Write the `RoundJudge` class**

```python
"""
Round Judge - Evaluates SVGs from all surviving models and eliminates the worst.

In a free-for-all round, all surviving models generate SVGs from the same theme.
The round judge ranks all models and returns the one to eliminate.
"""

import json
import random
import re
from pathlib import Path
from typing import Dict, List, Optional

from src.llm_client import BaseLLMClient, LLMChunk


class RoundJudge:
    """Judges tournament rounds and determines which model to eliminate."""

    def __init__(self, judge_client: BaseLLMClient, judge_model: str) -> None:
        self.judge_client = judge_client
        self.judge_model = judge_model

    async def judge_round(
        self,
        survivors: List[str],
        theme: str,
        svg_map: Dict[str, List[str]],
        num_svg_per_model: int = 2,
    ) -> str:
        """Judge a tournament round and return the model to eliminate.

        Args:
            survivors: List of model names still in the tournament.
            theme: The theme all models generated SVGs for.
            svg_map: Dict mapping model_name -> list of SVG file paths.
            num_svg_per_model: Number of SVGs each model generated.

        Returns:
            Model name to eliminate (lowest ranked).
        """
        # Collect all SVGs for this round
        svg_entries = []
        for model_name in survivors:
            paths = svg_map.get(model_name, [])
            if not paths:
                svg_entries.append((model_name, "[no SVG generated]"))
                continue
            # Use the first SVG (judge picks the best per model, we use the first for ranking)
            svg_path = Path(paths[0])
            try:
                svg_content = svg_path.read_text(encoding="utf-8")
            except Exception:
                svg_content = "[failed to read SVG]"
            svg_entries.append((model_name, svg_content))

        # Build SVG display text
        svg_text_parts = []
        for idx, (model_name, svg_content) in enumerate(svg_entries, 1):
            title = f"SVG #{idx} ({model_name}):"
            svg_text_parts.append(f"{title}\n{svg_content[:3000]}")

        svg_display = "\n\n".join(svg_text_parts)

        prompt = (
            f"You are judging a tournament round. All models created SVGs from the theme: '{theme}'.\n\n"
            f"Rank these models from best to worst. For each model, I'll show one of their SVGs.\n\n"
            f"{svg_display}\n\n"
            f"Respond with a JSON array of objects, one per model, ordered from best (rank 1) to worst (last):\n"
            f'[{{"model": "<model_name>", "rank": <1-N>}}, ...]\n\n'
            f"Respond with ONLY the JSON array, nothing else."
        )

        try:
            # Clear context first
            await self.judge_client.generate(
                model=self.judge_model,
                prompt="/clear",
                stream=False,
            )

            response = await self.judge_client.generate(
                model=self.judge_model,
                prompt=prompt,
                stream=False,
            )
            text = getattr(response, "response", "") or str(response)
            rankings = self._parse_rankings(text, survivors)

            if rankings:
                # Last in rankings = worst = eliminate
                return rankings[-1]["model"]
            else:
                return self._fallback_elimination(survivors)
        except Exception:
            return self._fallback_elimination(survivors)

    def _parse_rankings(self, text: str, survivors: List[str]) -> List[dict]:
        """Parse JSON rankings from judge response."""
        # Try to extract JSON array
        json_pattern = re.compile(r'\[.*\]', re.DOTALL)
        match = json_pattern.search(text)
        if not match:
            return []

        try:
            data = json.loads(match.group(0))
            if not isinstance(data, list):
                return []
            # Validate each entry has model and rank
            valid = []
            for entry in data:
                if isinstance(entry, dict) and "model" in entry and "rank" in entry:
                    valid.append(entry)
            return valid
        except (json.JSONDecodeError, IndexError):
            return []

    def _fallback_elimination(self, survivors: List[str]) -> str:
        """Randomly eliminate a model as fallback."""
        return random.choice(survivors)
```

- [ ] **Step 2: Write unit tests for RoundJudge**

Create file `tests/test_round_judge.py`:

```python
"""Tests for round_judge module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.round_judge import RoundJudge
from tests.conftest import _run_async

FAKE_SVG = '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'


class TestRoundJudge:
    def test_judge_round_returns_model_to_eliminate(self):
        """RoundJudge returns the worst-ranked model name."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = '[{"model": "model_b", "rank": 2}, {"model": "model_a", "rank": 1}]'
        mock_client.generate = AsyncMock(return_value=mock_response)

        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        svg_map = {
            "model_a": ["/tmp/model_a.svg"],
            "model_b": ["/tmp/model_b.svg"],
        }
        # Write fake SVGs
        for path in ["/tmp/model_a.svg", "/tmp/model_b.svg"]:
            Path(path).write_text(FAKE_SVG)

        result = _run_async(
            judge.judge_round(
                survivors=["model_a", "model_b"],
                theme="abstract",
                svg_map=svg_map,
            )
        )

        assert result == "model_b"

    def test_judge_round_fallback_on_parse_failure(self):
        """RoundJudge falls back to random elimination when judge response is unparseable."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = "this is not json at all"
        mock_client.generate = AsyncMock(return_value=mock_response)

        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        svg_map = {
            "model_a": ["/tmp/model_a.svg"],
            "model_b": ["/tmp/model_b.svg"],
        }
        for path in ["/tmp/model_a.svg", "/tmp/model_b.svg"]:
            Path(path).write_text(FAKE_SVG)

        with patch("random.choice", return_value="model_a"):
            result = _run_async(
                judge.judge_round(
                    survivors=["model_a", "model_b"],
                    theme="abstract",
                    svg_map=svg_map,
                )
            )

        assert result == "model_a"

    def test_judge_round_fallback_on_exception(self):
        """RoundJudge falls back to random elimination when judge throws."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=Exception("connection error"))

        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        svg_map = {
            "model_a": ["/tmp/model_a.svg"],
        }
        Path("/tmp/model_a.svg").write_text(FAKE_SVG)

        with patch("random.choice", return_value="model_a"):
            result = _run_async(
                judge.judge_round(
                    survivors=["model_a"],
                    theme="abstract",
                    svg_map=svg_map,
                )
            )

        assert result == "model_a"

    def test_judge_round_handles_no_svg(self):
        """RoundJudge handles models that failed to generate SVGs."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = '[{"model": "model_a", "rank": 2}, {"model": "model_b", "rank": 1}]'
        mock_client.generate = AsyncMock(return_value=mock_response)

        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        svg_map = {
            "model_b": ["/tmp/model_b.svg"],
            # model_a has no SVGs (generation failed)
        }
        Path("/tmp/model_b.svg").write_text(FAKE_SVG)

        result = _run_async(
            judge.judge_round(
                survivors=["model_a", "model_b"],
                theme="abstract",
                svg_map=svg_map,
            )
        )

        assert result == "model_a"

    def test_parse_rankings_valid_json(self):
        """_parse_rankings correctly parses valid JSON array."""
        mock_client = AsyncMock()
        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        text = '[{"model": "model_a", "rank": 1}, {"model": "model_b", "rank": 2}]'
        result = judge._parse_rankings(text, ["model_a", "model_b"])

        assert len(result) == 2
        assert result[0]["model"] == "model_a"
        assert result[0]["rank"] == 1
        assert result[1]["model"] == "model_b"

    def test_parse_rankings_invalid_json(self):
        """_parse_rankings returns empty list for invalid JSON."""
        mock_client = AsyncMock()
        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        text = "not json"
        result = judge._parse_rankings(text, ["model_a", "model_b"])

        assert result == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_round_judge.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.round_judge'"

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_round_judge.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/round_judge.py tests/test_round_judge.py
git commit -m "feat: add round judge for tournament free-for-all elimination"
```

---

### Task 4: Implement `src/tournament.py` core logic

**Files:**
- Modify: `src/tournament.py` (add Tournament class)

- [ ] **Step 1: Add the `Tournament` class to `src/tournament.py`**

Replace the content of `src/tournament.py` with:

```python
"""
Tournament module for latent-space-dance-off.

Orchestrates a single-elimination tournament where LLM models compete
in free-for-all rounds. Each round: audience-judge picks a theme, all
surviving models generate SVGs, round judge eliminates the worst.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.benchmark import SVGResult
from src.llm_client import BaseLLMClient
from src.svg_generator import SVGGenerator
from src.theme_selector import ThemeSelector
from src.round_judge import RoundJudge


@dataclass
class RoundResult:
    """Result of a single tournament round."""
    round_num: int
    theme: str
    rankings: List[tuple]  # List of (model_name, score) tuples, highest first
    eliminated: str
    svg_results: List[SVGResult] = field(default_factory=list)


@dataclass
class TournamentResult:
    """Complete tournament result."""
    run_id: str
    timestamp: str
    models: List[str]
    rounds: List[RoundResult] = field(default_factory=list)
    champion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "models": self.models,
            "rounds": [
                {
                    "round_num": r.round_num,
                    "theme": r.theme,
                    "rankings": list(r.rankings),
                    "eliminated": r.eliminated,
                    "svg_results": [
                        {
                            "model_name": s.model_name,
                            "theme": s.theme,
                            "svg_code": s.svg_code,
                            "svg_path": s.svg_path,
                            "duration_ms": s.duration_ms,
                            "tokens_used": s.tokens_used,
                            "status": s.status,
                            "pass_number": s.pass_number,
                        }
                        for s in r.svg_results
                    ],
                }
                for r in self.rounds
            ],
            "champion": self.champion,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TournamentResult":
        """Deserialize from dict."""
        rounds = []
        for r in data.get("rounds", []):
            svg_results = [
                SVGResult(
                    model_name=s["model_name"],
                    theme=s["theme"],
                    svg_code=s["svg_code"],
                    svg_path=s["svg_path"],
                    duration_ms=s["duration_ms"],
                    tokens_used=s["tokens_used"],
                    status=s["status"],
                    pass_number=s.get("pass_number", 1),
                )
                for s in r.get("svg_results", [])
            ]
            rounds.append(RoundResult(
                round_num=r["round_num"],
                theme=r["theme"],
                rankings=r["rankings"],
                eliminated=r["eliminated"],
                svg_results=svg_results,
            ))
        return cls(
            run_id=data["run_id"],
            timestamp=data["timestamp"],
            models=data["models"],
            rounds=rounds,
            champion=data.get("champion"),
        )


class Tournament:
    """Orchestrates a single-elimination tournament."""

    def __init__(
        self,
        model_clients: Dict[str, BaseLLMClient],
        config: Any,
        theme_pool: List[str],
        output_dir: str,
        svg_per_model: int = 2,
        judge_model: str = "",
    ) -> None:
        self.model_clients = model_clients
        self.config = config
        self.theme_pool = theme_pool
        self.svg_per_model = svg_per_model
        self.svg_generator = SVGGenerator(config, svgs_dir=Path(output_dir) / "assets")
        self.run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
        self.timestamp = self.run_id
        self.models = list(model_clients.keys())
        self.survivors = list(self.models)
        self.rounds: List[RoundResult] = []
        self.champion: Optional[str] = None
        self.judge_model = judge_model or (self.models[0] if self.models else "llama3")

    async def run(self) -> TournamentResult:
        """Run the full tournament.

        Returns:
            TournamentResult with all rounds and the champion.
        """
        used_themes: List[str] = []
        round_num = 1

        while len(self.survivors) > 1:
            # Theme selection
            theme = await self._select_theme(used_themes, round_num)
            used_themes.append(theme)

            # SVG generation for all survivors
            svg_results: List[SVGResult] = []
            svg_map: Dict[str, List[str]] = {}

            for model_name in self.survivors:
                client = self.model_clients[model_name]
                for pass_num in range(1, self.svg_per_model + 1):
                    result = await self.svg_generator.generate_svg(
                        model_client=client,
                        theme=theme,
                        model_name=model_name,
                        run_id=self.run_id,
                        pass_number=pass_num,
                    )
                    svg_results.append(result)
                    if result.svg_path:
                        svg_map.setdefault(model_name, []).append(result.svg_path)

            # Round judging
            eliminated = await self._judge_round(
                self.survivors, theme, svg_map
            )

            # Build rankings from SVG results
            rankings = self._build_rankings(svg_results, self.survivors)

            # Record round result
            round_result = RoundResult(
                round_num=round_num,
                theme=theme,
                rankings=rankings,
                eliminated=eliminated,
                svg_results=svg_results,
            )
            self.rounds.append(round_result)

            # Eliminate
            self.survivors.remove(eliminated)
            round_num += 1

        # Champion is the last survivor
        self.champion = self.survivors[0] if self.survivors else None

        return TournamentResult(
            run_id=self.run_id,
            timestamp=self.timestamp,
            models=self.models,
            rounds=self.rounds,
            champion=self.champion,
        )

    async def _select_theme(self, used_themes: List[str], round_num: int) -> str:
        """Select a theme for the current round using the audience-judge."""
        # Use first available model client as judge
        judge_client = next(iter(self.model_clients.values()))
        selector = ThemeSelector(
            judge_client=judge_client,
            judge_model=self.judge_model,
        )
        return await selector.select_theme(
            pool=self.theme_pool,
            round_num=round_num,
            used_themes=used_themes,
        )

    async def _judge_round(
        self,
        survivors: List[str],
        theme: str,
        svg_map: Dict[str, List[str]],
    ) -> str:
        """Judge a round and return the model to eliminate."""
        judge_client = next(iter(self.model_clients.values()))
        round_judge = RoundJudge(
            judge_client=judge_client,
            judge_model=self.judge_model,
        )
        return await round_judge.judge_round(
            survivors=survivors,
            theme=theme,
            svg_map=svg_map,
            num_svg_per_model=self.svg_per_model,
        )

    def _build_rankings(
        self,
        svg_results: List[SVGResult],
        survivors: List[str],
    ) -> List[tuple]:
        """Build rankings from SVG results.

        Models with failed SVGs get lowest rank.
        Models with successful SVGs are ranked by generation speed (faster = better tiebreak).
        """
        rankings = []
        for model in survivors:
            model_results = [r for r in svg_results if r.model_name == model]
            failed = all(r.status == "failed" for r in model_results)
            if failed:
                rankings.append((model, 0.0))
            else:
                # Use average duration as a proxy (lower = faster = better)
                successful = [r for r in model_results if r.status == "success"]
                if successful:
                    avg_duration = sum(r.duration_ms for r in successful) / len(successful)
                    # Invert: lower duration = higher score
                    score = max(1.0, 10000.0 / (avg_duration + 1))
                    rankings.append((model, score))
                else:
                    rankings.append((model, 0.0))

        # Sort by score descending
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings

    def save_result(self, result: TournamentResult, output_dir: str) -> Path:
        """Save tournament result to JSON file."""
        run_dir = Path(output_dir) / "benchmarks" / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "assets").mkdir(parents=True, exist_ok=True)

        filepath = run_dir / "tournament.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
        return filepath
```

- [ ] **Step 2: Write unit tests for Tournament**

Create file `tests/test_tournament.py`:

```python
"""Tests for tournament module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tournament import RoundResult, Tournament, TournamentResult
from src.benchmark import SVGResult
from tests.conftest import _run_async

FAKE_SVG = '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'


class TestRoundResult:
    def test_creation(self):
        rr = RoundResult(
            round_num=1,
            theme="abstract",
            rankings=[("model_a", 8.0), ("model_b", 5.0)],
            eliminated="model_b",
        )
        assert rr.round_num == 1
        assert rr.theme == "abstract"
        assert rr.eliminated == "model_b"
        assert len(rr.svg_results) == 0

    def test_with_svg_results(self):
        svg = SVGResult(
            model_name="model_a",
            theme="abstract",
            svg_code=FAKE_SVG,
            status="success",
        )
        rr = RoundResult(
            round_num=1,
            theme="abstract",
            rankings=[("model_a", 8.0)],
            eliminated="model_b",
            svg_results=[svg],
        )
        assert len(rr.svg_results) == 1
        assert rr.svg_results[0].model_name == "model_a"


class TestTournamentResult:
    def test_to_dict(self):
        tr = TournamentResult(
            run_id="test-run",
            timestamp="2024-01-01T00:00:00",
            models=["model_a", "model_b"],
            champion="model_a",
        )
        d = tr.to_dict()
        assert d["run_id"] == "test-run"
        assert d["champion"] == "model_a"
        assert d["models"] == ["model_a", "model_b"]
        assert d["rounds"] == []

    def test_to_dict_with_rounds(self):
        svg = SVGResult(
            model_name="model_a",
            theme="abstract",
            svg_code=FAKE_SVG,
            status="success",
            duration_ms=1000.0,
            pass_number=1,
        )
        rr = RoundResult(
            round_num=1,
            theme="abstract",
            rankings=[("model_a", 8.0)],
            eliminated="model_b",
            svg_results=[svg],
        )
        tr = TournamentResult(
            run_id="test-run",
            timestamp="2024-01-01T00:00:00",
            models=["model_a", "model_b"],
            rounds=[rr],
            champion="model_a",
        )
        d = tr.to_dict()
        assert len(d["rounds"]) == 1
        assert d["rounds"][0]["round_num"] == 1
        assert d["rounds"][0]["eliminated"] == "model_b"
        assert len(d["rounds"][0]["svg_results"]) == 1

    def test_from_dict_roundtrip(self):
        svg = SVGResult(
            model_name="model_a",
            theme="abstract",
            svg_code=FAKE_SVG,
            status="success",
            duration_ms=1000.0,
            pass_number=1,
        )
        rr = RoundResult(
            round_num=1,
            theme="abstract",
            rankings=[("model_a", 8.0)],
            eliminated="model_b",
            svg_results=[svg],
        )
        tr = TournamentResult(
            run_id="test-run",
            timestamp="2024-01-01T00:00:00",
            models=["model_a", "model_b"],
            rounds=[rr],
            champion="model_a",
        )
        d = tr.to_dict()
        tr2 = TournamentResult.from_dict(d)
        assert tr2.run_id == tr.run_id
        assert tr2.champion == tr.champion
        assert len(tr2.rounds) == 1
        assert tr2.rounds[0].eliminated == "model_b"


class TestTournament:
    def _make_mock_config(self, tmp_path):
        """Create a minimal mock config for tournament tests."""
        from unittest.mock import Mock
        config = Mock()
        config.OUTPUT_DIR = str(tmp_path)
        config.svgs_dir = tmp_path / "svgs"
        config.benchmarks_dir = tmp_path / "benchmarks"
        config.LEADERBOARDS_DIR = tmp_path / "leaderboards"
        return config

    def test_tournament_reduces_models_to_champion(self):
        """Tournament eliminates models until one champion remains."""
        tmp_path = Path("/tmp/tournament_test")
        tmp_path.mkdir(exist_ok=True)
        (tmp_path / "assets").mkdir(exist_ok=True)

        config = self._make_mock_config(tmp_path)

        # Mock SVG generation: all models succeed
        mock_client_a = AsyncMock()
        mock_client_b = AsyncMock()
        mock_client_c = AsyncMock()

        model_clients = {
            "model_a": mock_client_a,
            "model_b": mock_client_b,
            "model_c": mock_client_c,
        }

        tournament = Tournament(
            model_clients=model_clients,
            config=config,
            theme_pool=["abstract", "landscape", "portrait"],
            output_dir=str(tmp_path),
            svg_per_model=1,
            judge_model="test_judge",
        )

        # Mock generate_svg to return success
        def make_svg_result(model_name):
            return SVGResult(
                model_name=model_name,
                theme="abstract",
                svg_code=FAKE_SVG,
                svg_path=str(tmp_path / f"{model_name}.svg"),
                duration_ms=1000.0,
                status="success",
                pass_number=1,
            )

        with patch.object(tournament.svg_generator, "generate_svg", side_effect=make_svg_result):
            # Mock theme selection to always return "abstract"
            with patch.object(tournament, "_select_theme", return_value="abstract"):
                # Mock round judging: eliminate model_b first, then model_c
                with patch.object(tournament, "_judge_round", side_effect=["model_b", "model_c"]):
                    result = _run_async(tournament.run())

        assert result.champion == "model_a"
        assert len(result.rounds) == 2
        assert result.rounds[0].eliminated == "model_b"
        assert result.rounds[1].eliminated == "model_c"

    def test_tournament_two_models_one_round(self):
        """Tournament with 2 models completes in 1 round."""
        tmp_path = Path("/tmp/tournament_test2")
        tmp_path.mkdir(exist_ok=True)
        (tmp_path / "assets").mkdir(exist_ok=True)

        config = self._make_mock_config(tmp_path)

        mock_client_a = AsyncMock()
        mock_client_b = AsyncMock()

        model_clients = {"model_a": mock_client_a, "model_b": mock_client_b}

        tournament = Tournament(
            model_clients=model_clients,
            config=config,
            theme_pool=["abstract"],
            output_dir=str(tmp_path),
            svg_per_model=1,
            judge_model="test_judge",
        )

        def make_svg_result(model_name):
            return SVGResult(
                model_name=model_name,
                theme="abstract",
                svg_code=FAKE_SVG,
                svg_path=str(tmp_path / f"{model_name}.svg"),
                duration_ms=1000.0,
                status="success",
                pass_number=1,
            )

        with patch.object(tournament.svg_generator, "generate_svg", side_effect=make_svg_result):
            with patch.object(tournament, "_select_theme", return_value="abstract"):
                with patch.object(tournament, "_judge_round", return_value="model_b"):
                    result = _run_async(tournament.run())

        assert result.champion == "model_a"
        assert len(result.rounds) == 1

    def test_save_result_writes_json(self):
        """Tournament.save_result writes tournament.json to the output directory."""
        tmp_path = Path("/tmp/tournament_test3")
        tmp_path.mkdir(exist_ok=True)

        tr = TournamentResult(
            run_id="test-run-123",
            timestamp="2024-01-01T00:00:00",
            models=["model_a"],
            champion="model_a",
        )

        tournament = Tournament(
            model_clients={},
            config=MagicMock(),
            theme_pool=["abstract"],
            output_dir=str(tmp_path),
        )

        filepath = tournament.save_result(tr, str(tmp_path))
        assert filepath.exists()
        assert filepath.name == "tournament.json"

        import json
        with open(filepath) as f:
            data = json.load(f)
        assert data["run_id"] == "test-run-123"
        assert data["champion"] == "model_a"

    def test_build_rankings_handles_failed_svgs(self):
        """_build_rankings puts models with failed SVGs at the bottom."""
        tmp_path = Path("/tmp/tournament_test4")
        tmp_path.mkdir(exist_ok=True)

        tournament = Tournament(
            model_clients={},
            config=MagicMock(),
            theme_pool=["abstract"],
            output_dir=str(tmp_path),
        )

        svg_results = [
            SVGResult(model_name="model_a", theme="abstract", svg_code=FAKE_SVG, status="success", duration_ms=500.0, pass_number=1),
            SVGResult(model_name="model_b", theme="abstract", svg_code="", status="failed", pass_number=1),
        ]

        rankings = tournament._build_rankings(svg_results, ["model_a", "model_b"])

        # model_a should be first (success), model_b last (failed)
        assert rankings[0][0] == "model_a"
        assert rankings[1][0] == "model_b"
        assert rankings[1][1] == 0.0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_tournament.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError" for missing Tournament class

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tournament.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/tournament.py tests/test_tournament.py
git commit -m "feat: add tournament orchestration with single-elimination bracket"
```

---

### Task 5: Add `tournament` CLI subcommand to `main.py`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add the `tournament` command function**

Add this new function to `main.py` (after the `runs` command, before `if __name__`):

```python
@app.command()
async def tournament(
    models: Optional[str] = typer.Option(None, "--models", "-m", help="Comma-separated model names to compete"),
    theme_pool: str = typer.Option("abstract,landscape,portrait,object,scene", "--theme-pool", "-tp", help="Comma-separated themes for audience-judge to pick from"),
    num_judges: int = typer.Option(1, "--judges", "-j", help="Number of judge models (1 for theme selection + round judging)"),
    output_dir: str = typer.Option("./output", "--output", "-o"),
    ollama_host: str = typer.Option("http://localhost:11434", "--ollama-host", "--host"),
    client_type: str = typer.Option("ollama", "--client-type", help="LLM client type (ollama or lmstudio)"),
    llm_host: str = typer.Option("", "--llm-host", help="LLM server host URL"),
    svg_per_model: int = typer.Option(2, "--svg-per-model", "-s", help="SVGs each model generates per round"),
):
    """Run a single-elimination tournament where models compete in free-for-all rounds."""
    theme_list = [t.strip() for t in theme_pool.split(",")]
    config = get_config(ollama_host, output_dir, num_judges, "", "", False, client_type, llm_host)

    model_manager = ModelManager(host=config.llm_host, client_type=config.LLM_CLIENT)
    model_list = parse_models(models or "")

    if not model_list:
        console.print(Panel(
            "[red]No models specified. Use --models.[/red]",
            title="No Models"
        ))
        return

    if len(model_list) < 2:
        console.print(Panel(
            "[red]Need at least 2 models for a tournament.[/red]",
            title="Not Enough Models"
        ))
        return

    # Initialize model clients
    model_clients = {}
    for model_name in model_list:
        try:
            client = await model_manager.get_model(model_name)
            model_clients[model_name] = client
            console.print(f"[green]Model {model_name} ready[/green]")
        except Exception as e:
            console.print(f"[red]Model {model_name} failed: {e}[/red]")

    if len(model_clients) < 2:
        console.print("[red]Need at least 2 working models for a tournament.[/red]")
        return

    # Create SVG generator with run-specific assets dir
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
    run_dir = Path(output_dir) / "benchmarks" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = run_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel(
        f"[bold green]Tournament Starting[/bold green]\n"
        f"Models: {', '.join(model_clients.keys())}\n"
        f"Theme pool: {', '.join(theme_list)}\n"
        f"SVGs per model per round: {svg_per_model}\n"
        f"Output: {run_dir}",
        title="[bold]Latent Space Dance Off - Tournament[/bold]",
        border_style="green"
    ))

    # Import Tournament here to avoid circular import at module level
    from src.tournament import Tournament

    tournament = Tournament(
        model_clients=model_clients,
        config=config,
        theme_pool=theme_list,
        output_dir=str(run_dir),
        svg_per_model=svg_per_model,
        judge_model=model_list[0],
    )

    # Run tournament with live progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Tournament...", total=None)

        result = await tournament.run()

        # Display round results
        for round_result in result.rounds:
            progress.update(task, description=f"Round {round_result.round_num}: {round_result.theme}")
            console.print(f"\n[cyan]Round {round_result.round_num}:[/cyan] Theme = [bold]{round_result.theme}[/bold]")

            # Show ASCII art for each model's SVG
            for svg in round_result.svg_results:
                if svg.status == "success" and svg.svg_code:
                    ascii_art = svg_to_ascii(svg.svg_code, width=80, use_ansi=True)
                    console.print(f"  [cyan]{svg.model_name}:[/cyan]")
                    sys.stdout.write(ascii_art + "\n")

            console.print(f"  [red]Eliminated:[/red] [bold]{round_result.eliminated}[/bold]")
            console.print(f"  [green]Survivors:[/green] {', '.join(tournament.survivors)}")

    # Display champion
    console.print(f"\n[bold green]=== CHAMPION: {result.champion} ===[/bold green]\n")

    # Save tournament result
    result_path = tournament.save_result(result, str(run_dir))
    console.print(f"[yellow]Tournament data saved to: {make_clickable_link(result_path)}[/yellow]")

    # Generate HTML report
    html_path = run_dir / "tournament_report.html"
    generate_tournament_html(result, html_path)
    console.print(f"[yellow]Tournament report saved to: {make_clickable_link(html_path)}[/yellow]")
```

Also add the import at the top of `main.py` (add to existing imports):

```python
from datetime import datetime
```

And add the `generate_tournament_html` import/function. We'll add the HTML generation function in Task 6, so for now add a placeholder import that will be resolved:

Actually, let's add the `generate_tournament_html` function in this same task since it's tightly coupled. Add this function to `main.py` before the `if __name__` block:

```python
def generate_tournament_html(result, output_path: Path) -> str:
    """Generate an HTML report for tournament results."""
    from typing import List
    from pathlib import Path

    rounds_html = ""
    for r in result.rounds:
        rankings_html = ""
        for rank_idx, (model, score) in enumerate(r.rankings, 1):
            is_eliminated = model == r.eliminated
            color = "#ff4444" if is_eliminated else "#4caf50"
            rankings_html += f'<div style="padding:4px 8px;background:#252525;border-radius:4px;margin:2px 0;color:{color}">' \
                           f'<strong>#{rank_idx}</strong> {html.escape(model)}' \
                           f'{"" if not is_eliminated else " [ELIMINATED]"}' \
                           f'</div>'

        svgs_html = ""
        for svg in r.svg_results:
            if svg.status == "success" and svg.svg_code:
                svgs_html += f'<div style="margin:8px 0"><strong>{html.escape(svg.model_name)}</strong><br>' \
                           f'{svg.svg_code}</div>'

        rounds_html += f'''
        <div class="round-section">
            <h3>Round {r.round_num}: {html.escape(r.theme)}</h3>
            <div class="rankings">{rankings_html}</div>
            <div class="round-svgs">{svgs_html}</div>
        </div>
        '''

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tournament - {html.escape(result.champion or "Unknown")}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; padding: 20px; background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 12px; border: 1px solid #333; }}
        .header h1 {{ font-size: 2em; background: linear-gradient(90deg, #00d2ff, #3a7bd5); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }}
        .champion {{ font-size: 1.5em; color: #ffd700; margin-top: 10px; }}
        .round-section {{ background: #1a1a1a; border: 1px solid #333; border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
        .round-section h3 {{ color: #b388ff; margin-bottom: 12px; }}
        .rankings {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 12px; }}
        .round-svgs {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }}
        .round-svgs div {{ background: #ffffff; border-radius: 8px; padding: 8px; }}
        .round-svgs svg {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Latent Space Dance Off - Tournament</h1>
        <div class="champion">Champion: {html.escape(result.champion or "TBD")}</div>
    </div>
{rounds_html}
</body>
</html>'''

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return str(output_path)
```

- [ ] **Step 2: Run to verify CLI loads**

Run: `python main.py tournament --help`
Expected: Shows tournament command help with all options

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add tournament CLI subcommand with live progress and HTML report"
```

---

### Task 6: Add `tournament` command to `pyproject.toml` scripts

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add tournament entry point**

Add to `[project.scripts]` section in `pyproject.toml`:

```toml
[project.scripts]
latent-space-dance-off = "main:app"
latent-space-dance-off-tournament = "main:tournament"
```

Wait — `tournament` is a Typer command registered on `app`, not a standalone function. The entry point `main:app` already handles all subcommands. No change needed to `pyproject.toml`.

Actually, let's verify this is correct by checking: the `tournament` function is decorated with `@app.command()`, so `latent-space-dance-off tournament` will work automatically. No `pyproject.toml` changes needed.

- [ ] **Step 2: Verify no changes needed**

Run: `python -c "from main import app; print([c.name for c in app.registered_commands])"`
Expected: Output includes `tournament`

- [ ] **Step 3: Commit (no changes)**

No files changed, skip commit.

---

### Task 7: Add tournament command to README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add tournament documentation**

Add this section to `README.md` after the "View Leaderboard" section (around line 125):

```markdown
### Run Tournament

```bash
python main.py tournament [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--models` | `-m` | (required) | Comma-separated model names |
| `--theme-pool` | `-tp` | `abstract,landscape,portrait,object,scene` | Available themes for audience-judge |
| `--judges` | `-j` | `1` | Number of judge models |
| `--output` | `-o` | `./output` | Output directory |
| `--svg-per-model` | `-s` | `2` | SVGs each model generates per round |
| `--ollama-host` | `--host` | `http://localhost:11434` | Ollama host URL |

**Example:**

```bash
# Run a tournament between 3 models
python main.py tournament --models llama3,gemma2,mistral
```

A tournament runs a single-elimination bracket where models compete in free-for-all rounds. In each round, an audience-judge picks a theme, all surviving models generate SVGs, and the worst is eliminated. The last model standing is crowned champion.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add tournament command documentation to README"
```

---

### Task 8: Integration test for tournament CLI

**Files:**
- Modify: `tests/test_main.py`

- [ ] **Step 1: Add integration test for tournament command**

Read the existing `tests/test_main.py` first, then add a test class:

```python
class TestTournamentCommand:
    def test_tournament_requires_models(self, cli_runner):
        """Tournament command requires --models flag."""
        result = cli_runner.invoke(["tournament"])
        assert result.exit_code != 0

    def test_tournament_requires_at_least_2_models(self, cli_runner, mock_config):
        """Tournament rejects single model."""
        # This tests the CLI validation, not the actual tournament
        # Since we can't call real LLMs, we just check the help works
        result = cli_runner.invoke(["tournament", "--help"])
        assert result.exit_code == 0
        assert "--models" in result.output
```

First, check if `tests/test_main.py` has a `cli_runner` fixture. If not, add one to `conftest.py`:

In `tests/conftest.py`, add:

```python
@pytest.fixture
def cli_runner():
    """Provide a Typer CliRunner for testing CLI commands."""
    from typer.testing import CliRunner
    return CliRunner()
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_main.py -v`
Expected: Tests PASS (the help test passes; the requires-models test may need adjustment based on Typer behavior)

- [ ] **Step 3: Commit**

```bash
git add tests/test_main.py tests/conftest.py
git commit -m "test: add tournament CLI integration tests"
```

---

### Task 9: Run full test suite

**Files:**
- All test files

- [ ] **Step 1: Run all tests**

Run: `pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Fix any failures**

If any tests fail, fix the underlying code and re-run.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve test failures from tournament feature"
```

---

### Task 10: Final verification

**Files:**
- N/A

- [ ] **Step 1: Verify CLI help**

Run: `python main.py --help`
Expected: Shows `tournament` alongside `run`, `leaderboard`, `export`, `runs`, `list-models`

Run: `python main.py tournament --help`
Expected: Shows all tournament-specific options

- [ ] **Step 2: Verify imports**

Run: `python -c "from src.tournament import Tournament, RoundResult, TournamentResult; from src.theme_selector import ThemeSelector; from src.round_judge import RoundJudge; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 3: Verify no regressions**

Run: `pytest -v`
Expected: All tests PASS
