from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

# Mocking the environment based on the codebase
@dataclass
class JudgmentDataclass:
    svg_id: str
    svg_model_name: str
    judged_by: str
    creativity_score: Optional[float] = None
    aesthetics_score: Optional[float] = None
    complexity_score: Optional[float] = None
    reason: Optional[str] = None
    rank: Optional[int] = None
    winner_svg: Optional[str] = None
    judge_prompt: Optional[str] = None
    scores: Dict[str, float] = field(default_factory=dict)

class SVGResult(BaseModel):
    model_name: str
    theme: str
    svg_code: str
    svg_path: Optional[str] = None
    generation_prompt: Optional[str] = None
    pass_number: int = 1

class RunData(BaseModel):
    run_id: str
    timestamp: str
    svgs: List[SVGResult]
    benchmarks: List = []
    model_list: List[str]
    themes: List[str]
    judgments: List = []

class JudgmentPydantic(BaseModel):
    svg_id: str
    svg_model_name: str
    judged_by: str
    scores: Dict[str, Optional[float]] = Field(default_factory=dict)
    total_score: Optional[float] = None
    reason: Optional[str] = None
    rank: Optional[int] = None
    winner_svg: Optional[str] = None
    criteria_used: List[str] = Field(default_factory=lambda: ["creativity", "aesthetics", "complexity"])
    judge_prompt: Optional[str] = None

class Config:
    def __init__(self):
        self.judging_criteria = ["creativity", "aesthetics", "complexity"]
        # Mocking some paths that might be needed
        class MockPath:
            def mkdir(self, parents=True, exist_ok=True): pass
            def exists(self): return True
        self.leaderboards_dir = Path("/tmp/leaderboards")
        self.svgs_dir = Path("/tmp/svgs")

@dataclass
class SVGScore:
    svg_id: str
    model_name: str
    creativity_score: float = 0.0
    aesthetics_score: float = 0.0
    complexity_score: float = 0.0
    total_score: float = 0.0
    judgment_count: int = 0
    scores: Optional[dict] = None
    def __post_init__(self):
        if self.scores is None:
            self.scores = {}

class RankingSystem:
    def __init__(self, config):
        self.config = config
    
    def aggregate_all_judgments(self, run_data, judgments):
        # Use JudgmentDataclass instead of the one from ranking.py for this repro
        for i in range(len(judgments)):
            if not isinstance(judgments[i], JudgmentDataclass):
                j = judgments[i]
                if isinstance(j, dict):
                    scores_dict = j.get("scores", {})
                    judgments[i] = JudgmentDataclass(
                        svg_id=j["svg_id"],
                        svg_model_name=j.get("svg_model_name", "unknown"),
                        judged_by=j["judged_by"],
                        creativity_score=j.get("creativity_score") or scores_dict.get("creativity"),
                        aesthetics_score=j.get("aesthetics_score") or scores_dict.get("aesthetics"),
                        complexity_score=j.get("complexity_score") or scores_dict.get("complexity"),
                        reason=j.get("reason"),
                        rank=j.get("rank"),
                        winner_svg=j.get("winner_svg"),
                        judge_prompt=j.get("judge_prompt"),
                        scores=scores_dict
                    )
                else:
                    p_scores = getattr(j, "scores", {})
                    judgments[i] = JudgmentDataclass(
                        svg_id=getattr(j, "svg_id"),
                        svg_model_name=getattr(j, "svg_model_name"),
                        judged_by=getattr(j, "judged_by"),
                        creativity_score=getattr(j, "creativity_score", p_scores.get("creativity")),
                        aesthetics_score=getattr(j, "aesthetics_score", p_scores.get("aesthetics")),
                        complexity_score=getattr(j, "complexity_score", p_scores.get("complexity")),
                        reason=getattr(j, "reason"),
                        rank=getattr(j, "rank"),
                        winner_svg=getattr(j, "winner_svg"),
                        judge_prompt=getattr(j, "judge_prompt", None),
                        scores=p_scores
                    )
        return {}

def run_repro():
    config = Config()
    rs = RankingSystem(config)
    
    # 1. Simulate JSON data
    json_data = {
        "run_id": "test_run",
        "timestamp": "2026-01-01T00:00:00",
        "svgs": [],
        "benchmarks": [],
        "model_list": ["model1"],
        "themes": ["theme1"],
        "judgments": [
            {
                "svg_id": "model1_theme1_pass1",
                "judged_by": "judge1",
                "scores": {"creativity": 8.0, "aesthetics": 7.0, "complexity": 9.0},
                "total_score": 8.0,
                "reason": "Good",
                "rank": 1,
                "winner_svg": None,
                "criteria_used": ["creativity", "aesthetics", "complexity"],
                "judge_prompt": "PROMPT_1"
            }
        ]
    }

    # 2. Simulate loading from JSON (as BenchmarkManager does)
    from src.benchmark import RunData as BenchmarkRunData
    # Note: We are using the actual implementation if possible, but for repro we mock
    judgments = []
    for j in json_data["judgments"]:
        judgments.append(JudgmentPydantic(
            svg_id=j["svg_id"],
            svg_model_name="unknown", # not in JSON directly at top level, but in svg_id
            judged_by=j["judged_by"],
            scores=j["scores"],
            total_score=j["total_score"],
            reason=j["reason"],
            rank=j["rank"],
            winner_svg=j["winner_svg"],
            criteria_used=j["criteria_used"],
            judge_prompt=j["judge_prompt"]
        ))
    
    run_data = BenchmarkRunData(
        run_id=json_data["run_id"],
        timestamp=json_data["timestamp"],
        svgs=[],
        benchmarks=[],
        model_list=json_data["model_list"],
        themes=json_data["themes"],
        judgments=judgments
    )

    print(f"Before aggregation: {run_data.judgments[0].judge_prompt}")
    rs.aggregate_all_judgments(run_data, run_data.judgments)
    print(f"After aggregation: {run_data.judgments[0].judge_prompt}")

if __name__ == "__main__":
    # We need to make sure src is in path
    import sys
    sys.path.append('.')
    run_repro()
