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
