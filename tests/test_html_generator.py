"""Tests for src/html_generator.py."""

import json
from pathlib import Path

from src.html_generator import (
    _calculate_avg_score,
    _build_error_cell,
    _build_html,
    _build_row_html,
    _build_success_cell,
    _render_judge_prompts,
    calculate_tokens_per_second,
    format_duration,
    generate_benchmark_html,
    generate_report_from_file,
)


# --- calculate_tokens_per_second ---


class TestCalculateTokensPerSecond:

    def test_normal(self):
        result = calculate_tokens_per_second(100, 1000)
        assert result == 100.0

    def test_zero_duration(self):
        result = calculate_tokens_per_second(100, 0)
        assert result == 0.0

    def test_none_tokens(self):
        result = calculate_tokens_per_second(None, 5000)
        assert result == 0.0


# --- format_duration ---


class TestFormatDuration:

    def test_seconds_less_than_60(self):
        result = format_duration(30000)
        assert result == "30.00s"

    def test_minutes_60_to_3599_seconds(self):
        result = format_duration(120000)
        assert result == "2.00m"

    def test_hours_greater_than_3600_seconds(self):
        result = format_duration(7200000)
        assert result == "2.00h"


# --- _calculate_avg_score ---


class TestCalculateAvgScore:

    def test_multiple_judgments_with_total_score(self):
        judgments = [
            {"total_score": 8.0},
            {"total_score": 10.0},
            {"total_score": 6.0},
        ]
        result = _calculate_avg_score(judgments)
        assert result == 8.0

    def test_judgments_with_none_total_score_skipped(self):
        judgments = [
            {"total_score": 8.0},
            {"total_score": None},
            {"total_score": 10.0},
        ]
        result = _calculate_avg_score(judgments)
        assert result == 9.0

    def test_empty_list_returns_none(self):
        result = _calculate_avg_score([])
        assert result is None


# --- _render_judge_prompts ---


class TestRenderJudgePrompts:

    def test_with_judge_prompt_includes_details(self):
        judgments = [
            {
                "judged_by": "judge_1",
                "scores": {"creativity": 8},
                "criteria_used": ["creativity"],
                "reason": "Good job",
                "judge_prompt": "Write a poem",
            }
        ]
        result = _render_judge_prompts(judgments)
        assert "<details" in result
        assert "Write a poem" in result

    def test_without_judge_prompt_no_details(self):
        judgments = [
            {
                "judged_by": "judge_1",
                "scores": {"creativity": 5},
                "criteria_used": ["creativity"],
                "reason": "Meh",
                "judge_prompt": None,
            }
        ]
        result = _render_judge_prompts(judgments)
        assert "<details" not in result

    def test_multiple_judgments_renders_all(self):
        judgments = [
            {
                "judged_by": "judge_1",
                "scores": {"creativity": 8},
                "criteria_used": ["creativity"],
                "reason": "First",
                "judge_prompt": "Prompt one",
            },
            {
                "judged_by": "judge_2",
                "scores": {"aesthetics": 9},
                "criteria_used": ["aesthetics"],
                "reason": "Second",
                "judge_prompt": "Prompt two",
            },
        ]
        result = _render_judge_prompts(judgments)
        assert "judge_1" in result
        assert "judge_2" in result
        assert "Prompt one" in result
        assert "Prompt two" in result


# --- _build_success_cell ---


class TestBuildSuccessCell:

    def test_renders_model_name_score_duration_tokens_tps(self):
        svg_code = '<svg><circle/></svg>'
        result = _build_success_cell(
            model="model_a",
            theme="abstract",
            svg_code=svg_code,
            duration_ms=2000,
            tokens=400,
            tps=200.0,
            svg_path="/path/to/svg.svg",
            avg_score=8.50,
        )
        assert "model_a" in result
        assert svg_code in result
        assert "2.00s" in result
        assert "400" in result
        assert "200.0" in result

    def test_no_avg_score_no_score_str(self):
        svg_code = '<svg><circle/></svg>'
        result = _build_success_cell(
            model="model_a",
            theme="abstract",
            svg_code=svg_code,
            duration_ms=0,
            tokens=None,
            tps=0.0,
            svg_path="",
            avg_score=None,
        )
        assert 'class="cell-score"' not in result

    def test_svg_code_embedded(self):
        svg_code = '<svg id="test-svg"><circle/></svg>'
        result = _build_success_cell(
            model="model_a",
            theme="abstract",
            svg_code=svg_code,
            duration_ms=0,
            tokens=100,
            tps=100.0,
            svg_path="",
            avg_score=None,
        )
        assert svg_code in result


# --- _build_error_cell ---


class TestBuildErrorCell:

    def test_renders_error_message(self):
        result = _build_error_cell("model_a", "abstract", "GPU timeout")
        assert "model_a" in result
        assert "GPU timeout" in result

    def test_defaults_to_generation_failed(self):
        result = _build_error_cell("model_a", "abstract", "")
        assert "Generation failed" in result


# --- _build_row_html ---


class TestBuildRowHtml:

    def test_includes_theme_label_and_cells(self):
        svg_lookup = {
            ("model_a", "abstract"): {
                "status": "success",
                "svg_code": '<svg><circle/></svg>',
                "duration_ms": 1000,
                "tokens_used": 100,
                "svg_path": "/a.svg",
            },
            ("model_b", "abstract"): {
                "status": "failed",
                "error_message": "Error",
            },
        }
        result = _build_row_html("abstract", ["model_a", "model_b"], svg_lookup, {})
        assert "abstract" in result
        assert "model_a" in result
        assert "model_b" in result

    def test_includes_both_success_and_error_cells(self):
        svg_lookup = {
            ("model_a", "abstract"): {
                "status": "success",
                "svg_code": '<svg><circle/></svg>',
                "duration_ms": 1000,
                "tokens_used": 100,
                "svg_path": "",
            },
            ("model_b", "abstract"): {
                "status": "failed",
                "error_message": "Some error",
            },
        }
        result = _build_row_html("abstract", ["model_a", "model_b"], svg_lookup, {})
        assert "cell" in result
        assert 'class="cell failed"' in result
        assert 'class="cell">' in result


