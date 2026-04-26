"""
HTML report generator for latent-space-dance-off benchmark results.

Generates an interactive HTML page displaying SVG results in a grid layout
with models on the X-axis and themes on the Y-axis.
"""

import json
import html
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel


class SVGCellData(BaseModel):
    """Data for a single cell in the benchmark grid."""
    model_name: str
    theme: str
    svg_code: str
    svg_path: Optional[str] = None
    duration_ms: float = 0
    tokens_used: Optional[int] = None
    status: str = "success"
    error_message: Optional[str] = None


def calculate_tokens_per_second(tokens: Optional[int], duration_ms: float) -> float:
    """Calculate tokens per second from token count and duration."""
    if duration_ms > 0 and tokens is not None:
        return tokens / (duration_ms / 1000.0)
    return 0.0


def format_duration(ms: float) -> str:
    """Format duration in milliseconds to human-readable string."""
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.2f}h"


def generate_benchmark_html(run_data_dict: dict, output_path: Path) -> str:
    """
    Generate an HTML page for benchmark results.

    Args:
        run_data_dict: Dictionary with run_id, svgs, model_list, themes, judgments
        output_path: Path where the HTML file will be saved

    Returns:
        The path to the generated HTML file
    """
    models = run_data_dict.get("model_list", [])
    themes = run_data_dict.get("themes", [])
    svgs = run_data_dict.get("svgs", [])
    run_id = run_data_dict.get("run_id", "unknown")
    timestamp = run_data_dict.get("timestamp", "")
    judgments = run_data_dict.get("judgments", [])
    criteria = run_data_dict.get("criteria", ["creativity", "aesthetics", "complexity"])

    criteria_display = ", ".join(c.capitalize() for c in criteria)

    svg_lookup = {}
    for svg in svgs:
        key = (svg["model_name"], svg["theme"])
        svg_lookup[key] = svg

    judgments_lookup = {}
    for j in judgments:
        svg_id = j.get("svg_id", "")
        if svg_id not in judgments_lookup:
            judgments_lookup[svg_id] = []
        judgments_lookup[svg_id].append(j)

    html_content = _build_html(run_id, timestamp, models, themes, svg_lookup, judgments_lookup, criteria_display)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return str(output_path)


