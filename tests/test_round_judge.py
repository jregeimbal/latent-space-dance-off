"""Tests for round_judge module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.round_judge import RoundJudge
from tests.conftest import _run_async

FAKE_SVG = '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'


class TestRoundJudge:
    def test_judge_round_returns_model_to_eliminate(self):
        """RoundJudge returns the worst-ranked model name."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = '[{"model": "model_b", "rank": 2}, {"model": "model_a", "rank": 1}]'
        mock_client.generate = AsyncMock(return_value=mock_response)

        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        svg_map = {
            "model_a": ["/tmp/model_a.svg"],
            "model_b": ["/tmp/model_b.svg"],
        }
        # Write fake SVGs
        for path in ["/tmp/model_a.svg", "/tmp/model_b.svg"]:
            Path(path).write_text(FAKE_SVG)

        result = _run_async(
            judge.judge_round(
                survivors=["model_a", "model_b"],
                theme="abstract",
                svg_map=svg_map,
            )
        )

        assert result == "model_b"

    def test_judge_round_fallback_on_parse_failure(self):
        """RoundJudge falls back to random elimination when judge response is unparseable."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = "this is not json at all"
        mock_client.generate = AsyncMock(return_value=mock_response)

        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        svg_map = {
            "model_a": ["/tmp/model_a.svg"],
            "model_b": ["/tmp/model_b.svg"],
        }
        for path in ["/tmp/model_a.svg", "/tmp/model_b.svg"]:
            Path(path).write_text(FAKE_SVG)

        with patch("random.choice", return_value="model_a"):
            result = _run_async(
                judge.judge_round(
                    survivors=["model_a", "model_b"],
                    theme="abstract",
                    svg_map=svg_map,
                )
            )

        assert result == "model_a"

    def test_judge_round_fallback_on_exception(self):
        """RoundJudge falls back to random elimination when judge throws."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=Exception("connection error"))

        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        svg_map = {
            "model_a": ["/tmp/model_a.svg"],
        }
        Path("/tmp/model_a.svg").write_text(FAKE_SVG)

        with patch("random.choice", return_value="model_a"):
            result = _run_async(
                judge.judge_round(
                    survivors=["model_a"],
                    theme="abstract",
                    svg_map=svg_map,
                )
            )

        assert result == "model_a"

    def test_judge_round_handles_no_svg(self):
        """RoundJudge handles models that failed to generate SVGs."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = '[{"model": "model_a", "rank": 2}, {"model": "model_b", "rank": 1}]'
        mock_client.generate = AsyncMock(return_value=mock_response)

        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        svg_map = {
            "model_b": ["/tmp/model_b.svg"],
            # model_a has no SVGs (generation failed)
        }
        Path("/tmp/model_b.svg").write_text(FAKE_SVG)

        result = _run_async(
            judge.judge_round(
                survivors=["model_a", "model_b"],
                theme="abstract",
                svg_map=svg_map,
            )
        )

        assert result == "model_a"

    def test_parse_rankings_valid_json(self):
        """_parse_rankings correctly parses valid JSON array."""
        mock_client = AsyncMock()
        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        text = '[{"model": "model_a", "rank": 1}, {"model": "model_b", "rank": 2}]'
        result = judge._parse_rankings(text, ["model_a", "model_b"])

        assert len(result) == 2
        assert result[0]["model"] == "model_a"
        assert result[0]["rank"] == 1
        assert result[1]["model"] == "model_b"

    def test_parse_rankings_invalid_json(self):
        """_parse_rankings returns empty list for invalid JSON."""
        mock_client = AsyncMock()
        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        text = "not json"
        result = judge._parse_rankings(text, ["model_a", "model_b"])

        assert result == []

    def test_parse_rankings_duplicate_ranks_fallback(self):
        """_parse_rankings returns empty list when ranks are duplicated."""
        mock_client = AsyncMock()
        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        text = '[{"model": "model_a", "rank": 1}, {"model": "model_b", "rank": 1}]'
        result = judge._parse_rankings(text, ["model_a", "model_b"])

        assert result == []
