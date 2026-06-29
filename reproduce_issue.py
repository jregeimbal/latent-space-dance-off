from pathlib import Path
from src.benchmark import BenchmarkManager, RunData
from src.ranking import RankingSystem
from src.svg_judge import Judgment as PydanticJudgment

class MockConfig:
    def __init__(self):
        self.OUTPUT_DIR = "/tmp/output"
        self.benchmarks_dir = Path("/tmp/test_benchmarks")
        self.leaderboards_dir = Path("/tmp/test_leaderboards")
        self.svgs_dir = Path("/tmp/test_svgs")
        self.judging_criteria = ["creativity", "aesthetics", "complexity"]

def reproduce():
    config = MockConfig()
    # Create directories
    for d in [config.OUTPUT_DIR, config.benchmarks_dir, config.leaderboards_dir, config.svgs_dir]:
        Path(d).mkdir(parents=True, exist_ok=True)

    BenchmarkManager(config)
    rs = RankingSystem(config)

    run_id = "repro_run"
    judge_prompt = "THE SECRET PROMPT"

    # Create a Pydantic judgment as if it were loaded from JSON (or created during judging)
    p_judgment = PydanticJudgment(
        svg_id="test_svg",
        svg_model_name="test_model",
        judged_by="judge1",
        scores={"creativity": 8.0, "aesthetics": 7.0, "complexity": 9.0},
        total_score=8.0,
        reason="Great!",
        rank=1,
        winner_svg=None,
        criteria_used=["creativity", "aesthetics", "complexity"],
        judge_prompt=judge_prompt
    )

    # Create RunData with the Pydantic judgment
    run_data = RunData(
        run_id=run_id,
        timestamp="2026-01-01T00:00:00",
        svgs=[],
        benchmarks=[],
        model_list=["test_model"],
        themes=["theme1"],
        judgments=[p_judgment]
    )

    print(f"Before aggregation, judge_prompt in p_judgment: {p_judgment.judge_prompt}")
    print(f"Before aggregation, type of judgments[0]: {type(run_data.judgments[0])}")

    # The key step described in the issue
    rs.aggregate_all_judgments(run_data, run_data.judgments)

    print(f"After aggregation, type of judgments[0]: {type(run_data.judgments[0])}")
    
    if len(run_data.judgments) > 0:
        new_judgment = run_data.judgments[0]
        print(f"After aggregation, judge_prompt: '{new_judgment.judge_prompt}'")
        if new_judgment.judge_prompt == judge_prompt:
            print("SUCCESS: judge_prompt preserved!")
        else:
            print("FAILURE: judge_prompt LOST!")
    else:
        print("FAILURE: No judgments found!")

if __name__ == "__main__":
    reproduce()