def _build_html(run_id: str, timestamp: str, models: List[str],
                themes: List[str], svg_lookup: dict, judgments_lookup: dict,
                criteria_display: str = "Creativity, Aesthetics, Complexity") -> str:

    cells_html = []
    for theme in themes:
        for model in models:
            key = (model, theme)
            svg_data = svg_lookup.get(key)

            if svg_data and svg_data.get("status") == "success":
                svg_code = svg_data.get("svg_code", "")
                duration_ms = svg_data.get("duration_ms", 0)
                tokens = svg_data.get("tokens_used")
                tps = calculate_tokens_per_second(tokens, duration_ms)
                svg_path = svg_data.get("svg_path", "")
                svg_id = f"{model}_{theme}"
                cell_judgments = judgments_lookup.get(svg_id, [])
                avg_score = _calculate_avg_score(cell_judgments) if cell_judgments else None
                cells_html.append(_build_success_cell(model, theme, svg_code, duration_ms,
                                                       tokens, tps, svg_path, avg_score, cell_judgments))
            else:
                error_msg = ""
                if svg_data:
                    error_msg = svg_data.get("error_message", "Generation failed")
                cells_html.append(_build_error_cell(model, theme, error_msg))

    theme_labels_html = ""
    for theme in themes:
        short_theme = theme if len(theme) <= 40 else theme[:37] + "..."
        escaped_theme = html.escape(theme)
        theme_labels_html += f'<div class="theme-label" title="{escaped_theme}">{html.escape(short_theme)}</div>\n'

    model_labels_html = ""
    for model in models:
        model_labels_html += f'<div class="model-label">{html.escape(model)}</div>\n'

    dynamic_grid_css = f"""
      .grid-container {{
    display: grid;
    grid-template-columns: 180px repeat({len(models)}, 1fr);
    grid-template-rows: 50px repeat({len(themes)}, 1fr);
    gap: 8px;
    min-height: 600px;
      }}
"""

    responsive_css = f"""
      @media (max-width: 1200px) {{
       .grid-container {{
    grid-template-columns: 120px repeat({len(models)}, 1fr);
       }}
      }}
"""

    all_css = _JUDGING_CSS + dynamic_grid_css + responsive_css

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Latent Space Dance Off - {html.escape(run_id)}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0f0f0f;
            color: #e0e0e0;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border-radius: 12px;
            border: 1px solid #333;
        }}
        .header h1 {{
            font-size: 2em;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 8px;
        }}
         .header .meta {{
             color: #888;
             font-size: 0.9em;
         }}
         .corner {{
             background: transparent;
         }}
         .model-label {{
             background: #1a1a2e;
             display: flex;
             align-items: center;
             justify-content: center;
             padding: 8px;
             font-weight: 600;
             font-size: 0.85em;
             color: #00d2ff;
             border-radius: 8px;
             text-align: center;
             word-break: break-word;
             overflow-wrap: break-word;
             white-space: normal;
             border: 1px solid #333;
         }}
         .theme-label {{
             background: #1a1a2e;
             display: flex;
             align-items: center;
             padding: 8px 12px;
             font-weight: 500;
             font-size: 0.8em;
             color: #b388ff;
             border-radius: 8px;
             border: 1px solid #333;
             overflow-wrap: break-word;
             white-space: normal;
         }}
         .cell {{
             background: #1a1a1a;
             border-radius: 12px;
             border: 1px solid #333;
             padding: 12px;
             display: flex;
             flex-direction: column;
             min-height: 350px;
             overflow: hidden;
         }}
         .cell.failed {{
             border-color: #ff4444;
         }}
         .cell-header {{
             display: flex;
             justify-content: space-between;
             align-items: center;
             margin-bottom: 8px;
             padding-bottom: 8px;
             border-bottom: 1px solid #333;
         }}
         .cell-model {{
             font-weight: 600;
             color: #00d2ff;
             font-size: 0.8em;
         }}
         .cell-score {{
             font-weight: 700;
             color: #4caf50;
             font-size: 1em;
         }}
{all_css}
        .svg-container {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #ffffff;
            border-radius: 8px;
            padding: 8px;
            overflow: hidden;
            min-height: 200px;
        }}
        .svg-container svg {{
            max-width: 100%;
            max-height: 280px;
            width: auto;
            height: auto;
        }}
        .cell-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 6px;
            margin-top: 10px;
            padding-top: 8px;
            border-top: 1px solid #333;
        }}
        .stat {{
            text-align: center;
            padding: 6px;
            background: #252525;
            border-radius: 6px;
        }}
        .stat-value {{
            font-weight: 700;
            font-size: 0.95em;
            color: #fff;
        }}
        .stat-label {{
            font-size: 0.7em;
            color: #888;
            margin-top: 2px;
        }}
        .error-cell {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            flex: 1;
            color: #ff6b6b;
        }}
        .error-cell .error-icon {{
            font-size: 3em;
            margin-bottom: 10px;
        }}
        .error-cell .error-message {{
            font-size: 0.85em;
            text-align: center;
            padding: 0 10px;
            color: #ff8a8a;
        }}
        .svg-path {{
            font-size: 0.65em;
            color: #666;
            margin-top: 4px;
            word-break: break-all;
            text-align: center;
        }}
        .judge-block {{
            background: #1e1e1e;
            border: 1px solid #333;
            border-radius: 8px;
            overflow: hidden;
        }}
        .judge-block-header {{
            padding: 6px 10px;
            background: #252525;
            border-bottom: 1px solid #333;
            font-size: 0.8em;
            color: #f0a500;
        }}
        .judge-block-body {{
            padding: 8px 10px;
            font-size: 0.8em;
            color: #ccc;
        }}
        .judge-score-row {{
            margin-bottom: 4px;
            padding: 2px 0;
        }}
        .judge-score-value {{
            color: #4caf50;
            font-weight: 600;
        }}
        .judge-reason {{
            color: #aaa;
            font-style: italic;
            margin-top: 6px;
            padding-top: 6px;
            border-top: 1px solid #333;
        }}
        .judge-prompt-details {{
            margin-top: 8px;
            background: #151515;
            border-radius: 4px;
            border: 1px solid #2a2a2a;
        }}
        .judge-prompt-summary {{
            padding: 6px 12px;
            font-size: 0.85em;
            color: #00d2ff;
            cursor: pointer;
            user-select: none;
        }}
        .judge-prompt-details:hover .judge-prompt-summary {{
            background: #1e1e1e;
        }}
        .judge-prompt-text {{
            display: block;
            padding: 8px 12px;
            margin: 0;
            background: #0d0d0d;
            color: #7fff7f;
            font-family: 'SF Mono', 'Fira Code', monospace;
            font-size: 0.75em;
            line-height: 1.4;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 300px;
            overflow-y: auto;
            border-top: 1px solid #2a2a2a;
        }}
{responsive_css}
    </style>
