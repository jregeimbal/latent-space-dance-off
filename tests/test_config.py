import os
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest
from pydantic import ValidationError

from src.config import Config, get_config


# -- Default values --


class TestDefaultValues:

    def test_default_ollama_host(self):
        config = Config()
        assert config.OLLAMA_HOST == "http://localhost:11434"

    def test_default_num_judges(self):
        config = Config()
        assert config.NUM_JUDGES == 3

    def test_default_output_dir(self):
        config = Config()
        assert config.OUTPUT_DIR == "./output"

    def test_default_model_list(self):
        config = Config()
        assert config.MODEL_LIST == ""

    def test_default_num_themes(self):
        config = Config()
        assert config.NUM_THEMES == 3

    def test_default_creativity_weight(self):
        config = Config()
        assert config.DEFAULT_CREATIVITY_WEIGHT == 0.33

    def test_default_aesthetics_weight(self):
        config = Config()
        assert config.DEFAULT_AESTHETICS_WEIGHT == 0.33

    def test_default_complexity_weight(self):
        config = Config()
        assert config.DEFAULT_COMPLEXITY_WEIGHT == 0.34

    def test_default_judging_criteria(self):
        config = Config()
        assert config.JUDGING_CRITERIA == "creativity,aesthetics,complexity"

    def test_default_disable_judging(self):
        config = Config()
        assert config.DISABLE_JUDGING is False

    def test_disable_judging_custom(self):
        config = Config(DISABLE_JUDGING=True)
        assert config.DISABLE_JUDGING is True


# -- Env var loading (via constructor) --


class TestEnvVarLoading:

    def test_ollama_host_env(self):
        config = Config(OLLAMA_HOST="http://remote:11434")
        assert config.OLLAMA_HOST == "http://remote:11434"

    def test_ollama_host_empty_string_override(self):
        config = Config(OLLAMA_HOST="")
        assert config.OLLAMA_HOST == ""

    def test_num_judges_env(self):
        config = Config(NUM_JUDGES=5)
        assert config.NUM_JUDGES == 5

    def test_model_list_env(self):
        config = Config(MODEL_LIST="llama3,mistral,gemma")
        assert config.MODEL_LIST == "llama3,mistral,gemma"

    def test_multiple_fields_env(self):
        config = Config(
            MODEL_LIST="llama3,mistral,gemma",
            NUM_JUDGES=7,
        )
        assert config.MODEL_LIST == "llama3,mistral,gemma"
        assert config.NUM_JUDGES == 7

    def test_num_themes_env(self):
        config = Config(NUM_THEMES=5)
        assert config.NUM_THEMES == 5

    def test_models_property_uses_model_list_value(self):
        config = Config(MODEL_LIST="llama3,mistral,gemma")
        assert config.models == ["llama3", "mistral", "gemma"]

    def test_judging_criteria_property_uses_judging_criteria_value(self):
        config = Config(JUDGING_CRITERIA="style,originality")
        assert config.judging_criteria == ["style", "originality"]


# -- models property --


class TestModelsProperty:

    def test_models_empty(self):
        config = Config()
        assert config.models == []

    def test_models_single(self):
        config = Config(MODEL_LIST="llama3")
        assert config.models == ["llama3"]

    def test_models_multiple(self):
        config = Config(MODEL_LIST="llama3,mistral,gemma")
        assert config.models == ["llama3", "mistral", "gemma"]

    def test_models_whitespace_trimming(self):
        config = Config(MODEL_LIST=" llama3 , mistral , llama3 ")
        assert config.models == ["llama3", "mistral", "llama3"]

    def test_models_whitespace_only(self):
        config = Config(MODEL_LIST="       ")
        assert config.models == []

    def test_models_no_spaces_after_comma(self):
        config = Config(MODEL_LIST="a,b,c")
        assert config.models == ["a", "b", "c"]

    def test_models_falsy_entries_filtered(self):
        config = Config(MODEL_LIST="llama3,,mistral")
        assert config.models == ["llama3", "mistral"]


# -- judging_criteria property --


class TestJudgingCriteriaProperty:

    def test_judging_criteria_default(self):
        config = Config()
        assert config.judging_criteria == ["creativity", "aesthetics", "complexity"]

    def test_judging_criteria_custom(self):
        config = Config(JUDGING_CRITERIA="style,originality")
        assert config.judging_criteria == ["style", "originality"]

    def test_judging_criteria_empty_falls_back(self):
        config = Config(JUDGING_CRITERIA="")
        assert config.judging_criteria == ["creativity", "aesthetics", "complexity"]

    def test_judging_criteria_whitespace(self):
        config = Config(JUDGING_CRITERIA="style , originality ")
        assert config.judging_criteria == ["style", "originality"]

    def test_judging_criteria_falsy_entries_filtered(self):
        config = Config(JUDGING_CRITERIA="style,,originality")
        assert config.judging_criteria == ["style", "originality"]


# -- Path properties --


