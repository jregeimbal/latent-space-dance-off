# latent-space-dance-off

> Benchmark Ollama LLM models through SVG generation and AI-powered judging

A Python CLI application that evaluates Large Language Models by having them generate SVG images, then using AI to judge and rank each other's creations. The result is a data-driven leaderboard of SVG generation capabilities across different Ollama models.

## Features

- **SVG Generation**: Generate visual SVG art from prompts using various Ollama models
- **AI Judging**: Use LLMs as judges to compare and rank SVG outputs
- **Benchmark Tracking**: Record generation time, token usage, and performance metrics
- **Leaderboard System**: Aggregate judging results into a ranked leaderboard
- **Live Progress**: Real-time streaming progress with elapsed time during generation
- **HTML Reports**: Generate beautiful HTML benchmark reports
- **Structured Output**: Automatically saves SVGs, benchmarks, and results to organized directories

## Installation

### Prerequisites

- **Python**: 3.9 or higher
- **Ollama**: Installed and running locally (`ollama serve`)
- **Models**: At least one Ollama model pulled (e.g., `ollama pull llama3`)

### Install

```bash
git clone <repository-url>
cd latent-space-dance-off
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

### Configure

Copy the example environment file (optional):

```bash
cp .env.example .env
```

Edit `.env` to customize settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `NUM_JUDGES` | Number of judge models | `3` |
| `NUM_PASSES` | SVG passes per model per theme | `1` |
| `OUTPUT_DIR` | Output directory | `./output` |
| `MODEL_LIST` | Default models to benchmark | (empty) |
| `JUDGING_CRITERIA` | Comma-separated criteria | `creativity,aesthetics,complexity` |
| `DISABLE_JUDGING` | Skip judging phase | `False` |

## Usage

### List Available Models

```bash
python main.py list-models
```

### Run Benchmark

```bash
python main.py run [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--models` | `-m` | (required) | Comma-separated model names (e.g., `llama3,gemma2`) |
| `--themes` | `-t` | `abstract,landscape,portrait` | Comma-separated themes |
| `--judges` | `-j` | `3` | Number of judge models |
| `--passes` | `-p` | `1` | SVG passes per model per theme |
| `--output` | `-o` | `./output` | Output directory |
| `--ollama-host` | `--host` | `http://localhost:11434` | Ollama host URL |
| `--criteria` | `-c` | `creativity,aesthetics,complexity` | Judging criteria |
| `--no-judging` | | `False` | Skip the judging phase |

**Examples:**

```bash
# Run with specific models
python main.py run --models llama3,gemma2,mistral

# Run with custom themes
python main.py run --models llama3,gemma2 --themes abstract,landscape,portrait,object,scene

# Skip judging phase (generation only)
python main.py run --models llama3 --no-judging

# Generate 3 passes per model/theme for comparison
python main.py run --models llama3,gemma2 --passes 3

# Custom judge count and criteria
python main.py run --models llama3,gemma2 --judges 5 --criteria creativity,aesthetics,complexity,color_harmony
```

### View Leaderboard

```bash
python main.py leaderboard [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `run-id` | Specific run ID to view (default: latest) |
| `--ollama-host` | Ollama host URL |
| `--output` | Output directory |

```bash
# View latest leaderboard
python main.py leaderboard

# View specific run
python main.py leaderboard 2026-04-29T12:00:00.000000
```

### Run Dance-Off

```bash
python main.py dance-off [OPTIONS]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--models` | `-m` | (required) | Comma-separated model names |
| `--theme-pool` | `-tp` | `abstract,landscape,portrait,object,scene` | Available themes for audience-judge |
| `--judges` | `-j` | `1` | Number of judge models |
| `--output` | `-o` | `./output` | Output directory |
| `--svg-per-model` | `-s` | `2` | SVGs each model generates per round |
| `--ollama-host` | `--host` | `http://localhost:11434` | Ollama host URL |

**Example:**

```bash
# Run a dance-off between 3 models
python main.py dance-off --models llama3,gemma2,mistral
```

A dance-off runs a single-elimination bracket where models compete in free-for-all rounds. In each round, an audience-judge picks a theme, all surviving models generate SVGs, and the worst is eliminated. The last model standing is crowned champion.

### Export Results

```bash
python main.py export [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `run-id` | Run ID to export (default: latest) |
| `--format` | Export format: `csv` or `json` |
| `--ollama-host` | Ollama host URL |
| `--output` | Output directory |

```bash
# Export to CSV
python main.py export --format csv

# Export to JSON
python main.py export --format json
```

### List All Runs

```bash
python main.py runs
```

## Example Workflow

```bash
# 1. Pull models
ollama pull llama3
ollama pull gemma2
ollama pull mistral

# 2. List available models
python main.py list-models

# 3. Run benchmark
python main.py run --models llama3,gemma2,mistral --themes abstract,landscape,portrait

# 4. View leaderboard
python main.py leaderboard

# 5. Export results
python main.py export --format csv
```

## Examples

Here are some SVGs generated by the qwen3.6:35b-a3b-coding-bf16 model:

### Dancing Llama

![Dancing Llama](example_output/2026-04-27T12:17:38.942935/assets/2026-04-27T12:17:38.942935_qwen3.6:35b-a3b-coding-bf16_dancing%20llama.svg)

### Solvable Maze

![Solvable Maze](example_output/2026-04-29T22:10:11.861049/assets/2026-04-29T22:10:11.861049_qwen3.6:35b-a3b-coding-bf16_solvable%20maze%20but%20do%20not%20show%20the%20solution.svg)

## Output Structure

```
output/
├── benchmarks/
│   └── <run_id>/
│       ├── benchmark.json         # Full benchmark data
│       ├── benchmark_report.html  # HTML report with pass selector
│       └── assets/
│           └── <run_id>_<model>_<theme>_pass{N}.svg  # Generated SVGs (one per pass)
└── leaderboards/
    └── <run_id>-leaderboard.json  # Ranked leaderboard
    └── <run_id>.csv               # CSV export
```

## Judging Criteria

Models are evaluated on configurable criteria (default: `creativity,aesthetics,complexity`):

| Criterion | Description |
|-----------|-------------|
| `creativity` | How original and innovative is the design? |
| `aesthetics` | How visually pleasing and well-composed is the artwork? |
| `complexity` | How sophisticated and detailed is the artwork? |
| `color_harmony` | How well do the colors work together? |
| `composition` | How balanced and well-structured is the composition? |
| `technical_quality` | How technically sound is the SVG code? |
| `accuracy` | How accurate is the SVG with what was prompted? |

Customize via `--criteria` flag or `JUDGING_CRITERIA` environment variable.

## SVG Themes

Built-in themes with specialized prompts:

| Theme | Description |
|-------|-------------|
| `abstract` | Geometric shapes, colors, and patterns |
| `landscape` | Scenic views with sky, mountains, water |
| `portrait` | Stylized human figures |
| `object` | Everyday objects and concepts |
| `scene` | Detailed scenes with context |

Custom themes are supported (uses generic prompt).

## Project Structure

```
latent-space-dance-off/
├── main.py                 # CLI entry point
├── pyproject.toml          # Project configuration
├── README.md               # This file
├── .env.example            # Environment template
├── src/
│   ├── config.py           # Configuration management
│   ├── model_manager.py    # Ollama model management
│   ├── svg_generator.py    # SVG generation logic
│   ├── svg_judge.py        # SVG judging logic
│   ├── benchmark.py        # Benchmark recording
│   ├── ranking.py          # Aggregation & ranking
│   ├── html_generator.py   # HTML report generation
│   └── utils.py            # Utility functions
├── tests/                  # Test suite
└── output/                 # Generated output
```

## Testing

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_svg_judge.py -v
```

## License

MIT License