</head>
<body>
    <div class="header">
        <h1>Latent Space Dance Off</h1>
        <div class="meta">
            Run: {html.escape(run_id)} | Timestamp: {html.escape(timestamp)} |
            Models: {len(models)} | Themes: {len(themes)}
        </div>
        <div class="criteria-display">
            Judging Criteria: <span>{html.escape(criteria_display)}</span>
        </div>
    </div>
    <div class="grid-container">
        <div class="corner"></div>
{model_labels_html}
{"".join(_build_row_html(theme, models, svg_lookup, judgments_lookup) for theme in themes)}
    </div>
</body>
</html>'''


_JUDGING_CSS = '''
        .judging-summary {
            margin-top: 8px;
        }
        .judging-summary summary {
            list-style: none;
            cursor: pointer;
        }
        .judging-summary summary::-webkit-details-marker {
            display: none;
        }
        .show-judges-btn {
            display: inline-block;
            padding: 6px 12px;
            background: #252525;
            border: 1px solid #333;
            border-radius: 6px;
            color: #00d2ff;
            font-size: 0.8em;
            cursor: pointer;
            transition: background 0.2s;
        }
        .show-judges-btn:hover {
            background: #1e1e1e;
        }
        .show-judges-btn::after {
            content: ' [v]';
            color: #888;
            margin-left: 4px;
        }
        .judging-summary[open] .show-judges-btn::after {
            content: ' [^]';
        }
        .judges-collapsible {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 8px;
        }
'''


def _build_row_html(theme: str, models: List[str], svg_lookup: dict,
                     judgments_lookup: dict) -> str:
    """Build HTML for a single row (theme label + cells)."""
    escaped_theme = html.escape(theme)
    cells = []
    for model in models:
        key = (model, theme)
        svg_data = svg_lookup.get(key)
        if svg_data and svg_data.get("status") == "success":
            svg_code = svg_data.get("svg_code", "")
            duration_ms = svg_data.get("duration_ms", 0)
            tokens = svg_data.get("tokens_used")
            tps = calculate_tokens_per_second(tokens, duration_ms)
            svg_path = svg_data.get("svg_path", "")
            svg_id = f"{model}_{theme}"
            cell_judgments = judgments_lookup.get(svg_id, [])
            avg_score = _calculate_avg_score(cell_judgments) if cell_judgments else None
            cells.append(_build_success_cell(model, theme, svg_code, duration_ms,
                                             tokens, tps, svg_path, avg_score, cell_judgments))
        else:
            error_msg = ""
            if svg_data:
                error_msg = svg_data.get("error_message", "Generation failed")
            cells.append(_build_error_cell(model, theme, error_msg))
    row_html = f'      <div class="theme-label" title="{escaped_theme}">{escaped_theme}</div>\n{"".join(cells)}\n'
    return row_html


def _build_success_cell(model: str, theme: str, svg_code: str,
                        duration_ms: float, tokens: Optional[int],
                        tps: float, svg_path: str,
                        avg_score: Optional[float],
                        judgments: Optional[list] = None) -> str:
    """Build HTML for a successful SVG cell."""
    if judgments is None:
        judgments = []
    duration_str = format_duration(duration_ms)
    tokens_str = f"{tokens:,}" if tokens is not None else "N/A"
    tps_str = f"{tps:.1f}" if tps > 0 else "N/A"
    score_str = f"{avg_score:.2f}" if avg_score is not None else ""
    svg_embedded = svg_code
    judge_blocks_html = _render_judge_prompts(judgments) if judgments else ""
    judge_section = ""
    if judge_blocks_html:
        judge_section = f'''        <div class="judging-summary">
            <details>
                <summary class="show-judges-btn">Show judges scoring</summary>
                <div class="judges-collapsible">
{judge_blocks_html}
                </div>
            </details>
        </div>'''
    return f'''        <div class="cell">
            <div class="cell-header">
                <span class="cell-model">{html.escape(model)}</span>
                {f'<span class="cell-score">{score_str}</span>' if score_str else ''}
            </div>
            <div class="svg-container">
                {svg_embedded}
            </div>
            <div class="cell-stats">
                <div class="stat">
                    <div class="stat-value">{duration_str}</div>
                    <div class="stat-label">Duration</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{tokens_str}</div>
                    <div class="stat-label">Tokens</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{tps_str}</div>
                    <div class="stat-label">Tok/s</div>
                </div>
            </div>
            {f'<div class="svg-path">{html.escape(svg_path)}</div>' if svg_path else ''}
            {judge_section}
        </div>
