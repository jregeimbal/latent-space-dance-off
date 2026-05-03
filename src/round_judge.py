"""
Round Judge - Evaluates SVGs from all surviving models and eliminates the worst.

In a free-for-all round, all surviving models generate SVGs from the same theme.
The round judge ranks all models and returns the one to eliminate.
"""

import json
import random
import re
from pathlib import Path
from typing import Dict, List, Optional

from src.llm_client import BaseLLMClient, LLMChunk


class RoundJudge:
    """Judges tournament rounds and determines which model to eliminate."""

    def __init__(self, judge_client: BaseLLMClient, judge_model: str) -> None:
        self.judge_client = judge_client
        self.judge_model = judge_model

    async def judge_round(
        self,
        survivors: List[str],
        theme: str,
        svg_map: Dict[str, List[str]],
        num_svg_per_model: int = 2,
    ) -> str:
        """Judge a tournament round and return the model to eliminate.

        Args:
            survivors: List of model names still in the tournament.
            theme: The theme all models generated SVGs for.
            svg_map: Dict mapping model_name -> list of SVG file paths.
            num_svg_per_model: Number of SVGs each model generated.

        Returns:
            Model name to eliminate (lowest ranked).
        """
        # Collect all SVGs for this round
        svg_entries = []
        for model_name in survivors:
            paths = svg_map.get(model_name, [])
            if not paths:
                svg_entries.append((model_name, "[no SVG generated]"))
                continue
            # Use the first SVG (judge picks the best per model, we use the first for ranking)
            svg_path = Path(paths[0])
            try:
                svg_content = svg_path.read_text(encoding="utf-8")
            except Exception:
                svg_content = "[failed to read SVG]"
            svg_entries.append((model_name, svg_content))

        # Build SVG display text
        svg_text_parts = []
        for idx, (model_name, svg_content) in enumerate(svg_entries, 1):
            title = f"SVG #{idx} ({model_name}):"
            svg_text_parts.append(f"{title}\n{svg_content[:3000]}")

        svg_display = "\n\n".join(svg_text_parts)

        prompt = (
            f"You are judging a tournament round. All models created SVGs from the theme: '{theme}'.\n\n"
            f"Rank these models from best to worst. For each model, I'll show one of their SVGs.\n\n"
            f"{svg_display}\n\n"
            f"Respond with a JSON array of objects, one per model, ordered from best (rank 1) to worst (last):\n"
            f'[{{"model": "<model_name>", "rank": <1-N>}}, ...]\n\n'
            f"Respond with ONLY the JSON array, nothing else."
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
            rankings = self._parse_rankings(text, survivors)

            if rankings:
                # Last in rankings = worst = eliminate
                return rankings[-1]["model"]
            else:
                return self._fallback_elimination(survivors)
        except Exception:
            return self._fallback_elimination(survivors)

    def _parse_rankings(self, text: str, survivors: List[str]) -> List[dict]:
        """Parse JSON rankings from judge response."""
        # Try to extract JSON array
        json_pattern = re.compile(r'\[.*\]', re.DOTALL)
        match = json_pattern.search(text)
        if not match:
            return []

        try:
            data = json.loads(match.group(0))
            if not isinstance(data, list):
                return []
            # Validate each entry has model and rank
            valid = []
            for entry in data:
                if isinstance(entry, dict) and "model" in entry and "rank" in entry:
                    valid.append(entry)
            valid.sort(key=lambda e: e["rank"])
            return valid
        except (json.JSONDecodeError, IndexError):
            return []

    def _fallback_elimination(self, survivors: List[str]) -> str:
        """Randomly eliminate a model as fallback."""
        return random.choice(survivors)
