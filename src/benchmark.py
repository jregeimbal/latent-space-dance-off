"""
Benchmark recorder module for latent-space-dance-off.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class SVGResult(BaseModel):
    model_name: str
    theme: str
    svg_code: str
    svg_path: Optional[str] = None
    duration_ms: float = 0
    tokens_used: Optional[int] = None
    status: str = "success"
    error_message: Optional[str] = None


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


class BenchmarkManager:
    def __init__(self, config):
        self.config = config
        self.benchmarks_dir = Path(config.benchmarks_dir)
        self.benchmarks_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_run_id(self):
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")
    
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
        filepath = self.benchmarks_dir / f"{run_data.run_id}.json"
        json_data = {
            "run_id": run_data.run_id,
            "timestamp": run_data.timestamp,
            "svgs": [{"model_name": s.model_name, "theme": s.theme, 
                       "svg_code": s.svg_code, "svg_path": s.svg_path} 
                      for s in run_data.svgs],
            "benchmarks": [{"run_id": b.run_id, "model_name": b.model_name,
                            "theme": b.theme, "duration_ms": b.duration_ms,
                            "tokens": b.tokens} for b in run_data.benchmarks],
            "model_list": run_data.model_list,
            "themes": run_data.themes
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        return run_data.run_id
    
    def load_run_data(self, run_id):
        filepath = self.benchmarks_dir / f"{run_id}.json"
        if not filepath.exists():
            raise FileNotFoundError(f"No benchmark data found for run_id: {run_id}")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        svgs = [SVGResult(model_name=s["model_name"], theme=s["theme"],
                          svg_code=s["svg_code"], svg_path=s["svg_path"])
                for s in data.get("svgs", [])]
        benchmarks = [BenchmarkRecord(run_id=b["run_id"], model_name=b["model_name"],
                                      theme=b["theme"], duration_ms=b["duration_ms"],
                                      tokens=b.get("tokens"))
                     for b in data.get("benchmarks", [])]
        return RunData(run_id=data["run_id"], timestamp=data["timestamp"],
                      svgs=svgs, benchmarks=benchmarks,
                      model_list=data["model_list"], themes=data["themes"])
    
    def get_latest_run_id(self):
        try:
            files = list(self.benchmarks_dir.glob("*.json"))
            if not files:
                return None
            sorted_files = sorted(files, key=lambda f: f.stem, reverse=True)
            return sorted_files[0].stem
        except:
            return None
    
    def get_all_runs(self):
        runs = []
        try:
            for filepath in self.benchmarks_dir.glob("*.json"):
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
