"""Shared test fixtures for the latent-space-dance-off test suite."""

import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def mock_config():
    """Provide a minimal Config-like mock object for tests that don't need real env vars."""
    config = Mock()
    config.OLLAMA_HOST = "http://localhost:11434"
    config.LLM_CLIENT = "ollama"
    config.LLM_HOST = ""
    config.NUM_JUDGES = 3
    config.OUTPUT_DIR = "./output"
    config.MODEL_LIST = ""
    config.NUM_THEMES = 3
    config.DEFAULT_CREATIVITY_WEIGHT = 0.33
    config.DEFAULT_AESTHETICS_WEIGHT = 0.33
    config.DEFAULT_COMPLEXITY_WEIGHT = 0.34
    config.JUDGING_CRITERIA = "creativity,aesthetics,complexity"
    config.DISABLE_JUDGING = False
    config.NUM_PASSES = 1
    config.models = ["model_a", "model_b"]
    config.judging_criteria = ["creativity", "aesthetics", "complexity"]
    config.svgs_dir = Path("./output/svgs")
    config.benchmarks_dir = Path("./output/benchmarks")
    config.leaderboards_dir = Path("./output/leaderboards")
    return config


@pytest.fixture
def temp_output_dir(tmp_path):
    """Provide a temporary output directory structure."""
    svgs_dir = tmp_path / "svgs"
    benchmarks_dir = tmp_path / "benchmarks"
    leaderboards_dir = tmp_path / "leaderboards"
    svgs_dir.mkdir(parents=True, exist_ok=True)
    benchmarks_dir.mkdir(parents=True, exist_ok=True)
    leaderboards_dir.mkdir(parents=True, exist_ok=True)

    config = Mock()
    config.OLLAMA_HOST = "http://localhost:11434"
    config.LLM_CLIENT = "ollama"
    config.LLM_HOST = ""
    config.NUM_JUDGES = 3
    config.OUTPUT_DIR = str(tmp_path)
    config.MODEL_LIST = ""
    config.NUM_THEMES = 3
    config.DEFAULT_CREATIVITY_WEIGHT = 0.33
    config.DEFAULT_AESTHETICS_WEIGHT = 0.33
    config.DEFAULT_COMPLEXITY_WEIGHT = 0.34
    config.JUDGING_CRITERIA = "creativity,aesthetics,complexity"
    config.DISABLE_JUDGING = False
    config.NUM_PASSES = 1
    config.models = ["model_a", "model_b"]
    config.judging_criteria = ["creativity", "aesthetics", "complexity"]
    config.svgs_dir = svgs_dir
    config.benchmarks_dir = benchmarks_dir
    config.leaderboards_dir = leaderboards_dir
    return config, tmp_path


@pytest.fixture
def fake_svg():
    """Provide a minimal, valid SVG string for tests."""
    return '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'


@pytest.fixture
def sample_run_data(temp_output_dir):
    """Provide a RunData object populated with sample data.

    Returns (run_data, config, tmp_path) tuple.
    """
    config, tmp_path = temp_output_dir
    from src.benchmark import RunData, SVGResult

    run_data = RunData(
        run_id="test-run-001",
        timestamp="2024-01-01T12:00:00",
        model_list=["model_a", "model_b"],
        themes=["abstract", "landscape"],
        svgs=[
            SVGResult(
                model_name="model_a",
                theme="abstract",
                svg_code='<svg width="100" height="100"><circle cx="50" cy="50" r="40"/></svg>',
                svg_path=str(tmp_path / "model_a_abstract.svg"),
                duration_ms=1500,
                tokens_used=200,
                status="success",
                generation_prompt="Generate abstract svg",
            ),
            SVGResult(
                model_name="model_b",
                theme="landscape",
                svg_code='<svg width="100" height="100"><rect x="10" y="10" width="80" height="80"/></svg>',
                svg_path=str(tmp_path / "model_b_landscape.svg"),
                duration_ms=2000,
                tokens_used=300,
                status="success",
                generation_prompt="Generate landscape svg",
            ),
        ],
        benchmarks=[],
    )
    return run_data, config, tmp_path


def _run_async(coro):
    """Helper to run an async coroutine in a test without pytest-asyncio."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        asyncio.set_event_loop(None)
        loop.close()


@pytest.fixture
def cli_runner():
    """Provide a Typer CliRunner for testing CLI commands."""
    from typer.testing import CliRunner
    return CliRunner()
