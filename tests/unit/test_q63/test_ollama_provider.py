"""Tests for OllamaProvider — Q63 Task 427."""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch


class TestIsAvailable:
    def test_returns_false_when_server_down(self):
        from lidco.ai.ollama_provider import OllamaProvider
        provider = OllamaProvider(base_url="http://localhost:11434")
        with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
            assert provider.is_available() is False

    def test_returns_true_when_server_up(self):
        from lidco.ai.ollama_provider import OllamaProvider
        provider = OllamaProvider()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert provider.is_available() is True


class TestListModels:
    def test_returns_empty_on_error(self):
        from lidco.ai.ollama_provider import OllamaProvider
        provider = OllamaProvider()
        with patch("urllib.request.urlopen", side_effect=Exception("down")):
            models = provider.list_models()
        assert models == []

    def test_returns_model_names(self):
        from lidco.ai.ollama_provider import OllamaProvider
        provider = OllamaProvider()
        data = {"models": [{"name": "llama3"}, {"name": "mistral"}]}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(data).encode()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            models = provider.list_models()
        assert "llama3" in models
        assert "mistral" in models

    def test_empty_models_list(self):
        from lidco.ai.ollama_provider import OllamaProvider
        provider = OllamaProvider()
        data = {"models": []}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert provider.list_models() == []


class TestChat:
    @pytest.mark.asyncio
    async def test_chat_returns_content(self):
        from lidco.ai.ollama_provider import OllamaProvider
        provider = OllamaProvider()
        response_data = {"choices": [{"message": {"content": "hello!"}}]}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await provider.chat([{"role": "user", "content": "hi"}], model="llama3")
        assert result == "hello!"

    @pytest.mark.asyncio
    async def test_chat_returns_empty_on_no_choices(self):
        from lidco.ai.ollama_provider import OllamaProvider
        provider = OllamaProvider()
        response_data = {"choices": []}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await provider.chat([{"role": "user", "content": "hi"}], model="llama3")
        assert result == ""

    def test_base_url_stripped(self):
        from lidco.ai.ollama_provider import OllamaProvider
        provider = OllamaProvider(base_url="http://localhost:11434/")
        assert not provider.base_url.endswith("/")

    @pytest.mark.asyncio
    async def test_list_models_async(self):
        from lidco.ai.ollama_provider import OllamaProvider
        provider = OllamaProvider()
        with patch.object(provider, "list_models", return_value=["llama3"]):
            result = await provider.list_models_async()
        assert result == ["llama3"]
