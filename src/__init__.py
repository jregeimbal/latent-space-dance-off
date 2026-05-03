"""Latent Space Dance Off - An LLM benchmarking application."""

__version__ = "0.1.0"
__author__ = "Jon Regeimbal"

from src.config import Config, get_config
from src.llm_client import (
    BaseLLMClient,
    LLMChunk,
    OllamaClient,
    LMStudioClient,
    create_llm_client,
)
from src.model_manager import ModelManager, get_model_manager, ModelInfo
from src.svg_generator import SVGGenerator, SVGResult
from src.svg_judge import SVGJudge, Judgment, Comparison
from src.ranking import RankingSystem, Leaderboard, LeaderboardEntry
from src.benchmark import BenchmarkManager, RunData, SVGResult as BenchmarkSVGResult

__all__ = [
    "Config",
    "get_config",
    "BaseLLMClient",
    "LLMChunk",
    "OllamaClient",
    "LMStudioClient",
    "create_llm_client",
    "ModelManager",
    "get_model_manager",
    "ModelInfo",
    "SVGGenerator",
    "SVGResult",
    "SVGJudge",
    "Judgment",
    "Comparison",
    "RankingSystem",
    "Leaderboard",
    "LeaderboardEntry",
    "BenchmarkManager",
    "RunData",
    "BenchmarkSVGResult",
]
