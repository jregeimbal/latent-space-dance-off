"""Tests for model_manager module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm_client import LLMChunk
from src.model_manager import ModelInfo, ModelManager


def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        asyncio.set_event_loop(None)
        loop.close()


class TestModelInfo:
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
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ModelInfo(name="llama3")


class TestModelManagerConstructor:
    def test_stores_host(self):
        manager = ModelManager(host="http://custom:11434")
        assert manager._host == "http://custom:11434"

    def test_stores_client_type(self):
        manager = ModelManager(client_type="lmstudio")
        assert manager._client_type == "lmstudio"

    def test_initializes_client_to_none(self):
        manager = ModelManager()
        assert manager._client is None

    def test_default_host(self):
        manager = ModelManager()
        assert manager._host == "http://localhost:11434"

    def test_default_client_type(self):
        manager = ModelManager()
        assert manager._client_type == "ollama"


class TestModelManagerGetClient:
    @patch("src.model_manager.create_llm_client")
    def test_creates_client_on_first_call(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        manager = ModelManager()
        client = manager._get_client()
        MockCreate.assert_called_once_with(client_type="ollama", host="http://localhost:11434")
        assert client is mock_instance

    @patch("src.model_manager.create_llm_client")
    def test_returns_cached_instance_on_second_call(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        manager = ModelManager()
        client1 = manager._get_client()
        client2 = manager._get_client()
        assert client1 is client2
        MockCreate.assert_called_once()


class TestModelManagerGetAvailableModels:
    @patch("src.model_manager.create_llm_client")
    def test_parses_dict_format_response(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={
            "models": [
                {"name": "llama3", "size": 1234, "modified_at": "2024-01-01"},
                {"name": "gemma", "size": 5678, "modified_at": "2024-02-01"},
            ]
        })
        manager = ModelManager()
        models = _run_async(manager.get_available_models())
        assert len(models) == 2
        assert models[0].name == "llama3"
        assert models[0].size == 1234
        assert models[1].name == "gemma"
        assert models[1].size == 5678
        mock_instance.list.assert_called_once()

    @patch("src.model_manager.create_llm_client")
    def test_parses_model_objects_response(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_model = MagicMock()
        mock_model.model = "llama3"
        mock_model.size = 4048
        mock_model.modified_at = "2024-01-01T00:00:00"
        mock_instance.list = AsyncMock(return_value={
            "models": [mock_model]
        })
        manager = ModelManager()
        models = _run_async(manager.get_available_models())
        assert len(models) == 1
        assert models[0].name == "llama3"
        assert models[0].size == 4048

    @patch("src.model_manager.create_llm_client")
    def test_empty_response_returns_empty_list(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={"models": []})
        manager = ModelManager()
        models = _run_async(manager.get_available_models())
        assert models == []

    @patch("src.model_manager.create_llm_client")
    def test_missing_models_key_returns_empty_list(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={})
        manager = ModelManager()
        models = _run_async(manager.get_available_models())
        assert models == []

    @patch("src.model_manager.create_llm_client")
    def test_missing_attributes_uses_defaults(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance

        class MinimalModel:
            model = "minimal"

        mock_model = MinimalModel()
        mock_instance.list = AsyncMock(return_value={
            "models": [mock_model]
        })
        manager = ModelManager()
        models = _run_async(manager.get_available_models())
        assert len(models) == 1
        assert models[0].name == "minimal"
        assert models[0].size == 0
        assert models[0].modified_at == ""


class TestModelManagerListModels:
    @patch("src.model_manager.create_llm_client")
    def test_extracts_names_from_model_info_list(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={
            "models": [
                {"name": "llama3", "size": 100, "modified_at": "2024-01-01"},
                {"name": "gemma", "size": 200, "modified_at": "2024-02-01"},
            ]
        })
        manager = ModelManager()
        names = _run_async(manager.list_models())
        assert names == ["llama3", "gemma"]

    @patch("src.model_manager.create_llm_client")
    def test_empty_list_returns_empty(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={"models": []})
        manager = ModelManager()
        names = _run_async(manager.list_models())
        assert names == []


class TestModelManagerIsModelAvailable:
    @patch("src.model_manager.create_llm_client")
    def test_true_when_model_in_list(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={
            "models": [
                {"name": "llama3", "size": 100, "modified_at": "2024-01-01"},
            ]
        })
        manager = ModelManager()
        assert manager.is_model_available("llama3") is True

    @patch("src.model_manager.create_llm_client")
    def test_false_when_model_not_in_list(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_instance.list = AsyncMock(return_value={
            "models": [
                {"name": "llama3", "size": 100, "modified_at": "2024-01-01"},
            ]
        })
        manager = ModelManager()
        assert manager.is_model_available("unknown_model") is False

    @patch("src.model_manager.create_llm_client")
    def test_false_when_connection_fails(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_instance.list = AsyncMock(side_effect=Exception(
            "Connection refused"
        ))
        manager = ModelManager()
        assert manager.is_model_available("llama3") is False


class TestModelManagerGetModel:
    @patch("src.model_manager.create_llm_client")
    def test_validates_model_and_returns_client(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_instance.generate = AsyncMock(return_value=LLMChunk(response="ok"))

        manager = ModelManager()
        client = _run_async(manager.get_model("llama3"))

        mock_instance.generate.assert_called_once_with(
            model="llama3", prompt="Test", stream=False
        )
        assert client is mock_instance

    @patch("src.model_manager.create_llm_client")
    def test_uses_custom_client_type(self, MockCreate):
        mock_instance = AsyncMock()
        MockCreate.return_value = mock_instance
        mock_instance.generate = AsyncMock(return_value=LLMChunk(response="ok"))

        manager = ModelManager(client_type="lmstudio", host="http://custom:1234")
        _run_async(manager.get_model("mistral"))

        MockCreate.assert_called_once_with(client_type="lmstudio", host="http://custom:1234")
