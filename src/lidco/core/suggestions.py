"""Contextual next-step suggestions shown after each agent response."""

from __future__ import annotations

import re

# Maximum number of suggestions to show.
MAX_SUGGESTIONS = 3

# Keywords in response content that hint at what the user might want next.
_EXPLAIN_WORDS = re.compile(
    r"\b(объясн|описан|описыва|рассмотр|explain|overview|summary|describ)\w*",
    re.IGNORECASE,
)
_ERROR_WORDS = re.compile(
    r"\b(ошибк|traceback|error|exception|fail|сбой)\w*",
    re.IGNORECASE,
)
_TEST_WORDS = re.compile(
    r"\b(тест|test|pytest|coverage|покрыти)\w*",
    re.IGNORECASE,
)


# Number of history messages at which a /compact suggestion is added.
COMPACT_SUGGEST_THRESHOLD = 12


def suggest(
    tool_calls: list[dict],
    content: str = "",
    history_len: int = 0,
) -> list[str]:
    """Return up to MAX_SUGGESTIONS contextual next-step hints.

    Rules are heuristic — no LLM call.  Tool calls take priority; the
    response text is used as a secondary signal.
    """
    used_tools = {tc.get("tool", "") for tc in tool_calls}
    hints: list[str] = []

    # ── file edits ────────────────────────────────────────────────────────────
    if used_tools & {"file_write", "file_edit"}:
        hints.append("/diff  — просмотреть изменения")
        hints.append("запустить тесты: /run pytest")
        if len(hints) < MAX_SUGGESTIONS:
            hints.append("/lint  — проверить стиль кода")

    # ── tests were run ────────────────────────────────────────────────────────
    elif used_tools & {"run_tests", "bash"}:
        cmds = " ".join(
            tc.get("args", {}).get("command", "") for tc in tool_calls
            if tc.get("tool") == "bash"
        )
        if "pytest" in cmds or "test" in cmds.lower():
            hints.append("coverage_guard  — проверить покрытие")
            hints.append("зафиксировать: попросите «сделай git commit»")
        else:
            hints.append("/status  — статус сессии")
            hints.append("/retry  — повторить последний запрос")

    # ── search / read only ────────────────────────────────────────────────────
    elif used_tools & {"grep", "glob", "file_read"} and not (
        used_tools & {"file_write", "file_edit", "bash"}
    ):
        hints.append("уточните: «отредактируй найденный файл»")
        hints.append("/as coder <задача>  — переключиться на кодера")

    # ── git operations ────────────────────────────────────────────────────────
    elif used_tools & {"git"}:
        hints.append("попросите: «создай pull request»")
        hints.append("/status  — статус сессии")

    # ── pure text response (no tool calls) ───────────────────────────────────
    elif not used_tools:
        if _ERROR_WORDS.search(content):
            hints.append("попросите: «исправь эту ошибку»")
            hints.append("/debug on  — включить режим отладки")
        elif _EXPLAIN_WORDS.search(content):
            hints.append("попросите: «реализуй описанное»")
            hints.append("/as architect <вопрос>  — спросить архитектора")
        elif _TEST_WORDS.search(content):
            hints.append("попросите: «напиши тесты»")
            hints.append("/as tester <задача>  — переключиться на тестера")
        else:
            hints.append("/retry  — повторить с уточнением")
            hints.append("/export  — экспортировать диалог")

    # ── fallback ─────────────────────────────────────────────────────────────
    if not hints:
        hints.append("/status  — статус сессии")
        hints.append("/retry  — повторить последний запрос")

    # ── Task 166: compact suggestion when history is long ─────────────────────
    if history_len >= COMPACT_SUGGEST_THRESHOLD and len(hints) < MAX_SUGGESTIONS:
        hints.append("/compact  — сжать историю диалога")

    return hints[:MAX_SUGGESTIONS]
