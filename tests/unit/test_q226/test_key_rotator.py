"""Tests for lidco.gateway.key_rotator."""
from __future__ import annotations

import pytest

from lidco.gateway.key_rotator import ApiKey, KeyRotator


class TestApiKeyDataclass:
    def test_defaults(self) -> None:
        ak = ApiKey(key="sk-123", provider="openai")
        assert ak.usage_count == 0
        assert ak.exhausted is False
        assert ak.last_used == 0.0


class TestKeyRotatorRoundRobin:
    def test_add_key(self) -> None:
        kr = KeyRotator(strategy="round-robin")
        ak = kr.add_key("openai", "sk-1")
        assert ak.provider == "openai"
        assert ak.key == "sk-1"

    def test_round_robin_rotation(self) -> None:
        kr = KeyRotator(strategy="round-robin")
        kr.add_key("openai", "sk-1")
        kr.add_key("openai", "sk-2")
        first = kr.next_key("openai")
        second = kr.next_key("openai")
        assert first is not None
        assert second is not None
        assert first.key != second.key

    def test_round_robin_wraps(self) -> None:
        kr = KeyRotator(strategy="round-robin")
        kr.add_key("openai", "sk-1")
        kr.add_key("openai", "sk-2")
        keys = [kr.next_key("openai").key for _ in range(4)]  # type: ignore[union-attr]
        assert keys == ["sk-1", "sk-2", "sk-1", "sk-2"]

    def test_skips_exhausted(self) -> None:
        kr = KeyRotator(strategy="round-robin")
        kr.add_key("openai", "sk-1")
        kr.add_key("openai", "sk-2")
        kr.mark_exhausted("openai", "sk-1")
        nk = kr.next_key("openai")
        assert nk is not None
        assert nk.key == "sk-2"

    def test_all_exhausted_returns_none(self) -> None:
        kr = KeyRotator(strategy="round-robin")
        kr.add_key("openai", "sk-1")
        kr.mark_exhausted("openai", "sk-1")
        assert kr.next_key("openai") is None


class TestKeyRotatorLeastUsed:
    def test_least_used_picks_minimum(self) -> None:
        kr = KeyRotator(strategy="least-used")
        kr.add_key("openai", "sk-1")
        kr.add_key("openai", "sk-2")
        kr.mark_used("openai", "sk-1")
        kr.mark_used("openai", "sk-1")
        nk = kr.next_key("openai")
        assert nk is not None
        assert nk.key == "sk-2"


class TestKeyRotatorGeneral:
    def test_remove_key(self) -> None:
        kr = KeyRotator()
        kr.add_key("openai", "sk-1")
        assert kr.remove_key("openai", "sk-1") is True
        assert kr.remove_key("openai", "sk-1") is False

    def test_mark_used_updates(self) -> None:
        kr = KeyRotator()
        kr.add_key("openai", "sk-1")
        ak = kr.mark_used("openai", "sk-1")
        assert ak is not None
        assert ak.usage_count == 1
        assert ak.last_used > 0

    def test_mark_used_nonexistent(self) -> None:
        kr = KeyRotator()
        assert kr.mark_used("openai", "sk-nope") is None

    def test_reset(self) -> None:
        kr = KeyRotator()
        kr.add_key("openai", "sk-1")
        kr.mark_used("openai", "sk-1")
        kr.mark_exhausted("openai", "sk-1")
        count = kr.reset("openai")
        assert count == 1
        keys = kr.keys("openai")
        assert keys[0].usage_count == 0
        assert keys[0].exhausted is False

    def test_providers(self) -> None:
        kr = KeyRotator()
        kr.add_key("openai", "sk-1")
        kr.add_key("anthropic", "ak-1")
        assert sorted(kr.providers()) == ["anthropic", "openai"]

    def test_summary(self) -> None:
        kr = KeyRotator()
        kr.add_key("openai", "sk-1")
        kr.add_key("openai", "sk-2")
        kr.mark_exhausted("openai", "sk-2")
        s = kr.summary()
        assert s["openai"]["total"] == 2
        assert s["openai"]["active"] == 1
        assert s["openai"]["exhausted"] == 1

    def test_invalid_strategy_raises(self) -> None:
        with pytest.raises(ValueError):
            KeyRotator(strategy="random")

    def test_next_key_unknown_provider(self) -> None:
        kr = KeyRotator()
        assert kr.next_key("nope") is None
