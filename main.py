"""
Main CLI entry point for latent-space-dance-off.

A CLI application to benchmark LLM models by having them generate SVG images
and judge each other's work.
"""

import asyncio
import html
import json
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich._spinners import SPINNERS

from src.config import Config
from src.model_manager import ModelManager
from src.svg_generator import SVGGenerator
from src.svg_judge import SVGJudge
from src.ranking import RankingSystem, Leaderboard
from src.benchmark import BenchmarkManager, BenchmarkRecord, RunData, SVGResult
from src.html_generator import generate_benchmark_html, generate_dance_off_html
from src.utils import format_duration, svg_to_ascii, make_clickable_link

app = typer.Typer(
    name="latent-space-dance-off",
    help="Benchmark LLM models by having them create and judge SVG art.",
    add_completion=False
)

console = Console()

spinner_frames = ["◤", "▀", "◥", "▐", "◢", "▂", "◣", "▌"]
# Register the custom spinner in the global SPINNERS dictionary
SPINNERS["spinner_frames"] = {
    "interval": 120,  # Milliseconds between frames
    "frames": spinner_frames
}

def get_config(
    ollama_host: str = "http://localhost:11434",
    output_dir: str = "./output",
    num_judges: int = 3,
    model_list: str = "",
    judging_criteria: str = "",
    disable_judging: bool = False,
    client_type: str = "ollama",
    llm_host: str = "",
):
    config = Config(
        OLLAMA_HOST=ollama_host,
        OUTPUT_DIR=output_dir,
        NUM_JUDGES=num_judges,
        MODEL_LIST=model_list,
        JUDGING_CRITERIA=judging_criteria,
        DISABLE_JUDGING=disable_judging,
        LLM_CLIENT=client_type,
        LLM_HOST=llm_host,
    )
    return config


def parse_models(models_str: str) -> List[str]:
    if not models_str:
        return []
    return [m.strip() for m in models_str.split(",") if m.strip()]


@app.command()
def list_models(
    ollama_host: str = typer.Option("http://localhost:11434", "--ollama-host", "-h"),
    client_type: str = typer.Option("ollama", "--client-type", "-c", help="LLM client type (ollama or lmstudio)"),
):
    manager = ModelManager(host=ollama_host, client_type=client_type)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        models = loop.run_until_complete(manager.list_models())
    finally:
        loop.close()

    if not models:
        console.print(Panel(
              "[red]No models found. Pull a model to your LLM server to add models.[/red]",
            title="No Models Available"
          ))
        return

    table = Table(title="Available Models")
    table.add_column("Model Name", style="cyan")
    table.add_column("Size", style="magenta")
    table.add_column("Modified", style="yellow")

    for model_name in models:
        table.add_row(
            model_name if model_name else "Unknown",
              "N/A",
              "N/A"
           )

    console.print(table)


