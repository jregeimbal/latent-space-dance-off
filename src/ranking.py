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


from src.svg_judge import Judgment


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
    total_score: float = 0.0
    judgment_count: int = 0
    scores: Optional[dict] = None

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
            model_name = judgment.svg_model_name
            
            # Extract model name from svg_id (format: model_name_theme_passN)
            # The svg_id format is: {model_name}_{theme}_pass{pass_number}
            # We need to identify the model from the svg_id
            # Since model names can contain underscores, we match against known models
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

            matched_criteria = []
            for criterion in self.config.judging_criteria:
                score = judgment.scores.get(criterion)
                if score is not None:
                    svg_score.scores[criterion] = svg_score.scores.get(criterion, 0.0) + score
                    matched_criteria.append(criterion)

            if not matched_criteria:
                import logging
                logging.getLogger(__name__).warning(f"No criteria matched for judgment {judgment.svg_id} by {judgment.judged_by}")
                continue

            svg_score.judgment_count += 1
        
        for svg_id in scores:
            svg_score = scores[svg_id]
            if svg_score.judgment_count > 0:
                  # Average the scores
                for criterion in svg_score.scores:
                    svg_score.scores[criterion] /= svg_score.judgment_count
                
                 # Calculate total as simple average of criterion scores
                total = 0.0
                for criterion in self.config.judging_criteria:
                    total += svg_score.scores.get(criterion, 0.0)
                if len(svg_score.scores) > 0:
                    total = total / len(svg_score.scores)
                
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
            # Collect all SVG files for this model across all passes
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
