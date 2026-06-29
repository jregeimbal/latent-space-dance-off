import asyncio
import json
from pathlib import Path
import sys

# Add root to path
sys.path.append('/opt/data/home/.zeroshot/worktrees/blazing-storm-57')

from src.benchmark import BenchmarkManager
from src.ranking import RankingSystem

class MockConfig:
    def __init__(self):
        self.OUTPUT_DIR = "/tmp/output"
        self.benchmarks_dir = Path("/tmp/benchmarks")
        self.leaderboards_dir = Path("/tmp/leaderboards")
        self.svgs_dir = Path("/tmp/svgs")
        self.judging_criteria = ["creativity", "aesthetics", "complexity"]

async def reproduce():
    # Setup environment
    config = MockConfig()
    config.benchmarks_dir.mkdir(parents=True, exist_ok=True)
    config.leaderboards_dir.mkdir(parents=True, exist_ok=True)
    config.svgs_dir.mkdir(parents=True, exist_ok=True)

    bm = BenchmarkManager(config)
    rs = RankingSystem(config)

    run_id = "test_repro"
    run_dir = config.benchmarks_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create a dummy benchmark.json with judge_prompt
    judge_prompt_val = "THE SECRET PROMPT"
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
                "reason": "ok",
                "rank": 1,
                "winner_svg": None,
                "judge_prompt": judge_prompt_val
            }
        ]
    }

    with open(run_dir / "benchmark.json", "w") as f:
        json.dump(data, f)

    # 2. Load using BenchmarkManager (which uses Pydantic Judgment from svg_judge)
    print("Loading run data...")
    run_data = bm.load_run_data(run_id)
    
    # Verify it loaded correctly initially
    first_judgment = run_data.judgments[0]
    print(f"Initial judge_prompt: '{first_judgment.judge_prompt}'")

    # 3. Run the aggregation (which should convert to dataclass Judgment from ranking)
    print("Running aggregate_all_judgments...")
    rs.aggregate_all_judgments(run_data, run_data.judgments)

    # 4. Check if it's preserved
    new_judgment = run_data.judgments[0]
    print(f"Post-aggregation judge_prompt: '{new_judgment.judge_prompt}'")

    if new_judgment.judge_prompt == judge_prompt_val:
        print("SUCCESS: judge_prompt preserved.")
    else:
        print("FAILURE: judge_prompt LOST!")

if __name__ == "__main__":
    asyncio.run(reproduce())
