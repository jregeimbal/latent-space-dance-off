"""
Theme Selector - Audience-judge picks themes for tournament rounds.

Uses a judge LLM to select themes from a pool, avoiding repeats from past rounds.
"""

from typing import List, Optional

from src.llm_client import BaseLLMClient, LLMChunk


class ThemeSelector:
    """Selects themes for tournament rounds using a judge LLM."""

    def __init__(self, judge_client: BaseLLMClient, judge_model: str) -> None:
        self.judge_client = judge_client
        self.judge_model = judge_model

    async def select_theme(
        self,
        pool: List[str],
        round_num: int,
        used_themes: List[str],
    ) -> str:
        """Select a theme for the current round.

        Args:
            pool: Available themes to choose from.
            round_num: Current round number (1-based).
            used_themes: Themes already used in previous rounds.

        Returns:
            Selected theme string.
        """
        available = [t for t in pool if t not in used_themes]
        if not available:
            available = pool  # Allow repeats if pool exhausted

        prompt = (
            f"You are the audience judge for a tournament round. "
            f"This is round {round_num}. "
            f"Available themes: {', '.join(pool)}. "
            f"Themes already used: {', '.join(used_themes) if used_themes else 'none'}. "
            f"Pick one theme from the available list that would make for an interesting round. "
            f"Respond with ONLY the theme name, nothing else."
        )

        try:
            # Clear context first
            await self.judge_client.generate(
                model=self.judge_model,
                prompt="/clear",
                stream=False,
            )

            response = await self.judge_client.generate(
                model=self.judge_model,
                prompt=prompt,
                stream=False,
            )
            text = getattr(response, "response", "") or str(response)
            theme = text.strip().strip('"').strip("'").strip()
            if theme and theme in pool:
                return theme
            # Fallback: pick first available
            return available[0]
        except Exception:
            return available[0]
