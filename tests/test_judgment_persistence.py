import pytest
import json
from pathlib import Path
from src.benchmark import BenchmarkManager
from src.ranking import RankingSystem, Judgment as DataclassJudgment

class MockConfig:
    def __init__(self, base_dir: Path):
        self.OUTPUT_DIR = base_dir / "output"
        self.benchmarks_dir = base_dir / "test_benchmarks"
        self.leaderboards_dir = base_dir / "test_leaderboards"
        self.svgs_dir = base_dir / "test_svgs"
        self.judging_criteria = ["creativity", "aesthetics", "complexity"]

@pytest.fixture
def config(tmp_path):
    cfg = MockConfig(tmp_path)
    cfg.benchmarks_dir.mkdir(parents=True, exist_ok=True)
    cfg.leaderboards_dir.mkdir(parents=True, exist_ok=True)
    cfg.svgs_dir.mkdir(parents=True, exist_ok=True)
    return cfg

@pytest.fixture
def benchmark_manager(config):
    return BenchmarkManager(config)

@pytest.fixture
def ranking_system(config):
    return RankingSystem(config)

def test_judgment_persistence(benchmark_manager, ranking_system, config):
    """AC1: Loaded Judgment objects preserve the judge_prompt from benchmark.json."""
    run_id = "persistence_test"
    run_dir = config.benchmarks_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    judge_prompt_text = "This is a test judge prompt."
    
    # Simulate benchmark JSON containing judgments with the judge_prompt field
    data = {
        "run_id": run_id,
        "timestamp": "2026-01-01T00:00:00",
        "svgs": [],
        "benchmarks": [],
        "model_list": ["m1"],
        "themes": ["t1"],
        "judgments": [
            {
                "svg_id": "m1_t1_p1",
                "judged_by": "judge1",
                "scores": {"creativity": 8.0, "aesthetics": 7.0, "complexity": 9.0},
                "total_score": 8.0,
                "reason": "Great work!",
                "rank": 1,
                "winner_svg": None,
                "judge_prompt": judge_prompt_text
            }
        ]
    }

    with open(run_dir / "benchmark.json", "w") as f:
        json.dump(data, f)

    # Load the data
    run_data = benchmark_manager.load_run_data(run_id)
    
    # Rebuild judgments (this is where it's supposed to be lost)
    ranking_system.aggregate_all_judgments(run_data, run_data.judgments)

    # Verify persistence
    for judgment in run_data.judgments:
        assert isinstance(judgment, DataclassJudgment)
        assert judgment.judge_prompt == judge_prompt_text

def test_backward_compatibility(benchmark_manager, ranking_system, config):
    """AC2: Backward compatibility: Loading JSON without judge_prompt does not fail and sets the field to None."""
    run_id = "legacy_test"
    run_dir = config.benchmarks_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Legacy data without judge_prompt
    data = {
        "run_id": run_id,
        "timestamp": "2026-01-01T00:00:00",
        "svgs": [],
        "benchmarks": [],
        "model_list": ["m1"],
        "themes": ["t1"],
        "judgments": [
            {
                "svg_id": "m1_t1_p1",
                "judged_by": "judge1",
                "scores": {"creativity": 5.0, "aesthetics": 5.0, "complexity": 5.0},
                "total_score": 5.0,
                "reason": "Ok",
                "rank": 2,
                "winner_svg": None
                # judge_prompt is missing here
            }
        ]
    }

    with open(run_dir / "benchmark.json", "w") as f:
        json.dump(data, f)

    # Load the data
    run_data = benchmark_manager.load_run_data(run_id)
    
    # Rebuild judgments
    ranking_system.aggregate_all_judgments(run_data, run_data.judgments)

    # Verify field is None and it didn't crash
    for judgment in run_data.judgments:
        assert isinstance(judgment, DataclassJudgment)
        assert judgment.judge_prompt is None
