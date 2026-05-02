"""
LLM Client abstraction for multi-provider support.

Provides a unified interface for generating text and listing models
across different LLM backends (Ollama, LM Studio, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from rich.console import Console
import httpx
import json
console = Console()

class LLMChunk:
    """Unified response chunk from LLM generation.

    Provides both attribute access (.response) and dict-style access (.get())
    for compatibility with existing code patterns.
    """

    __slots__ = ("response", "eval_count", "prompt_eval_count")

    def __init__(
        self,
        response: str = "",
        eval_count: Optional[int] = None,
        prompt_eval_count: Optional[int] = None,
    ) -> None:
        self.response = response
        self.eval_count = eval_count
        self.prompt_eval_count = prompt_eval_count

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-style access for compatibility."""
        if key == "response":
            return self.response
        if key == "eval_count":
            return self.eval_count
        if key == "prompt_eval_count":
            return self.prompt_eval_count
        return default


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients.

    Defines the interface that all LLM client implementations must support.
    """

    @abstractmethod
    async def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        format: Optional[str] = None,
    ) -> Union[LLMChunk, AsyncIterator[LLMChunk]]:
        """Generate text from the model.

        Args:
            model: Model name to use.
            prompt: The prompt to send to the model.
            stream: If True, return an async iterator of chunks.
            format: Optional response format (e.g. "json").

        Returns:
            A single LLMChunk if stream=False, or an AsyncIterator[LLMChunk] if stream=True.
        """
        ...

    @abstractmethod
    async def list(self) -> Dict[str, Any]:
        """List available models.

        Returns:
            Dict with 'models' key containing a list of model info dicts/objects.
        """
        ...


class _OllamaHttpClient(BaseLLMClient):
    """HTTP-based LLM client using Ollama-compatible API.

    Uses the following endpoints:
    - POST /api/generate for text generation
    - GET /api/tags for listing models
    """

    def __init__(self, host: str = "http://localhost:11434") -> None:
        self._host = host.rstrip("/")
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(base_url=self._host, timeout=300)
        return self._http_client

    async def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        format: Optional[str] = None,
    ) -> Union[LLMChunk, AsyncIterator[LLMChunk]]:
        client = self._get_http_client()
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }
        if format is not None:
            payload["format"] = format

        if stream:
            return self._streaming_generate(client, payload)
        else:
            return await self._non_streaming_generate(client, payload)

    async def _non_streaming_generate(
        self, client: httpx.AsyncClient, payload: Dict[str, Any]
    ) -> LLMChunk:
        response = await client.post("/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return LLMChunk(
            response=data.get("response", ""),
            eval_count=data.get("eval_count"),
            prompt_eval_count=data.get("prompt_eval_count"),
        )

    async def _streaming_generate(
        self, client: httpx.AsyncClient, payload: Dict[str, Any]
    ) -> AsyncIterator[LLMChunk]:
        async with client.stream("POST", "/api/generate", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if not data_str:
                    continue
                try:
                    data = json.loads(data_str)
                    yield LLMChunk(
                        response=data.get("response", ""),
                        eval_count=data.get("eval_count"),
                        prompt_eval_count=data.get("prompt_eval_count"),
                    )
                except json.JSONDecodeError:
                    continue

    async def list(self) -> Dict[str, Any]:
        client = self._get_http_client()
        response = await client.get("/api/tags")
        response.raise_for_status()
        return response.json()


class OllamaClient(_OllamaHttpClient):
    """Ollama client (default port 11434)."""

    def __init__(self, host: str = "http://localhost:11434") -> None:
        super().__init__(host)


def _get_token_count(usage: Dict[str, Any], field: str) -> Optional[int]:
    """Extract token count from usage dict, checking multiple field names.

    Different APIs use different field names for token counts:
    - OpenAI: completion_tokens / prompt_tokens
    - Ollama: eval_count / prompt_eval_count
    - LM Studio: eval_batch_size (for completion tokens)
    """

    # console.print( f"Debug: Entering _get_token_count with usage: {usage} and field: '{field}'")

    if not usage:
        return None
    # Try the primary field name first
    if field in usage:
        return usage[field]
    # Try alternative field names
    alternatives = {
        "completion_tokens": ["eval_count", "eval_batch_size","completion_tokens"],
        "prompt_tokens": ["prompt_eval_count"],
    }

    # console.print( f"Debug: usage dict keys: {list(usage.keys())}, looking for field '{field}' with alternatives {alternatives.get(field, [])}")
    for alt in alternatives.get(field, []):
        if alt in usage:
            return usage[alt]
    return None


class _OpenAIHttpClient(BaseLLMClient):
    """HTTP-based LLM client using OpenAI-compatible API.

    Used by LM Studio and other OpenAI-compatible servers.
    Uses the following endpoints:
    - POST /v1/chat/completions for text generation
    - GET /v1/models for listing models
    """

    def __init__(self, host: str = "http://localhost:1234") -> None:
        self._host = host.rstrip("/")
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(base_url=self._host, timeout=300)
        return self._http_client

    async def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        format: Optional[str] = None,
    ) -> Union[LLMChunk, AsyncIterator[LLMChunk]]:
        client = self._get_http_client()
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }
        if format is not None:
            payload["response_format"] = {"type": "json_object"}

        if stream:
            return self._streaming_generate(client, payload)
        else:
            return await self._non_streaming_generate(client, payload)

    async def _non_streaming_generate(
        self, client: httpx.AsyncClient, payload: Dict[str, Any]
    ) -> LLMChunk:
        response = await client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
        else:
            content = ""
        usage = data.get("usage") or {}
        return LLMChunk(
            response=content,
            eval_count=_get_token_count(usage, "completion_tokens"),
            prompt_eval_count=_get_token_count(usage, "prompt_tokens"),
        )

    async def _streaming_generate(
        self, client: httpx.AsyncClient, payload: Dict[str, Any]
    ) -> AsyncIterator[LLMChunk]:
        async with client.stream("POST", "/v1/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    data = json.loads(data_str)
                    # console.print( f"Debug: Received streaming chunk data: {data}" )
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                    else:
                        content = ""
                    usage = data.get("usage") or {}
                    yield LLMChunk(
                        response=content,
                        eval_count=_get_token_count(usage, "completion_tokens"),
                        prompt_eval_count=_get_token_count(usage, "prompt_tokens"),
                    )
                except json.JSONDecodeError:
                    continue

    async def list(self) -> Dict[str, Any]:
        client = self._get_http_client()
        response = await client.get("/v1/models")
        response.raise_for_status()
        data = response.json()
        # Normalize to Ollama-compatible format: {"models": [...]}
        models_list = []
        for model in data.get("data", []):
            models_list.append({
                "name": model.get("id", ""),
                "size": 0,
                "modified_at": "",
            })
        return {"models": models_list}


class LMStudioClient(_OpenAIHttpClient):
    """LM Studio client using OpenAI-compatible API (default port 1234)."""

    def __init__(self, host: str = "http://localhost:1234") -> None:
        super().__init__(host)


def create_llm_client(client_type: str = "ollama", host: Optional[str] = None) -> BaseLLMClient:
    """Factory function to create the appropriate LLM client.

    Args:
        client_type: Type of client ("ollama" or "lmstudio").
        host: Optional host URL. Uses default port for the client type if not provided.

    Returns:
        A BaseLLMClient instance.
    """
    if client_type.lower() == "lmstudio":
        if host is None:
            host = "http://localhost:1234"
        return LMStudioClient(host)
    else:
        if host is None:
            host = "http://localhost:11434"
        return OllamaClient(host)
