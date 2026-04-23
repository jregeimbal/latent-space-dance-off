"""
SVG generator module for latent-space-dance-off.

Generates SVG images using LLMs and handles output management.
"""

import asyncio
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ollama import AsyncClient
from pydantic import BaseModel, Field


class SVGResult(BaseModel):
    """Represents the result of an SVG generation."""

    model_name: str
    """Name of the model that generated the SVG."""

    theme: str
    """Theme of the generated SVG (abstract, landscape, etc.)."""

    svg_code: str
    """The generated SVG code."""

    svg_path: Optional[str] = Field(None, description="Path where SVG was saved")

    duration_ms: float = Field(0, description="Duration in milliseconds")

    tokens_used: Optional[int] = Field(None, description="Number of tokens used")

    status: str = Field("success", description="Generation status (success/failed)")

    error_message: Optional[str] = Field(None, description="Error message if generation failed")


class SVGGenerator:
    """
    Generates SVG images using LLMs and manages output.

    This class handles:
        - Prompt generation for different SVG themes
        - SVG extraction from LLM responses
        - Saving SVG files to disk
        - Benchmark tracking

    Attributes:
        config: Configuration object for output paths
        svgs_dir: Path to SVGs output directory
    """

    def __init__(self, config) -> None:
        """Initialize SVGGenerator with configuration."""
        self.config = config
        self.svgs_dir = Path(config.svgs_dir)
        self.svgs_dir.mkdir(parents=True, exist_ok=True)

    def generate_abstract_svg_prompt(self, model_name: str) -> str:
        """Generate prompt for abstract SVG."""
        return f"""You are {model_name}, an AI artist specializing in abstract SVG art.
Generate a beautiful abstract SVG image using geometric shapes, colors, and patterns.
- Include at least 5 different shapes or geometric forms
- Use at least 3 different colors or gradients
- Include some symmetry or repeating patterns
- Make it visually interesting and balanced
- Respond with ONLY the SVG code, no explanations

Your SVG should be at least 400x400 pixels and use SVG elements like:
<rect>, <circle>, <ellipse>, <polygon>, <polyline>, <path>, <line>"""

    def generate_landscape_svg_prompt(self, model_name: str) -> str:
        """Generate prompt for landscape SVG."""
        return f"""You are {model_name}, an AI landscape artist.
Generate a beautiful landscape SVG scene with depth and atmosphere.
- Include sky with gradient (sunset, sunrise, or night)
- Create at least 3 layers (foreground, midground, background)
- Add natural elements (mountains, trees, water, hills, clouds)
- Use at least 4 different colors for depth
- Respond with ONLY the SVG code, no explanations

Your SVG should be at least 800x600 pixels and use elements like:
<rect>, <circle>, <polygon>, <path>, <linearGradient>, <radialGradient>"""

    def generate_portrait_svg_prompt(self, model_name: str) -> str:
        """Generate prompt for portrait SVG."""
        return f"""You are {model_name}, an AI portrait artist.
Generate a stylized SVG portrait artwork.
- Create a stylized human face or figure
- Use at least 3 different colors or shades
- Include artistic details (hair, clothing, accessories)
- Consider composition and balance
- Respond with ONLY the SVG code, no explanations

Your SVG should be at least 400x400 pixels and use elements like:
<ellipse>, <circle>, <path>, <rect>, <g> for grouping"""

    def generate_object_svg_prompt(self, model_name: str) -> str:
        """Generate prompt for object SVG."""
        return f"""You are {model_name}, an AI object designer.
Generate a creative SVG illustration of an everyday object or concept.
- Create a recognizable main subject (cup, clock, flower, lightbulb, etc.)
- Use at least 3 different colors
- Add detail work (shading, highlights, patterns)
- Use clean, vector-style design
- Respond with ONLY the SVG code, no explanations

Your SVG should be at least 400x400 pixels and use elements like:
<rect>, <circle>, <path>, <polygon>, <g>"""

    def generate_scene_svg_prompt(self, model_name: str) -> str:
        """Generate prompt for scene SVG."""
        return f"""You are {model_name}, an AI scene creator.
Generate a creative SVG illustration of a complete scene.
- Create a detailed main subject with rich context
- Include background, midground, and foreground elements
- Use at least 4 different colors
- Consider composition, balance, and visual interest
- Respond with ONLY the SVG code, no explanations

Your SVG should be at least 600x400 pixels and use SVG elements creatively."""

    def _get_svg_prompt(self, theme: str, model_name: str) -> str:
        """Get appropriate SVG prompt based on theme."""
        prompts = {
            "abstract": self.generate_abstract_svg_prompt,
            "landscape": self.generate_landscape_svg_prompt,
            "portrait": self.generate_portrait_svg_prompt,
            "object": self.generate_object_svg_prompt,
            "scene": self.generate_scene_svg_prompt,
        }

        prompt_func = prompts.get(theme)
        if not prompt_func:
            prompt_func = self.generate_abstract_svg_prompt

        return prompt_func(model_name)

    def _extract_svg_from_response(self, text: str) -> str:
        """Extract SVG code from LLM response."""
        # Pattern 1: SVG in markdown code blocks
        pattern_with_markdown = re.compile(r'```(?:svg)?\s*(<svg.*?</svg>)\s*```', re.DOTALL | re.IGNORECASE)
        match = pattern_with_markdown.search(text)
        if match:
            return match.group(1)

        # Pattern 2: Raw SVG
        pattern_raw = re.compile(r'(<svg.*?</svg>)', re.DOTALL | re.IGNORECASE)
        match = pattern_raw.search(text)
        if match:
            return match.group(1)

        # Try to find SVG by looking for opening and closing tags
        start = text.lower().find('<svg')
        if start == -1:
            raise ValueError("No SVG code found in response")

        end = text.lower().find('</svg>', start)
        if end == -1:
            raise ValueError("SVG closing tag not found")

        return text[start:end + 6]

    async def generate_svg(self, model_client: AsyncClient, theme: str, model_name: str, run_id: str = None) -> SVGResult:
        """Generate SVG by calling the model."""
        start_time = time.perf_counter()

        try:
            # Generate prompt
            prompt = self._get_svg_prompt(theme, model_name)

            # Call the model
            response = await model_client.generate(
                model=model_name,
                prompt=prompt,
                stream=False
            )

             # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
              # Ollama returns Model object with attr 'response', not dict
            svg_output = getattr(response, 'response', None) or str(response)
            tokens_evaluated = getattr(response, 'prompt_eval_count', None)
            tokens = svg_output
            
             # Extract SVG
            svg_code = self._extract_svg_from_response(svg_output)

            # Determine filename
            if run_id:
                svg_filename = f"{run_id}_{model_name.replace('/', '_')}_{theme}.svg"
            else:
                svg_filename = f"{model_name.replace('/', '_')}_{theme}.svg"

            svg_path = self.svgs_dir / svg_filename

            # Save SVG
            await self._save_svg(svg_code, svg_path)

            return SVGResult(
                model_name=model_name,
                theme=theme,
                svg_code=svg_code,
                svg_path=str(svg_path),
                duration_ms=duration_ms,
                tokens_used=tokens_evaluated,
                status="success"
             )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return SVGResult(
                model_name=model_name,
                theme=theme,
                svg_code="",
                svg_path=None,
                duration_ms=duration_ms,
                tokens_used=None,
                status="failed",
                error_message=str(e)
            )

    async def _save_svg(self, svg_code: str, filepath: Path) -> None:
        """Save SVG code to file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(svg_code)

    async def generate_multiple_svgs(
        self,
        model_clients: Dict[str, AsyncClient],
        themes: List[str],
        concurrency: int = 5
    ) -> List[SVGResult]:
        """Generate SVGs for all models and themes with rate limiting."""
        semaphore = asyncio.Semaphore(concurrency)

        async def generate_task(model_name: str):
            async with semaphore:
                model_client = model_clients[model_name]
                results = []
                for theme in themes:
                    result = await self.generate_svg(model_client, theme, model_name)
                    results.append(result)
                return results

        # Get all model names
        model_names = list(model_clients.keys())

        # Generate tasks for all models
        tasks = [generate_task(model_name) for model_name in model_names]

        # Execute all tasks and flatten results
        all_results = []
        for results in await asyncio.gather(*tasks):
            all_results.extend(results)

        return all_results
