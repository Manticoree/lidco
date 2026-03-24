"""Tests for PredictionBackend (T512)."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from lidco.prediction.backend import PredictionBackend, PredictionBackendConfig


@pytest.fixture
def disabled_backend():
    return PredictionBackend(PredictionBackendConfig(backend="disabled"))


@pytest.fixture
def remote_backend():
    return PredictionBackend(PredictionBackendConfig(backend="remote"))


@pytest.fixture
def ollama_backend():
    return PredictionBackend(PredictionBackendConfig(
        backend="ollama",
        ollama_url="http://localhost:11434",
        ollama_model="codellama:7b",
    ))


def test_default_config_is_remote():
    b = PredictionBackend()
    assert b.active_backend == "remote"


def test_active_backend_disabled(disabled_backend):
    assert disabled_backend.active_backend == "disabled"


def test_predict_disabled_returns_empty(disabled_backend):
    result = asyncio.run(disabled_backend.predict("prompt"))
    assert result == ""


def test_predict_remote_returns_empty_stub(remote_backend):
    result = asyncio.run(remote_backend.predict("prompt"))
    assert result == ""


def test_predict_ollama_calls_call_ollama(ollama_backend):
    async def fake_call_ollama(url, model, prompt, max_tokens, temperature):
        return "hello from ollama"

    with patch.object(PredictionBackend, "call_ollama", side_effect=fake_call_ollama):
        result = asyncio.run(ollama_backend.predict("prompt"))
    assert result == "hello from ollama"


def test_predict_ollama_returns_empty_on_error(ollama_backend):
    async def boom(url, model, prompt, max_tokens, temperature):
        raise ConnectionError("refused")

    with patch.object(PredictionBackend, "call_ollama", side_effect=boom):
        result = asyncio.run(ollama_backend.predict("prompt"))
    assert result == ""


def test_switch_backend_changes_active(remote_backend):
    remote_backend.switch_backend("ollama")
    assert remote_backend.active_backend == "ollama"


def test_switch_backend_is_immutable_config(remote_backend):
    old_model = remote_backend._config.ollama_model
    remote_backend.switch_backend("ollama")
    assert remote_backend._config.ollama_model == old_model


def test_create_llm_fn_returns_none_when_disabled(disabled_backend):
    fn = disabled_backend.create_llm_fn()
    assert fn is None


def test_create_llm_fn_returns_callable_for_remote(remote_backend):
    fn = remote_backend.create_llm_fn()
    assert callable(fn)


def test_create_llm_fn_callable_returns_string(remote_backend):
    fn = remote_backend.create_llm_fn()
    result = asyncio.run(fn("test prompt"))
    assert isinstance(result, str)


def test_switch_to_disabled_then_create_llm_fn(remote_backend):
    remote_backend.switch_backend("disabled")
    fn = remote_backend.create_llm_fn()
    assert fn is None
