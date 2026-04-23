"""
ISOLATED Unit Test for utils.py
Target: src/utils.py
Session: ses_1

**WARNING**: THIS FILE WILL BE DELETED AFTER TEST PASSES
Test code preserved in: .opencode/unit-tests/
"""

import pytest
from pathlib import Path
from unittest.mock import mock_open, patch
import sys
import os

# Add src to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils import (
    parse_svg_from_response,
    generate_svg_prompt,
    format_duration,
    write_svg,
)


class TestParseSvgFromResponse:
    """Tests for parse_svg_from_response function"""

    def test_extract_svg_from_plain_text(self):
        """Should extract SVG from plain text"""
        text = """Here is the SVG you requested:
        <svg width="100" height="100">
            <circle cx="50" cy="50" r="40"/>
        </svg>
        """
        result = parse_svg_from_response(text)
        assert '<svg' in result
        assert '</svg>' in result
        assert '<circle' in result

    def test_extract_svg_from_markdown_code_block(self):
        """Should extract SVG from markdown code block"""
        text = """```svg
        <svg width="200" height="200">
            <rect x="10" y="10" width="180" height="180"/>
        </svg>
        ```"""
        result = parse_svg_from_response(text)
        assert '<svg' in result
        assert '</svg>' in result
        assert '<rect' in result

    def test_extract_svg_from_markdown_python_block(self):
        """Should extract SVG even from non-SVG markdown blocks"""
        text = """```python
        svg_content = \"\"\"
        <svg width="150" height="150">
            <polygon points="50,50 100,100 150,50"/>
        </svg>
        \"\"\"
        ```"""
        result = parse_svg_from_response(text)
        assert '<svg' in result
        assert '</svg>' in result
        assert '<polygon' in result

    def test_raise_error_when_no_svg_found(self):
        """Should raise ValueError when no SVG tags are found"""
        text = "This is just regular text with no SVG content"
        with pytest.raises(ValueError) as exc_info:
            parse_svg_from_response(text)
        assert "No SVG found" in str(exc_info.value)

    def test_handle_multiple_svg_tags(self):
        """Should extract the first SVG found when multiple exist"""
        text = """<svg width="50" height="50">&lt;/svg&gt;<svg width="300" height="300">
            <line x1="0" y1="0" x2="300" y2="300"/>
        </svg>"""
        result = parse_svg_from_response(text)
        assert 'width="300"' in result
        assert '<line' in result

    def test_handle_whitespace_in_svg(self):
        """Should handle SVG with excessive whitespace"""
        text = """
        
        <svg  
            width="250" 
            height="250"
        >
            <ellipse cx="125" cy="125" rx="100" ry="80"/>
        </svg>
        
        """
        result = parse_svg_from_response(text)
        assert '<svg' in result
        assert '<ellipse' in result


class TestGenerateSvgPrompt:
    """Tests for generate_svg_prompt function"""

    def test_abstract_theme(self):
        """Should generate appropriate prompt for abstract theme"""
        prompt = generate_svg_prompt(theme="abstract", model_name="gemma3")
        assert "abstract" in prompt.lower()
        assert "SVG" in prompt or "svg" in prompt
        assert "gemma3" in prompt.lower()

    def test_landscape_theme(self):
        """Should generate appropriate prompt for landscape theme"""
        prompt = generate_svg_prompt(theme="landscape", model_name="llama3.2")
        assert "landscape" in prompt.lower()
        assert "SVG" in prompt or "svg" in prompt
        assert "llama3.2" in prompt.lower()

    def test_portrait_theme(self):
        """Should generate appropriate prompt for portrait theme"""
        prompt = generate_svg_prompt(theme="portrait", model_name="mistral")
        assert "portrait" in prompt.lower()
        assert "SVG" in prompt or "svg" in prompt
        assert "mistral" in prompt.lower()

    def test_object_theme(self):
        """Should generate appropriate prompt for object theme"""
        prompt = generate_svg_prompt(theme="object", model_name="phi3")
        assert "object" in prompt.lower()
        assert "SVG" in prompt or "svg" in prompt
        assert "phi3" in prompt.lower()

    def test_scene_theme(self):
        """Should generate appropriate prompt for scene theme"""
        prompt = generate_svg_prompt(theme="scene", model_name="llava")
        assert "scene" in prompt.lower()
        assert "SVG" in prompt or "svg" in prompt
        assert "llava" in prompt.lower()

    def test_custom_theme(self):
        """Should generate a prompt for custom themes"""
        prompt = generate_svg_prompt(theme="cyberpunk", model_name="gemma3")
        assert "cyberpunk" in prompt.lower()
        assert "SVG" in prompt or "svg" in prompt

    def test_prompt_structure_has_instructions(self):
        """Should include model-specific instructions"""
        prompt = generate_svg_prompt(theme="abstract", model_name="gemma3")
        # Check for typical SVG generation instructions
        assert any(phrase.lower() in prompt.lower() 
                   for phrase in [
                       "svg", "vector", "shape", "color", 
                       "design", "graphic"
                   ])


class TestFormatDuration:
    """Tests for format_duration function"""

    def test_format_seconds(self):
        """Should format seconds correctly"""
        assert format_duration(3) == "3s"
        assert format_duration(30) == "30s"

    def test_format_minutes(self):
        """Should format minutes and seconds correctly"""
        assert format_duration(60) == "1m 0s"
        assert format_duration(90) == "1m 30s"
        assert format_duration(125) == "2m 5s"

    def test_format_multiple_minutes(self):
        """Should format multiple minutes correctly"""
        assert format_duration(95) == "1m 35s"
        assert format_duration(180) == "3m 0s"
        assert format_duration(3661) == "1h 1m 1s"

    def test_format_decimal_seconds(self):
        """Should handle decimal values"""
        assert format_duration(60.5) == "1m 0s"
        assert format_duration(125.9) == "2m 6s"

    def test_format_zero(self):
        """Should handle zero duration"""
        assert format_duration(0) == "0s"

    def test_format_less_than_one_second(self):
        """Should handle very small values"""
        assert format_duration(0.5) == "1s"
        assert format_duration(0.1) == "1s"


class TestWriteSvg:
    """Tests for write_svg function"""

    def test_write_svg_to_file(self, tmp_path):
        """Should write SVG content to specified file path"""
        svg_content = '<svg width="100" height="100"><circle cx="50" cy="50" r="40"/></svg>'
        filepath = tmp_path / "test.svg"
        
        write_svg(svg_content, filepath)
        
        assert filepath.exists()
        content = filepath.read_text()
        assert svg_content in content

    def test_create_directories_if_needed(self, tmp_path):
        """Should create directories if they don't exist"""
        svg_content = '<svg width="50" height="50"/></svg>'
        subdirectory = tmp_path / "subdir" / "nested"
        filepath = subdirectory / "test.svg"
        
        write_svg(svg_content, filepath)
        
        assert filepath.exists()

    def test_write_svg_with_xml_declaration(self, tmp_path):
        """Should preserve XML declaration in SVG"""
        svg_content = '<?xml version="1.0" encoding="UTF-8"?><svg width="100"/></svg>'
        filepath = tmp_path / "test.svg"
        
        write_svg(svg_content, filepath)
        
        content = filepath.read_text()
        assert '<?xml' in content

    def test_write_svg_with_special_characters(self, tmp_path):
        """Should handle SVG with special characters"""
        svg_content = '<svg><text>&copy; 2024 Test &amp; Company</text></svg>'
        filepath = tmp_path / "test.svg"
        
        write_svg(svg_content, filepath)
        
        content = filepath.read_text()
        assert '&' in content