async def _run_impl(
    models: Optional[str],
    themes: str,
    num_judges: int,
    output_dir: str,
    ollama_host: str,
    judging_criteria: str = "creativity,aesthetics,complexity",
    disable_judging: bool = False,
    num_passes: int = 1,
    client_type: str = "ollama",
    llm_host: str = "",
):
    theme_list = [t.strip() for t in themes.split(",")]
    config = get_config(ollama_host, output_dir, num_judges, models or "", judging_criteria, disable_judging, client_type, llm_host)
    
    model_manager = ModelManager(host=config.llm_host, client_type=config.LLM_CLIENT)
    benchmark_manager = BenchmarkManager(config)
    ranking_system = RankingSystem(config)
    svg_judge = SVGJudge(config)

    model_list = parse_models(models or "")

    if not model_list:
        console.print(Panel(
              "[red]No models specified. Use --models or check available models with list-models.[/red]",
            title="No Models"
          ))
        return

    info_lines = [
        f"Starting benchmark with {len(model_list)} models and {len(theme_list)} themes",
        f"Models: {', '.join(model_list)}",
        f"Themes: {', '.join(theme_list)}",
        f"Judges: {'None' if disable_judging else num_judges}",
        f"Passes: {num_passes}",
        f"Output: {output_dir}"
       ]
    console.print(Panel("\n".join(info_lines),
        title="[bold green]Latent Space Dance Off[/bold green]",
        border_style="green"
      ))

    console.print("[cyan]Initializing model managers...[/cyan]")

    model_clients = {}
    for model_name in model_list:
        try:
            client = await model_manager.get_model(model_name)
            model_clients[model_name] = client
            console.print(f"[green]Model {model_name} ready[/green]")
        except Exception as e:
            console.print(f"[red]Model {model_name} failed: {e}[/red]")

    if not model_clients:
        console.print("[red]No models available. Exiting.[/red]")
        return

    run_id = benchmark_manager.generate_run_id()
    console.print(f"[yellow]Run ID: {run_id}[/yellow]")
    # Create run directory with assets subfolder
    run_dir = benchmark_manager._ensure_run_dir(run_id)
    assets_dir = run_dir / "assets"
    svg_generator = SVGGenerator(config, svgs_dir=assets_dir)
    console.print(f"[yellow]Output directory: {run_dir}[/yellow]")
    console.print(f"\n[cyan]Generating SVGs for {len(model_clients)} models x {len(theme_list)} themes x {num_passes} passes...[/cyan]")

    with Progress(
        SpinnerColumn(spinner_name="spinner_frames", style="green"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
       ) as progress:
        svg_task = progress.add_task("Generating SVGs...", total=len(model_clients) * len(theme_list) * num_passes)

        svg_results = []
        streamed_text = ""

        def update_progress(cleaned: str):
            nonlocal streamed_text
            streamed_text += cleaned
            last_20 = streamed_text[-20:]
            elapsed = time.perf_counter() - generation_start
            elapsed_str = f"{elapsed:.1f}s"
            progress.update(svg_task, description=f"Generating {model_name} ({theme}, pass {pass_num}) | {elapsed_str} | {last_20}")

        for model_name in model_clients:
            for theme in theme_list:
                for pass_num in range(1, num_passes + 1):
                    streamed_text = ""
                    generation_start = time.perf_counter()
                    progress.update(svg_task, description=f"Generating {model_name} ({theme}, pass {pass_num}) | 0.0s | Thinking...")
                    result = await svg_generator.generate_svg(model_clients[model_name], theme, model_name, run_id, progress_callback=update_progress, pass_number=pass_num)
                    svg_results.append(result)
                    final_elapsed = time.perf_counter() - generation_start
                    progress.update(svg_task, description=f"Generating {model_name} ({theme}, pass {pass_num}) | Done ({final_elapsed:.1f}s)")
                    progress.update(svg_task, advance=1)

    console.print("\n[cyan]Benchmark Results[/cyan]")
    console.print(Panel.fit("[bold]Generation Results[/bold]"))

    for result in svg_results:
        status_icon = "[green]Success[/green]" if result.status == "success" else "[red]Failed[/red]"
        tokens_str = f"{result.tokens_used:,}" if result.tokens_used else "N/A"
        duration_str = format_duration(result.duration_ms / 1000)
        tps = (result.tokens_used / (result.duration_ms / 1000)) if result.duration_ms > 0 and result.tokens_used else 0

        console.print(f"{status_icon} {result.model_name} ({result.theme})")
        console.print(f"  Status: {result.status}")
        console.print(f"  Duration: {duration_str}")
        console.print(f"  Tokens: {tokens_str} ({tps:.2f} tokens/sec)")
        console.print(f"  File: {make_clickable_link(result.svg_path)}", markup=False, highlight=False)
        if result.status == "success" and result.svg_code:
            ascii_art = svg_to_ascii(result.svg_code, width=100, use_ansi=True)
            import sys
            sys.stdout.write(ascii_art + "\n")

    run_data = RunData(
        run_id=run_id,
        timestamp=run_id,
        svgs=[SVGResult(
            model_name=r.model_name,
            theme=r.theme,
            svg_code=r.svg_code,
            svg_path=r.svg_path,
            duration_ms=r.duration_ms,
            tokens_used=int(r.tokens_used) if r.tokens_used else None,
            status=r.status,
            error_message=r.error_message,
            generation_prompt=r.generation_prompt,
            pass_number=r.pass_number
            ) for r in svg_results],
        benchmarks=[BenchmarkRecord(
            run_id=run_id,
            model_name=r.model_name,
            theme=r.theme,
            duration_ms=r.duration_ms,
            tokens=r.tokens_used
        ) for r in svg_results],
        model_list=list(model_clients.keys()),
        themes=theme_list
        )

    if svg_results and not disable_judging:
        console.print(f"\n[cyan]Starting judgment phase with {num_judges} judge models...[/cyan]\n")
        
         # Show judgment progress
        svg_judge_count = len(list(model_clients.values())) * len(svg_results)
        
        with Progress(
            SpinnerColumn(spinner_name="spinner_frames", style="green"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
               ) as progress:
            judge_task = progress.add_task(" Judging SVGs...", total=svg_judge_count)
            
             # judge_models = list(model_clients.values())
             # if len(judge_models) < num_judges:
             #     judge_models = judge_models * (num_judges // len(judge_models) + 1)
            
            judgments = await svg_judge.run_all_judgments(model_clients, svg_results, num_judges, progress, judge_task)
            run_data.judgments = judgments
            aggregated = svg_judge.aggregate_judgments(svg_results, judgments)

        benchmark_manager.save_run_data(run_data)
        sys.stdout.write(f"\nBenchmark data saved to: {make_clickable_link(run_dir / 'benchmark.json')}\n")
        
          # Generate HTML report
        html_path = run_dir / "benchmark_report.html"
        run_data_dict = {
              "run_id": run_data.run_id,
              "timestamp": run_data.timestamp,
              "svgs": [{"model_name": s.model_name, "theme": s.theme,
                        "svg_code": s.svg_code, "svg_path": s.svg_path,
                        "duration_ms": s.duration_ms, "tokens_used": s.tokens_used,
                        "status": s.status, "pass_number": s.pass_number} for s in run_data.svgs],
               "model_list": run_data.model_list,
               "themes": run_data.themes,
               "judgments": [],
               "criteria": config.judging_criteria
            }
          # Convert judgments to dicts
        for j in getattr(run_data, 'judgments', []):
               # Handle both old format (individual scores) and new format (scores dict)
            scores_dict = j.scores if hasattr(j, 'scores') and j.scores else {
                   "creativity": j.creativity_score if hasattr(j, 'creativity_score') else None,
                   "aesthetics": j.aesthetics_score if hasattr(j, 'aesthetics_score') else None,
                   "complexity": j.complexity_score if hasattr(j, 'complexity_score') else None
                }
            
            run_data_dict["judgments"].append({
                    "svg_id": j.svg_id,
                    "judged_by": j.judged_by,
                    "scores": scores_dict,
                    "total_score": j.total_score,
                    "reason": j.reason,
                    "rank": j.rank,
                    "winner_svg": j.winner_svg,
                    "criteria_used": getattr(j, 'criteria_used', config.judging_criteria),
                    "judge_prompt": getattr(j, 'judge_prompt', None)
               })
        generate_benchmark_html(run_data_dict, html_path)
        sys.stdout.write(f"HTML report saved to: {make_clickable_link(html_path)}\n")
        
        leaderboard = ranking_system.generate_leaderboard(run_data)
        leaderboard_path = ranking_system.save_leaderboard(leaderboard, run_dir=run_dir)
        
        criteria_display = ", ".join(c.capitalize() for c in config.judging_criteria)
        console.print(f"\n[bold cyan]Judge output (Criteria: {criteria_display}):[/bold cyan]\n")
        for judgment in judgments:
            scores_str = ", ".join(f"{c.capitalize()}={getattr(judgment, 'scores', {}).get(c, 'N/A')}" for c in config.judging_criteria)
            console.print(f"    {judgment.svg_id}: {scores_str}")
        
        console.print("\n[bold cyan]Final Rankings:[/bold cyan]\n")
        console.print(Panel.fit(f"[bold]Final Rankings (Criteria: {criteria_display})[/bold]"))

        table = Table(title="Leaderboard")
        table.add_column("Rank", style="yellow", justify="center")
        table.add_column("Model", style="magenta")
        table.add_column("SVG ID", style="cyan")
        
           # Add columns for each criterion dynamically
        for criterion in config.judging_criteria:
            table.add_column(criterion.capitalize(), justify="right")
        table.add_column("Total", justify="right", style="bold green")

        for entry in leaderboard.rankings:
                # Get scores for each criterion dynamically
            score_values = []
            for criterion in config.judging_criteria:
                score_val = entry.get_score(criterion) if hasattr(entry, 'get_score') else getattr(entry, f'{criterion}_score', 0)
                score_values.append(f"{score_val:.2f}")
            
            score_values.append(f"{entry.total_score:.2f}")
            
            table.add_row(
                str(entry.rank),
                entry.model_name,
                entry.svg_id,
                   *score_values                  )
        console.print(table)
        sys.stdout.write(f"\nLeaderboard saved to: {make_clickable_link(leaderboard_path)}\n")
    elif svg_results and disable_judging:
        
        benchmark_manager.save_run_data(run_data)
        sys.stdout.write(f"\nBenchmark data saved to: {make_clickable_link(run_dir / 'benchmark.json')}\n")
        
          # Generate HTML report without judging data
        html_path = run_dir / "benchmark_report.html"
        run_data_dict = {
              "run_id": run_data.run_id,
              "timestamp": run_data.timestamp,
              "svgs": [{"model_name": s.model_name, "theme": s.theme,
                        "svg_code": s.svg_code, "svg_path": s.svg_path,
                        "duration_ms": s.duration_ms, "tokens_used": s.tokens_used,
                        "status": s.status, "pass_number": s.pass_number} for s in run_data.svgs],
               "model_list": run_data.model_list,
               "themes": run_data.themes,
               "judgments": [],
                "criteria": config.judging_criteria
             }
        generate_benchmark_html(run_data_dict, html_path)
        sys.stdout.write(f"HTML report saved to: {make_clickable_link(html_path)}\n")
        
        console.print("[yellow]Judging was disabled. No judge output or leaderboard generated.[/yellow]")
    else:
        console.print("[red]No SVGs to judge.[/red]")

    console.print("\n[bold green]Benchmark complete![/bold green]")


@app.command()
def run(
    models: Optional[str] = typer.Option(None, "--models", "-m"),
    themes: str = typer.Option("abstract,landscape,portrait", "--themes", "-t"),
    num_judges: int = typer.Option(3, "--judges", "-j"),
    output_dir: str = typer.Option("./output", "--output", "-o"),
    ollama_host: str = typer.Option("http://localhost:11434", "--ollama-host", "--host"),
    client_type: str = typer.Option("ollama", "--client-type", help="LLM client type (ollama or lmstudio)"),
    llm_host: str = typer.Option("", "--llm-host", help="LLM server host URL (defaults to --ollama-host)"),
    judging_criteria: str = typer.Option("creativity,aesthetics,complexity", "--criteria", "-c", help="Comma-separated list of judging criteria"),
    no_judging: bool = typer.Option(False, "--no-judging", help="Skip the judging phase entirely"),
    num_passes: int = typer.Option(1, "--passes", "-p", help="Number of SVG passes per model per theme"),
):
    asyncio.run(_run_impl(models, themes, num_judges, output_dir, ollama_host, judging_criteria, no_judging, num_passes, client_type, llm_host))


@app.command()
def leaderboard(
    run_id: Optional[str] = typer.Argument(None, help="Run ID to show leaderboard for"),
    ollama_host: str = typer.Option("http://localhost:11434", "--ollama-host", "--host"),
    output_dir: str = typer.Option("./output", "--output", "-o")
):
    config = Config(OLLAMA_HOST=ollama_host, OUTPUT_DIR=output_dir)
    ranking_system = RankingSystem(config)

    try:
        if run_id:
            leaderboard_obj = ranking_system.load_leaderboard(run_id)
        else:
            benchmark_manager = BenchmarkManager(config)
            latest_run = benchmark_manager.get_latest_run_id()
            if not latest_run:
                console.print("[red]No benchmark runs found.[/red]")
                return
            leaderboard_obj = ranking_system.load_leaderboard(latest_run)

        console.print(Panel.fit(f"[bold]Leaderboard for Run: {leaderboard_obj.run_id}[/bold]"))

        table = Table(title="Rankings")
        table.add_column("Rank", style="yellow", justify="center")
        table.add_column("Model", style="magenta")
        table.add_column("SVG ID", style="cyan")
        table.add_column("Creativity", justify="right")
        table.add_column("Aesthetics", justify="right")
        table.add_column("Complexity", justify="right")
        table.add_column("Total", justify="right")

        for entry in leaderboard_obj.rankings:
            table.add_row(
                str(entry.rank),
                entry.model_name,
                entry.svg_id,
                f"{entry.get_score('creativity'):.2f}",
                f"{entry.get_score('aesthetics'):.2f}",
                f"{entry.get_score('complexity'):.2f}",
                f"{entry.total_score:.2f}"
               )

        console.print(table)
        csv_path = ranking_system.export_to_csv(leaderboard_obj)
        sys.stdout.write(f"\n[yellow]Saved CSV: {make_clickable_link(csv_path)}[/yellow]\n")

    except FileNotFoundError as e:
        console.print(f"[red]Leaderboard not found: {e}[/red]")


@app.command()
def export(
    run_id: Optional[str] = typer.Argument(None, help="Run ID to export"),
    format: str = typer.Option("csv", "--format", "-f"),
    ollama_host: str = typer.Option("http://localhost:11434", "--ollama-host", "--host"),
    output_dir: str = typer.Option("./output", "--output", "-o")
):
    config = Config(OLLAMA_HOST=ollama_host, OUTPUT_DIR=output_dir)
    ranking_system = RankingSystem(config)
    benchmark_manager = BenchmarkManager(config)

    try:
        if run_id:
            leaderboard_obj = ranking_system.load_leaderboard(run_id)
        else:
            latest_run = benchmark_manager.get_latest_run_id()
            if not latest_run:
                console.print("[red]No benchmark runs found.[/red]")
                return
            leaderboard_obj = ranking_system.load_leaderboard(latest_run)

        if format == "csv":
            filepath = ranking_system.export_to_csv(leaderboard_obj)
            sys.stdout.write(f"[green]Exported to CSV: {make_clickable_link(filepath)}[/green]\n")
        elif format == "json":
            filepath = ranking_system.save_leaderboard(leaderboard_obj)
            sys.stdout.write(f"[green]Exported to JSON: {make_clickable_link(filepath)}[/green]\n")

    except FileNotFoundError as e:
        console.print(f"[red]Leaderboard not found: {e}[/red]")


@app.command()
def runs(
    ollama_host: str = typer.Option("http://localhost:11434", "--ollama-host", "--host"),
    output_dir: str = typer.Option("./output", "--output", "-o")
):
    config = Config(OLLAMA_HOST=ollama_host, OUTPUT_DIR=output_dir)
    benchmark_manager = BenchmarkManager(config)
    runs_list = benchmark_manager.get_all_runs()

    if not runs_list:
        console.print("[yellow]No benchmark runs found.[/yellow]")
        return

    table = Table(title="Benchmark Runs")
    table.add_column("Run ID", style="cyan")
    table.add_column("Timestamp", style="magenta")
    table.add_column("Models", style="yellow")
    table.add_column("Themes", style="green")

    for run in runs_list:
        table.add_row(
            run.run_id,
            run.timestamp,
              ", ".join(run.model_list),
              ", ".join(run.themes)
          )

    console.print(table)


@app.command()
def dance_off(
    models: Optional[str] = typer.Option(None, "--models", "-m", help="Comma-separated model names to compete"),
    theme_pool: str = typer.Option("abstract,landscape,portrait,object,scene", "--theme-pool", "-tp", help="Comma-separated themes for audience-judge to pick from"),
    num_judges: int = typer.Option(1, "--judges", "-j", help="Number of judge models (1 for theme selection + round judging)"),
    output_dir: str = typer.Option("./output", "--output", "-o"),
    ollama_host: str = typer.Option("http://localhost:11434", "--ollama-host", "--host"),
    client_type: str = typer.Option("ollama", "--client-type", help="LLM client type (ollama or lmstudio)"),
    llm_host: str = typer.Option("", "--llm-host", help="LLM server host URL"),
    svg_per_model: int = typer.Option(2, "--svg-per-model", "-s", help="SVGs each model generates per round"),
):
    """Run a single-elimination dance-off where models compete in free-for-all rounds. Each round: audience-judge picks a theme, all surviving models generate SVGs, round judge eliminates the worst."""
    asyncio.run(_dance_off_impl(models, theme_pool, num_judges, output_dir, ollama_host, client_type, llm_host, svg_per_model))


async def _dance_off_impl(
    models: Optional[str],
    theme_pool: str,
    num_judges: int,
    output_dir: str,
    ollama_host: str,
    client_type: str,
    llm_host: str,
    svg_per_model: int,
):
    theme_list = [t.strip() for t in theme_pool.split(",")]
    config = get_config(ollama_host, output_dir, num_judges, "", "", False, client_type, llm_host)

    model_manager = ModelManager(host=config.llm_host, client_type=config.LLM_CLIENT)
    benchmark_manager = BenchmarkManager(config)
    model_list = parse_models(models or "")

    if not model_list:
        console.print(Panel(
            "[red]No models specified. Use --models.[/red]",
            title="No Models"
        ))
        return

    if len(model_list) < 2:
        console.print(Panel(
            "[red]Need at least 2 models for a dance-off.[/red]",
            title="Not Enough Models"
        ))
        return

    # Initialize model clients
    model_clients = {}
    for model_name in model_list:
        try:
            client = await model_manager.get_model(model_name)
            model_clients[model_name] = client
            console.print(f"[green]Model {model_name} ready[/green]")
        except Exception as e:
            console.print(f"[red]Model {model_name} failed: {e}[/red]")

    if len(model_clients) < 2:
        console.print("[red]Need at least 2 working models for a dance-off.[/red]")
        return

    # Create run directory using BenchmarkManager
    run_id = benchmark_manager.generate_run_id()
    run_dir = benchmark_manager._ensure_run_dir(run_id)
    assets_dir = run_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel(
        f"[bold green]Dance-Off Starting[/bold green]\n"
        f"Models: {', '.join(model_clients.keys())}\n"
        f"Theme pool: {', '.join(theme_list)}\n"
        f"SVGs per model per round: {svg_per_model}\n"
        f"Output: {run_dir}",
        title="[bold]Latent Space Dance Off - Dance-Off[/bold]",
        border_style="green"
    ))

    # Import DanceOff here to avoid circular import at module level
    from src.dance_off import DanceOff

    dance_off = DanceOff(
        model_clients=model_clients,
        config=config,
        theme_pool=theme_list,
        output_dir=str(run_dir),
        svg_per_model=svg_per_model,
        judge_model=model_list[0],
    )

    # Run dance-off with live progress
    with Progress(
        SpinnerColumn(spinner_name="spinner_frames", style="green"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Dance-Off...", total=None)

        result = await dance_off.run()

        # Display round results
        for round_result in result.rounds:
            progress.update(task, description=f"Round {round_result.round_num}: {round_result.theme}")
            console.print(f"\n[cyan]Round {round_result.round_num}:[/cyan] Theme = [bold]{round_result.theme}[/bold]")

            # Show ASCII art for each model's SVG
            for svg in round_result.svg_results:
                if svg.status == "success" and svg.svg_code:
                    try:
                        ascii_art = svg_to_ascii(svg.svg_code, width=80, use_ansi=True)
                        console.print(f"  [cyan]{svg.model_name}:[/cyan]")
                        import sys
                        sys.stdout.write(ascii_art + "\n")
                    except Exception:
                        console.print(f"  [dim]{svg.model_name}: [italic](SVG render skipped)[/italic][/dim]")

            console.print(f"  [red]Eliminated:[/red] [bold]{round_result.eliminated}[/bold]")
            console.print(f"  [green]Survivors:[/green] {', '.join(dance_off.survivors)}")

    # Display champion
    console.print(f"\n[bold green]=== CHAMPION: {result.champion} ===[/bold green]\n")

    # Save dance-off result
    result_path = dance_off.save_result(result, str(run_dir))
    sys.stdout.write(f"\nDance-off data saved to: {make_clickable_link(result_path)}\n")

    # Generate HTML report
    html_path = run_dir / "dance_off_report.html"
    generate_dance_off_html(result, html_path)
    sys.stdout.write(f"Dance-off report saved to: {make_clickable_link(html_path)}\n")


if __name__ == "__main__":
    app()