class TestPathProperties:

    def test_svgs_dir_default_output(self):
        config = Config()
        assert config.svgs_dir == Path("./output/svgs")

    def test_svgs_dir_custom_output(self):
        config = Config(OUTPUT_DIR="./runs")
        assert config.svgs_dir == Path("./runs/svgs")

    def test_benchmarks_dir_default(self):
        config = Config()
        assert config.benchmarks_dir == Path("./output/benchmarks")

    def test_benchmarks_dir_custom(self):
        config = Config(OUTPUT_DIR="./runs")
        assert config.benchmarks_dir == Path("./runs/benchmarks")

    def test_leaderboards_dir_default(self):
        config = Config()
        assert config.leaderboards_dir == Path("./output/leaderboards")

    def test_leaderboards_dir_custom(self):
        config = Config(OUTPUT_DIR="./runs")
        assert config.leaderboards_dir == Path("./runs/leaderboards")


# -- output_path() --


class TestOutputPath:

    def test_output_path_default(self):
        config = Config()
        assert config.output_path("results.svg") == Path("./output/results.svg")

    def test_output_path_custom_output_dir(self):
        config = Config(OUTPUT_DIR="./results")
        assert config.output_path("chart.svg") == Path("./results/chart.svg")


# -- get_judge_count() --


class TestGetJudgeCount:

    def test_judge_count_default(self):
        config = Config()
        assert config.get_judge_count() == 3

    def test_judge_count_custom(self):
        config = Config(NUM_JUDGES=7)
        assert config.get_judge_count() == 7


# -- get_run_id_file() --


class TestGetRunIdFile:

    def test_run_id_file_default(self):
        config = Config()
        assert config.get_run_id_file() == Path("./output/run_ids.txt")

    def test_run_id_file_custom_output_dir(self):
        config = Config(OUTPUT_DIR="./results")
        assert config.get_run_id_file() == Path("./results/run_ids.txt")


# -- create_output_dirs() --


class TestCreateOutputDirs:

    def test_create_output_dirs_calls_mkdir(self):
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            config = Config()
            config.create_output_dirs()
            assert mock_mkdir.call_count == 3

    def test_create_output_dirs_calls_mkdir_with_correct_kwargs(self):
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            config = Config(OUTPUT_DIR="./output")
            config.create_output_dirs()
            assert mock_mkdir.call_count == 3
            for call_args in mock_mkdir.call_args_list:
                assert call_args.kwargs.get("parents") is True
                assert call_args.kwargs.get("exist_ok") is True


# -- Pydantic validation --


class TestPydanticValidation:

    def test_num_judges_below_minimum_raises(self):
        with pytest.raises(ValidationError):
            Config(NUM_JUDGES=0)

    def test_num_judges_above_maximum_raises(self):
        with pytest.raises(ValidationError):
            Config(NUM_JUDGES=51)

    def test_num_judges_boundaries_accepted(self):
        Config(NUM_JUDGES=1)
        Config(NUM_JUDGES=50)

    def test_creativity_weight_below_zero_raises(self):
        with pytest.raises(ValidationError):
            Config(DEFAULT_CREATIVITY_WEIGHT=-0.01)

    def test_creativity_weight_above_one_raises(self):
        with pytest.raises(ValidationError):
            Config(DEFAULT_CREATIVITY_WEIGHT=1.01)

    def test_creativity_weight_boundaries_accepted(self):
        Config(DEFAULT_CREATIVITY_WEIGHT=0)
        Config(DEFAULT_CREATIVITY_WEIGHT=1)

    def test_aesthetics_weight_below_zero_raises(self):
        with pytest.raises(ValidationError):
            Config(DEFAULT_AESTHETICS_WEIGHT=-0.01)

    def test_aesthetics_weight_above_one_raises(self):
        with pytest.raises(ValidationError):
            Config(DEFAULT_AESTHETICS_WEIGHT=1.01)

    def test_aesthetics_weight_boundaries_accepted(self):
        Config(DEFAULT_AESTHETICS_WEIGHT=0)
        Config(DEFAULT_AESTHETICS_WEIGHT=1)

    def test_complexity_weight_below_zero_raises(self):
        with pytest.raises(ValidationError):
            Config(DEFAULT_COMPLEXITY_WEIGHT=-0.01)

    def test_complexity_weight_above_one_raises(self):
        with pytest.raises(ValidationError):
            Config(DEFAULT_COMPLEXITY_WEIGHT=1.01)

    def test_complexity_weight_boundaries_accepted(self):
        Config(DEFAULT_COMPLEXITY_WEIGHT=0)
        Config(DEFAULT_COMPLEXITY_WEIGHT=1)


# -- __str__ --


class TestStr:

    def test_str_non_empty(self):
        config = Config()
        result = str(config)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_str_contains_ollama_host(self):
        config = Config()
        assert "OLLAMA_HOST" in str(config)

    def test_str_contains_num_judges(self):
        config = Config(NUM_JUDGES=4)
        assert "NUM_JUDGES: 4" in str(config)

    def test_str_contains_models(self):
        config = Config(MODEL_LIST="llama3,mistral")
        assert "MODELS:" in str(config)


# -- get_config() --


class TestGetConfig:

    def test_get_config_returns_config_instance(self):
        result = get_config()
        assert isinstance(result, Config)

    def test_get_config_returns_default_values(self):
        result = get_config()
        assert result.OLLAMA_HOST == "http://localhost:11434"
        assert result.NUM_JUDGES == 3
