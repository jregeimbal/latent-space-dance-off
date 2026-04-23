"""Model Manager - Ollama model management and client handling."""

import asyncio
from datetime import datetime
from typing import List, Optional
from ollama import AsyncClient
from pydantic import BaseModel


class ModelInfo(BaseModel):
    """Information about an Ollama model."""
    name: str
    size: int
    modified_at: str


class ModelManager:
    """Class for managing Ollama models and AsyncClient instances."""

    def __init__(self, host: str = "http://localhost:11434") -> None:
        """Initialize the ModelManager with a host URL."""
        self._host = host
        self._client: Optional[AsyncClient] = None
        self._models_cache: Optional[List[ModelInfo]] = None

    def _get_client(self) -> AsyncClient:
        """Get or create the AsyncClient instance."""
        if self._client is None:
            self._client = AsyncClient(host=self._host)
        return self._client

    async def get_available_models(self) -> List[ModelInfo]:
        """Get a list of all available Ollama models."""
        client = self._get_client()
        response = await client.list()

        models = []
        if not response or "models" not in response:
            return []

        for model in response["models"]:
            # Handle Model objects from Ollama (attribute is 'model', not 'name')
            if hasattr(model, "model"):
                name = model.model
                size = model.size if hasattr(model, 'size') else 0
                modified_at = model.modified_at if hasattr(model, 'modified_at') else ""
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

    async def get_model(self, model_name: str) -> AsyncClient:
        """Get an AsyncClient for a specific model."""
        client = self._get_client()
        # Test model by generating a simple response
        await client.generate(model=model_name, prompt="Test", stream=False)
        return client


_default_manager: Optional["ModelManager"] = None


def get_model_manager(host: str = "http://localhost:11434") -> ModelManager:
    """Get or create the default ModelManager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = ModelManager(host=host)
    return _default_manager
