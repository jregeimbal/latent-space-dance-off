"""Tests for model_manager module."""

import pytest
from unittest.mock import AsyncMock, patch

from src.model_manager import ModelInfo, ModelManager


class TestModelInfo:
    """Tests for the ModelInfo Pydantic model."""

    def test_creation_with_all_fields(self):
        info = ModelInfo(
            name="llama3",
            size=4048375808,
            modified_at="2024-01-01T12:00:00Z",
        )
        assert info.name == "llama3"
        assert info.size == 4048375808
        assert info.modified_at == "2024-01-01T12:00:00Z"

    def test_default_values(self):
        pytest.importorskip("pydantic")
        from pydantic import ValidationError

        # size and modified_at have no defaults in the schema,
        # so omitting them raises
        with pytest.raises(ValidationError):
            ModelInfo(name="llama3")


class TestModelManagerGetClient:
    """Tests for the ModelManager._get_client method."""

    def test_client_starts_none(self):
        manager = ModelManager()
        assert manager._client is None

    @patch("src.model_manager.AsyncClient")
    def test_creates_client_on_first_call(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        manager = ModelManager()
        client = manager._get_client()
        MockAsyncClient.assert_called_once_with(host="http://localhost:11434")
        assert client is mock_instance

    @patch("src.model_manager.AsyncClient")
    def test_returns_cached_instance_on_second_call(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        manager = ModelManager()
        client1 = manager._get_client()
        client2 = manager._get_client()
        assert client1 is client2
        MockAsyncClient.assert_called_once()


class TestModelManagerGetAvailableModels:
    """Tests for the ModelManager.get_available_models async method."""

    def _run_async(self, coro):
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    @patch("src.model_manager.AsyncClient")
    def test_parses_dict_format_response(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={
            "models": [
                {"name": "llama3", "size": 1234, "modified_at": "2024-01-01"},
                {"name": "gemma", "size": 5678, "modified_at": "2024-02-01"},
            ]
        })
        manager = ModelManager()
        models = self._run_async(manager.get_available_models())
        assert len(models) == 2
        assert models[0].name == "llama3"
        assert models[0].size == 1234
        assert models[1].name == "gemma"
        assert models[1].size == 5678
        mock_instance.list.assert_called_once()

    @patch("src.model_manager.AsyncClient")
    def test_parses_model_objects_response(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        mock_model = AsyncMock()
        mock_model.model = "llama3"
        mock_model.size = 4048
        mock_model.modified_at = "2024-01-01T00:00:00"
        mock_instance.list = AsyncMock(return_value={
            "models": [mock_model]
        })
        manager = ModelManager()
        models = self._run_async(manager.get_available_models())
        assert len(models) == 1
        assert models[0].name == "llama3"
        assert models[0].size == 4048

    @patch("src.model_manager.AsyncClient")
    def test_empty_response_returns_empty_list(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={"models": []})
        manager = ModelManager()
        models = self._run_async(manager.get_available_models())
        assert models == []

    @patch("src.model_manager.AsyncClient")
    def test_missing_models_key_returns_empty_list(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={})
        manager = ModelManager()
        models = self._run_async(manager.get_available_models())
        assert models == []

    @patch("src.model_manager.AsyncClient")
    def test_missing_attributes_uses_defaults(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance

        class MinimalModel:
            model = "minimal"

        mock_model = MinimalModel()
        mock_instance.list = AsyncMock(return_value={
            "models": [mock_model]
        })
        manager = ModelManager()
        models = self._run_async(manager.get_available_models())
        assert len(models) == 1
        assert models[0].name == "minimal"
        assert models[0].size == 0
        assert models[0].modified_at == ""


class TestModelManagerListModels:
    """Tests for the ModelManager.list_models async method."""

    def _run_async(self, coro):
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    @patch("src.model_manager.AsyncClient")
    def test_extracts_names_from_model_info_list(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={
            "models": [
                {"name": "llama3", "size": 100, "modified_at": "2024-01-01"},
                {"name": "gemma", "size": 200, "modified_at": "2024-02-01"},
            ]
        })
        manager = ModelManager()
        names = self._run_async(manager.list_models())
        assert names == ["llama3", "gemma"]

    @patch("src.model_manager.AsyncClient")
    def test_empty_list_returns_empty(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={"models": []})
        manager = ModelManager()
        names = self._run_async(manager.list_models())
        assert names == []


class TestModelManagerIsModelAvailable:
    """Tests for the ModelManager.is_model_available method."""

    @patch("src.model_manager.AsyncClient")
    def test_true_when_model_in_list(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={
            "models": [
                {"name": "llama3", "size": 100, "modified_at": "2024-01-01"},
            ]
        })
        manager = ModelManager()
        assert manager.is_model_available("llama3") is True

    @patch("src.model_manager.AsyncClient")
    def test_false_when_model_not_in_list(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={
            "models": [
                {"name": "llama3", "size": 100, "modified_at": "2024-01-01"},
            ]
        })
        manager = ModelManager()
        assert manager.is_model_available("unknown_model") is False

    @patch("src.model_manager.AsyncClient")
    def test_false_when_ollama_not_running(self, MockAsyncClient):
        mock_instance = AsyncMock()
        MockAsyncClient.return_value = mock_instance
        mock_instance.list = AsyncMock(side_effect=Exception(
            "Connection refused"
        ))
        manager = ModelManager()
        assert manager.is_model_available("llama3") is False


class TestModelManagerConstructor:
    """Tests for the ModelManager constructor."""

    def test_stores_host(self):
        manager = ModelManager(host="http://custom:11434")
        assert manager._host == "http://custom:11434"

    def test_initializes_client_to_none(self):
        manager = ModelManager()
        assert manager._client is None

    def test_default_host(self):
        manager = ModelManager()
        assert manager._host == "http://localhost:11434"
