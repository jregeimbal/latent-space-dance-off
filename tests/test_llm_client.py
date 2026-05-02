"""Tests for llm_client module."""

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm_client import (
    BaseLLMClient,
    LLMChunk,
    LMStudioClient,
    OllamaClient,
    _get_token_count,
    create_llm_client,
)


# ---------------------------------------------------------------------------
# _get_token_count helper
# ---------------------------------------------------------------------------

class TestGetTokenCount:
    def test_completion_tokens_standard(self):
        usage = {"completion_tokens": 50}
        assert _get_token_count(usage, "completion_tokens") == 50

    def test_completion_tokens_eval_count_fallback(self):
        usage = {"eval_count": 45}
        assert _get_token_count(usage, "completion_tokens") == 45

    def test_completion_tokens_eval_batch_size_fallback(self):
        usage = {"eval_batch_size": 40}
        assert _get_token_count(usage, "completion_tokens") == 40

    def test_completion_tokens_prefers_primary_field(self):
        usage = {"completion_tokens": 50, "eval_count": 45}
        assert _get_token_count(usage, "completion_tokens") == 50

    def test_prompt_tokens_standard(self):
        usage = {"prompt_tokens": 100}
        assert _get_token_count(usage, "prompt_tokens") == 100

    def test_prompt_tokens_prompt_eval_count_fallback(self):
        usage = {"prompt_eval_count": 90}
        assert _get_token_count(usage, "prompt_tokens") == 90

    def test_empty_usage_returns_none(self):
        assert _get_token_count({}, "completion_tokens") is None

    def test_none_usage_returns_none(self):
        assert _get_token_count(None, "completion_tokens") is None


# ---------------------------------------------------------------------------
# LLMChunk
# ---------------------------------------------------------------------------

