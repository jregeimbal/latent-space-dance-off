"""Utility functions for latent-space-dance-off."""

import re
from pathlib import Path
from typing import Optional


def parse_svg_from_response(text):
    """Extract SVG code from LLM response text."""
    pattern_with_markdown = re.compile(r'```\w*\s*(<svg.*?</svg>)\s*```', re.DOTALL | re.IGNORECASE)
    match = pattern_with_markdown.search(text)
    if match:
        return match.group(1)
    
    pattern_raw = re.compile(r'(<svg.*?</svg>)', re.DOTALL | re.IGNORECASE)
    match = pattern_raw.search(text)
    if match:
        return match.group(1)
    
    start = text.lower().find('<svg')
    if start == -1:
        raise ValueError("No SVG code found in response")
    
    end = text.lower().find('</svg>', start)
    if end == -1:
        raise ValueError("SVG closing tag not found")
    
    return text[start:end + 6]


def generate_svg_prompt(theme, model_name):
    """Generate prompt for SVG generation task."""
    theme_prompts = {
        "abstract": f"""You are {model_name}, an AI that excels at creating abstract SVG artwork.
Generate a beautiful abstract SVG image using shapes, colors, and patterns.
Do not use any images or external resources.
Include these elements:
1. At least 5 different shapes or geometric forms
2. At least 3 different colors or gradients
3. Some form of symmetry or repeating pattern
4. A balanced composition

Respond with ONLY the SVG code, no explanations.
Your SVG should be at least 400x400 pixels.""",
        
        "landscape": f"""You are {model_name}, an AI landscape artist.
Generate a beautiful landscape SVG scene with depth and atmosphere.
- Include sky with gradient (sunset, sunrise, or night)
- Create at least 3 layers (foreground, midground, background)
- Add natural elements (mountains, trees, water, hills, clouds)
- Use at least 4 different colors for depth
- Respond with ONLY the SVG code, no explanations

Your SVG should be at least 800x600 pixels and use elements like:
<rect>, <circle>, <polygon>, <path>, <linearGradient>, <radialGradient>""",
        
        "portrait": f"""You are {model_name}, an AI portrait artist.
Generate a stylized SVG portrait artwork.
- Create a stylized human face or figure
- Use at least 3 different colors or shades
- Include artistic details (hair, clothing, accessories)
- Consider composition and balance
- Respond with ONLY the SVG code, no explanations

Your SVG should be at least 400x400 pixels and use elements like:
<ellipse>, <circle>, <path>, <rect>, <g> for grouping""",
        
        "object": f"""You are {model_name}, an AI object designer.
Generate a creative SVG illustration of an everyday object or concept.
- Create a recognizable main subject (cup, clock, flower, lightbulb, etc.)
- Use at least 3 different colors
- Add detail work (shading, highlights, patterns)
- Use clean, vector-style design
- Respond with ONLY the SVG code, no explanations

Your SVG should be at least 400x400 pixels and use elements like:
<rect>, <circle>, <path>, <polygon>, <g>""",
        
        "scene": f"""You are {model_name}, an AI scene creator.
Generate a creative SVG illustration of a complete scene.
- Create a detailed main subject with rich context
- Include background, midground, and foreground elements
- Use at least 4 different colors
- Consider composition, balance, and visual interest
- Respond with ONLY the SVG code, no explanations

Your SVG should be at least 600x400 pixels and use SVG elements creatively."""
    }
    
    return theme_prompts.get(theme, theme_prompts["abstract"])


def format_duration(seconds):
    """Format duration for display."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining = seconds % 60
        return f"{minutes}m {remaining:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remaining = seconds % 60
        return f"{hours}h {minutes}m {remaining:.1f}s"


def write_svg(svg, filepath):
    """Save SVG content to file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(svg)


def calculate_tokens_per_second(tokens, duration_ms):
    """Calculate tokens per second rate."""
    if duration_ms <= 0:
        return 0.0
    return tokens / (duration_ms / 1000.0)
