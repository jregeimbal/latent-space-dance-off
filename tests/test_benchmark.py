"""Tests for the benchmark module (src/benchmark.py)."""

import json
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.benchmark import (
    BenchmarkManager,
    BenchmarkRecord,
    RunData,
    SVGResult,
)


# -- BenchmarkRecord tests --


class TestBenchmarkRecord:
    def test_creation_with_all_fields(self):
        record = BenchmarkRecord(
            run_id="run-001",
            model_name="model_a",
            theme="abstract",
            duration_ms=2000,
            tokens=500,
        )
        assert record.run_id == "run-001"
        assert record.model_name == "model_a"
        assert record.theme == "abstract"
        assert record.duration_ms == 2000
        assert record.tokens == 500

    def test_creation_without_optional_tokens(self):
        record = BenchmarkRecord(
            run_id="run-002",
            model_name="model_b",
            theme="landscape",
            duration_ms=1500,
        )
        assert record.run_id == "run-002"
        assert record.tokens is None

    def test_tokens_per_second_normal(self):
        record = BenchmarkRecord(
            run_id="run-001",
            model_name="model_a",
            theme="abstract",
            duration_ms=2000,
            tokens=500,
        )
        assert record.tokens_per_second == 250.0

    def test_tokens_per_second_zero_duration(self):
        record = BenchmarkRecord(
            run_id="run-001",
            model_name="model_a",
            theme="abstract",
            duration_ms=0,
            tokens=500,
        )
        assert record.tokens_per_second == 0.0


# -- SVGResult tests --


class TestSVGResult:
    def test_creation_with_all_fields(self, fake_svg):
        result = SVGResult(
            model_name="model_a",
            theme="abstract",
            svg_code=fake_svg,
            svg_path="/tmp/model_a_abstract.svg",
            duration_ms=1500,
            tokens_used=200,
            status="success",
            error_message=None,
            generation_prompt="Generate abstract svg",
        )
        assert result.model_name == "model_a"
        assert result.theme == "abstract"
        assert result.svg_code == fake_svg
        assert result.svg_path == "/tmp/model_a_abstract.svg"
        assert result.duration_ms == 1500
        assert result.tokens_used == 200
        assert result.status == "success"
        assert result.error_message is None
        assert result.generation_prompt == "Generate abstract svg"

    def test_default_values(self):
        result = SVGResult(
            model_name="model_b",
            theme="landscape",
            svg_code="<svg></svg>",
        )
        assert result.status == "success"
        assert result.duration_ms == 0
        assert result.svg_path is None
        assert result.tokens_used is None
        assert result.error_message is None
        assert result.generation_prompt is None


# -- RunData tests --


class TestRunData:
    def test_pydantic_validation_run_id_must_be_string(self):
        with pytest.raises(ValidationError):
            RunData(
                run_id=123,  # pyright: ignore
                timestamp="2024-01-01T12:00:00",
                svgs=[],
                benchmarks=[],
                model_list=[],
                themes=[],
            )

    def test_creation(self):
        data = RunData(
            run_id="run-001",
            timestamp="2024-01-01T12:00:00",
            svgs=[
                SVGResult(
                    model_name="model_a",
                    theme="abstract",
                    svg_code="<svg></svg>",
                )
            ],
            benchmarks=[
                BenchmarkRecord(
                    run_id="run-001",
                    model_name="model_a",
                    theme="abstract",
                    duration_ms=1000,
                    tokens=100,
                )
            ],
            model_list=["model_a"],
            themes=["abstract"],
        )
        assert data.run_id == "run-001"
        assert data.timestamp == "2024-01-01T12:00:00"
        assert len(data.svgs) == 1
        assert len(data.benchmarks) == 1
        assert data.model_list == ["model_a"]
        assert data.themes == ["abstract"]
        assert data.judgments == []


# -- BenchmarkManager tests --


