"""Tests for lidco.budget.session_init."""
from __future__ import annotations

import unittest

from lidco.budget.session_init import SessionBudgetInit, SessionInitializer


class TestSessionBudgetInit(unittest.TestCase):
    def test_defaults(self) -> None:
        init = SessionBudgetInit()
        assert init.model == ""
        assert init.context_limit == 128000
        assert init.max_output == 4096
        assert init.available_for_conversation == 0

    def test_frozen(self) -> None:
        init = SessionBudgetInit()
        with self.assertRaises(AttributeError):
            init.model = "changed"  # type: ignore[misc]


class TestSessionInitializer(unittest.TestCase):
    def test_initialize_defaults(self) -> None:
        si = SessionInitializer()
        result = si.initialize()
        assert result.context_limit == 128000
        assert result.system_prompt_reserve == 3000
        assert result.tool_reserve == 5000
        assert result.available_for_conversation == 128000 - 3000 - 5000

    def test_initialize_custom_limit(self) -> None:
        si = SessionInitializer(default_limit=64000)
        result = si.initialize(model="gpt-4", context_limit=200000, system_prompt_tokens=10000)
        assert result.context_limit == 200000
        assert result.model == "gpt-4"
        assert result.system_prompt_reserve == 10000
        assert result.available_for_conversation == 200000 - 10000 - 5000

    def test_initialize_uses_default_when_zero(self) -> None:
        si = SessionInitializer(default_limit=50000)
        result = si.initialize()
        assert result.context_limit == 50000

    def test_available_never_negative(self) -> None:
        si = SessionInitializer(default_limit=1000)
        result = si.initialize(system_prompt_tokens=999000)
        assert result.available_for_conversation == 0

    def test_estimate_system_tokens(self) -> None:
        si = SessionInitializer()
        assert si.estimate_system_tokens("abcd") == 1
        assert si.estimate_system_tokens("a" * 400) == 100

    def test_recommend_reserves(self) -> None:
        si = SessionInitializer()
        recs = si.recommend_reserves(128000)
        assert recs["system"] == 5000  # min(5000, 6400)
        assert recs["tools"] == 10000  # min(10000, 12800)
        assert recs["buffer"] == 5000  # min(5000, 6400)

    def test_recommend_reserves_small_limit(self) -> None:
        si = SessionInitializer()
        recs = si.recommend_reserves(10000)
        assert recs["system"] == 500
        assert recs["tools"] == 1000
        assert recs["buffer"] == 500

    def test_summary(self) -> None:
        si = SessionInitializer()
        result = si.initialize(model="claude-3")
        text = si.summary(result)
        assert "claude-3" in text
        assert "128,000" in text

    def test_summary_no_model(self) -> None:
        si = SessionInitializer()
        result = si.initialize()
        text = si.summary(result)
        assert "(default)" in text


if __name__ == "__main__":
    unittest.main()