class TestLLMChunk:
    def test_default_values(self):
        chunk = LLMChunk()
        assert chunk.response == ""
        assert chunk.eval_count is None
        assert chunk.prompt_eval_count is None

    def test_with_values(self):
        chunk = LLMChunk(response="hello", eval_count=10, prompt_eval_count=50)
        assert chunk.response == "hello"
        assert chunk.eval_count == 10
        assert chunk.prompt_eval_count == 50

    def test_get_attribute_response(self):
        chunk = LLMChunk(response="test")
        assert chunk.get("response") == "test"

    def test_get_attribute_eval_count(self):
        chunk = LLMChunk(eval_count=42)
        assert chunk.get("eval_count") == 42

    def test_get_attribute_prompt_eval_count(self):
        chunk = LLMChunk(prompt_eval_count=100)
        assert chunk.get("prompt_eval_count") == 100

    def test_get_unknown_key_returns_default(self):
        chunk = LLMChunk()
        assert chunk.get("unknown", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# Client classes - construction
# ---------------------------------------------------------------------------

class TestClientConstruction:
    def test_ollama_client_default_host(self):
        client = OllamaClient()
        assert client._host == "http://localhost:11434"

    def test_ollama_client_custom_host(self):
        client = OllamaClient(host="http://custom:9999")
        assert client._host == "http://custom:9999"

    def test_ollama_client_trims_trailing_slash(self):
        client = OllamaClient(host="http://localhost:11434/")
        assert client._host == "http://localhost:11434"

    def test_lmstudio_client_default_host(self):
        client = LMStudioClient()
        assert client._host == "http://localhost:1234"

    def test_lmstudio_client_custom_host(self):
        client = LMStudioClient(host="http://custom:5678")
        assert client._host == "http://custom:5678"

    def test_clients_are_base_llm_client(self):
        ollama = OllamaClient()
        lmstudio = LMStudioClient()
        assert isinstance(ollama, BaseLLMClient)
        assert isinstance(lmstudio, BaseLLMClient)


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

class TestCreateLLMClient:
    def test_default_creates_ollama(self):
        client = create_llm_client()
        assert isinstance(client, OllamaClient)
        assert client._host == "http://localhost:11434"

    def test_ollama_type(self):
        client = create_llm_client("ollama")
        assert isinstance(client, OllamaClient)

    def test_lmstudio_type(self):
        client = create_llm_client("lmstudio")
        assert isinstance(client, LMStudioClient)
        assert client._host == "http://localhost:1234"

    def test_lmstudio_uppercase(self):
        client = create_llm_client("LMSTUDIO")
        assert isinstance(client, LMStudioClient)

    def test_ollama_with_custom_host(self):
        client = create_llm_client("ollama", host="http://custom:11434")
        assert isinstance(client, OllamaClient)
        assert client._host == "http://custom:11434"

    def test_lmstudio_with_custom_host(self):
        client = create_llm_client("lmstudio", host="http://custom:1234")
        assert isinstance(client, LMStudioClient)
        assert client._host == "http://custom:1234"


# ---------------------------------------------------------------------------
# Ollama non-streaming generate (mocked httpx)
# ---------------------------------------------------------------------------

class TestOllamaNonStreamingGenerate:
    def _make_mock_response(self, data: Dict[str, Any]) -> MagicMock:
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = data
        return mock

    @pytest.mark.asyncio
    async def test_ollama_non_streaming_returns_chunk(self):
        with patch("src.llm_client.httpx.AsyncClient") as MockHttpx:
            mock_instance = AsyncMock()
            MockHttpx.return_value = mock_instance
            mock_instance.post = AsyncMock(
                return_value=self._make_mock_response({
                    "response": "<svg></svg>",
                    "eval_count": 50,
                    "prompt_eval_count": 200,
                })
            )

            client = OllamaClient()
            result = await client.generate(model="llama3", prompt="test", stream=False)

            assert isinstance(result, LLMChunk)
            assert result.response == "<svg></svg>"
            assert result.eval_count == 50
            assert result.prompt_eval_count == 200

            mock_instance.post.assert_called_once_with(
                "/api/generate",
                json={"model": "llama3", "prompt": "test", "stream": False},
            )

    @pytest.mark.asyncio
    async def test_ollama_non_streaming_with_format(self):
        with patch("src.llm_client.httpx.AsyncClient") as MockHttpx:
            mock_instance = AsyncMock()
            MockHttpx.return_value = mock_instance
            mock_instance.post = AsyncMock(
                return_value=self._make_mock_response({
                    "response": '{"key": "value"}',
                    "eval_count": 10,
                    "prompt_eval_count": 30,
                })
            )

            client = OllamaClient()
            result = await client.generate(
                model="llama3", prompt="test", stream=False, format="json"
            )

            call_args = mock_instance.post.call_args
            assert call_args[1]["json"]["format"] == "json"
            assert result.response == '{"key": "value"}'


# ---------------------------------------------------------------------------
# Ollama streaming generate (mocked httpx)
# ---------------------------------------------------------------------------

class TestOllamaStreamingGenerate:
    def _make_sse_lines(self, chunks: list) -> list:
        """Convert chunk dicts to SSE data lines."""
        lines = []
        for chunk in chunks:
            data_str = json.dumps(chunk)
            lines.append(f"data: {data_str}")
        lines.append("data: [DONE]")
        return lines

    @pytest.mark.asyncio
    async def test_streaming_yields_chunks(self):
        sse_lines = self._make_sse_lines([
            {"response": "hello", "eval_count": None, "prompt_eval_count": None},
            {"response": " world", "eval_count": None, "prompt_eval_count": None},
            {"response": "", "eval_count": 5, "prompt_eval_count": 20},
        ])

        async def async_iter_lines():
            for line in sse_lines:
                yield line

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = async_iter_lines

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=mock_stream)

        with patch("src.llm_client.httpx.AsyncClient", return_value=mock_http):
            client = OllamaClient()
            result = await client.generate(model="llama3", prompt="test", stream=True)

            chunks = []
            async for chunk in result:
                chunks.append(chunk)

            assert len(chunks) == 3
            assert chunks[0].response == "hello"
            assert chunks[1].response == " world"
            assert chunks[2].response == ""
            assert chunks[2].eval_count == 5

    @pytest.mark.asyncio
    async def test_streaming_empty_response(self):
        async def async_iter_lines():
            return
            yield

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = async_iter_lines

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=mock_stream)

        with patch("src.llm_client.httpx.AsyncClient", return_value=mock_http):
            client = OllamaClient()
            result = await client.generate(model="llama3", prompt="test", stream=True)

            chunks = []
            async for chunk in result:
                chunks.append(chunk)

            assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_streaming_skips_malformed_json(self):
        sse_lines = [
            "data: {invalid json",
            "data: {}",
        ]

        async def async_iter_lines():
            for line in sse_lines:
                yield line

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = async_iter_lines

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=mock_stream)

        with patch("src.llm_client.httpx.AsyncClient", return_value=mock_http):
            client = OllamaClient()
            result = await client.generate(model="llama3", prompt="test", stream=True)

            chunks = []
            async for chunk in result:
                chunks.append(chunk)

            assert len(chunks) == 1
            assert chunks[0].response == ""