# --- _build_html ---


class TestBuildHtml:

    def test_complete_html_document_structure(self):
        svg_lookup = {}
        judgments_lookup = {}
        result = _build_html(
            run_id="run-1",
            timestamp="2024-01-01",
            models=["model_a"],
            themes=["theme-1"],
            svg_lookup=svg_lookup,
            judgments_lookup=judgments_lookup,
        )
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "<head>" in result
        assert "<style>" in result
        assert "<body>" in result
        assert 'class="grid-container"' in result

    def test_includes_model_labels(self):
        svg_lookup = {}
        judgments_lookup = {}
        result = _build_html(
            run_id="run-1",
            timestamp="2024-01-01",
            models=["model_a", "model_b"],
            themes=["theme-1"],
            svg_lookup=svg_lookup,
            judgments_lookup=judgments_lookup,
        )
        assert 'class="model-label"' in result
        assert "model_a" in result
        assert "model_b" in result

    def test_includes_theme_labels(self):
        svg_lookup = {}
        judgments_lookup = {}
        result = _build_html(
            run_id="run-1",
            timestamp="2024-01-01",
            models=["model_a"],
            themes=["fantasy", "sci-fi"],
            svg_lookup=svg_lookup,
            judgments_lookup=judgments_lookup,
        )
        assert 'class="theme-label"' in result
        assert "fantasy" in result
        assert "sci-fi" in result

    def test_run_id_in_title(self):
        svg_lookup = {}
        judgments_lookup = {}
        result = _build_html(
            run_id="my-run",
            timestamp="",
            models=[],
            themes=[],
            svg_lookup=svg_lookup,
            judgments_lookup=judgments_lookup,
        )
        assert "my-run" in result


# --- generate_benchmark_html ---


class TestGenerateBenchmarkHtml:

    def test_writes_html_file_to_output_path(self, tmp_path):
        run_data_dict = {
            "run_id": "test-run",
            "timestamp": "2024-01-01",
            "model_list": ["model_a"],
            "themes": ["abstract"],
            "svgs": [],
            "judgments": [],
            "criteria": ["creativity"],
        }
        output_path = tmp_path / "report.html"
        result = generate_benchmark_html(run_data_dict, output_path)

        assert Path(result).exists()

    def test_returns_file_path_string(self, tmp_path):
        run_data_dict = {
            "run_id": "test-run",
            "timestamp": "2024-01-01",
            "model_list": [],
            "themes": [],
            "svgs": [],
            "judgments": [],
            "criteria": [],
        }
        output_path = tmp_path / "output" / "report.html"
        result = generate_benchmark_html(run_data_dict, output_path)
        assert result == str(output_path)

    def test_creates_parent_directories(self, tmp_path):
        run_data_dict = {
            "run_id": "test-run",
            "timestamp": "",
            "model_list": [],
            "themes": [],
            "svgs": [],
            "judgments": [],
            "criteria": [],
        }
        output_path = tmp_path / "deeply" / "nested" / "dir" / "report.html"
        result = generate_benchmark_html(run_data_dict, output_path)
        assert Path(result).exists()

    def test_html_contains_run_id(self, tmp_path):
        run_data_dict = {
            "run_id": "super-secret-run",
            "timestamp": "",
            "model_list": [],
            "themes": [],
            "svgs": [],
            "judgments": [],
            "criteria": [],
        }
        output_path = tmp_path / "report.html"
        generate_benchmark_html(run_data_dict, output_path)
        content = Path(output_path).read_text()
        assert "super-secret-run" in content


# --- generate_report_from_file ---


class TestGenerateReportFromFile:

    def test_reads_json_and_writes_html(self, tmp_path):
        benchmark_data = {
            "run_id": "from-file-run",
            "timestamp": "2024-06-01",
            "model_list": ["model_x"],
            "themes": ["nature"],
            "svgs": [],
            "judgments": [],
            "criteria": ["creativity"],
        }
        json_path = tmp_path / "benchmark.json"
        with open(json_path, "w") as f:
            json.dump(benchmark_data, f)

        result = generate_report_from_file(str(json_path))

        assert Path(result).exists()
        assert "benchmark_report.html" in result

    def test_returns_path_string(self, tmp_path):
        benchmark_data = {
            "run_id": "x",
            "timestamp": "",
            "model_list": [],
            "themes": [],
            "svgs": [],
            "judgments": [],
            "criteria": [],
        }
        json_path = tmp_path / "data.json"
        with open(json_path, "w") as f:
            json.dump(benchmark_data, f)

        result = generate_report_from_file(str(json_path))
        assert isinstance(result, str)

    def test_custom_output_dir(self, tmp_path):
        benchmark_data = {
            "run_id": "x",
            "timestamp": "",
            "model_list": [],
            "themes": [],
            "svgs": [],
            "judgments": [],
            "criteria": [],
        }
        json_path = tmp_path / "sub" / "benchmark.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w") as f:
            json.dump(benchmark_data, f)

        out_dir = tmp_path / "custom"
        out_dir.mkdir(parents=True, exist_ok=True)
        result = generate_report_from_file(str(json_path), str(out_dir))

        assert Path(result).exists()
        assert str(out_dir) in result
