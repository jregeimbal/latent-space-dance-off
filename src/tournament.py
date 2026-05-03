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
        if not model_clients:
            raise ValueError("At least one model client is required")
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
