"""Utility functions for latent-space-dance-off."""

import contextlib
import io
import os
import re
import tempfile

import cairosvg
from PIL import Image


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



# ─── SVG → ASCII art ─────────────────────────────────────────────────────────

def make_clickable_link(path: str | os.PathLike[str], text: str | None = None) -> str:
    """Wrap text in OSC 8 terminal hyperlink escape sequences."""
    if text is None:
        text = str(path)
    # OSC 8 hyperlink format: \033]8;;URI\033\\text\033]8;;\033\\
    uri = f"file://{os.path.abspath(path)}"
    return f"\033]8;;{uri}\033\\{text}\033]8;;\033\\"


def svg_to_ascii(svg_code: str, width: int = 120, use_ansi: bool = False, use_ansi16: bool = False) -> str:
    """Convert SVG code to ASCII art for terminal display.

    Uses cairosvg to render SVG to PNG, img2ascii for character layout,
    then samples colors from the rendered image for ANSI color support.

    Args:
        svg_code: The SVG XML string
        width: Output width in characters
        use_ansi: Whether to use ANSI color codes

    Returns:
        ASCII art string
    """
    from img2ascii.text_gen import generate_ascii_t

    if not svg_code or not svg_code.strip():
        return "[empty SVG]"

    # Render SVG to PNG bytes using cairosvg
    png_bytes = cairosvg.svg2png(bytestring=svg_code.encode("utf-8"))
    assert png_bytes is not None, "cairosvg failed to render SVG"
    color_image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    gray_image = color_image.convert("L")

    # Calculate height maintaining character aspect ratio (chars ~2x taller than wide)
    img_w, img_h = gray_image.size
    cell_ratio = 2.0
    height = max(int(width * img_h / img_w / cell_ratio), 1)

    # Resize both images to target dimensions
    gray_image = gray_image.resize((width, height), Image.Resampling.LANCZOS)
    color_image = color_image.resize((width, height), Image.Resampling.LANCZOS)

    # Use img2ascii to get ASCII character layout
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "input.png")
        out_path = os.path.join(tmpdir, "output.txt")
        gray_image.save(img_path)

        with contextlib.redirect_stdout(open(os.devnull, "w")):
            generate_ascii_t(inputfile=img_path, outputfile=out_path, kernel=1, density=0.3)

        with open(out_path, "r") as f:
            ascii_lines = f.read().rstrip("\n").split("\n")

    if use_ansi:
        # Build color-coded output by sampling RGB from the resized image
        colored_lines = []
        for row, line in enumerate(ascii_lines):
            line_parts = []
            last_color = None
            for col, char in enumerate(line):
                pixel = color_image.getpixel((col, row))
                if isinstance(pixel, tuple):
                    r, g, b = pixel
                else:
                    r = g = b = int(pixel or 0)
                ansi = _rgb_to_ansi16(r, g, b) if use_ansi16 else _rgb_to_ansi256(r, g, b)
                if ansi != last_color:
                    line_parts.append(f"\033[38;5;{ansi}m")
                    last_color = ansi
                line_parts.append(char)
            colored_lines.append("".join(line_parts) + "\033[0m")
        return "\n".join(colored_lines)

    return "\n".join(ascii_lines)


def _rgb_to_ansi16(r: int, g: int, b: int) -> int:
    """Map RGB color to nearest 256-color ANSI code."""
    colors = {
        (0,0,0): 0, (0,0,128): 4, (0,128,0): 2, (0,128,128): 6,
        (128,0,0): 1, (128,0,128): 5, (128,128,0): 3, (192,192,192): 7,
        (128,128,128): 8, (255,0,0): 9, (0,255,0): 10, (255,255,0): 11,
        (0,0,255): 12, (255,0,255): 13, (0,255,255): 14, (255,255,255): 15,
    }
    closest = min(colors.keys(), key=lambda c: (c[0]-r)**2 + (c[1]-g)**2 + (c[2]-b)**2)
    return colors[closest]

def _rgb_to_ansi256(r, g, b):
    # Define valid intensity levels for the color cube
    cube_levels = [0x00, 0x5f, 0x87, 0xaf, 0xd7, 0xff]
    
    # Check if it's a grayscale color (R=G=B)
    if r == g == b:
        # Find nearest grayscale index (232-255)
        # Grayscale steps are 8 + 10*y for y in 0..23
        y = round((r - 8) / 10)
        if 0 <= y <= 23:
            return 232 + y
        # Fallback to nearest cube if out of grayscale range
        # (Though grayscale range covers most grays)
    
    # Round each component to nearest cube level
    def round_to_cube(val):
        return min(range(len(cube_levels)), key=lambda i: abs(cube_levels[i] - val))
    
    r_idx = round_to_cube(r)
    g_idx = round_to_cube(g)
    b_idx = round_to_cube(b)
    
    # Calculate ANSI index for 216-color cube
    return 16 + (r_idx * 36) + (g_idx * 6) + b_idx