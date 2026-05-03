"""Model Manager - LLM model management and client handling."""

import asyncio
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from src.llm_client import BaseLLMClient, create_llm_client


class ModelInfo(BaseModel):
    """Information about an LLM model."""

    name: str
    size: int
    modified_at: str


class ModelManager:
    """Class for managing LLM models and client instances."""

    def __init__(self, host: str = "http://localhost:11434", client_type: str = "ollama") -> None:
        """Initialize the ModelManager with a host URL and client type.

        Args:
            host: The LLM server host URL.
            client_type: The type of LLM client ("ollama" or "lmstudio").
        """
        self._host = host
        self._client_type = client_type
        self._client: Optional[BaseLLMClient] = None
        self._models_cache: Optional[List[ModelInfo]] = None

    def _get_client(self) -> BaseLLMClient:
        """Get or create the LLM client instance."""
        if self._client is None:
            self._client = create_llm_client(client_type=self._client_type, host=self._host)
        return self._client

    async def get_available_models(self) -> List[ModelInfo]:
        """Get a list of all available models."""
        client = self._get_client()
        response = await client.list()

        models = []
        if not response or "models" not in response:
            return []

        for model in response["models"]:
            if hasattr(model, "model"):
                name = model.model
                size = model.size if hasattr(model, "size") else 0
                modified_at = model.modified_at if hasattr(model, "modified_at") else ""
                if isinstance(modified_at, datetime):
                    modified_at = str(modified_at)
            else:
                name = model.get("name", "") if isinstance(model, dict) else ""
                size = model.get("size", 0) if isinstance(model, dict) else 0
                modified_at = model.get("modified_at", "") if isinstance(model, dict) else ""

            models.append(ModelInfo(
                name=name,
                size=size,
                modified_at=str(modified_at) if modified_at else ""
            ))

        return models

    async def list_models(self) -> List[str]:
        """Get a simple list of model names."""
        models = await self.get_available_models()
        return [model.name for model in models]

    def is_model_available(self, model_name: str) -> bool:
        """Check if a specific model is available."""
        try:
            models = asyncio.run(self.list_models())
            return model_name in models
        except Exception:
            return False

    async def get_model(self, model_name: str) -> BaseLLMClient:
        """Get a client for a specific model.

        Validates the model is available by making a test generate call.

        Args:
            model_name: The name of the model to validate.

        Returns:
            The shared BaseLLMClient instance.
        """
        client = self._get_client()
        await client.generate(model=model_name, prompt="Test", stream=False)
        return client


_default_manager: Optional["ModelManager"] = None


def get_model_manager(
    host: str = "http://localhost:11434",
    client_type: str = "ollama",
) -> ModelManager:
    """Get or create the default ModelManager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = ModelManager(host=host, client_type=client_type)
    return _default_manager
