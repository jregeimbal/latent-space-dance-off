"""
Benchmark recorder module for latent-space-dance-off.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SVGResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    model_name: str
    theme: str
    svg_code: str
    svg_path: Optional[str] = None
    duration_ms: float = 0
    tokens_used: Optional[int] = None
    status: str = "success"
    error_message: Optional[str] = None
    generation_prompt: Optional[str] = None
    pass_number: int = 1

    # Dynamically set by BenchmarkManager.record_generation()
    benchmark_record: Optional["BenchmarkRecord"] = Field(default=None, exclude=True)


class BenchmarkRecord(BaseModel):
    run_id: str
    model_name: str
    theme: str
    duration_ms: float
    tokens: Optional[int] = None
    
    @property
    def tokens_per_second(self):
        if self.duration_ms > 0 and self.tokens is not None:
            return self.tokens / (self.duration_ms / 1000.0)
        return 0.0


class RunData(BaseModel):
    run_id: str
    timestamp: str
    svgs: List[SVGResult]
    benchmarks: List[BenchmarkRecord]
    model_list: List[str]
    themes: List[str]
    judgments: List = []


class BenchmarkManager:
    def __init__(self, config):
        self.config = config
        self.output_dir = Path(config.OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._current_run_dir = None
    
    def generate_run_id(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
    
    def _ensure_run_dir(self, run_id: str) -> Path:
        """Create and return the run directory: output/benchmarks/{run_id}/"""
        run_dir = self.config.benchmarks_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "assets").mkdir(parents=True, exist_ok=True)
        self._current_run_dir = run_dir
        return run_dir
    
    def calculate_tokens_per_second(self, tokens, duration_ms):
        if duration_ms > 0:
            return tokens / (duration_ms / 1000.0)
        return 0.0
    
    def record_generation(self, svg_result, run_id):
        benchmark_record = BenchmarkRecord(
            run_id=run_id,
            model_name=svg_result.model_name,
            theme=svg_result.theme,
            duration_ms=svg_result.duration_ms,
            tokens=svg_result.tokens_used
        )
        svg_result.benchmark_record = benchmark_record
        return benchmark_record
    
    def save_run_data(self, run_data):
        run_dir = self._ensure_run_dir(run_data.run_id)
        filepath = run_dir / "benchmark.json"
        json_data = {
            "run_id": run_data.run_id,
            "timestamp": run_data.timestamp,
            "svgs": [{"model_name": s.model_name, "theme": s.theme, 
                      "svg_code": s.svg_code, "svg_path": s.svg_path,
                      "generation_prompt": s.generation_prompt,
                      "pass_number": s.pass_number}
                      for s in run_data.svgs],
            "benchmarks": [{"run_id": b.run_id, "model_name": b.model_name,
                            "theme": b.theme, "duration_ms": b.duration_ms,
                            "tokens": b.tokens} for b in run_data.benchmarks],
            "model_list": run_data.model_list,
            "themes": run_data.themes
        }
        # Convert judgments to list of dicts
        judgments_list = []
        for j in getattr(run_data, 'judgments', []):
             # Handle both old format (individual scores) and new format (scores dict)
            scores_dict = j.scores if hasattr(j, 'scores') and j.scores else {
                 "creativity": j.creativity_score if hasattr(j, 'creativity_score') else None,
                 "aesthetics": j.aesthetics_score if hasattr(j, 'aesthetics_score') else None,
                 "complexity": j.complexity_score if hasattr(j, 'complexity_score') else None
             }
            
            judgments_list.append({
                 "svg_id": j.svg_id,
                 "judged_by": j.judged_by,
                 "scores": scores_dict,
                 "total_score": j.total_score,
                 "reason": j.reason,
                 "rank": j.rank,
                 "winner_svg": j.winner_svg,
                 "criteria_used": getattr(j, 'criteria_used', ["creativity", "aesthetics", "complexity"]),
                 "judge_prompt": getattr(j, 'judge_prompt', None)
              })
        json_data["judgments"] = judgments_list

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        return run_data.run_id
    
    def load_run_data(self, run_id):
        run_dir = self.config.benchmarks_dir / run_id
        filepath = run_dir / "benchmark.json"
        if not filepath.exists():
            raise FileNotFoundError(f"No benchmark data found for run_id: {run_id}")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            svgs = [SVGResult(model_name=s["model_name"], theme=s["theme"],
                              svg_code=s["svg_code"], svg_path=s["svg_path"],
                              generation_prompt=s.get("generation_prompt"),
                              pass_number=s.get("pass_number", 1))
                    for s in data.get("svgs", [])]
        benchmarks = [BenchmarkRecord(run_id=b["run_id"], model_name=b["model_name"],
                                      theme=b["theme"], duration_ms=b["duration_ms"],
                                      tokens=b.get("tokens"))
                     for b in data.get("benchmarks", [])]
        # Load judgments
        from src.svg_judge import Judgment
        judgments = []
        for j in data.get("judgments", []):
            # Handle both old format (individual scores) and new format (scores dict)
            scores = {}
            if "scores" in j:
                # New format with dynamic scores
                scores = j.get("scores", {})
            else:
                # Old format with individual scores
                scores = {
                    "creativity": j.get("creativity_score"),
                    "aesthetics": j.get("aesthetics_score"),
                    "complexity": j.get("complexity_score")
                }
            
            judgments.append(Judgment(
                svg_id=j["svg_id"],
                svg_model_name=j.get("svg_model_name", "unknown"),
                judged_by=j["judged_by"],
                scores=scores,
                total_score=j.get("total_score"),
                reason=j.get("reason"),
                rank=j.get("rank"),
                winner_svg=j.get("winner_svg"),
                criteria_used=j.get("criteria_used", ["creativity", "aesthetics", "complexity"]),
                judge_prompt=j.get("judge_prompt")
             ))
        return RunData(run_id=data["run_id"], timestamp=data["timestamp"],
                      svgs=svgs, benchmarks=benchmarks,
                      model_list=data["model_list"], themes=data["themes"])
    
    def get_latest_run_id(self):
        try:
             # Find directories (new structure) first, then fall back to flat JSON files
            run_dirs = [d for d in self.config.benchmarks_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
            if run_dirs:
                sorted_dirs = sorted(run_dirs, key=lambda d: d.name, reverse=True)
                return sorted_dirs[0].name
             # Fallback: look for flat benchmark JSON files
            files = list(self.config.benchmarks_dir.glob("*.json"))
            if not files:
                return None
            sorted_files = sorted(files, key=lambda f: f.stem, reverse=True)
            return sorted_files[0].stem
        except:
            return None
    
    def get_all_runs(self):
        runs = []
        try:
             # New structure: directories containing benchmark.json
            for run_dir in self.config.benchmarks_dir.iterdir():
                if run_dir.is_dir() and not run_dir.name.startswith('.'):
                    benchmark_file = run_dir / "benchmark.json"
                    if benchmark_file.exists():
                        try:
                            runs.append(self.load_run_data(run_dir.name))
                        except:
                            continue
            # Fallback: flat benchmark JSON files
            for filepath in self.output_dir.glob("*.json"):
                if filepath.is_file():
                    try:
                        runs.append(self.load_run_data(filepath.stem))
                    except:
                        continue
        except:
            pass 
        return sorted(runs, key=lambda r: r.run_id)
    def start_timer(self):
        return time.time()
    
    def stop_timer(self, start_time):
        return (time.time() - start_time) * 1000


_default_manager = None

def get_benchmark_manager(config):
    global _default_manager
    if _default_manager is None:
        _default_manager = BenchmarkManager(config)
    return _default_manager
