"""
SVG Judge module for latent-space-dance-off.

Judges SVG images using LLMs and aggregates scores for ranking.
"""

import json
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Judgment(BaseModel):
    """Represents a single judgment made by a model about an SVG."""

    svg_id: str
    judged_by: str
    creativity_score: Optional[float] = Field(None, ge=1, le=10)
    aesthetics_score: Optional[float] = Field(None, ge=1, le=10)
    complexity_score: Optional[float] = Field(None, ge=1, le=10)
    total_score: Optional[float] = Field(None, ge=1, le=10)
    reason: Optional[str] = Field(None, description="Reasoning for the judgment")
    rank: Optional[int] = Field(None, description="Ranking among compared SVGs")
    winner_svg: Optional[str] = Field(None, description="Winner in head-to-head")


class Comparison(BaseModel):
    """Head-to-head comparison between two SVGs."""

    svg1_model: str
    svg2_model: str
    winner: str
    reasoning: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))


class SVGJudge:
    """Judges SVG images using LLMs and aggregates scores."""

    def __init__(self, config) -> None:
        self.config = config
        self.num_judges = config.NUM_JUDGES if hasattr(config, 'NUM_JUDGES') else 3

    async def judge_svg(self, judge_model, svg_path: Path, svg_content: str, svg_id: str) -> Judgment:
        prompt = f"""You are an expert art critic and AI judge.
You are judging an SVG artwork created by an AI.
Rate this SVG on a scale of 1-10 for each category:

**Creativity**: How original and innovative is this design?
**Aesthetics**: How visually pleasing and well-composed is this SVG?
**Complexity**: How sophisticated and detailed is this artwork?

Provide your scores as a JSON object:
{{
    "creativity_score": <1-10>,
    "aesthetics_score": <1-10>,
    "complexity_score": <1-10>,
    "reason": "<brief explanation>"
}}

SVG Content:
{svg_content[:5000]}

Respond with ONLY the JSON object."""

        try:
            response = await judge_model.generate(
                model="llama3",
                prompt=prompt,
                format="json",
                stream=False
            )
            tokens = response.get('response') if isinstance(response, dict) else str(response)
            data = self._parse_json_response(tokens)

            return Judgment(
                svg_id=svg_id,
                judged_by="llama3",
                creativity_score=float(data.get('creativity_score', 5)),
                aesthetics_score=float(data.get('aesthetics_score', 5)),
                complexity_score=float(data.get('complexity_score', 5)),
                total_score=self._calculate_total(
                    float(data.get('creativity_score', 5)),
                    float(data.get('aesthetics_score', 5)),
                    float(data.get('complexity_score', 5))
                ),
                reason=data.get('reason', 'No reasoning provided')
            )
        except Exception as e:
            return Judgment(
                svg_id=svg_id,
                judged_by="llama3",
                creativity_score=5.0,
                aesthetics_score=5.0,
                complexity_score=5.0,
                total_score=5.0,
                reason=f"Error during judging: {str(e)}"
            )

    def _calculate_total(self, creativity: float, aesthetics: float, complexity: float) -> float:
        return (creativity + aesthetics + complexity) / 3

    def _parse_json_response(self, text: str) -> Dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        json_pattern = re.compile(r'```(?:json)?\s*({.*})\s*```', re.DOTALL)
        match = json_pattern.search(text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        json_start = text.find('{')
        json_end = text.rfind('}')
        if json_start >= 0 and json_end > json_start:
            try:
                return json.loads(text[json_start:json_end + 1])
            except json.JSONDecodeError:
                pass

        return {'creativity_score': 5, 'aesthetics_score': 5, 'complexity_score': 5, 'reason': 'Parsing fallback'}

    async def compare_svgs(self, judge_model, svg1_path: Path, svg2_path: Path, 
                          svg1_content: str, svg2_content: str, svg1_id: str, svg2_id: str) -> Comparison:
        prompt = f"""You are an art critic choosing between two AI-generated SVG images.
Choose which one is better and explain why.

SVG #1 ({svg1_id}):
{svg1_content[:2500]}

SVG #2 ({svg2_id}):
{svg2_content[:2500]}

Respond with a JSON object:
{{
    "winner": "<svg1_id or svg2_id>",
    "reasoning": "<why this one is better>"
}}

Respond with ONLY the JSON."""

        try:
            response = await judge_model.generate(
                model="llama3",
                prompt=prompt,
                format="json",
                stream=False
            )
            tokens = response.get('response') if isinstance(response, dict) else str(response)
            data = self._parse_json_response(tokens)
            winner = data.get('winner', svg1_id)
            return Comparison(
                svg1_model=svg1_id.split('_')[0],
                svg2_model=svg2_id.split('_')[0],
                winner=winner,
                reasoning=data.get('reasoning', 'No reasoning provided')
            )
        except Exception as e:
            return Comparison(
                svg1_model=svg1_id.split('_')[0],
                svg2_model=svg2_id.split('_')[0],
                winner=random.choice([svg1_id, svg2_id]),
                reasoning=f"Error: {str(e)}"
            )

    async def run_all_judgments(self, judge_models: List, svg_results: List, 
                                 num_judges: Optional[int] = None) -> List[Judgment]:
        judge_count = num_judges or self.num_judges
        selected_judges = judge_models[:] if len(judge_models) >= judge_count else judge_models * judge_count
        judgments = []
        svg_list = svg_results.copy()
        random.shuffle(svg_list)

        for svg_result in svg_list:
            svg_id = f"{svg_result.model_name}_{svg_result.theme}"
            for judge_model in selected_judges:
                judgment = await self.judge_svg(
                    judge_model=judge_model,
                    svg_path=Path(svg_result.svg_path) if svg_result.svg_path else None,
                    svg_content=svg_result.svg_code,
                    svg_id=svg_id
                )
                judgments.append(judgment)
        return judgments

    def aggregate_judgments(self, svg_results: List, judgments: List) -> Dict[str, Dict]:
        aggregated = {}
        for svg_result in svg_results:
            model_name = svg_result.model_name
            svg_id = f"{model_name}_{svg_result.theme}"
            svg_judgments = [j for j in judgments if j.svg_id == svg_id]
            if not svg_judgments:
                continue

            creativity_scores = [j.creativity_score for j in svg_judgments if j.creativity_score is not None]
            aesthetics_scores = [j.aesthetics_score for j in svg_judgments if j.aesthetics_score is not None]
            complexity_scores = [j.complexity_score for j in svg_judgments if j.complexity_score is not None]

            avg_creativity = sum(creativity_scores) / len(creativity_scores) if creativity_scores else 5.0
            avg_aesthetics = sum(aesthetics_scores) / len(aesthetics_scores) if aesthetics_scores else 5.0
            avg_complexity = sum(complexity_scores) / len(complexity_scores) if complexity_scores else 5.0

            aggregated[model_name] = {
                'creativity': avg_creativity,
                'aesthetics': avg_aesthetics,
                'complexity': avg_complexity,
                'total': (avg_creativity + avg_aesthetics + avg_complexity) / 3,
                'judgment_count': len(svg_judgments),
                'themes': [svg_result.theme for svg_result in svg_results if svg_result.model_name == model_name]
            }
        return aggregated