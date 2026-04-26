"""Tests for src utils module."""

import importlib.util
import sys
from pathlib import Path

import pytest

# Directly load src.utils without triggering src/__init__.py
_spec = importlib.util.spec_from_file_location(
     "src.utils",
     Path(__file__).parent.parent / "src" / "utils.py",
)
_utils = importlib.util.module_from_spec(_spec)
sys.modules["src.utils"] = _utils
_spec.loader.exec_module(_utils)

parse_svg_from_response = _utils.parse_svg_from_response
generate_svg_prompt = _utils.generate_svg_prompt
format_duration = _utils.format_duration
write_svg = _utils.write_svg
calculate_tokens_per_second = _utils.calculate_tokens_per_second


# parse_svg_from_response tests

class TestParseSvgFromResponse:
    def test_extract_svg_from_plain_text(self):
        text = "Here is your image: <svg xmlns='http://www.w3.org/2000/svg'><rect/></svg> Done."
        result = parse_svg_from_response(text)
        assert "<svg" in result
        assert "</svg>" in result

    def test_extract_svg_from_markdown_code_block(self):
        text = "```svg\n<svg xmlns='http://www.w3.org/2000/svg'><circle r='50'/></svg>\n```"
        result = parse_svg_from_response(text)
        assert "<svg" in result
        assert "</svg>" in result
        assert "<circle" in result

    def test_extract_from_non_svg_markdown_block(self):
        text = "```python\nprint('hello')\n```"
        with pytest.raises(ValueError):
            parse_svg_from_response(text)

    def test_raise_valueerror_when_no_svg_tags(self):
        text = "Just some regular text with no SVG at all."
        with pytest.raises(ValueError, match="No SVG"):
            parse_svg_from_response(text)

    def test_handle_multiple_svg_tags_returns_first(self):
        text = "<svg><a/></svg> <svg><b/></svg>"
        result = parse_svg_from_response(text)
        assert "<a/>" in result
        assert "<b/>" not in result

    def test_handle_whitespace_in_svg(self):
        text = "<svg  xmlns='http://www.w3.org/2000/svg'><rect/></svg>"
        result = parse_svg_from_response(text)
        assert "<svg" in result
        assert "</svg>" in result
        assert "<rect/>" in result


# generate_svg_prompt tests

class TestGenerateSvgPrompt:
    def test_abstract_theme(self):
        prompt = generate_svg_prompt("abstract", "MuseGPT")
        assert "MuseGPT" in prompt
        assert "abstract SVG" in prompt
        assert "5 different shapes" in prompt

    def test_landscape_theme(self):
        prompt = generate_svg_prompt("landscape", "ArtBot")
        assert "ArtBot" in prompt
        assert "landscape" in prompt
        assert "gradient" in prompt
        assert "foreground" in prompt

    def test_portrait_theme(self):
        prompt = generate_svg_prompt("portrait", "DrawAI")
        assert "DrawAI" in prompt
        assert "portrait" in prompt
        assert "portrait" in prompt.lower()
        assert "face" in prompt

    def test_object_theme(self):
        prompt = generate_svg_prompt("object", "VecPro")
        assert "VecPro" in prompt
        assert "object" in prompt
        assert "cup" in prompt or "clock" in prompt

    def test_scene_theme(self):
        prompt = generate_svg_prompt("scene", "SceneGen")
        assert "SceneGen" in prompt
        assert "scene" in prompt
        assert "midground" in prompt
        assert "foreground" in prompt

    def test_custom_theme_fallback_to_abstract(self):
        prompt = generate_svg_prompt("manga", "MuseGPT")
        assert "abstract" in prompt.lower()


# format_duration tests

class TestFormatDuration:
    def test_seconds_under_60(self):
        assert format_duration(30) == "30.0s"
        assert format_duration(59.9) == "59.9s"

    def test_minutes_range(self):
        assert format_duration(60) == "1m 0.0s"
        assert format_duration(120) == "2m 0.0s"

    def test_hours_range(self):
        result = format_duration(3600)
        assert "h" in result
        assert "1h 0m 0.0s" in result

    def test_hours_with_minutes(self):
        result = format_duration(3665)
        assert "1h 1m 5.0s" in result

    def test_zero_duration(self):
        assert format_duration(0) == "0.0s"

    def test_decimal_values(self):
        result = format_duration(45.7)
        assert result == "45.7s"

    def test_very_small_values(self):
        result = format_duration(0.5)
        assert result == "0.5s"


# write_svg tests

class TestWriteSvg:
    def test_write_to_file(self, tmp_path):
        svg = "<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>"
        filepath = tmp_path / "output.svg"
        write_svg(svg, filepath)
        assert filepath.exists()
        assert filepath.read_text() == svg

    def test_create_directories_if_needed(self, tmp_path):
        svg = "<svg xmlns='http://www.w3.org/2000/svg'><circle r='10'/></svg>"
        filepath = tmp_path / "deep" / "nested" / "dir" / "output.svg"
        write_svg(svg, filepath)
        assert filepath.exists()

    def test_preserve_xml_declaration(self, tmp_path):
        svg = '<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        filepath = tmp_path / "declaration.svg"
        write_svg(svg, filepath)
        content = filepath.read_text()
        assert '<?xml' in content
        assert 'version="1.0"' in content

    def test_handle_special_characters(self, tmp_path):
        svg = "<svg xmlns='http://www.w3.org/2000/svg'><text>&amp;é&uuml;</text></svg>"
        filepath = tmp_path / "special.svg"
        write_svg(svg, filepath)
        content = filepath.read_text()
        assert "&amp;" in content or '&' in content


# calculate_tokens_per_second tests

class TestCalculateTokensPerSecond:
    def test_normal_case(self):
        result = calculate_tokens_per_second(1024, 2048)
        assert result == 500.0

    def test_zero_duration_returns_zero(self):
        result = calculate_tokens_per_second(100, 0)
        assert result == 0.0

    def test_negative_duration_returns_zero(self):
        result = calculate_tokens_per_second(100, -500)
        assert result == 0.0
