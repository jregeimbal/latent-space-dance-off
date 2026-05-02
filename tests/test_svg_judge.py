"""Tests for svg_judge module."""

from pathlib import Path
from typing import Dict, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError

from src.llm_client import LLMChunk
from src.svg_judge import Comparison, Judgment, SVGJudge

from tests.conftest import _run_async


def _scores(creativity: float = 5.0, aesthetics: float = 5.0, complexity: float = 5.0) -> Dict[str, Optional[float]]:
    return {"creativity": creativity, "aesthetics": aesthetics, "complexity": complexity}


class TestJudgmentModel:
    def test_creation_with_scores(self, mock_config):
        scores = _scores(creativity=7.5, aesthetics=8.0, complexity=6.5)
        judgment = Judgment(
            svg_id="test_1",
            svg_model_name="model_a",
            judged_by="judge_1",
            scores=scores,
            total_score=7.3,
            reason="good art",
        )
        assert judgment.scores == scores
        assert judgment.total_score == 7.3
        assert judgment.svg_id == "test_1"

    def test_criteria_used_defaults(self, mock_config):
        judgment = Judgment(
            svg_id="test_2",
            svg_model_name="model_a",
            judged_by="judge_1",
            scores=_scores(),
            total_score=5.0,
        )
        assert judgment.criteria_used == ["creativity", "aesthetics", "complexity"]

    def test_total_score_bounded_below(self, mock_config):
        with pytest.raises(ValidationError):
            Judgment(
                svg_id="test_3",
                svg_model_name="model_a",
                judged_by="judge_1",
                scores=_scores(creativity=1.0, aesthetics=1.0, complexity=1.0),
                total_score=0.5,
            )

    def test_total_score_bounded_above(self, mock_config):
        with pytest.raises(ValidationError):
            Judgment(
                svg_id="test_4",
                svg_model_name="model_a",
                judged_by="judge_1",
                scores=_scores(creativity=10.0, aesthetics=10.0, complexity=10.0),
                total_score=11.0,
            )


class TestComparisonModel:
    def test_creation(self, mock_config):
        comparison = Comparison(
            svg1_model="model_a",
            svg2_model="model_b",
            winner="model_a",
            reasoning="more creative",
        )
        assert comparison.svg1_model == "model_a"
        assert comparison.svg2_model == "model_b"
        assert comparison.winner == "model_a"
        assert comparison.reasoning == "more creative"

    def test_timestamp_defaults(self, mock_config):
        comparison = Comparison(
            svg1_model="model_a",
            svg2_model="model_b",
            winner="model_a",
        )
        assert comparison.timestamp is not None
        assert len(comparison.timestamp) > 0


class TestParseJsonResponse:
    def setup_method(self, method):
        mock_config = Mock()
        mock_config.NUM_JUDGES = 3
        mock_config.judging_criteria = ["creativity", "aesthetics", "complexity"]
        self.judge = SVGJudge(mock_config)

    def test_valid_plain_json(self):
        text = '{"creativity_score": 7, "aesthetics_score": 8, "reason": "nice"}'
        result = self.judge._parse_json_response(text)
        assert result["creativity_score"] == 7
        assert result["aesthetics_score"] == 8
        assert result["reason"] == "nice"

    def test_json_in_markdown_code_block(self):
        text = '```json\n{"creativity_score": 9, "reason": "amazing"}\n```'
        result = self.judge._parse_json_response(text)
        assert result["creativity_score"] == 9
        assert result["reason"] == "amazing"

    def test_raw_json_with_braces_extracted(self):
        text = 'Some preamble text {"creativity_score": 6}\nMore text'
        result = self.judge._parse_json_response(text)
        assert result["creativity_score"] == 6

    def test_malformed_response_falls_back_to_default_scores(self):
        text = "this is not json at all {{{"
        result = self.judge._parse_json_response(text)
        assert result["creativity_score"] == 5
        assert result["aesthetics_score"] == 5
        assert result["complexity_score"] == 5
        assert result["reason"] == "Parsing fallback"


class TestCalculateTotal:
    def setup_method(self, method):
        mock_config = Mock()
        mock_config.NUM_JUDGES = 3
        mock_config.judging_criteria = ["creativity", "aesthetics", "complexity"]
        self.judge = SVGJudge(mock_config)

    def test_simple_average(self):
        total = self.judge._calculate_total(7.0, 8.0, 9.0)
        assert total == 8.0

    def test_average_fractions(self):
        total = self.judge._calculate_total(5.0, 6.0, 7.0)
        assert total == pytest.approx(6.0)

    def test_same_scores(self):
        total = self.judge._calculate_total(3.0, 3.0, 3.0)
        assert total == 3.0