# ---------------------------------------------------------------------------
# Ollama list models (mocked httpx)
# ---------------------------------------------------------------------------

class TestOllamaListModels:
    def _make_mock_response(self, data: Dict[str, Any]) -> MagicMock:
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = data
        return mock

    @pytest.mark.asyncio
    async def test_ollama_list(self):
        with patch("src.llm_client.httpx.AsyncClient") as MockHttpx:
            mock_instance = AsyncMock()
            MockHttpx.return_value = mock_instance
            mock_instance.get = AsyncMock(
                return_value=self._make_mock_response({
                    "models": [
                        {"name": "llama3", "size": 100, "modified_at": "2024-01-01"},
                        {"name": "gemma", "size": 200, "modified_at": "2024-02-01"},
                    ]
                })
            )

            client = OllamaClient()
            result = await client.list()

            assert result == {
                "models": [
                    {"name": "llama3", "size": 100, "modified_at": "2024-01-01"},
                    {"name": "gemma", "size": 200, "modified_at": "2024-02-01"},
                ]
            }
            mock_instance.get.assert_called_once_with("/api/tags")


# ---------------------------------------------------------------------------
# LM Studio non-streaming generate (OpenAI-compatible API)
# ---------------------------------------------------------------------------

class TestLMStudioNonStreamingGenerate:
    def _make_mock_response(self, data: Dict[str, Any]) -> MagicMock:
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = data
        return mock

    @pytest.mark.asyncio
    async def test_lmstudio_non_streaming_returns_chunk(self):
        with patch("src.llm_client.httpx.AsyncClient") as MockHttpx:
            mock_instance = AsyncMock()
            MockHttpx.return_value = mock_instance
            mock_instance.post = AsyncMock(
                return_value=self._make_mock_response({
                    "choices": [{
                        "message": {"role": "assistant", "content": "hello world"},
                        "finish_reason": "stop",
                    }],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 50,
                        "total_tokens": 60,
                    },
                })
            )

            client = LMStudioClient()
            result = await client.generate(model="mistral", prompt="hi", stream=False)

            assert isinstance(result, LLMChunk)
            assert result.response == "hello world"
            assert result.eval_count == 50
            assert result.prompt_eval_count == 10

            mock_instance.post.assert_called_once_with(
                "/v1/chat/completions",
                json={
                    "model": "mistral",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )

    @pytest.mark.asyncio
    async def test_lmstudio_with_format(self):
        with patch("src.llm_client.httpx.AsyncClient") as MockHttpx:
            mock_instance = AsyncMock()
            MockHttpx.return_value = mock_instance
            mock_instance.post = AsyncMock(
                return_value=self._make_mock_response({
                    "choices": [{"message": {"content": '{"key": "value"}'}},],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 10},
                })
            )

            client = LMStudioClient()
            result = await client.generate(
                model="mistral", prompt="respond in json", stream=False, format="json"
            )

            call_args = mock_instance.post.call_args
            assert call_args[1]["json"]["response_format"] == {"type": "json_object"}
            assert result.response == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_lmstudio_empty_choices(self):
        with patch("src.llm_client.httpx.AsyncClient") as MockHttpx:
            mock_instance = AsyncMock()
            MockHttpx.return_value = mock_instance
            mock_instance.post = AsyncMock(
                return_value=self._make_mock_response({
                    "choices": [],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 0},
                })
            )

            client = LMStudioClient()
            result = await client.generate(model="mistral", prompt="hi", stream=False)

            assert result.response == ""


