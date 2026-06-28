"""Tests for src/html_generator.py."""

import json
from pathlib import Path

from src.html_generator import (
    _calculate_avg_score,
    _build_error_cell,
    _build_html,
    _build_row_html,
    _build_success_cells,
    _build_pass_selector_cell,
    _render_judge_prompts,
    calculate_tokens_per_second,
    format_duration,
    generate_benchmark_html,
    generate_dance_off_html,
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


# --- _build_pass_selector_cell ---


class TestBuildPassSelectorCell:

    def test_renders_model_name_score_duration_tokens_tps(self):
        import base64
        svg_code = '<svg><circle/></svg>'
        encoded = base64.b64encode(svg_code.encode('utf-8')).decode('utf-8')
        pass_options = [{
            "pass_number": 1,
            "svg_code": svg_code,
            "duration_ms": 2000,
            "tokens": 400,
            "tps": 200.0,
            "svg_path": "/path/to/svg.svg",
            "avg_score": 8.50,
            "judgments": [],
        }]
        result = _build_pass_selector_cell(
            model="model_a",
            theme="abstract",
            pass_options=pass_options,
        )
        assert "model_a" in result
        assert f'src="data:image/svg+xml;base64,{encoded}"' in result
        assert "2.00s" in result
        assert "400" in result
        assert "200.0" in result
        assert "Pass 1" in result
        assert 'class="pass-dropdown"' in result

    def test_no_avg_score_no_score_str(self):
        pass_options = [{
            "pass_number": 1,
            "svg_code": '<svg><circle/></svg>',
            "duration_ms": 0,
            "tokens": None,
            "tps": 0.0,
            "svg_path": "",
            "avg_score": None,
            "judgments": [],
        }]
        result = _build_pass_selector_cell(
            model="model_a",
            theme="abstract",
            pass_options=pass_options,
        )
        assert 'class="cell-score"' not in result

    def test_svg_code_embedded(self):
        import base64
        svg_code = '<svg id="test-svg"><circle/></svg>'
        encoded = base64.b64encode(svg_code.encode('utf-8')).decode('utf-8')
        pass_options = [{
            "pass_number": 1,
            "svg_code": svg_code,
            "duration_ms": 0,
            "tokens": 100,
            "tps": 100.0,
            "svg_path": "",
            "avg_score": None,
            "judgments": [],
        }]
        result = _build_pass_selector_cell(
            model="model_a",
            theme="abstract",
            pass_options=pass_options,
        )
        assert f'src="data:image/svg+xml;base64,{encoded}"' in result

    def test_multiple_passes_shows_dropdown(self):
        import base64
        svg1 = '<svg id="p1"/></svg>'
        svg2 = '<svg id="p2"/></svg>'
        encoded1 = base64.b64encode(svg1.encode('utf-8')).decode('utf-8')
        encoded2 = base64.b64encode(svg2.encode('utf-8')).decode('utf-8')

        pass_options = [
            {
                "pass_number": 1,
                "svg_code": svg1,
                "duration_ms": 1000,
                "tokens": 100,
                "tps": 100.0,
                "svg_path": "/p1.svg",
                "avg_score": 7.0,
                "judgments": [],
            },
            {
                "pass_number": 2,
                "svg_code": svg2,
                "duration_ms": 2000,
                "tokens": 200,
                "tps": 100.0,
                "svg_path": "/p2.svg",
                "avg_score": 8.0,
                "judgments": [],
            },
        ]
        result = _build_pass_selector_cell(
            model="model_a",
            theme="abstract",
            pass_options=pass_options,
        )
        assert '<option value="1"' in result
        assert '<option value="2"' in result
        assert 'selected' in result
        assert f'src="data:image/svg+xml;base64,{encoded1}"' in result
        assert f'src="data:image/svg+xml;base64,{encoded2}"' in result
        assert 'data-pass="1"' in result
        assert 'data-pass="2"' in result
        assert 'class="pass-dropdown"' in result
        assert 'class="pass-selector"' in result
        # First pass should be visible (no display:none), second hidden
        first_pass_idx = result.index('data-pass="1"')
        second_pass_idx = result.index('data-pass="2"')
        assert result[first_pass_idx:first_pass_idx+100].find('display') == -1 or result[first_pass_idx:first_pass_idx+100].find("display: ''") != -1
        assert 'display: none' in result[second_pass_idx:]


# --- _build_error_cell ---


class TestBuildErrorCell:

    def test_renders_error_message(self):
        result = _build_error_cell("model_a", "abstract", "GPU timeout")
        assert "model_a" in result
        assert "GPU timeout" in result

    def test_defaults_to_generation_failed(self):
        result = _build_error_cell("model_a", "abstract", "")
        assert "Generation failed" in result


# --- _calculate_avg_score ---


# --- _build_row_html ---


class TestBuildRowHtml:

    def test_includes_theme_label_and_cells(self):
        svg_lookup = {
            ("model_a", "abstract"): [{
                "status": "success",
                "svg_code": '<svg><circle/></svg>',
                "duration_ms": 1000,
                "tokens_used": 100,
                "svg_path": "/a.svg",
            }],
            ("model_b", "abstract"): [{
                "status": "failed",
                "error_message": "Error",
            }],
        }
        result = _build_row_html("abstract", ["model_a", "model_b"], svg_lookup, {})
        assert "abstract" in result
        assert "model_a" in result
        assert "model_b" in result

    def test_includes_both_success_and_error_cells(self):
        svg_lookup = {
            ("model_a", "abstract"): [{
                "status": "success",
                "svg_code": '<svg><circle/></svg>',
                "duration_ms": 1000,
                "tokens_used": 100,
                "svg_path": "",
            }],
            ("model_b", "abstract"): [{
                "status": "failed",
                "error_message": "Some error",
            }],
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


# --- Multi-pass tests ---


class TestMultiPass:

    def test_build_success_cells_multiple_passes(self):
        import base64
        svg1 = '<svg id="pass1"><circle/></svg>'
        svg2 = '<svg id="pass2"><rect/></svg>'
        encoded1 = base64.b64encode(svg1.encode('utf-8')).decode('utf-8')
        encoded2 = base64.b64encode(svg2.encode('utf-8')).decode('utf-8')

        svg_list = [
            {
                "status": "success",
                "svg_code": svg1,
                "duration_ms": 1000,
                "tokens_used": 100,
                "svg_path": "/pass1.svg",
                "pass_number": 1,
            },
            {
                "status": "success",
                "svg_code": svg2,
                "duration_ms": 1500,
                "tokens_used": 120,
                "svg_path": "/pass2.svg",
                "pass_number": 2,
            },
        ]
        result = _build_success_cells("model_a", "abstract", svg_list, {})
        assert f'src="data:image/svg+xml;base64,{encoded1}"' in result
        assert f'src="data:image/svg+xml;base64,{encoded2}"' in result

    def test_build_row_html_multiple_passes(self):
        import base64
        svg1 = '<svg><circle/></svg>'
        svg2 = '<svg><rect/></svg>'
        encoded1 = base64.b64encode(svg1.encode('utf-8')).decode('utf-8')
        encoded2 = base64.b64encode(svg2.encode('utf-8')).decode('utf-8')

        svg_lookup = {
            ("model_a", "abstract"): [
                {
                    "status": "success",
                    "svg_code": svg1,
                    "duration_ms": 1000,
                    "tokens_used": 100,
                    "svg_path": "/a1.svg",
                    "pass_number": 1,
                },
                {
                    "status": "success",
                    "svg_code": svg2,
                    "duration_ms": 2000,
                    "tokens_used": 200,
                    "svg_path": "/a2.svg",
                    "pass_number": 2,
                },
            ],
        }
        result = _build_row_html("abstract", ["model_a"], svg_lookup, {})
        assert f'src="data:image/svg+xml;base64,{encoded1}"' in result
        assert f'src="data:image/svg+xml;base64,{encoded2}"' in result

    def test_build_row_html_mixed_passes_success_and_fail(self):
        import base64
        svg1 = '<svg><circle/></svg>'
        encoded1 = base64.b64encode(svg1.encode('utf-8')).decode('utf-8')

        svg_lookup = {
            ("model_a", "abstract"): [
                {
                    "status": "success",
                    "svg_code": svg1,
                    "duration_ms": 1000,
                    "tokens_used": 100,
                    "svg_path": "/a1.svg",
                    "pass_number": 1,
                },
                {
                    "status": "failed",
                    "error_message": "timeout",
                    "svg_path": None,
                    "pass_number": 2,
                },
            ],
        }
        result = _build_row_html("abstract", ["model_a"], svg_lookup, {})
        assert f'src="data:image/svg+xml;base64,{encoded1}"' in result
        # Failed pass should not render as error cell since there's a success
        assert 'class="cell failed"' not in result
        # Only successful passes are rendered
        assert '/a1.svg' in result

    def test_generate_benchmark_html_with_multiple_passes(self, tmp_path):
        import base64
        svg1 = '<svg id="p1"><circle/></svg>'
        svg2 = '<svg id="p2"><rect/></svg>'
        encoded1 = base64.b64encode(svg1.encode('utf-8')).decode('utf-8')
        encoded2 = base64.b64encode(svg2.encode('utf-8')).decode('utf-8')

        run_data_dict = {
            "run_id": "run-1",
            "timestamp": "2024-01-01",
            "model_list": ["model_a"],
            "themes": ["abstract"],
            "svgs": [
                {
                    "model_name": "model_a",
                    "theme": "abstract",
                    "svg_code": svg1,
                    "svg_path": "/p1.svg",
                    "duration_ms": 1000,
                    "tokens_used": 100,
                    "status": "success",
                    "pass_number": 1,
                },
                {
                    "model_name": "model_a",
                    "theme": "abstract",
                    "svg_code": svg2,
                    "svg_path": "/p2.svg",
                    "duration_ms": 2000,
                    "tokens_used": 200,
                    "status": "success",
                    "pass_number": 2,
                },
            ],
            "judgments": [],
            "criteria": ["creativity"],
        }
        result = generate_benchmark_html(run_data_dict, Path("/tmp/test_multi_pass.html"))
        with open(result, "r") as f:
            html = f.read()
        assert f'src="data:image/svg+xml;base64,{encoded1}"' in html
        assert f'src="data:image/svg+xml;base64,{encoded2}"' in html
        assert "Pass 1" in html
        assert "Pass 2" in html
        assert 'class="pass-dropdown"' in html
        assert "switchPass" in html

    def test_generate_benchmark_html_with_judgments_multiple_passes(self, tmp_path):
        run_data_dict = {
            "run_id": "run-1",
            "timestamp": "2024-01-01",
            "model_list": ["model_a"],
            "themes": ["abstract"],
            "svgs": [
                {
                    "model_name": "model_a",
                    "theme": "abstract",
                    "svg_code": '<svg id="p1"><circle/></svg>',
                    "svg_path": "/p1.svg",
                    "duration_ms": 1000,
                    "tokens_used": 100,
                    "status": "success",
                    "pass_number": 1,
                },
                {
                    "model_name": "model_a",
                    "theme": "abstract",
                    "svg_code": '<svg id="p2"><rect/></svg>',
                    "svg_path": "/p2.svg",
                    "duration_ms": 2000,
                    "tokens_used": 200,
                    "status": "success",
                    "pass_number": 2,
                },
            ],
            "judgments": [
                {
                    "svg_id": "model_a_abstract_pass1",
                    "judged_by": "judge_1",
                    "scores": {"creativity": 8.0},
                    "total_score": 8.0,
                    "reason": "Good pass 1",
                    "criteria_used": ["creativity"],
                    "judge_prompt": None,
                },
                {
                    "svg_id": "model_a_abstract_pass2",
                    "judged_by": "judge_1",
                    "scores": {"creativity": 9.0},
                    "total_score": 9.0,
                    "reason": "Good pass 2",
                    "criteria_used": ["creativity"],
                    "judge_prompt": None,
                },
            ],
            "criteria": ["creativity"],
        }
        result = generate_benchmark_html(run_data_dict, Path("/tmp/test_multi_pass_judged.html"))
        with open(result, "r") as f:
            html = f.read()
        assert "Good pass 1" in html
        assert "Good pass 2" in html
        assert "8.0" in html
        assert "9.0" in html


# --- Security Tests ---


class TestSecurity:

    def test_xss_prevention_in_benchmark_html(self, tmp_path):
        malicious_svg = '<svg><script>alert("xss")</script></svg>'
        run_data_dict = {
            "run_id": "test-run",
            "timestamp": "2024-01-01",
            "model_list": ["model_a"],
            "themes": ["abstract"],
            "svgs": [
                {
                    "model_name": "model_a",
                    "theme": "abstract",
                    "svg_code": malicious_svg,
                    "duration_ms": 1000,
                    "tokens_used": 100,
                    "status": "success",
                    "pass_number": 1,
                }
            ],
            "judgments": [],
            "criteria": ["creativity"],
        }
        output_path = tmp_path / "report.html"
        generate_benchmark_html(run_data_dict, output_path)
        content = output_path.read_text()

        assert '<script>alert("xss")</script>' not in content
        assert 'data:image/svg+xml;base64,' in content

    def test_xss_prevention_in_dance_off_html(self, tmp_path):
        from unittest.mock import MagicMock
        malicious_svg = '<svg><script>alert("xss")</script></svg>'

        mock_svg = MagicMock()
        mock_svg.status = "success"
        mock_svg.svg_code = malicious_svg
        mock_svg.model_name = "model_a"

        mock_round = MagicMock()
        mock_round.round_num = 1
        mock_round.theme = "abstract"
        mock_round.rankings = [("model_a", 10.0)]
        mock_round.eliminated = "model_b"
        mock_round.svg_results = [mock_svg]

        mock_result = MagicMock()
        mock_result.rounds = [mock_round]
        mock_result.champion = "model_a"

        output_path = tmp_path / "danceoff.html"
        generate_dance_off_html(mock_result, output_path)
        content = output_path.read_text()

        assert '<script>alert("xss")</script>' not in content
        assert 'data:image/svg+xml;base64,' in content
