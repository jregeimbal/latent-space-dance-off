"""
ISOLATED Unit Test for config.py
Target: src/config.py
Session: ses_3

**WARNING**: THIS FILE WILL BE DELETED AFTER TEST PASSES
Test code preserved in: .opencode/unit-tests/
"""

import pytest
from pathlib import Path
from unittest.mock import mock_open, patch
from pydantic import ValidationError

# Import target file ONLY
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import Config


class TestConfig:
    """Isolated tests for Config class."""
    
    def test_default_values(self):
        """Test that defaults are set correctly."""
        config = Config()
        
        assert config.OLLAMA_HOST == "http://localhost:11434"
        assert config.NUM_JUDGES == 3
        assert config.OUTPUT_DIR == "./output"
        assert config.MODEL_LIST == ""
    
    def test_ollama_host_from_env(self):
        """Test OLLAMA_HOST can be set from environment."""
        with patch.dict('os.environ', {'OLLAMA_HOST': 'http://custom-host:11434'}):
            config = Config()
            assert config.OLLAMA_HOST == "http://custom-host:11434"
    
    def test_num_judges_from_env(self):
        """Test NUM_JUDGES can be set from environment."""
        with patch.dict('os.environ', {'NUM_JUDGES': '5'}):
            config = Config()
            assert config.NUM_JUDGES == 5
    
    def test_get_models_empty(self):
        """Test get_models returns empty list when MODEL_LIST is empty."""
        config = Config()
        assert config.get_models() == []
    
    def test_get_models_single(self):
        """Test get_models parses single model."""
        with patch.dict('os.environ', {'MODEL_LIST': 'llama3'}):
            config = Config()
            assert config.get_models() == ['llama3']
    
    def test_get_models_multiple(self):
        """Test get_models parses multiple comma-separated models."""
        with patch.dict('os.environ', {'MODEL_LIST': 'llama3,mistral,gemma'}):
            config = Config()
            assert config.get_models() == ['llama3', 'mistral', 'gemma']
    
    def test_get_models_with_spaces(self):
        """Test get_models handles whitespace in MODEL_LIST."""
        with patch.dict('os.environ', {'MODEL_LIST': '  llama3  ,  mistral  ,  gemma  '}):
            config = Config()
            assert config.get_models() == ['llama3', 'mistral', 'gemma']
    
    def test_output_path(self):
        """Test output_path joins OUTPUT_DIR with filename."""
        config = Config()
        path = config.output_path("test.svg")
        assert path == Path("./output/test.svg")
    
    def test_output_path_with_subdir(self):
        """Test output_path handles filenames with subdirectories."""
        config = Config()
        path = config.output_path("results/test.svg")
        assert path == Path("./output/results/test.svg")
    
    def test_get_judge_count_minimum(self):
        """Test get_judge_count returns minimum 1."""
        config = Config()
        assert config.get_judge_count() == 3
    
    def test_get_judge_count_from_env(self):
        """Test get_judge_count uses NUM_JUDGES from environment."""
        with patch.dict('os.environ', {'NUM_JUDGES': '7'}):
            config = Config()
            assert config.get_judge_count() == 7
    
    def test_create_output_dirs(self):
        """Test create_output_dirs creates output directory."""
        with patch.object(Path, 'mkdir') as mock_mkdir:
            config = Config()
            config.create_output_dirs()
            mock_mkdir.assert_called_once()
    
    def test_get_run_id_file(self):
        """Test get_run_id_file returns correct path."""
        config = Config()
        path = config.get_run_id_file()
        assert path == Path("./output/run_id.txt")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
