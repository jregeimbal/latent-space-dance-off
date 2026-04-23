"""
ISOLATED Unit Test for benchmark.py
Target: src/benchmark.py
Session: ses_X

**WARNING**: THIS FILE WILL BE DELETED AFTER TEST PASSES
Test code preserved in: .opencode/unit-tests/
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Import the target module
import sys
sys.path.insert(0, 'src')

from benchmark import (
    BenchmarkManager,
    BenchmarkRecord,
    RunData,
    SVGResult
)


class MockConfig:
    """Mock Config for testing"""
    def __init__(self):
        self.output_dir = Path("/tmp/test_benchmarks")
        self.benchmarks_dir = self.output_dir / "benchmarks"


@pytest.fixture
def mock_config():
    """Create mock config"""
    return MockConfig()


@pytest.fixture
def benchmark_manager(mock_config):
    """Create BenchmarkManager instance"""
    # Ensure test directory exists
    mock_config.benchmarks_dir.mkdir(parents=True, exist_ok=True)
    bm = BenchmarkManager(mock_config)
    return bm


class TestBenchmarkRecord:
    """Tests for BenchmarkRecord Pydantic model"""
    
    def test_benchmark_record_creation(self):
        """Test creating a BenchmarkRecord instance"""
        record = BenchmarkRecord(
            run_id="test-run-123",
            model_name="llama3",
            theme="abstract",
            duration_ms=1500,
            tokens=125
        )
        
        assert record.run_id == "test-run-123"
        assert record.model_name == "llama3"
        assert record.theme == "abstract"
        assert record.duration_ms == 1500
        assert record.tokens == 125
        assert record.tokens_per_second == pytest.approx(83.33, rel=0.01)
    
    def test_benchmark_record_zero_duration(self):
        """Test that tps is 0 when duration is 0"""
        record = BenchmarkRecord(
            run_id="test-run-123",
            model_name="llama3",
            theme="landscape",
            duration_ms=0,
            tokens=100
        )
        
        assert record.tokens_per_second == 0.0
    
    def test_benchmark_record_pydantic_validation(self):
        """Test Pydantic validation of fields"""
        with pytest.raises(ValueError):
            BenchmarkRecord(
                run_id=123,  # Should be string
                model_name="test",
                theme="abstract",
                duration_ms=100,
                tokens=50
            )


class TestSVGResult:
    """Tests for SVGResult Pydantic model"""
    
    def test_svg_result_creation(self):
        """Test creating SVGResult instance"""
        svg_result = SVGResult(
            model_name="llama3",
            theme="abstract",
            svg_code="<svg></svg>",
            svg_path="/tmp/test.svg"
        )
        
        assert svg_result.model_name == "llama3"
        assert svg_result.theme == "abstract"
        assert svg_result.svg_code == "<svg></svg>"
        assert svg_result.svg_path == "/tmp/test.svg"
        assert svg_result.benchmark_record is None


class TestBenchmarkManager:
    """Tests for BenchmarkManager class"""
    
    def test_initialization(self, benchmark_manager, mock_config):
        """Test BenchmarkManager initialization"""
        assert benchmark_manager.config == mock_config
        assert benchmark_manager.benchmarks_dir == mock_config.benchmarks_dir
    
    def test_generate_run_id(self, benchmark_manager):
        """Test run_id generation"""
        run_id = benchmark_manager.generate_run_id()
        
        assert isinstance(run_id, str)
        assert len(run_id) > 0
        # Run ID should contain timezone notation
        assert 'T' in run_id or '.' in run_id
    
    def test_calculate_tokens_per_second(self, benchmark_manager):
        """Test tokens per second calculation"""
        # Test normal case
        tps = benchmark_manager.calculate_tokens_per_second(100, 1000)
        assert tps == pytest.approx(100.0, rel=0.01)
        
        # Test zero duration (should return 0)
        tps_zero = benchmark_manager.calculate_tokens_per_second(100, 0)
        assert tps_zero == 0.0
        
        # Test decimal duration
        tps_decimal = benchmark_manager.calculate_tokens_per_second(50, 500)
        assert tps_decimal == pytest.approx(100.0, rel=0.01)
    
    def test_record_generation(self, benchmark_manager, mock_config):
        """Test recording a generation"""
        svg_result = SVGResult(
            model_name="llama3",
            theme="abstract",
            svg_code="<svg></svg>",
            svg_path="/tmp/test.svg"
        )
        run_id = "test-run-123"
        
        # Mock time to return fixed value
        with patch('benchmark.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 4, 22, 20, 30, 0)
            mock_datetime.utcnow.return_value = datetime(2026, 4, 22, 20, 30, 0)
            
            record = benchmark_manager.record_generation(svg_result, run_id)
        
        assert record.run_id == run_id
        assert record.model_name == "llama3"
        assert record.theme == "abstract"
        assert isinstance(record.duration_ms, (int, float))
        assert record.tokens is None  # Not provided in SVGResult
    
    def test_save_run_data_creates_file(self, benchmark_manager, mock_config):
        """Test saving run data to file"""
        run_data = RunData(
            run_id="test-run-456",
            timestamp="2026-04-22T20:30:00Z",
            svgs=[],
            benchmarks=[],
            model_list=["llama3", "gemma2"],
            themes=["abstract", "landscape"]
        )
        
        saved_id = benchmark_manager.save_run_data(run_data)
        
        assert saved_id == "test-run-456"
        expected_path = mock_config.benchmarks_dir / "test-run-456.json"
        assert expected_path.exists()
    
    def test_save_run_data_content(self, benchmark_manager, mock_config):
        """Test saved run data content"""
        run_data = RunData(
            run_id="test-run-789",
            timestamp="2026-04-22T20:45:00Z",
            svgs=[],
            benchmarks=[],
            model_list=["mistral"],
            themes=["portrait"]
        )
        
        benchmark_manager.save_run_data(run_data)
        
        expected_path = mock_config.benchmarks_dir / "test-run-789.json"
        with open(expected_path, 'r') as f:
            data = json.load(f)
        
        assert data["run_id"] == "test-run-789"
        assert data["timestamp"] == "2026-04-22T20:45:00Z"
        assert data["model_list"] == ["mistral"]
        assert data["themes"] == ["portrait"]
    
    def test_load_run_data(self, benchmark_manager, mock_config):
        """Test loading run data from file"""
        # First save some data
        run_data = RunData(
            run_id="load-test-123",
            timestamp="2026-04-22T21:00:00Z",
            svgs=[],
            benchmarks=[BenchmarkRecord(
                run_id="load-test-123",
                model_name="llama3",
                theme="abstract",
                duration_ms=500,
                tokens=75
            )],
            model_list=["llama3"],
            themes=["abstract"]
        )
        benchmark_manager.save_run_data(run_data)
        
        # Load it back
        loaded_data = benchmark_manager.load_run_data("load-test-123")
        
        assert loaded_data.run_id == "load-test-123"
        assert len(loaded_data.benchmarks) == 1
        assert loaded_data.benchmarks[0].model_name == "llama3"
    
    def test_load_run_data_not_found(self, benchmark_manager, mock_config):
        """Test loading non-existent run data raises error"""
        with pytest.raises(FileNotFoundError):
            benchmark_manager.load_run_data("non-existent-run-id")
    
    def test_get_latest_run_id(self, benchmark_manager, mock_config):
        """Test getting latest run ID"""
        # Create some test files
        test_files = [
            "2026-04-22T20:00:00",
            "2026-04-22T21:00:00",
            "2026-04-22T22:00:00"
        ]
        
        for run_id in test_files:
            run_data = RunData(
                run_id=run_id,
                timestamp=f"2026-04-22T{run_id.split('T')[1]}",
                svgs=[],
                benchmarks=[],
                model_list=["test"],
                themes=["test"]
            )
            benchmark_manager.save_run_data(run_data)
        
        latest = benchmark_manager.get_latest_run_id()
        
        assert latest == "2026-04-22T22:00:00"
    
    def test_get_latest_run_id_empty(self, benchmark_manager, mock_config):
        """Test getting latest run ID when no runs exist"""
        latest = benchmark_manager.get_latest_run_id()
        assert latest is None
    
    def test_get_all_runs(self, benchmark_manager, mock_config):
        """Test getting all run data"""
        # Create some test runs
        for i in range(2):
            run_data = RunData(
                run_id=f"test-run-{i}",
                timestamp=f"2026-04-22T{i}:00:00Z",
                svgs=[],
                benchmarks=[],
                model_list=["model-i"],
                themes=["theme-i"]
            )
            benchmark_manager.save_run_data(run_data)
        
        all_runs = benchmark_manager.get_all_runs()
        
        assert len(all_runs) == 2
        assert all(isinstance(run, RunData) for run in all_runs)
    
    def test_run_data_pydantic_validation(self, benchmark_manager, mock_config):
        """Test RunData Pydantic validation"""
        with pytest.raises(ValueError):
            # timestamp must be string
            RunData(
                run_id=123,
                timestamp=123,  # Should be string
                svgs=[],
                benchmarks=[],
                model_list=["llama3"],
                themes=["abstract"]
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
