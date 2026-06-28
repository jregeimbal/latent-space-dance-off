"""Tests for dance-off module."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dance_off import RoundResult, DanceOff, DanceOffResult
from src.benchmark import SVGResult
from tests.conftest import _run_async

FAKE_SVG = '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'


class TestRoundResult:
    def test_creation(self):
        rr = RoundResult(
            round_num=1,
            theme="abstract",
            rankings=[("model_a", 8.0), ("model_b", 5.0)],
            eliminated="model_b",
        )
        assert rr.round_num == 1
        assert rr.theme == "abstract"
        assert rr.eliminated == "model_b"
        assert len(rr.svg_results) == 0

    def test_with_svg_results(self):
        svg = SVGResult(
            model_name="model_a",
            theme="abstract",
            svg_code=FAKE_SVG,
            status="success",
        )
        rr = RoundResult(
            round_num=1,
            theme="abstract",
            rankings=[("model_a", 8.0)],
            eliminated="model_b",
            svg_results=[svg],
        )
        assert len(rr.svg_results) == 1
        assert rr.svg_results[0].model_name == "model_a"


class TestDanceOffResult:
    def test_to_dict(self):
        tr = DanceOffResult(
            run_id="test-run",
            timestamp="2024-01-01T00:00:00",
            models=["model_a", "model_b"],
            champion="model_a",
        )
        d = tr.to_dict()
        assert d["run_id"] == "test-run"
        assert d["champion"] == "model_a"
        assert d["models"] == ["model_a", "model_b"]
        assert d["rounds"] == []

    def test_to_dict_with_rounds(self):
        svg = SVGResult(
            model_name="model_a",
            theme="abstract",
            svg_code=FAKE_SVG,
            status="success",
            duration_ms=1000.0,
            pass_number=1,
        )
        rr = RoundResult(
            round_num=1,
            theme="abstract",
            rankings=[("model_a", 8.0)],
            eliminated="model_b",
            svg_results=[svg],
        )
        tr = DanceOffResult(
            run_id="test-run",
            timestamp="2024-01-01T00:00:00",
            models=["model_a", "model_b"],
            rounds=[rr],
            champion="model_a",
        )
        d = tr.to_dict()
        assert len(d["rounds"]) == 1
        assert d["rounds"][0]["round_num"] == 1
        assert d["rounds"][0]["eliminated"] == "model_b"
        assert len(d["rounds"][0]["svg_results"]) == 1

    def test_from_dict_roundtrip(self):
        svg = SVGResult(
            model_name="model_a",
            theme="abstract",
            svg_code=FAKE_SVG,
            status="success",
            duration_ms=1000.0,
            pass_number=1,
        )
        rr = RoundResult(
            round_num=1,
            theme="abstract",
            rankings=[("model_a", 8.0)],
            eliminated="model_b",
            svg_results=[svg],
        )
        tr = DanceOffResult(
            run_id="test-run",
            timestamp="2024-01-01T00:00:00",
            models=["model_a", "model_b"],
            rounds=[rr],
            champion="model_a",
        )
        d = tr.to_dict()
        tr2 = DanceOffResult.from_dict(d)
        assert tr2.run_id == tr.run_id
        assert tr2.champion == tr.champion
        assert len(tr2.rounds) == 1
        assert tr2.rounds[0].eliminated == "model_b"

    def test_from_dict_missing_required_field_raises(self):
        """DanceOffResult.from_dict raises KeyError for missing required fields."""
        with pytest.raises(KeyError, match="run_id"):
            DanceOffResult.from_dict({"timestamp": "2024-01-01", "models": []})

        with pytest.raises(KeyError, match="timestamp"):
            DanceOffResult.from_dict({"run_id": "test"})

        with pytest.raises(KeyError, match="models"):
            DanceOffResult.from_dict({"run_id": "test", "timestamp": "2024-01-01"})


class TestDanceOff:
    def _make_mock_config(self, tmp_path):
        """Create a minimal mock config for dance-off tests."""
        from unittest.mock import Mock
        config = Mock()
        config.OUTPUT_DIR = str(tmp_path)
        config.svgs_dir = tmp_path / "svgs"
        config.benchmarks_dir = tmp_path / "benchmarks"
        config.LEADERBOARDS_DIR = tmp_path / "leaderboards"
        return config

    def test_dance_off_reduces_models_to_champion(self, tmp_path):
        """Dance-off eliminates models until one champion remains."""
        config = self._make_mock_config(tmp_path)

        # Mock SVG generation: all models succeed
        mock_client_a = AsyncMock()
        mock_client_b = AsyncMock()
        mock_client_c = AsyncMock()

        model_clients = {
            "model_a": mock_client_a,
            "model_b": mock_client_b,
            "model_c": mock_client_c,
        }

        dance_off = DanceOff(
            model_clients=model_clients,
            config=config,
            theme_pool=["abstract", "landscape", "portrait"],
            output_dir=str(tmp_path),
            svg_per_model=1,
            judge_model="test_judge",
        )

        # Mock generate_svg to return success
        def make_svg_result(model_name, theme="abstract", **kwargs):
            return SVGResult(
                model_name=model_name,
                theme=theme,
                svg_code=FAKE_SVG,
                svg_path=str(tmp_path / f"{model_name}.svg"),
                duration_ms=1000.0,
                status="success",
                pass_number=1,
            )

        with patch.object(dance_off.svg_generator, "generate_svg", side_effect=make_svg_result):
            # Mock theme selection to always return "abstract"
            with patch.object(dance_off, "_select_theme", return_value="abstract"):
                # Mock round judging: eliminate model_b first, then model_c
                with patch.object(dance_off, "_judge_round", side_effect=["model_b", "model_c"]):
                    result = _run_async(dance_off.run())

        assert result.champion == "model_a"
        assert len(result.rounds) == 2
        assert result.rounds[0].eliminated == "model_b"
        assert result.rounds[1].eliminated == "model_c"

    def test_dance_off_two_models_one_round(self, tmp_path):
        """Dance-off with 2 models completes in 1 round."""
        config = self._make_mock_config(tmp_path)

        mock_client_a = AsyncMock()
        mock_client_b = AsyncMock()

        model_clients = {"model_a": mock_client_a, "model_b": mock_client_b}

        dance_off = DanceOff(
            model_clients=model_clients,
            config=config,
            theme_pool=["abstract"],
            output_dir=str(tmp_path),
            svg_per_model=1,
            judge_model="test_judge",
        )

        def make_svg_result(model_name, theme="abstract", **kwargs):
            return SVGResult(
                model_name=model_name,
                theme=theme,
                svg_code=FAKE_SVG,
                svg_path=str(tmp_path / f"{model_name}.svg"),
                duration_ms=1000.0,
                status="success",
                pass_number=1,
            )

        with patch.object(dance_off.svg_generator, "generate_svg", side_effect=make_svg_result):
            with patch.object(dance_off, "_select_theme", return_value="abstract"):
                with patch.object(dance_off, "_judge_round", return_value="model_b"):
                    result = _run_async(dance_off.run())

        assert result.champion == "model_a"
        assert len(result.rounds) == 1

    def test_save_result_writes_json(self, tmp_path):
        """DanceOff.save_result writes dance_off.json to the output directory."""
        tr = DanceOffResult(
            run_id="test-run-123",
            timestamp="2024-01-01T00:00:00",
            models=["model_a"],
            champion="model_a",
        )

        dance_off = DanceOff(
            model_clients={"dummy": AsyncMock()},
            config=MagicMock(),
            theme_pool=["abstract"],
            output_dir=str(tmp_path),
        )

        filepath = dance_off.save_result(tr, str(tmp_path))
        assert filepath.exists()
        assert filepath.name == "dance_off.json"

        with open(filepath) as f:
            data = json.load(f)
        assert data["run_id"] == "test-run-123"
        assert data["champion"] == "model_a"

    def test_build_rankings_handles_failed_svgs(self, tmp_path):
        """_build_rankings puts models with failed SVGs at the bottom."""
        dance_off = DanceOff(
            model_clients={"dummy": AsyncMock()},
            config=MagicMock(),
            theme_pool=["abstract"],
            output_dir=str(tmp_path),
        )

        svg_results = [
            SVGResult(model_name="model_a", theme="abstract", svg_code=FAKE_SVG, status="success", duration_ms=500.0, pass_number=1),
            SVGResult(model_name="model_b", theme="abstract", svg_code="", status="failed", pass_number=1),
        ]

        rankings = dance_off._build_rankings(svg_results, ["model_a", "model_b"])

        # model_a should be first (success), model_b last (failed)
        assert rankings[0][0] == "model_a"
        assert rankings[1][0] == "model_b"
        assert rankings[1][1] == 0.0
