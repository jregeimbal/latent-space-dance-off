from unittest.mock import AsyncMock, patch
from src.dance_off import DanceOff
from src.benchmark import SVGResult
from tests.conftest import _run_async

FAKE_SVG = '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'


class TestDanceOffFallback:
    def test_fallback_on_invalid_model_name(self, tmp_path):
        """If judge returns invalid model name, eliminate lowest-scored survivor."""
        from unittest.mock import Mock
        config = Mock()
        config.OUTPUT_DIR = str(tmp_path)
        config.svgs_dir = tmp_path / "svgs"
        config.benchmarks_dir = tmp_path / "benchmarks"
        config.leaderboards_dir = tmp_path / "leaderboards"

        mock_client_a = AsyncMock()
        mock_client_b = AsyncMock()
        model_clients = {"model_high": mock_client_a, "model_low": mock_client_b}

        dance_off = DanceOff(
            model_clients=model_clients,
            config=config,
            theme_pool=["abstract"],
            output_dir=str(tmp_path),
            svg_per_model=1,
            judge_model="test_judge",
        )

        # Setup SVG results: model_high is faster (higher score), model_low is slower (lower score)
        def make_svg_result(model_name, theme="abstract", **kwargs):
            duration = 500.0 if model_name == "model_high" else 2000.0
            return SVGResult(
                model_name=model_name,
                theme=theme,
                svg_code=FAKE_SVG,
                svg_path=str(tmp_path / f"{model_name}.svg"),
                duration_ms=duration,
                status="success",
                pass_number=1,
            )

        with patch.object(dance_off.svg_generator, "generate_svg", side_effect=make_svg_result):
             with patch.object(dance_off, "_select_theme", return_value="abstract"):
                 # Mock RoundJudge.judge_round to return a hallucinated model name
                 with patch("src.round_judge.RoundJudge.judge_round", new_callable=AsyncMock) as mock_judge:
                     mock_judge.return_value = "hallucinated_model"
                     
                     result = _run_async(dance_off.run())

        # The eliminated model should be the one with the lowest score, which is 'model_low'
        assert result.rounds[0].eliminated == "model_low"
        assert result.champion == "model_high"
