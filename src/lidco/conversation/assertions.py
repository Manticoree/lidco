"""Assertion engine for validating conversation properties."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssertionResult:
    """Result of a single assertion check."""

    assertion: str
    passed: bool
    details: str


class AssertionEngine:
    """Run assertions against a conversation message list."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages: list[dict] = list(messages)

    def assert_contains(self, turn: int, text: str) -> bool:
        """Return True if the message at *turn* contains *text*."""
        if turn < 0 or turn >= len(self._messages):
            return False
        content = self._messages[turn].get("content", "") or ""
        return text in content

    def assert_role(self, turn: int, role: str) -> bool:
        """Return True if the message at *turn* has the given *role*."""
        if turn < 0 or turn >= len(self._messages):
            return False
        return self._messages[turn].get("role", "") == role

    def assert_token_count(self, turn: int, max_tokens: int) -> bool:
        """Return True if estimated tokens at *turn* are under *max_tokens*."""
        if turn < 0 or turn >= len(self._messages):
            return False
        content = self._messages[turn].get("content", "") or ""
        tokens = len(content) // 4 if isinstance(content, str) else 0
        return tokens <= max_tokens

    def assert_no_empty_turns(self) -> tuple[bool, list[int]]:
        """Return (True, []) if no empty turns, else (False, [indices])."""
        empty_indices: list[int] = []
        for idx, msg in enumerate(self._messages):
            content = msg.get("content", "") or ""
            if not content:
                empty_indices.append(idx)
        return (len(empty_indices) == 0, empty_indices)

    def run_all(self, assertions: list[dict]) -> list[AssertionResult]:
        """Run a list of assertion dicts and return results.

        Each dict should have:
          - ``type``: one of ``contains``, ``role``, ``token_count``, ``no_empty``
          - ``turn``: int (not needed for ``no_empty``)
          - ``value``: the expected value (text, role name, or max tokens)
        """
        results: list[AssertionResult] = []
        for a in assertions:
            a_type = a.get("type", "")
            turn = a.get("turn", 0)
            value = a.get("value", "")

            if a_type == "contains":
                passed = self.assert_contains(turn, str(value))
                results.append(AssertionResult(
                    assertion=f"contains({turn}, {value!r})",
                    passed=passed,
                    details="found" if passed else "not found",
                ))
            elif a_type == "role":
                passed = self.assert_role(turn, str(value))
                results.append(AssertionResult(
                    assertion=f"role({turn}, {value!r})",
                    passed=passed,
                    details="match" if passed else "mismatch",
                ))
            elif a_type == "token_count":
                passed = self.assert_token_count(turn, int(value))
                results.append(AssertionResult(
                    assertion=f"token_count({turn}, {value})",
                    passed=passed,
                    details="within limit" if passed else "exceeds limit",
                ))
            elif a_type == "no_empty":
                passed, indices = self.assert_no_empty_turns()
                results.append(AssertionResult(
                    assertion="no_empty_turns",
                    passed=passed,
                    details=f"empty turns: {indices}" if indices else "none",
                ))
            else:
                results.append(AssertionResult(
                    assertion=f"unknown({a_type})",
                    passed=False,
                    details=f"unknown assertion type: {a_type}",
                ))
        return results
