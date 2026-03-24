"""Code explainer — generate human-readable explanations of code blocks."""
from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExplanationSection:
    title: str
    body: str


@dataclass
class CodeExplanation:
    subject: str      # function/class name or file path
    language: str     # "python" etc.
    sections: list[ExplanationSection]
    complexity: str   # "low" | "medium" | "high"

    def format(self) -> str:
        lines = [f"## {self.subject} [{self.language}, complexity: {self.complexity}]"]
        for s in self.sections:
            lines.append(f"\n### {s.title}\n{s.body}")
        return "\n".join(lines)


def _estimate_complexity(node: ast.AST) -> str:
    """Heuristic complexity: count branches, loops, nested functions."""
    branches = 0
    loops = 0
    nesting = 0
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.IfExp)):
            branches += 1
        elif isinstance(child, (ast.For, ast.While, ast.AsyncFor)):
            loops += 1
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nesting += 1
    score = branches + loops * 2 + nesting
    if score <= 3:
        return "low"
    if score <= 8:
        return "medium"
    return "high"


def _args_summary(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = func_node.args
    parts: list[str] = []
    for a in args.args:
        annotation = ""
        if a.annotation and isinstance(a.annotation, ast.Name):
            annotation = f": {a.annotation.id}"
        elif a.annotation and isinstance(a.annotation, ast.Constant):
            annotation = f": {a.annotation.value}"
        parts.append(a.arg + annotation)
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")
    return ", ".join(parts)


class CodeExplainer:
    """Generate structured explanations for Python functions, classes, and files.

    Without an LLM client, uses static AST analysis.
    With an LLM client (has .complete(prompt) -> str), generates richer explanations.
    """

    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client

    def explain_function(self, source: str, func_name: str | None = None) -> CodeExplanation:
        """Explain a function by name (or the first function found) from source."""
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return CodeExplanation(
                subject=func_name or "unknown", language="python",
                sections=[ExplanationSection("Error", f"SyntaxError: {e}")],
                complexity="low",
            )

        target: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if func_name is None or node.name == func_name:
                    target = node
                    break

        if target is None:
            return CodeExplanation(
                subject=func_name or "?", language="python",
                sections=[ExplanationSection("Not found", f"Function '{func_name}' not found.")],
                complexity="low",
            )

        docstring = ast.get_docstring(target) or "(no docstring)"
        args_str = _args_summary(target)
        complexity = _estimate_complexity(target)
        is_async = isinstance(target, ast.AsyncFunctionDef)

        # Count returns
        returns = [n for n in ast.walk(target) if isinstance(n, ast.Return)]
        # Detect try/except
        has_error_handling = any(isinstance(n, ast.Try) for n in ast.walk(target))

        sections = [
            ExplanationSection("Signature", f"{'async ' if is_async else ''}def {target.name}({args_str})"),
            ExplanationSection("Docstring", docstring),
            ExplanationSection("Behaviour", (
                f"- {'Async' if is_async else 'Sync'} function\n"
                f"- {len(returns)} return point(s)\n"
                f"- Error handling: {'yes' if has_error_handling else 'no'}\n"
                f"- Complexity: {complexity}"
            )),
        ]
        return CodeExplanation(subject=target.name, language="python", sections=sections, complexity=complexity)

    def explain_file(self, file_path: str) -> CodeExplanation:
        """Explain a Python file's top-level structure."""
        p = Path(file_path)
        if not p.exists():
            return CodeExplanation(
                subject=file_path, language="python",
                sections=[ExplanationSection("Error", "File not found")],
                complexity="low",
            )
        source = p.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return CodeExplanation(
                subject=p.name, language="python",
                sections=[ExplanationSection("Error", str(e))],
                complexity="low",
            )

        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        functions = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_")]
        imports = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imports += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module:
                imports.append(n.module)
        imports = list(dict.fromkeys(imports))[:10]

        module_doc = ast.get_docstring(tree) or "(no module docstring)"
        complexity = _estimate_complexity(tree)

        sections = [
            ExplanationSection("Module docstring", module_doc),
            ExplanationSection("Public API", f"Classes: {', '.join(classes) or 'none'}\nFunctions: {', '.join(functions[:10]) or 'none'}"),
            ExplanationSection("Dependencies", ", ".join(imports) or "none"),
        ]
        return CodeExplanation(subject=p.name, language="python", sections=sections, complexity=complexity)

    async def explain_async(self, source: str, func_name: str | None = None) -> CodeExplanation:
        """Use LLM if available; otherwise fall back to static analysis."""
        if self._llm is None:
            return self.explain_function(source, func_name)
        prompt = f"Explain this Python code concisely:\n```python\n{source[:3000]}\n```"
        try:
            text = await self._llm.complete(prompt)
            return CodeExplanation(
                subject=func_name or "code",
                language="python",
                sections=[ExplanationSection("AI Explanation", str(text))],
                complexity="unknown",
            )
        except Exception:
            return self.explain_function(source, func_name)
