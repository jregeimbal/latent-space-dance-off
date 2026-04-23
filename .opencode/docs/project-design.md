# Project Context: latent-space-dance-off

## Overview
A Python CLI application that benchmarks Ollama LLM models by having them generate SVG images, then have models judge and rank each other's SVGs, producing a final leaderboard.

## Environment
- **Language**: Python 3.9.6
- **Build system**: Not configured (needs pyproject.toml)
- **Package Manager**: pip

## Tech Stack
- **Ollama Python Client**: `ollama` - async client for LLM interactions
- **Async Library**: `asyncio` (stdlib) - for parallel model calls
- **HTTP/REST**: `httpx` - Ollama client dependency
- **CLI Framework**: `typer` or `click` - for CLI interface
- **Data Storage**: 
  - JSON files for benchmark data and results
  - SVG files saved to disk
  - SQLite (optional) for structured data storage

## Project Structure
```
latent-space-dance-off/
├── pyproject.toml              # Dependencies & project config
├── README.md                   # Documentation
├── main.py                     # CLI entry point
├── .env                        # Environment variables (OLLAMA_API_KEY, etc.)
│
├── src/
│   ├── __init__.py
│   ├── main.py                 # CLI entry point (if using src layout)
│   │
│   ├── model_manager.py        # Manages Ollama models, available models list
│   ├── svg_generator.py        # Generates SVG prompts and images
│   ├── svg_judge.py            # Judges/ranks SVG images
│   ├── benchmark.py            # Records benchmarks (duration, tokens/sec)
│   └── ranking.py              # Aggregates scores, produces final ranking
│
├── data/
│   ├── svgs/                   # Generated SVG files
│   │   ├── model_1.svg
│   │   ├── model_1_vs_model_2_judge_1.svg
│   │   └── ...
│   ├── benchmarks/             # Benchmark JSON files
│   │   ├── run_2026-04-22T20-18-40.json
│   │   └── ...
│   └── results/                # Final ranking results
│       └── leaderboard.json
│
└── tests/
    ├── __init__.py
    ├── test_svg_generator.py
    ├── test_svg_judge.py
    ├── test_benchmark.py
    └── test_ranking.py
```

## Components

### 1. Model Manager (`src/model_manager.py`)
**Responsibility**: Manage Ollama models, fetch available models, handle connections.

**Key Functions**:
- `get_available_models()`: List all available models via `ollama.list()`
- `get_model_info(model_name)`: Get model details via `ollama.show(model_name)`
- `is_model_available(model_name)`: Check if model is pulled
- `pull_model(model_name)`: Pull a model if not available
- `create_async_client(host)`: Create AsyncClient for async operations

**Confidence**: HIGH - Based on Ollama Python client docs

---

### 2. SVG Generator (`src/svg_generator.py`)
**Responsibility**: Prompt models to generate SVG images with various themes.

**Key Functions**:
- `generate_svg_prompt(theme)`: Create prompt for a specific theme
- `request_svg_generation(model_name, theme)`: Ask model to generate SVG
- `parse_svg_response(response)`: Extract SVG code from model response
- `save_svg(svg_code, filename)`: Write SVG to file
- Generate SVGs for themes: "abstract", "landscape", "portrait", "object", "scene"

**Prompt Template**:
```
"You are an expert SVG generator. Create a visually appealing SVG image 
with the theme: '{theme}'. Return ONLY the SVG code, no markdown, no explanation.
Ensure it's valid XML and includes proper SVG elements."
```

**Confidence**: HIGH - Standard LLM image generation pattern

---

### 3. SVG Judge (`src/svg_judge.py`)
**Responsibility**: Have models judge and rank SVG images.

**Key Functions**:
- `judge_svg(model_judge, svg_file, criteria)`: Judge a single SVG
- `compare_svgs(model_judge, svg1_path, svg2_path)`: Compare 2 SVGs head-to-head
- `run_all_comparisons(judge_model, svg_list, comparison_method)`: All-vs-all or round-robin
- Parse model's written judgment into structured scores

**Comparison Methods**:
- **All-vs-All**: Each model generates SVGs, then all models judge all SVGs
- **Round-Robin**: Each model judges each other model once
- **Head-to-Head**: Pairwise comparisons between SVGs

**Prompts**:
```
"Compare these two SVG images. Judge based on: creativity, aesthetics, 
completeness, and technical quality. Rank them 1-2 and explain your choice
in detail."
```

**Confidence**: MEDIUM - Requires parsing free-text responses

---

### 4. Benchmark Recorder (`src/benchmark.py`)
**Responsibility**: Track timing and token metrics.

**Key Metrics**:
- Generation duration (milliseconds)
- Tokens generated (if available from Ollama response)
- Tokens per second
- Model performance rankings

**Key Functions**:
- `start_timer()`: Start timing
- `stop_timer()`: Stop and return duration
- `record_generation(model, theme, duration, output_tokens)`: Record benchmark data
- `calculate_tokens_per_second(tokens, duration)`: Calculate rate
- `save_benchmark(run_data)`: Save to JSON file in data/benchmarks/
- `load_benchmark(run_id)`: Load previous benchmark for comparison

**Confidence**: HIGH - Standard benchmarking pattern

---

### 5. Ranking System (`src/ranking.py`)
**Responsibility**: Aggregate all judgments into final rankings.

**Key Functions**:
- `aggregate_scores(svg_id, all_judgments)`: Combine all judgments for one SVG
- `calculate_final_ranking(judgment_data)`: Compute overall leaderboard
- `generate_leaderboard(results)`: Format final ranked list
- `save_leaderboard(ranking, filepath)`: Save to data/results/