# ---------------------------------------------------------------------------
# LM Studio streaming generate (OpenAI-compatible API)
# ---------------------------------------------------------------------------

class TestLMStudioStreamingGenerate:
    def _make_sse_lines(self, chunks: list) -> list:
        """Convert chunk dicts to OpenAI-style SSE data lines."""
        lines = []
        for chunk in chunks:
            data_str = json.dumps(chunk)
            lines.append(f"data: {data_str}")
        lines.append("data: [DONE]")
        return lines

    @pytest.mark.asyncio
    async def test_streaming_yields_chunks(self):
        sse_lines = self._make_sse_lines([
            {"choices": [{"delta": {"content": "hello"}}], "usage": None},
            {"choices": [{"delta": {"content": " world"}}], "usage": None},
            {"choices": [{"delta": {"content": ""}}], "usage": {"completion_tokens": 5, "prompt_tokens": 20}},
        ])

        async def async_iter_lines():
            for line in sse_lines:
                yield line

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = async_iter_lines

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=mock_stream)

        with patch("src.llm_client.httpx.AsyncClient", return_value=mock_http):
            client = LMStudioClient()
            result = await client.generate(model="mistral", prompt="hi", stream=True)

            chunks = []
            async for chunk in result:
                chunks.append(chunk)

            assert len(chunks) == 3
            assert chunks[0].response == "hello"
            assert chunks[1].response == " world"
            assert chunks[2].response == ""
            assert chunks[2].eval_count == 5

    @pytest.mark.asyncio
    async def test_streaming_handles_done(self):
        sse_lines = [
            "data: {\"choices\": [{\"delta\": {\"content\": \"hi\"}}]}",
            "data: [DONE]",
        ]

        async def async_iter_lines():
            for line in sse_lines:
                yield line

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = async_iter_lines

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_http = AsyncMock()
        mock_http.stream = MagicMock(return_value=mock_stream)

        with patch("src.llm_client.httpx.AsyncClient", return_value=mock_http):
            client = LMStudioClient()
            result = await client.generate(model="mistral", prompt="hi", stream=True)

            chunks = []
            async for chunk in result:
                chunks.append(chunk)

            assert len(chunks) == 1
            assert chunks[0].response == "hi"


# ---------------------------------------------------------------------------
# LM Studio list models (OpenAI-compatible API)
# ---------------------------------------------------------------------------

class TestLMStudioListModels:
    def _make_mock_response(self, data: Dict[str, Any]) -> MagicMock:
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = data
        return mock

    @pytest.mark.asyncio
    async def test_lmstudio_list_normalizes_to_ollama_format(self):
        with patch("src.llm_client.httpx.AsyncClient") as MockHttpx:
            mock_instance = AsyncMock()
            MockHttpx.return_value = mock_instance
            mock_instance.get = AsyncMock(
                return_value=self._make_mock_response({
                    "object": "list",
                    "data": [
                        {"id": "mistral", "object": "model", "created": 1234567890},
                        {"id": "llama3", "object": "model", "created": 1234567891},
                    ],
                })
            )

            client = LMStudioClient()
            result = await client.list()

            assert result == {
                "models": [
                    {"name": "mistral", "size": 0, "modified_at": ""},
                    {"name": "llama3", "size": 0, "modified_at": ""},
                ]
            }
            mock_instance.get.assert_called_once_with("/v1/models")
