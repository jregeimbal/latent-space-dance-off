"""Tests for src/svg_generator.py."""

from unittest.mock import AsyncMock

import pytest

from src.llm_client import LLMChunk
from src.svg_generator import SVGGenerator, SVGResult


def _run_async(coro):
    """Helper to run an async coroutine in a test without pytest-asyncio."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        asyncio.set_event_loop(None)
        loop.close()


# ---------------------------------------------------------------------------
# 1. SVGResult (pydantic)
# ---------------------------------------------------------------------------

class TestSVGResult:
    def test_creation_with_all_fields(self):
        result = SVGResult(
            model_name="llama3",
            theme="abstract",
            svg_code="<svg></svg>",
            svg_path="/tmp/out.svg",
            duration_ms=123.4,
            tokens_used=42,
            status="success",
            error_message=None,
            generation_prompt="make svg",
        )
        assert result.model_name == "llama3"
        assert result.theme == "abstract"
        assert result.svg_code == "<svg></svg>"
        assert result.svg_path == "/tmp/out.svg"
        assert result.duration_ms == 123.4
        assert result.tokens_used == 42
        assert result.status == "success"
        assert result.error_message is None
        assert result.generation_prompt == "make svg"

    def test_default_values(self):
        result = SVGResult(
            model_name="llama3",
            theme="abstract",
            svg_code="<svg></svg>",
        )
        assert result.svg_path is None
        assert result.duration_ms == 0
        assert result.tokens_used is None
        assert result.status == "success"
        assert result.error_message is None
        assert result.generation_prompt is None


# ---------------------------------------------------------------------------
# 2. Prompt generators
# ---------------------------------------------------------------------------

class TestPromptGenerators:
    @pytest.fixture
    def generator(self, mock_config):
        return SVGGenerator(mock_config)

    def test_generate_abstract_svg_prompt(self, generator):
        prompt = generator.generate_abstract_svg_prompt("llama3")
        assert "llama3" in prompt
        shape_keywords = ["rect", "circle", "ellipse", "polygon", "polyline", "path", "line"]
        found = [kw for kw in shape_keywords if kw in prompt]
        assert len(found) >= 5
        assert "3 different colors" in prompt or "3 different colors or gradients" in prompt
        assert "SVG" in prompt
        assert "Respond with ONLY" in prompt

    def test_generate_landscape_svg_prompt(self, generator):
        prompt = generator.generate_landscape_svg_prompt("llama3")
        assert "landscape" in prompt.lower()
        assert "llama3" in prompt
        scene_words = ["sky", "mountain", "water", "tree", "cloud"]
        found = [w for w in scene_words if w in prompt.lower()]
        assert len(found) >= 3
        assert "SVG" in prompt
        assert "Respond with ONLY" in prompt

    def test_generate_portrait_svg_prompt(self, generator):
        prompt = generator.generate_portrait_svg_prompt("llama3")
        assert "portrait" in prompt.lower()
        assert "llama3" in prompt
        portrait_refs = ["face", "figure", "hair", "clothing"]
        found = [w for w in portrait_refs if w in prompt.lower()]
        assert len(found) >= 3
        assert "SVG" in prompt
        assert "Respond with ONLY" in prompt

    def test_generate_object_svg_prompt(self, generator):
        prompt = generator.generate_object_svg_prompt("llama3")
        assert "object" in prompt.lower()
        assert "llama3" in prompt
        object_refs = ["cup", "clock", "flower", "lightbulb", "subject"]
        found = [w for w in object_refs if w in prompt.lower()]
        assert len(found) >= 3
        assert "SVG" in prompt
        assert "Respond with ONLY" in prompt

    def test_generate_scene_svg_prompt(self, generator):
        prompt = generator.generate_scene_svg_prompt("llama3")
        assert "scene" in prompt.lower()
        assert "llama3" in prompt
        scene_refs = ["background", "midground", "foreground"]
        found = [w for w in scene_refs if w in prompt.lower()]
        assert len(found) >= 3
        assert "SVG" in prompt
        assert "Respond with ONLY" in prompt

    def test_generate_generic_svg_prompt(self, generator):
        prompt = generator.generate_generic_svg_prompt("abstract", "llama3")
        assert "abstract" in prompt.lower()
        assert "SVG" in prompt


# ---------------------------------------------------------------------------
# 3. SVGGenerator._get_svg_prompt
# ---------------------------------------------------------------------------

class TestGetSvgPrompt:
    @pytest.fixture
    def generator(self, mock_config):
        return SVGGenerator(mock_config)

    def test_routes_abstract(self, generator):
        prompt = generator._get_svg_prompt("abstract", "llama3")
        assert "abstract" in prompt.lower()
        assert "geometric shapes" in prompt.lower()

    def test_routes_landscape(self, generator):
        prompt = generator._get_svg_prompt("landscape", "llama3")
        assert "landscape" in prompt.lower()

    def test_routes_portrait(self, generator):
        prompt = generator._get_svg_prompt("portrait", "llama3")
        assert "portrait" in prompt.lower()

    def test_routes_object(self, generator):
        prompt = generator._get_svg_prompt("object", "llama3")
        assert "object" in prompt.lower()

    def test_routes_scene(self, generator):
        prompt = generator._get_svg_prompt("scene", "llama3")
        assert "scene" in prompt.lower()

    def test_unknown_theme_falls_back_to_generic(self, generator):
        prompt = generator._get_svg_prompt("nebula", "llama3")
        assert "nebula" in prompt
        assert "rect" in prompt
        assert "circle" in prompt


# ---------------------------------------------------------------------------
# 4. SVGGenerator._extract_svg_from_response
# ---------------------------------------------------------------------------

class TestExtractSvgFromResponse:
    @pytest.fixture
    def generator(self, mock_config):
        return SVGGenerator(mock_config)

    def test_extract_from_markdown_svg_block(self, generator):
        response = "```svg\n<svg width=\"100\"><circle/></svg>\n```"
        extracted = generator._extract_svg_from_response(response)
        assert "<svg" in extracted
        assert "</svg>" in extracted
        assert "width" in extracted

    def test_extract_from_markdown_code_block(self, generator):
        response = "```\n<svg><rect/></svg>\n```"
        extracted = generator._extract_svg_from_response(response)
        assert "<svg" in extracted
        assert "</svg>" in extracted

    def test_extract_raw_svg(self, generator):
        response = "Here is some text <svg><circle/></svg> more text"
        extracted = generator._extract_svg_from_response(response)
        assert "<svg" in extracted
        assert "</svg>" in extracted

    def test_raise_valueerror_no_svg_found(self, generator):
        with pytest.raises(ValueError, match="No SVG code found"):
            generator._extract_svg_from_response("just plain text")

    def test_raise_valueerror_no_closing_tag(self, generator):
        with pytest.raises(ValueError, match="SVG closing tag not found"):
            generator._extract_svg_from_response("here is an <svg open")


# ---------------------------------------------------------------------------
# 5. SVGGenerator.__init__
# ---------------------------------------------------------------------------

class TestSVGGeneratorInit:
    def test_creates_svgs_dir_via_config(self, mock_config, tmp_path):
        mock_config.svgs_dir = tmp_path / "svgs"
        generator = SVGGenerator(mock_config)
        assert generator.svgs_dir == tmp_path / "svgs"
        assert (tmp_path / "svgs").is_dir()

    def test_custom_svgs_dir(self, mock_config, tmp_path):
        custom = tmp_path / "custom_svgs"
        generator = SVGGenerator(mock_config, svgs_dir=custom)
        assert generator.svgs_dir == custom
        assert custom.is_dir()


# ---------------------------------------------------------------------------
# 6. SVGGenerator.generate_svg (async)
# ---------------------------------------------------------------------------

class TestGenerateSvg:
    @pytest.fixture
    def generator(self, mock_config, tmp_path):
        return SVGGenerator(mock_config, svgs_dir=tmp_path / "svgs")

    def test_success_path(self, generator):
        mock_clear = LLMChunk(response="ok", eval_count=10, prompt_eval_count=5)
        mock_response = LLMChunk(
            response='<svg width="100"><circle/></svg>',
            eval_count=50,
            prompt_eval_count=200,
        )

        async def make_iter(chunks):
            for c in chunks:
                yield c

        mock_client = AsyncMock()
        mock_client.generate.side_effect = [
            make_iter([mock_clear]),
            make_iter([mock_response]),
        ]

        async def _do():
            return await generator.generate_svg(mock_client, "abstract", "llama3", "run-1")

        result = _run_async(_do())

        assert result.status == "success"
        assert result.model_name == "llama3"
        assert result.theme == "abstract"
        assert "svg" in result.svg_code.lower()
        assert result.svg_path is not None
        assert result.error_message is None
        assert result.svg_path.endswith("run-1_llama3_abstract_pass1.svg")
        assert result.tokens_used == 50
        assert mock_client.generate.call_count == 2

    def test_failure_path(self, generator):
        mock_client = AsyncMock()

        async def fail_gen(*args, **kwargs):
            raise RuntimeError("model timeout")

        mock_client.generate = AsyncMock(side_effect=fail_gen)

        async def _do():
            return await generator.generate_svg(mock_client, "landscape", "llama3", "run-2")

        result = _run_async(_do())

        assert result.status == "failed"
        assert result.model_name == "llama3"
        assert result.theme == "landscape"
        assert result.svg_code == ""
        assert "timeout" in result.error_message.lower()
        assert result.tokens_used is None


# ---------------------------------------------------------------------------
# 7. SVGGenerator._save_svg (async)
# ---------------------------------------------------------------------------

class TestSaveSvg:
    @pytest.fixture
    def generator(self, mock_config, tmp_path):
        return SVGGenerator(mock_config, svgs_dir=tmp_path / "svgs")

    def test_writes_content_to_file(self, generator, tmp_path):
        filepath = tmp_path / "test.svg"
        content = '<svg><rect width="10" height="10"/></svg>'

        async def _do():
            await generator._save_svg(content, filepath)

        _run_async(_do())
        assert filepath.read_text() == content

    def test_creates_parent_directories(self, generator, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "out.svg"
        content = '<svg></svg>'

        async def _do():
            await generator._save_svg(content, nested)

        _run_async(_do())
        assert nested.read_text() == content


# ---------------------------------------------------------------------------
# 8. SVGGenerator.generate_multiple_svgs (async)
# ---------------------------------------------------------------------------

class TestGenerateMultipleSvgs:
    @pytest.fixture
    def generator(self, mock_config, tmp_path):
        return SVGGenerator(mock_config, svgs_dir=tmp_path / "svgs")

    def test_calls_generate_svg_for_each_model_x_theme(self, generator, tmp_path):
        mock_clear = LLMChunk(response="ok", eval_count=5, prompt_eval_count=2)
        mock_response = LLMChunk(
            response='<svg width="100"><circle/></svg>',
            eval_count=30,
            prompt_eval_count=100,
        )

        async def make_iter(chunks):
            for c in chunks:
                yield c

        calls = []
        for _ in range(4):
            calls.append(make_iter([mock_clear]))
            calls.append(make_iter([mock_response]))

        mock_client = AsyncMock()
        mock_client.generate.side_effect = calls

        model_clients = {"model_a": mock_client, "model_b": mock_client}
        themes = ["abstract", "landscape"]

        async def _do():
            return await generator.generate_multiple_svgs(model_clients, themes, concurrency=5)

        results = _run_async(_do())

        assert len(results) == 4

        for r in results:
            assert r.status == "success"

        models_seen = {r.model_name for r in results}
        themes_seen = {r.theme for r in results}
        assert models_seen == {"model_a", "model_b"}
        assert themes_seen == {"abstract", "landscape"}

        assert not any(isinstance(r, list) for r in results)
