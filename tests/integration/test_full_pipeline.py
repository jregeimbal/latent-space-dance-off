"""Integration tests for the full benchmark and dance-off pipelines."""

import json
from typing import Any, AsyncIterator, Dict, Optional, Union

from src.llm_client import BaseLLMClient, LLMChunk

VALID_SVG = (
    '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">'
    '<rect width="100" height="100" fill="blue"/></svg>'
)

JUDGE_RESPONSE = json.dumps({
    "creativity_score": 7,
    "aesthetics_score": 8,
    "complexity_score": 6,
    "reason": "test judgment",
})

RANKING_RESPONSE = json.dumps([
    {"model": "model-a", "rank": 1},
    {"model": "model-b", "rank": 2},
])


class MockLLMClient(BaseLLMClient):
    def __init__(self, ranking_response: str = RANKING_RESPONSE):
        self._ranking_response = ranking_response

    async def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        format: Optional[str] = None,
    ) -> Union[LLMChunk, AsyncIterator[LLMChunk]]:
        if prompt in ("/clear", "Test"):
            if stream:
                return self._stream("")
            return LLMChunk(response="")

        if stream:
            return self._stream(VALID_SVG)

        if "Rate this SVG" in prompt:
            return LLMChunk(response=JUDGE_RESPONSE)

        if "Pick one theme" in prompt:
            return LLMChunk(response="abstract")

        if "Rank these models" in prompt:
            return LLMChunk(response=self._ranking_response)

        return LLMChunk(response=VALID_SVG)

    async def _stream(self, text: str) -> AsyncIterator[LLMChunk]:
        yield LLMChunk(response=text)

    async def list(self) -> Dict[str, Any]:
        return {"models": []}


async def test_full_benchmark_pipeline(tmp_path):
    from src.config import Config
    from src.model_manager import ModelManager
    from src.svg_generator import SVGGenerator
    from src.svg_judge import SVGJudge
    from src.benchmark import (
        BenchmarkManager,
        BenchmarkRecord,
        RunData,
        SVGResult as BenchSVGResult,
    )
    from src.ranking import RankingSystem
    from src.html_generator import generate_benchmark_html

    config = Config(OUTPUT_DIR=str(tmp_path))
    config.create_output_dirs()

    mock = MockLLMClient()

    manager = ModelManager(host="http://localhost:11434", client_type="ollama")
    manager._client = mock

    await manager.get_model("model-a")
    await manager.get_model("model-b")

    model_clients = {"model-a": mock, "model-b": mock}

    generator = SVGGenerator(config)
    themes = ["abstract"]

    svg_results = await generator.generate_multiple_svgs(model_clients, themes)

    assert len(svg_results) == 2
    assert all(r.status == "success" for r in svg_results)
    assert all(r.svg_code for r in svg_results)

    judge = SVGJudge(config)
    judgments = await judge.run_all_judgments(model_clients, svg_results)

    assert len(judgments) > 0
    assert all(j.total_score is not None for j in judgments)

    run_id = "test-integration-run"
    timestamp = "2024-01-01T00:00:00"

    bench_svgs = [
        BenchSVGResult(
            model_name=r.model_name,
            theme=r.theme,
            svg_code=r.svg_code,
            svg_path=r.svg_path,
            duration_ms=r.duration_ms,
            tokens_used=r.tokens_used,
            status=r.status,
            generation_prompt=r.generation_prompt,
            pass_number=r.pass_number,
        )
        for r in svg_results
    ]

    bench_records = [
        BenchmarkRecord(
            run_id=run_id,
            model_name=r.model_name,
            theme=r.theme,
            duration_ms=r.duration_ms,
            tokens=r.tokens_used,
        )
        for r in svg_results
    ]

    run_data = RunData(
        run_id=run_id,
        timestamp=timestamp,
        svgs=bench_svgs,
        benchmarks=bench_records,
        model_list=["model-a", "model-b"],
        themes=themes,
        judgments=judgments,
    )

    bench_manager = BenchmarkManager(config)
    bench_manager.save_run_data(run_data)

    benchmark_file = config.benchmarks_dir / run_id / "benchmark.json"
    assert benchmark_file.exists()

    with open(benchmark_file) as f:
        saved_data = json.load(f)
    assert saved_data["run_id"] == run_id
    assert len(saved_data["svgs"]) == 2
    assert len(saved_data["judgments"]) > 0

    ranking_system = RankingSystem(config)
    leaderboard = ranking_system.generate_leaderboard(run_data)

    assert len(leaderboard.rankings) == 2
    assert all(entry.total_score > 0 for entry in leaderboard.rankings)

    html_dict = {
        "run_id": run_id,
        "timestamp": timestamp,
        "model_list": ["model-a", "model-b"],
        "themes": themes,
        "svgs": [
            {
                "model_name": s.model_name,
                "theme": s.theme,
                "svg_code": s.svg_code,
                "svg_path": s.svg_path,
                "duration_ms": s.duration_ms,
                "tokens_used": s.tokens_used,
                "status": s.status,
                "pass_number": s.pass_number,
            }
            for s in bench_svgs
        ],
        "judgments": [
            {
                "svg_id": j.svg_id,
                "judged_by": j.judged_by,
                "scores": j.scores,
                "total_score": j.total_score,
                "reason": j.reason,
                "criteria_used": j.criteria_used,
            }
            for j in judgments
        ],
        "criteria": config.judging_criteria,
    }

    html_path = tmp_path / "report.html"
    generate_benchmark_html(html_dict, html_path)

    assert html_path.exists()
    html_content = html_path.read_text()
    assert "model-a" in html_content
    assert "model-b" in html_content
    assert "image/svg+xml" in html_content


async def test_dance_off_pipeline(tmp_path):
    from src.config import Config
    from src.dance_off import DanceOff

    config = Config(OUTPUT_DIR=str(tmp_path))
    config.create_output_dirs()

    mock_a = MockLLMClient()
    mock_b = MockLLMClient()
    model_clients = {"model-a": mock_a, "model-b": mock_b}

    dance_off = DanceOff(
        model_clients=model_clients,
        config=config,
        theme_pool=["abstract", "landscape"],
        output_dir=str(tmp_path / "dance_off"),
        svg_per_model=1,
    )

    result = await dance_off.run()

    assert result.champion in ("model-a", "model-b")
    assert len(result.rounds) == 1
    assert result.rounds[0].eliminated in ("model-a", "model-b")
    assert result.rounds[0].eliminated != result.champion
