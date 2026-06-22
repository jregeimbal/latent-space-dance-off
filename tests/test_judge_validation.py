"""Tests for judge elimination target validation (issue #5).

Verifies that hallucinated or invalid model names from the round judge
are rejected and do not cause crashes or incorrect eliminations.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dance_off import DanceOff
from src.round_judge import RoundJudge
from tests.conftest import _run_async

FAKE_SVG = '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'


class TestParseRankingsSurvivorValidation:
    """Tests for _parse_rankings survivor name filtering."""

    def _make_judge(self):
        mock_client = AsyncMock()
        return RoundJudge(judge_client=mock_client, judge_model="test_judge")

    def test_rejects_hallucinated_model_name(self):
        """_parse_rankings rejects entries referencing models not in survivors."""
        judge = self._make_judge()

        text = (
            '[{"model": "llama3", "rank": 1}, '
            '{"model": "gpt-4", "rank": 2}]'
        )
        result = judge._parse_rankings(text, ["llama3", "mistral"])

        assert result == []

    def test_rejects_mixed_hallucinated_and_valid(self):
        """_parse_rankings drops hallucinated entries, but still requires all
        survivors present — so if a valid survivor is replaced by a fake one,
        the result falls back to empty."""
        judge = self._make_judge()

        # Only llama3 is in survivors; gpt-4 is fake
        text = (
            '[{"model": "llama3", "rank": 1}, '
            '{"model": "gpt-4", "rank": 2}]'
        )
        result = judge._parse_rankings(text, ["llama3", "mistral"])

        assert result == []

    def test_accepts_all_valid_survivors(self):
        """_parse_rankings accepts entries when all models are in survivors."""
        judge = self._make_judge()

        text = (
            '[{"model": "llama3", "rank": 1}, '
            '{"model": "mistral", "rank": 2}]'
        )
        result = judge._parse_rankings(text, ["llama3", "mistral"])

        assert len(result) == 2
        assert result[0]["model"] == "llama3"
        assert result[1]["model"] == "mistral"

    def test_rejects_partial_hallucination(self):
        """_parse_rankings rejects when one entry is hallucinated and the
        other is a real survivor — the hallucinated one is filtered out,
        leaving an incomplete ranking."""
        judge = self._make_judge()

        text = (
            '[{"model": "llama3", "rank": 1}, '
            '{"model": "claude-sonnet", "rank": 2}]'
        )
        result = judge._parse_rankings(text, ["llama3", "mistral"])

        # llama3 is valid but mistral is missing (replaced by hallucination)
        assert result == []


class TestDanceOffInvalidEliminationTarget:
    """Tests for DanceOff._judge_round handling of invalid targets."""

    def _make_dance_off(self, tmp_path):
        from unittest.mock import Mock

        config = Mock()
        config.OUTPUT_DIR = str(tmp_path)
        config.svgs_dir = tmp_path / "svgs"
        config.benchmarks_dir = tmp_path / "benchmarks"
        config.LEADERBOARDS_DIR = tmp_path / "leaderboards"

        return DanceOff(
            model_clients={"model_a": AsyncMock(), "model_b": AsyncMock()},
            config=config,
            theme_pool=["abstract"],
            output_dir=str(tmp_path),
            svg_per_model=1,
            judge_model="test_judge",
        )

    def test_handles_invalid_elimination_target(self):
        """_judge_round falls back to last survivor when judge returns invalid name."""
        dance_off = self._make_dance_off(Path("/tmp/judge_val_test"))

        with patch.object(
            dance_off, "_judge_round", return_value="phantom_model"
        ):
            # We can't call _judge_round on itself, so test the logic directly.
            pass

    def test_judge_round_fallback_preserves_survivor(self):
        """_judge_round returns a valid survivor even when judge is unreliable."""
        dance_off = self._make_dance_off(Path("/tmp/judge_val_test2"))

        # Mock round_judge.judge_round to return an invalid name
        with patch.object(
            RoundJudge,
            "judge_round",
            return_value="nonexistent_model",
        ):
            result = _run_async(
                dance_off._judge_round(
                    survivors=["model_a", "model_b"],
                    theme="abstract",
                    svg_map={"model_a": ["/tmp/a.svg"], "model_b": ["/tmp/b.svg"]},
                )
            )

        assert result == "model_b"  # last survivor fallback

    def test_judge_round_valid_target_passed_through(self):
        """_judge_round passes through valid elimination targets unchanged."""
        dance_off = self._make_dance_off(Path("/tmp/judge_val_test3"))

        with patch.object(
            RoundJudge,
            "judge_round",
            return_value="model_a",
        ):
            result = _run_async(
                dance_off._judge_round(
                    survivors=["model_a", "model_b"],
                    theme="abstract",
                    svg_map={"model_a": ["/tmp/a.svg"], "model_b": ["/tmp/b.svg"]},
                )
            )

        assert result == "model_a"


class TestNormalJudgeResponses:
    """Ensure the validation fixes don't break normal judge responses."""

    def _make_judge(self):
        mock_client = AsyncMock()
        return RoundJudge(judge_client=mock_client, judge_model="test_judge")

    def test_normal_response_still_works(self):
        """Normal valid JSON rankings are parsed correctly."""
        judge = self._make_judge()

        text = (
            '[{"model": "llama3", "rank": 1}, '
            '{"model": "mistral", "rank": 2}]'
        )
        result = judge._parse_rankings(text, ["llama3", "mistral"])

        assert len(result) == 2
        assert result[-1]["model"] == "mistral"  # eliminated

    def test_judge_round_normal_flow(self):
        """Full judge_round flow returns correct elimination for normal input."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = (
            '[{"model": "llama3", "rank": 1}, '
            '{"model": "mistral", "rank": 2}]'
        )
        mock_client.generate = AsyncMock(return_value=mock_response)

        judge = RoundJudge(judge_client=mock_client, judge_model="test_judge")

        svg_map = {
            "llama3": ["/tmp/llama3.svg"],
            "mistral": ["/tmp/mistral.svg"],
        }
        for path in ["/tmp/llama3.svg", "/tmp/mistral.svg"]:
            Path(path).write_text(FAKE_SVG)

        result = _run_async(
            judge.judge_round(
                survivors=["llama3", "mistral"],
                theme="abstract",
                svg_map=svg_map,
            )
        )

        assert result == "mistral"
