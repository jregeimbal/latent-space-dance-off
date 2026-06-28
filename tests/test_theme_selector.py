"""Tests for theme_selector module."""

from unittest.mock import AsyncMock, MagicMock


from src.theme_selector import ThemeSelector
from tests.conftest import _run_async


class TestThemeSelector:
    def test_select_theme_picks_from_pool(self):
        """ThemeSelector picks a theme from the available pool."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = "landscape"
        mock_client.generate = AsyncMock(return_value=mock_response)

        selector = ThemeSelector(judge_client=mock_client, judge_model="test_model")

        result = _run_async(
            selector.select_theme(
                pool=["abstract", "landscape", "portrait"],
                round_num=1,
                used_themes=[],
            )
        )

        assert result == "landscape"

    def test_select_theme_avoids_used_themes(self):
        """ThemeSelector skips themes already used in past rounds."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = "portrait"
        mock_client.generate = AsyncMock(return_value=mock_response)

        selector = ThemeSelector(judge_client=mock_client, judge_model="test_model")

        result = _run_async(
            selector.select_theme(
                pool=["abstract", "landscape", "portrait"],
                round_num=2,
                used_themes=["abstract", "landscape"],
            )
        )

        assert result == "portrait"

    def test_select_theme_falls_back_when_judge_fails(self):
        """ThemeSelector falls back to first available theme on judge error."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=Exception("connection error"))

        selector = ThemeSelector(judge_client=mock_client, judge_model="test_model")

        result = _run_async(
            selector.select_theme(
                pool=["abstract", "landscape"],
                round_num=1,
                used_themes=[],
            )
        )

        assert result == "abstract"

    def test_select_theme_cycles_when_pool_exhausted(self):
        """ThemeSelector allows repeats when all themes have been used."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = "abstract"
        mock_client.generate = AsyncMock(return_value=mock_response)

        selector = ThemeSelector(judge_client=mock_client, judge_model="test_model")

        result = _run_async(
            selector.select_theme(
                pool=["abstract", "landscape"],
                round_num=3,
                used_themes=["abstract", "landscape"],
            )
        )

        assert result == "abstract"

    def test_select_theme_strips_quotes(self):
        """ThemeSelector strips surrounding quotes from judge response."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.response = '"landscape"'
        mock_client.generate = AsyncMock(return_value=mock_response)

        selector = ThemeSelector(judge_client=mock_client, judge_model="test_model")

        result = _run_async(
            selector.select_theme(
                pool=["abstract", "landscape"],
                round_num=1,
                used_themes=[],
            )
        )

        assert result == "landscape"
