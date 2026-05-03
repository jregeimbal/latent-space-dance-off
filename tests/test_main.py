from unittest.mock import patch

from main import get_config, parse_models


class TestGetConfig:
    def test_returns_config_instance_with_defaults(self):
        with patch("main.Config") as MockConfig:
            result = get_config()

            MockConfig.assert_called_once_with(
                OLLAMA_HOST="http://localhost:11434",
                OUTPUT_DIR="./output",
                NUM_JUDGES=3,
                MODEL_LIST="",
                JUDGING_CRITERIA="",
                DISABLE_JUDGING=False,
                LLM_CLIENT="ollama",
                LLM_HOST="",
            )
            assert result == MockConfig.return_value

    def test_overrides_ollama_host(self):
        with patch("main.Config") as MockConfig:
            get_config(ollama_host="http://example.com:9999")

            MockConfig.assert_called_once()
            call_kwargs = MockConfig.call_args[1]
            assert call_kwargs["OLLAMA_HOST"] == "http://example.com:9999"

    def test_overrides_output_dir(self):
        with patch("main.Config") as MockConfig:
            get_config(output_dir="/tmp/results")

            call_kwargs = MockConfig.call_args[1]
            assert call_kwargs["OUTPUT_DIR"] == "/tmp/results"

    def test_overrides_num_judges(self):
        with patch("main.Config") as MockConfig:
            get_config(num_judges=5)

            call_kwargs = MockConfig.call_args[1]
            assert call_kwargs["NUM_JUDGES"] == 5

    def test_overrides_model_list(self):
        with patch("main.Config") as MockConfig:
            get_config(model_list="model1,model2")

            call_kwargs = MockConfig.call_args[1]
            assert call_kwargs["MODEL_LIST"] == "model1,model2"

    def test_overrides_judging_criteria(self):
        with patch("main.Config") as MockConfig:
            get_config(judging_criteria="style,clarity")

            call_kwargs = MockConfig.call_args[1]
            assert call_kwargs["JUDGING_CRITERIA"] == "style,clarity"

    def test_disables_judging(self):
        with patch("main.Config") as MockConfig:
            get_config(disable_judging=True)

            call_kwargs = MockConfig.call_args[1]
            assert call_kwargs["DISABLE_JUDGING"] is True

    def test_judging_enabled_by_default(self):
        with patch("main.Config") as MockConfig:
            get_config()

            call_kwargs = MockConfig.call_args[1]
            assert call_kwargs["DISABLE_JUDGING"] is False


class TestParseModels:
    def test_empty_string_returns_empty_list(self):
        assert parse_models("") == []

    def test_single_model_string(self):
        assert parse_models("gpt-oss") == ["gpt-oss"]

    def test_multiple_comma_separated(self):
        result = parse_models("m1,m2,m3")
        assert result == ["m1", "m2", "m3"]

    def test_extra_whitespace_stripped(self):
        result = parse_models(" m1 , m2 , m3 ")
        assert result == ["m1", "m2", "m3"]

    def test_empty_entries_between_commas_filtered(self):
        result = parse_models("m1,,m2,,m3")
        assert result == ["m1", "m2", "m3"]

    def test_whitespace_only_entries_filtered(self):
        result = parse_models("m1,  ,,,m2")
        assert result == ["m1", "m2"]


class TestDanceOffCommand:
    def test_dance_off_help_shows_options(self, cli_runner):
        """Dance-off command --help shows all options."""
        from main import app
        result = cli_runner.invoke(app, ["dance-off", "--help"])
        assert result.exit_code == 0
        assert "--models" in result.output
        assert "--theme-pool" in result.output
        assert "--judges" in result.output
        assert "--output" in result.output
        assert "--svg-per-model" in result.output

    def test_dance_off_command_exists(self, cli_runner):
        """Dance-off command is registered in the app."""
        from main import app
        command_names = [c.callback.__name__ for c in app.registered_commands if c.callback]
        assert "dance_off" in command_names