**Scoring System**:
- Each judgment: 1st place = 1 point, 2nd place = 0 points
- Or use: 1st = N-1 points, 2nd = N-2, etc. (N = number of competitors)
- Add creativity, aesthetics, completeness, quality scores if available
- Weight different criteria if needed

**Confidence**: HIGH - Standard ranking/aggregation pattern

---

## API Endpoints vs CLI

**Recommended**: CLI tool (simpler, no web framework overhead)

**CLI Commands**:
```bash
# Main commands
python -m latent_space_dance_off list-models          # Show available models
python -m latent_space_dance_off run --model-list abc,xyz  # Run benchmark with specific models
python -m latent_space_dance_off run --all            # Run with all available models
python -m latent_space_dance_off compare --svgs svg1.svg svg2.svg  # Compare two SVGs
python -m latent_space_dance-off judge --models abc,xyz --svgs *.svg  # Judge SVGs
python -m latent_space_dance-off leaderboard            # Show final rankings
python -m latent_space_dance-off export --format json|csv  # Export results

# Options
--num-themes 5              # How many SVG themes to generate
--num-judges 3              # How many models judge each SVG
--comparison-mode all-vs-all | round-robin | head-to-head
--output-dir data/          # Output directory
--verbose                   # Show detailed output
```

**Alternative**: Web UI with FastAPI if visual interaction is desired (can be added later as extension)

---

## Data Storage

### Directory Structure
```
data/
├── svgs/
│   ├── [run_id]/
│   │   └── [model_name]_[theme].svg
├── benchmarks/
│   └── [run_id].json
└── results/
    └── [run_id]-leaderboard.json
```

### JSON Schema Examples

**Benchmark Run:**
```json
{
  "run_id": "2026-04-22T20-18-40",
  "timestamp": "2026-04-22T20:18:40Z",
  "models": ["llama3", "gemma2", "mistral"],
  "themes": ["abstract", "landscape", "portrait"],
  "generations": [
    {
      "model": "llama3",
      "theme": "abstract",
      "duration_ms": 15234,
      "output_tokens": 234,
      "tokens_per_second": 15.3,
      "svg_file": "svgs/2026-04-22T20-18-40/llama3_abstract.svg"
    }
  ]
}
```

**Leaderboard:**
```json
{
  "run_id": "2026-04-22T20-18-40",
  "timestamp": "2026-04-22T20:18:40Z",
  "total_judgments": 9,
  "rankings": [
    {
      "model": "llama3",
      "svg_file": "svgs/llama3_abstract.svg",
      "total_points": 12,
      "avg_score": 4.0,
      "rank": 1,
      "judgments_received": [
        {
          "judged_by": "gemma2",
          "rank": 1,
          "reason": "Creative color choices"
        }
      ]
    }
  ]
}
```

---

## Judging Process

### Recommended: All-vs-All with Round-Robin Judges

**Step 1**: All models generate N SVGs each (N themes)
**Step 2**: Each model judges every other model's SVG (excluding its own)
**Step 3**: Collect all judgments, compute aggregated scores
**Step 4**: Generate final leaderboard

**Parallel Execution**:
- SVG generation can be parallelized (one async task per model)
- Judging can be parallelized (one async task per judge-model)
- Total parallelism: (NumModels × N Themes) for generation + (NumJudges × NumSVGs) for judging

**Example for 3 models (A, B, C) with 3 themes:**
- Generation: A produces 3 SVGs, B produces 3 SVGs, C produces 3 SVGs (6 total async tasks)
- Judgment: A judges B and C's SVGs (6 judgments), B judges A and C's SVGs (6 judgments), C judges A and B's SVGs (6 judgments) = 18 total async tasks

---

## Dependencies

### Required (pyproject.toml):
```toml
[project]
name = "latent-space-dance-off"
version = "0.1.0"
description = "Benchmark Ollama LLMs with SVG generation and judging"
requires-python = ">=3.9"

[tool.poetry.dependencies]
python = "^3.9"
ollama = ">=0.1.0"
typer = ">=0.9.0"
rich = ">=13.0.0"        # For CLI output formatting
pydantic = ">=2.0.0"      # For data validation
httpx = ">=0.25.0"        # Ollama client dependency

[tool.poetry.dev-dependencies]
pytest = ">=7.4.0"
pytest-asyncio = ">=0.21.0"
mypy = ">=1.0.0"
black = ">=23.0.0"
```

### Alternative (requirements.txt):
```
ollama>=0.1.0
typer>=0.9.0
rich>=13.0.0
pydantic>=2.0.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

---

## Async Task Pattern

```python
import asyncio
from ollama import AsyncClient

async def generate_svg_for_model(model: AsyncClient, theme: str):
    prompt = f"Generate an SVG with the theme: {theme}"
    response = await model.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
    return parse_svg(response)

async def benchmark_all_models(models, themes):
    tasks = []
    for model_name in models:
        for theme in themes:
            client = AsyncClient()
            tasks.append(generate_svg_for_model(client, theme))
    
    results = await asyncio.gather(*tasks)
    return results
```

---

## File-Level Implementation Plan

See `.opencode/todo.md` for detailed task breakdown.

## Key Challenges & Solutions

1. **SVG Parsing**: Models may return markdown code blocks
   - Solution: Extract SVG content between ```xml/svg ``` markers or <svg> tags

2. **Model Quality Variation**: Different models have different capabilities
   - Solution: Run multiple judges, weight by model quality (optional)

3. **Parallel Concurrency**: Too many async tasks may overwhelm Ollama
   - Solution: Use asyncio.Semaphore or asyncio.Semaphore for rate limiting

4. **Judging Subjectivity**: Human-like judgments vary
   - Solution: Aggregate multiple judgments, use majority voting

5. **Token Count Tracking**: Ollama may not always provide token metrics
   - Solution: Handle missing token data gracefully in benchmark recorder
