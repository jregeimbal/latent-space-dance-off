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
from rich.progress import TaskID, Progress

from ollama import AsyncClient
from pydantic import BaseModel, Field
from rich.console import Console

console = Console()

class Judgment(BaseModel):
    """Represents a single judgment made by a model about an SVG."""

    svg_id: str
    svg_model_name: str
    judged_by: str
    scores: Dict[str, Optional[float]] = Field(default_factory=dict, description="Dynamic scores for each criterion")
    total_score: Optional[float] = Field(None, ge=1, le=10)
    reason: Optional[str] = Field(None, description="Reasoning for the judgment")
    rank: Optional[int] = Field(None, description="Ranking among compared SVGs")
    winner_svg: Optional[str] = Field(None, description="Winner in head-to-head")
    criteria_used: List[str] = Field(default_factory=lambda: ["creativity", "aesthetics", "complexity"], description="List of criteria used for this judgment")


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

    async def judge_svg(self, model_client: AsyncClient, svg_path: Path, svg_content: str, svg_id: str, model_name: str, judge_name: str, generation_prompt: Optional[str] = None) -> Judgment:
        # Build prompt with dynamic criteria
        criteria = self.config.judging_criteria
        criterion_descriptions = {
            "creativity": "How original and innovative is this design?",
            "aesthetics": "How visually pleasing and well-composed is this SVG?",
            "complexity": "How sophisticated and detailed is this artwork?",
            "color_harmony": "How well do the colors work together?",
            "composition": "How balanced and well-structured is the composition?",
            "technical_quality": "How technically sound is the SVG code?",
            "accuracy": "How accurate is the SVG with what was prompted?",
        }
        
        criterion_prompts = ""
        score_fields = ""
        for criterion in criteria:
            description = criterion_descriptions.get(criterion, f"How good is this SVG for {criterion}?")
            criterion_prompts += f"\n**{criterion.capitalize()}**: {description}"
            score_fields += f'      "{criterion}_score": <1-10>,\n'
        
        prompt = f"""You are an expert art critic and AI judge.
You are judging an SVG artwork created by an AI.
Rate this SVG on a scale of 1-10 for each category:{criterion_prompts}

This SVG was generated from the following prompt:
{generation_prompt[:2000] if generation_prompt else 'No prompt provided.'}

Provide your scores as a JSON object:
{{
{score_fields}       "reason": "<brief explanation>"

SVG Content:
{svg_content[:5000]}

Respond with ONLY the JSON object."""

        try:
            response = await model_client.generate(
                model=model_name,
                prompt=prompt,
                stream=False
             )
            svg_output = getattr(response, 'response', None) or str(response)
            data = self._parse_json_response(svg_output)

             # Extract scores for each criterion
            scores = {}
            total = 0.0
            count = 0
            for criterion in self.config.judging_criteria:
                score_key = f'{criterion}_score'
                score_val = float(data.get(score_key, 5))
                scores[criterion] = score_val
                total += score_val
                count += 1
            
            avg_total = total / count if count > 0 else 5.0

            return Judgment(
                svg_id=svg_id,
                svg_model_name=model_name,
                judged_by=judge_name,
                scores=scores,
                total_score=avg_total,
                reason=data.get('reason', 'No reasoning provided'),
                rank=None,
                winner_svg=None,
                criteria_used=self.config.judging_criteria
             )
        except Exception as e:
            console.print(f"[red]Error during judging SVG {svg_id} with model {model_name}: {str(e)}[/red]")
            scores: Dict[str, Optional[float]] = {criterion: 5.0 for criterion in self.config.judging_criteria}
            return Judgment(
                svg_id=svg_id,
                svg_model_name=model_name,
                judged_by=judge_name,
                scores=scores,
                total_score=5.0,
                reason=f"Error during judging: {str(e)}",
                rank=None,
                winner_svg=None,
                criteria_used=self.config.judging_criteria
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
            data = self._parse_json_response(tokens if tokens else '{}')
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

    async def run_all_judgments(self, model_clients: Dict, svg_results: List, 
                                 num_judges: Optional[int] = None, 
                                 progress: Optional[Progress] = None,
                                 judge_task: Optional[TaskID] = None) -> List[Judgment]:
        judge_count = num_judges or self.num_judges
        judgments = []
        svg_list = svg_results.copy()
        random.shuffle(svg_list)

        for model_name in model_clients:
            for svg_result in svg_list:
                svg_id = f"{svg_result.model_name}_{svg_result.theme}"
                for judge_idx in [1]:
                    if progress and judge_task is not None:
                        progress.update(judge_task, description=f"Judging {svg_id} with {model_name}")

                    judgment = await self.judge_svg(
                        model_client=model_clients[model_name],
                        model_name=svg_result.model_name,
                        judge_name=f"judge_{model_name}_{judge_idx}",
                        svg_path=Path(svg_result.svg_path) if svg_result.svg_path else Path("/dev/null"),
                        svg_content=svg_result.svg_code,
                        svg_id=svg_id,
                        generation_prompt=svg_result.generation_prompt
                     )
                    # Update progress as judgments complete
                    if progress and judge_task is not None:
                        progress.update(judge_task, advance=len(judgments))
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

            # Aggregate scores for each criterion dynamically
            criterion_scores = {}
            for criterion in self.config.judging_criteria:
                scores = [j.scores.get(criterion, 5.0) for j in svg_judgments if j.scores.get(criterion) is not None]
                criterion_scores[criterion] = sum(scores) / len(scores) if scores else 5.0

             # Calculate total as simple average of criterion scores
            total = 0.0
            counted_criteria = [c for c in self.config.judging_criteria if c in criterion_scores]
            if counted_criteria:
                total += sum(criterion_scores[c] for c in counted_criteria)
                total = total / len(counted_criteria)

            aggregated[model_name] = {
                **criterion_scores,
                'total': total,
                'judgment_count': len(svg_judgments),
                'themes': [svg_result.theme for svg_result in svg_results if svg_result.model_name == model_name],
                'criteria': self.config.judging_criteria
            }
        return aggregated