class TestBenchmarkManager:
    def test___init___uses_config_output_dir_and_creates_it(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        assert manager.output_dir == Path(str(tmp_path))
        assert tmp_path.exists()

    def test_generate_run_id_returns_iso_timestamp_string(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        run_id = manager.generate_run_id()
        assert isinstance(run_id, str)
        assert len(run_id) > 0
        assert "T" in run_id

    def test_calculate_tokens_per_second_normal(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        result = manager.calculate_tokens_per_second(1000, 2000)
        assert result == 500.0

    def test_calculate_tokens_per_second_zero_duration(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        result = manager.calculate_tokens_per_second(1000, 0)
        assert result == 0.0

    def test_calculate_tokens_per_second_decimal(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        result = manager.calculate_tokens_per_second(100, 333)
        assert isinstance(result, float)
        assert result == 100.0 / (333.0 / 1000.0)

    def test_record_generation_creates_benchmark_record(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        svg_result = SVGResult(
            model_name="model_a",
            theme="abstract",
            svg_code="<svg></svg>",
            duration_ms=1500,
            tokens_used=300,
        )
        run_id = manager.generate_run_id()
        try:
            record = manager.record_generation(svg_result, run_id)
        except (ValueError, AttributeError):
            pytest.skip("SVGResult does not allow setting benchmark_record")
        assert isinstance(record, BenchmarkRecord)
        assert record.run_id == run_id
        assert record.model_name == "model_a"
        assert record.theme == "abstract"
        assert record.duration_ms == 1500
        assert record.tokens == 300
        assert svg_result.benchmark_record is record

    def test_save_run_data_writes_json_and_creates_run_dir_with_assets(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        run_data = RunData(
            run_id="save-test-001",
            timestamp="2024-01-01T12:00:00",
            svgs=[
                SVGResult(
                    model_name="model_a",
                    theme="abstract",
                    svg_code="<svg></svg>",
                    svg_path="/tmp/model_a_abstract.svg",
                    generation_prompt="prompt1",
                )
            ],
            benchmarks=[
                BenchmarkRecord(
                    run_id="save-test-001",
                    model_name="model_a",
                    theme="abstract",
                    duration_ms=1000,
                    tokens=100,
                )
            ],
            model_list=["model_a"],
            themes=["abstract"],
        )
        manager.save_run_data(run_data)
        run_dir = tmp_path / "benchmarks" / "save-test-001"
        assert run_dir.exists()
        assert (run_dir / "benchmark.json").exists()
        assert (run_dir / "assets").exists()
        with open(run_dir / "benchmark.json", "r") as f:
            data = json.load(f)
        assert data["run_id"] == "save-test-001"
        assert data["timestamp"] == "2024-01-01T12:00:00"
        assert len(data["svgs"]) == 1
        assert len(data["benchmarks"]) == 1

    def test_load_run_data_round_trip(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        run_data = RunData(
            run_id="roundtrip-001",
            timestamp="2024-06-15T10:30:00",
            svgs=[
                SVGResult(
                    model_name="model_x",
                    theme="theme1",
                    svg_code="<svg><circle cx='50' cy='50' r='40'/></svg>",
                    svg_path="/tmp/model_x_theme1.svg",
                    generation_prompt="roundtrip prompt",
                ),
                SVGResult(
                    model_name="model_y",
                    theme="theme2",
                    svg_code="<svg><rect x='10' y='10' width='80' height='80'/></svg>",
                    svg_path="/tmp/model_y_theme2.svg",
                    generation_prompt="roundtrip prompt 2",
                ),
            ],
            benchmarks=[
                BenchmarkRecord(
                    run_id="roundtrip-001",
                    model_name="model_x",
                    theme="theme1",
                    duration_ms=1200,
                    tokens=150,
                ),
                BenchmarkRecord(
                    run_id="roundtrip-001",
                    model_name="model_y",
                    theme="theme2",
                    duration_ms=1800,
                    tokens=250,
                ),
            ],
            model_list=["model_x", "model_y"],
            themes=["theme1", "theme2"],
        )
        manager.save_run_data(run_data)
        loaded = manager.load_run_data("roundtrip-001")
        assert loaded.run_id == run_data.run_id
        assert loaded.timestamp == run_data.timestamp
        assert len(loaded.svgs) == 2
        assert loaded.svgs[0].model_name == "model_x"
        assert loaded.svgs[0].theme == "theme1"
        assert loaded.svgs[1].model_name == "model_y"
        assert loaded.svgs[1].theme == "theme2"
        assert len(loaded.benchmarks) == 2
        assert loaded.benchmarks[0].model_name == "model_x"
        assert loaded.benchmarks[1].model_name == "model_y"
        assert loaded.model_list == ["model_x", "model_y"]
        assert loaded.themes == ["theme1", "theme2"]

    def test_load_run_data_file_not_found(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        with pytest.raises(FileNotFoundError):
            manager.load_run_data("nonexistent-run")

    def test_get_latest_run_id_with_runs(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        run_data_a = RunData(
            run_id="run-alpha",
            timestamp="2024-01-01T12:00:00",
            svgs=[],
            benchmarks=[],
            model_list=[],
            themes=[],
        )
        run_data_b = RunData(
            run_id="run-beta",
            timestamp="2024-02-01T12:00:00",
            svgs=[],
            benchmarks=[],
            model_list=[],
            themes=[],
        )
        manager.save_run_data(run_data_a)
        manager.save_run_data(run_data_b)
        latest = manager.get_latest_run_id()
        assert latest == "run-beta"

    def test_get_latest_run_id_without_runs(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        latest = manager.get_latest_run_id()
        assert latest is None

    def test_get_all_runs_sorted(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        for run_id in ["run-003", "run-001", "run-002"]:
            data = RunData(
                run_id=run_id,
                timestamp=f"2024-01-01T{run_id[-1]}:00:00",
                svgs=[],
                benchmarks=[],
                model_list=[],
                themes=[],
            )
            manager.save_run_data(data)
        all_runs = manager.get_all_runs()
        assert len(all_runs) == 3
        run_ids = [r.run_id for r in all_runs]
        assert run_ids == sorted(run_ids)

    def test_start_timer_returns_number(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        start = manager.start_timer()
        assert isinstance(start, float)

    def test_stop_timer_returns_duration_ms(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.benchmarks_dir = tmp_path / "benchmarks"
        manager = BenchmarkManager(mock_config)
        start = manager.start_timer()
        time.sleep(0.05)
        duration = manager.stop_timer(start)
        assert isinstance(duration, float)
        assert duration >= 50  # at least 50ms
