"""
Ranking System for latent-space-dance-off
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# Import Config from src.config
from src.config import Config


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
    scores: Optional[dict] = None   # Dynamic scores for custom criteria
    
    def __post_init__(self):
        if self.scores is None:
            self.scores = {}


class LeaderboardEntry(BaseModel):
    rank: int
    svg_id: str
    creativity_score: float
    aesthetics_score: float
    complexity_score: float
    total_score: float
    judgment_count: int = 0
    svg_files: List[str] = []
    model_name: str
    
    @classmethod
    def from_svg_score(cls, svg_score, rank, svg_files=None):
        return cls(
            rank=rank,
            svg_id=svg_score.svg_id,
            model_name=svg_score.model_name,
            creativity_score=svg_score.creativity_score,
            aesthetics_score=svg_score.aesthetics_score,
            complexity_score=svg_score.complexity_score,
            total_score=svg_score.total_score,
            judgment_count=svg_score.judgment_count,
            svg_files=svg_files or []
        )


class Leaderboard(BaseModel):
    run_id: str
    timestamp: str
    total_judgments: int
    total_models: int
    rankings: List[LeaderboardEntry]
    meta: Dict = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
class RankingSystem:
    def __init__(self, config):
        self.config = config
        self._ensure_output_dirs()
    
    def _ensure_output_dirs(self):
        self.config.leaderboards_dir.mkdir(parents=True, exist_ok=True)
        self.config.svgs_dir.mkdir(parents=True, exist_ok=True)
    
    def aggregate_all_judgments(self, run_data, judgments):
         # Use run_data.themes and run_data.models from RunData
        scores = {}
        # for model_name in run_data.model_list:
        #     scores[model_name] = ModelScore(
        #         model_name=model_name,
        #         creativity_score=0.0,
        #         aesthetics_score=0.0,
        #         complexity_score=0.0,
        #         total_score=0.0,
        #         judgment_count=0
        #     )
        
        for judgment in judgments:
            svg_id = judgment.svg_id
            if svg_id not in scores:
                scores[svg_id] = SVGScore(svg_id=svg_id, model_name=judgment.svg_model_name, 
                                                  scores={}, total_score=0.0, judgment_count=0)
            
            svg_score = scores[svg_id]
            
               # Handle both old format (individual scores) and new format (scores dict)
            if hasattr(judgment, 'scores') and judgment.scores:
                   # New format with dynamic scores
                for criterion in self.config.judging_criteria:
                    if judgment.scores.get(criterion) is not None:
                        if criterion not in svg_score.scores:
                            svg_score.scores[criterion] = 0.0
                        svg_score.scores[criterion] += judgment.scores[criterion]
            else:
                   # Old format with individual scores
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
                  # Average the scores
                for criterion in svg_score.scores:
                    svg_score.scores[criterion] /= svg_score.judgment_count
                
                  # Calculate total using config weights if available
                total = 0.0
                for criterion in self.config.judging_criteria:
                    weight_key = f'DEFAULT_{criterion.upper()}_WEIGHT'
                    weight = getattr(self.config, weight_key, 1.0 / len(self.config.judging_criteria))
                    total += svg_score.scores.get(criterion, 0.0) * weight
                
                  # If weights don't sum to 1, normalize
                if len(self.config.judging_criteria) > 0:
                    total = total / len(self.config.judging_criteria)
                
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
            entry.svg_files = []
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
                       f"{entry.creativity_score:.2f}", f"{entry.aesthetics_score:.2f}",
                       f"{entry.complexity_score:.2f}", f"{entry.total_score:.2f}"]
                f.write(','.join(row) + chr(10))
        return str(filepath)
    
    def create_run_id(self):
        return datetime.now().isoformat()
    
    def get_top_models(self, leaderboard, n=5):
        return leaderboard.rankings[:n]
    
    def get_svg_stats(self, leaderboard, svg_id):
        for entry in leaderboard.rankings:
            if entry.svg_id == svg_id:
                return {'rank': entry.rank, 'creativity': entry.creativity_score,
                        'aesthetics': entry.aesthetics_score, 'complexity': entry.complexity_score,
                        'total': entry.total_score, 'judgments_received': entry.judgment_count,
                        'svg_files': entry.svg_files}
        return None
