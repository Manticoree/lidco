"""Smart suggestions engine — Q126."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Suggestion:
    id: str
    category: str  # "refactor"/"test"/"doc"/"perf"/"security"
    message: str
    file: str = ""
    line: int = 0
    confidence: float = 0.0
    priority: int = 1  # 1=low, 2=medium, 3=high


# ---------------------------------------------------------------------------
# Built-in rules
# ---------------------------------------------------------------------------

def rule_long_function(code: str, filename: str = "") -> list[Suggestion]:
    """Functions > 50 lines → refactor suggestion."""
    import ast
    suggestions = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return suggestions
    lines = code.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            length = end - node.lineno
            if length > 50:
                suggestions.append(
                    Suggestion(
                        id=f"long_fn_{node.name}_{node.lineno}",
                        category="refactor",
                        message=f"Function '{node.name}' is {length} lines (>50). Consider splitting.",
                        file=filename,
                        line=node.lineno,
                        confidence=0.8,
                        priority=2,
                    )
                )
    return suggestions


def rule_no_docstring(code: str, filename: str = "") -> list[Suggestion]:
    """Classes/functions without docstrings → doc suggestion."""
    import ast
    suggestions = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return suggestions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            has_doc = (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            )
            if not has_doc:
                kind = "Class" if isinstance(node, ast.ClassDef) else "Function"
                suggestions.append(
                    Suggestion(
                        id=f"no_doc_{node.name}_{node.lineno}",
                        category="doc",
                        message=f"{kind} '{node.name}' lacks a docstring.",
                        file=filename,
                        line=node.lineno,
                        confidence=0.7,
                        priority=1,
                    )
                )
    return suggestions


def rule_hardcoded_string(code: str, filename: str = "") -> list[Suggestion]:
    """Hardcoded IPs, URLs, or password-like strings → security suggestion."""
    suggestions = []
    _ip = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
    _url = re.compile(r'https?://[^\s\'"]{5,}')
    _pw = re.compile(r'(?i)(password|passwd|secret|api_?key)\s*=\s*["\'][^"\']{3,}["\']')
    for i, line in enumerate(code.splitlines(), 1):
        if _ip.search(line) or _url.search(line) or _pw.search(line):
            suggestions.append(
                Suggestion(
                    id=f"hardcoded_{i}",
                    category="security",
                    message=f"Line {i}: possible hardcoded credential or URL.",
                    file=filename,
                    line=i,
                    confidence=0.65,
                    priority=3,
                )
            )
    return suggestions


def rule_todo_comment(code: str, filename: str = "") -> list[Suggestion]:
    """# TODO/FIXME → refactor suggestion."""
    suggestions = []
    pattern = re.compile(r'#\s*(TODO|FIXME)\b', re.IGNORECASE)
    for i, line in enumerate(code.splitlines(), 1):
        if pattern.search(line):
            suggestions.append(
                Suggestion(
                    id=f"todo_{i}",
                    category="refactor",
                    message=f"Line {i}: unresolved TODO/FIXME comment.",
                    file=filename,
                    line=i,
                    confidence=0.9,
                    priority=1,
                )
            )
    return suggestions


def rule_bare_except(code: str, filename: str = "") -> list[Suggestion]:
    """Bare `except:` → refactor suggestion."""
    import ast
    suggestions = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return suggestions
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            suggestions.append(
                Suggestion(
                    id=f"bare_except_{node.lineno}",
                    category="refactor",
                    message=f"Line {node.lineno}: bare `except:` catches all exceptions. Specify exception type.",
                    file=filename,
                    line=node.lineno,
                    confidence=0.85,
                    priority=2,
                )
            )
    return suggestions


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SuggestionEngine:
    def __init__(self, rules: list[Callable] = None) -> None:
        self._rules: list[Callable] = list(rules) if rules else []

    def analyze(self, code: str, filename: str = "") -> list[Suggestion]:
        results: list[Suggestion] = []
        for rule in self._rules:
            try:
                results.extend(rule(code, filename))
            except Exception:
                pass
        return results

    def add_rule(self, rule: Callable) -> None:
        self._rules.append(rule)

    def filter(
        self,
        suggestions: list[Suggestion],
        min_confidence: float = 0.0,
        category: str = None,
    ) -> list[Suggestion]:
        out = [s for s in suggestions if s.confidence >= min_confidence]
        if category is not None:
            out = [s for s in out if s.category == category]
        return out

    def top_n(self, suggestions: list[Suggestion], n: int) -> list[Suggestion]:
        sorted_s = sorted(suggestions, key=lambda s: (s.priority, s.confidence), reverse=True)
        return sorted_s[:n]

    @staticmethod
    def with_defaults() -> "SuggestionEngine":
        return SuggestionEngine(
            rules=[
                rule_long_function,
                rule_no_docstring,
                rule_hardcoded_string,
                rule_todo_comment,
                rule_bare_except,
            ]
        )
