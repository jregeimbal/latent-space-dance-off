"""
Ranking System for latent-space-dance-off
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# Import Config from src.config


@dataclass
class Judgment:
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


@dataclass
class RunData:
    run_id: str
    timestamp: str
    models: List[str]
    themes: List[str]
    generations: List[dict] = field(default_factory=list)
    judgments: List[Judgment] = field(default_factory=list)
    output_dir: str = "data"


@dataclass
class SVGScore:
    svg_id: str
    model_name: str
    creativity_score: float = 0.0
    aesthetics_score: float = 0.0
    complexity_score: float = 0.0
    total_score: float = 0.0
    judgment_count: int = 0
    scores: Optional[dict] = None    # Dynamic scores for custom criteria
    
    def __post_init__(self):
        if self.scores is None:
            self.scores = {}
    
    def get_score(self, criterion: str) -> float:
        return self.scores.get(criterion, 0.0) if self.scores else 0.0


class LeaderboardEntry(BaseModel):
    rank: int = 0
    svg_id: str = ""
    model_name: str = ""
    total_score: float = 0.0
    judgment_count: int = 0
    svg_files: List[str] = []
    scores: Dict[str, float] = Field(default_factory=dict)

    def get_score(self, criterion: str) -> float:
        return self.scores.get(criterion, 0.0)
    
    @classmethod
    def from_svg_score(cls, svg_score, rank, svg_files=None):
        scores = dict(svg_score.scores) if svg_score.scores else {}
        return cls(
            rank=rank,
            svg_id=svg_score.svg_id,
            model_name=svg_score.model_name,
            total_score=svg_score.total_score,
            judgment_count=svg_score.judgment_count,
            svg_files=svg_files or [],
            scores=scores
        )


class Leaderboard(BaseModel):
    run_id: str
    timestamp: str
    total_judgments: int
    total_models: int
    rankings: List[LeaderboardEntry]
    meta: Dict = Field(default_factory=dict)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class RankingSystem:
    def __init__(self, config):
        self.config = config
        self._ensure_output_dirs()
    
    def _ensure_output_dirs(self):
        self.config.leaderboards_dir.mkdir(parents=True, exist_ok=True)
        self.config.svgs_dir.mkdir(parents=True, exist_ok=True)
    
    def aggregate_all_judgments(self, run_data, judgments):
        # Ensure all judgments are Judgment dataclasses to preserve judge_prompt during reconstruction if needed
        for i in range(len(judgments)):
            if not isinstance(judgments[i], Judgment):
                j = judgments[i]
                if isinstance(j, dict):
                    scores_dict = j.get("scores", {})
                    judgments[i] = Judgment(
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
                    # Assume it's the Pydantic model from src.svg_judge
                    p_scores = getattr(j, "scores", {})
                    judgments[i] = Judgment(
                        svg_id=getattr(j, "svg_id", ""),
                        svg_model_name=getattr(j, "svg_model_name", "unknown"),
                        judged_by=getattr(j, "judged_by", "unknown"),
                        creativity_score=getattr(j, "creativity_score", p_scores.get("creativity")),
                        aesthetics_score=getattr(j, "aesthetics_score", p_scores.get("aesthetics")),
                        complexity_score=getattr(j, "complexity_score", p_scores.get("complexity")),
                        reason=getattr(j, "reason", None),
                        rank=getattr(j, "rank", None),
                        winner_svg=getattr(j, "winner_svg", None),
                        judge_prompt=getattr(j, "judge_prompt", None),
                        scores=p_scores
                    )

        # Use run_data.themes and run_data.models from RunData
        scores = {}
        
        for judgment in judgments:
            svg_id = judgment.svg_id
            model_name = judgment.svg_model_name
            
            resolved_model = None
            for known_model in run_data.model_list:
                if svg_id.startswith(f"{known_model}_"):
                    resolved_model = known_model
                    break
            
            if resolved_model is None:
                resolved_model = model_name
            
            if resolved_model not in scores:
                scores[resolved_model] = SVGScore(svg_id=resolved_model, model_name=resolved_model, 
                                                  scores={}, total_score=0.0, judgment_count=0)
            
            svg_score = scores[resolved_model]
            
            if hasattr(judgment, 'scores') and judgment.scores:
                for criterion in self.config.judging_criteria:
                    val = judgment.scores.get(criterion)
                    if val is not None:
                        if criterion not in svg_score.scores:
                            svg_score.scores[criterion] = 0.0
                        svg_score.scores[criterion] += val
            else:
                if judgment.creativity_score is not None:
                    if 'creativity' not in svg_score.scores:
                        svg_score.scores['creativity'] = 0.0
                    svg_score.scores['creativity'] += judgment.creativity_score
                if judgment.aesthetics_score is not None:
                    if 'aesthetics' not in svg_score.scores:
                        svg_score.scores['aesthetics'] = 0.0
                    svg_score.scores['aesthetics'] += judgment.aesthetics_score
                if judgment.complexity_score is not None:
                    if 'complexity' not in svg_score.scores:
                        svg_score.scores['complexity'] = 0.0
                    svg_score.scores['complexity'] += judgment.complexity_score
            svg_score.judgment_count += 1
        
        for svg_id in scores:
            svg_score = scores[svg_id]
            if svg_score.judgment_count > 0:
                for criterion in svg_score.scores:
                    svg_score.scores[criterion] /= svg_score.judgment_count
                
                total = 0.0
                found_any = False
                for criterion in self.config.judging_criteria:
                    val = svg_score.scores.get(criterion)
                    if val is not None:
                        total += val
                        found_any = True
                if found_any:
                    total = total / len([c for c in self.config.judging_criteria if c in svg_score.scores])
                
                svg_score.total_score = total
        return scores
    
    def calculate_final_ranking(self, model_scores):
        sorted_models = sorted(model_scores.values(), key=lambda s: s.total_score, reverse=True)
        rankings = []
        for rank, model_score in enumerate(sorted_models, start=1):
            entry = LeaderboardEntry.from_svg_score(model_score, rank, [])
            rankings.append(entry)
        return rankings
    
    def generate_leaderboard(self, run_data):
        model_scores = self.aggregate_all_judgments(run_data, run_data.judgments)
        rankings = self.calculate_final_ranking(model_scores)
        for entry in rankings:
            svg_files = [s.svg_path for s in run_data.svgs 
                        if s.model_name == entry.model_name and s.svg_path]
            entry.svg_files = svg_files
        return Leaderboard(
            run_id=run_data.run_id,
            timestamp=run_data.timestamp,
            total_judgments=len(run_data.judgments),
            total_models=len(run_data.model_list),
            rankings=rankings,
            meta={'themes': run_data.themes}
        )
    
    def save_leaderboard(self, leaderboard, run_dir: Optional[Path] = None):
        if run_dir is not None:
            save_dir = run_dir
        else:
            (self.config.leaderboards_dir).mkdir(parents=True, exist_ok=True)
            save_dir = self.config.leaderboards_dir
        filepath = save_dir / f"{leaderboard.run_id}-leaderboard.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(leaderboard.model_dump(), f, indent=2)
        return str(filepath)
    
    def load_leaderboard(self, run_id):
        filepath = self.config.leaderboards_dir / f"{run_id}-leaderboard.json"
        if not filepath.exists():
            raise FileNotFoundError(f"Leaderboard not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Leaderboard(**data)
    
    def export_to_csv(self, leaderboard, filepath=None):
        if filepath is None:
            filepath = self.config.leaderboards_dir / f"{leaderboard.run_id}.csv"
        (Path(filepath)).parent.mkdir(parents=True, exist_ok=True)
        headers = ['rank', 'model', 'creativity', 'aesthetics', 'complexity', 'total']
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(','.join(headers) + chr(10))
            for entry in leaderboard.rankings:
                row = [str(entry.rank), entry.svg_id,
                       f"{entry.get_score('creativity'):.2f}", f"{entry.get_score('aesthetics'):.2f}",
                       f"{entry.get_score('complexity'):.2f}", f"{entry.total_score:.2f}"]
                f.write(','.join(row) + chr(10))
        return str(filepath)
    
    def create_run_id(self):
        return datetime.now().isoformat()
    
    def get_top_models(self, leaderboard, n=5):
        return leaderboard.rankings[:n]
    
    def get_svg_stats(self, leaderboard, svg_id):
        for entry in leaderboard.rankings:
            if entry.svg_id == svg_id:
                return {'rank': entry.rank, 'creativity': entry.get_score('creativity'),
                         'aesthetics': entry.get_score('aesthetics'), 'complexity': entry.get_score('complexity'),
                         'total': entry.total_score, 'judgments_received': entry.judgment_count,
                         'svg_files': entry.svg_files}
        return None