class TestJudgeSvg:
    def test_happy_path(self, mock_config):
        judge = SVGJudge(mock_config)
        mock_client = AsyncMock()
        mock_response = LLMChunk(
            response='{"creativity_score": 8, "aesthetics_score": 7, "complexity_score": 6, "reason": "good work"}'
        )
        mock_client.generate = AsyncMock(return_value=mock_response)

        svg_path = Path("/tmp/test.svg")
        svg_content = '<svg><circle cx="50" cy="50" r="40"/></svg>'

        result = _run_async(
            judge.judge_svg(
                model_client=mock_client,
                svg_path=svg_path,
                svg_content=svg_content,
                svg_id="model_a_abstract",
                model_name="model_a",
                judge_name="judge_model_a_1",
                generation_prompt="draw abstract art",
            )
        )

        assert isinstance(result, Judgment)
        assert result.scores["creativity"] == 8.0
        assert result.scores["aesthetics"] == 7.0
        assert result.scores["complexity"] == 6.0
        assert result.total_score == pytest.approx(7.0)
        assert result.reason == "good work"
        assert result.judged_by == "judge_model_a_1"
        assert result.judge_prompt is not None

    def test_error_path_returns_default_scores(self, mock_config):
        judge = SVGJudge(mock_config)
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=Exception("connect error"))

        svg_path = Path("/tmp/test.svg")
        svg_content = '<svg><circle cx="50" cy="50" r="40"/></svg>'

        result = _run_async(
            judge.judge_svg(
                model_client=mock_client,
                svg_path=svg_path,
                svg_content=svg_content,
                svg_id="model_a_abstract",
                model_name="model_a",
                judge_name="judge_model_a_1",
                generation_prompt="draw abstract art",
            )
        )

        assert isinstance(result, Judgment)
        assert result.scores["creativity"] == 5.0
        assert result.scores["aesthetics"] == 5.0
        assert result.scores["complexity"] == 5.0
        assert result.total_score == 5.0
        assert result.reason is not None and "Error during judging" in result.reason


class TestRunAllJudgments:
    def test_runs_judgments_for_models_and_svgs(self, mock_config):
        judge = SVGJudge(mock_config)

        class MockSVGResult:
            def __init__(
                self,
                model_name,
                theme,
                svg_code="svg",
                svg_path=None,
                generation_prompt=None,
                pass_number=1,
            ):
                self.model_name = model_name
                self.theme = theme
                self.svg_code = svg_code
                self.svg_path = svg_path
                self.generation_prompt = generation_prompt
                self.pass_number = pass_number

        svg_results = [
            MockSVGResult("model_a", "abstract"),
            MockSVGResult("model_b", "landscape"),
        ]

        mock_response = LLMChunk(
            response='{"creativity_score": 7, "aesthetics_score": 8, "complexity_score": 9, "reason": "nice"}'
        )
        mock_client_a = AsyncMock()
        mock_client_a.generate = AsyncMock(return_value=mock_response)
        mock_client_b = AsyncMock()
        mock_client_b.generate = AsyncMock(return_value=mock_response)

        model_clients = {"model_a": mock_client_a, "model_b": mock_client_b}

        with patch("random.shuffle", side_effect=lambda x: None):
            results = _run_async(judge.run_all_judgments(model_clients, svg_results))

        assert isinstance(results, list)
        assert len(results) == 4
        for judgment in results:
            assert isinstance(judgment, Judgment)


class TestAggregateJudgments:
    def test_aggregates_scores_per_criterion(self, mock_config):
        judge = SVGJudge(mock_config)

        class MockSVGResult:
            def __init__(self, model_name, theme, svg_path=None, pass_number=1):
                self.model_name = model_name
                self.theme = theme
                self.svg_path = svg_path
                self.pass_number = pass_number

        svg_results = [
            MockSVGResult("model_a", "abstract"),
            MockSVGResult("model_b", "landscape"),
        ]

        judgments = [
            Judgment(
                svg_id="model_a_abstract_pass1",
                svg_model_name="model_a",
                judged_by="judge_1",
                scores=_scores(creativity=8.0, aesthetics=7.0, complexity=6.0),
                total_score=7.0,
            ),
            Judgment(
                svg_id="model_b_landscape_pass1",
                svg_model_name="model_b",
                judged_by="judge_1",
                scores=_scores(creativity=9.0, aesthetics=8.0, complexity=7.0),
                total_score=8.0,
            ),
        ]

        result = judge.aggregate_judgments(svg_results, judgments)

        assert "model_a" in result
        model_a = result["model_a"]
        assert model_a["creativity"] == pytest.approx(8.0)
        assert model_a["aesthetics"] == pytest.approx(7.0)
        assert model_a["complexity"] == pytest.approx(6.0)
        assert isinstance(model_a["themes"], list)
        assert model_a["criteria"] == ["creativity", "aesthetics", "complexity"]

        assert "model_b" in result
        model_b = result["model_b"]
        assert model_b["creativity"] == pytest.approx(9.0)
        assert model_b["aesthetics"] == pytest.approx(8.0)
        assert model_b["complexity"] == pytest.approx(7.0)
        assert isinstance(model_b["themes"], list)

    def test_handles_missing_judgments_for_model(self, mock_config):
        judge = SVGJudge(mock_config)

        class MockSVGResult:
            def __init__(self, model_name, theme, pass_number=1):
                self.model_name = model_name
                self.theme = theme
                self.pass_number = pass_number

        svg_results = [
            MockSVGResult("model_a", "abstract"),
            MockSVGResult("model_b", "landscape"),
        ]

        judgments = [
            Judgment(
                svg_id="model_a_abstract_pass1",
                svg_model_name="model_a",
                judged_by="judge_1",
                scores=_scores(creativity=7.0, aesthetics=7.0, complexity=7.0),
                total_score=7.0,
            )
        ]

        result = judge.aggregate_judgments(svg_results, judgments)

        assert "model_a" in result
        assert "model_b" not in result


class TestSVGJudgeConstructor:
    def test_uses_config_num_judges(self, mock_config):
        mock_config.NUM_JUDGES = 5
        judge = SVGJudge(mock_config)
        assert judge.num_judges == 5

    def test_defaults_to_3_when_missing(self):
        mock_config = Mock(spec=["judging_criteria"])
        mock_config.judging_criteria = ["creativity", "aesthetics", "complexity"]
        judge = SVGJudge(mock_config)
        assert judge.num_judges == 3