'''


def _build_error_cell(model: str, theme: str, error_message: str) -> str:
    """Build HTML for a failed/error cell."""
    return f'''        <div class="cell failed">
            <div class="cell-header">
                <span class="cell-model">{html.escape(model)}</span>
            </div>
            <div class="error-cell">
                <div class="error-icon">&#9888;</div>
                <div class="error-message">{html.escape(error_message) if error_message else 'Generation failed'}</div>
            </div>
        </div>
'''


def _calculate_avg_score(judgments: list) -> Optional[float]:
    """Calculate average total score from judgments."""
    scores = [j.get("total_score") for j in judgments if j.get("total_score") is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)


def _render_judge_prompts(judgments: list) -> str:
    """Build HTML for individual judge blocks (without collapse wrapper)."""
    blocks = []
    for idx, j in enumerate(judgments):
        judge_name = html.escape(j.get("judged_by", f"judge_{idx}"))
        reason = html.escape(j.get("reason", "No reasoning") or "")
        criteria_used = j.get("criteria_used", ["creativity", "aesthetics", "complexity"])
        scores = j.get("scores", {})
        score_section = "".join(
            f'<div class="judge-score-row"><strong>{html.escape(str(c))}:</strong> <span class="judge-score-value">{scores.get(c, "N/A")}</span></div>'
            for c in criteria_used
        )
        judge_prompt = j.get("judge_prompt")
        prompt_section = ""
        if judge_prompt:
            escaped_prompt = html.escape(judge_prompt)
            prompt_section = f'''                    <details class="judge-prompt-details">
                        <summary class="judge-prompt-summary">Show judge prompt</summary>
                        <pre class="judge-prompt-text">{escaped_prompt}</pre>
                    </details>'''
        blocks.append(f'''        <div class="judge-block">
            <div class="judge-block-header"><strong>{judge_name}</strong></div>
            <div class="judge-block-body">
                {score_section}
                <div class="judge-reason">{reason}</div>
                {prompt_section}
            </div>
        </div>''')
    return "".join(blocks)


def generate_report_from_file(benchmark_json_path: str, output_dir: Optional[str] = None) -> str:
    """
    Generate HTML report from a benchmark.json file.

    Args:
        benchmark_json_path: Path to benchmark.json file
        output_dir: Optional output directory (defaults to same dir as benchmark.json)

    Returns:
        Path to generated HTML file
    """
    with open(benchmark_json_path, "r", encoding="utf-8") as f:
        run_data = json.load(f)
    path_obj = Path(benchmark_json_path)
    output_path = Path(output_dir) if output_dir is not None else path_obj.parent
    html_path = output_path / "benchmark_report.html"
    return generate_benchmark_html(run_data, html_path)
