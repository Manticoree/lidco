"""WikiGenerator — auto-generates module documentation from code + git history.

Combines:
- AST extraction (docstrings, signatures, type hints)
- Git log for recent change history
- Optional LLM synthesis for natural language summary
"""
from __future__ import annotations

import ast
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_WIKI_DIR = ".lidco/wiki"


@dataclass
class FuncDoc:
    name: str
    signature: str
    docstring: str = ""
    is_async: bool = False


@dataclass
class ClassDoc:
    name: str
    docstring: str = ""
    methods: list[FuncDoc] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)


@dataclass
class WikiPage:
    module_path: str
    summary: str
    classes: list[ClassDoc] = field(default_factory=list)
    functions: list[FuncDoc] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)
    generated_at: str = ""

    def to_markdown(self) -> str:
        lines = [
            f"# {self.module_path}",
            "",
            f"*Generated: {self.generated_at}*",
            "",
            "## Summary",
            "",
            self.summary,
            "",
        ]
        if self.classes:
            lines += ["## Classes", ""]
            for cls in self.classes:
                bases_str = f"({', '.join(cls.bases)})" if cls.bases else ""
                lines.append(f"### `{cls.name}{bases_str}`")
                if cls.docstring:
                    lines.append(f"{cls.docstring}")
                for m in cls.methods:
                    prefix = "async " if m.is_async else ""
                    lines.append(f"- `{prefix}{m.name}{m.signature}`")
                    if m.docstring:
                        lines.append(f"  {m.docstring}")
                lines.append("")
        if self.functions:
            lines += ["## Functions", ""]
            for f in self.functions:
                prefix = "async " if f.is_async else ""
                lines.append(f"### `{prefix}{f.name}{f.signature}`")
                if f.docstring:
                    lines.append(f"{f.docstring}")
                lines.append("")
        if self.recent_changes:
            lines += ["## Recent Changes", ""]
            for change in self.recent_changes:
                lines.append(f"- {change}")
            lines.append("")
        return "\n".join(lines)


class WikiGenerator:
    """Generates a WikiPage for a Python module."""

    def __init__(self, llm_client: Any | None = None, max_git_lines: int = 10) -> None:
        self._llm = llm_client
        self._max_git_lines = max_git_lines

    def generate_module(self, path: str, project_dir: Path) -> WikiPage:
        """Generate a WikiPage for *path* (relative or absolute)."""
        p = Path(path)
        if not p.is_absolute():
            p = project_dir / path

        classes, functions = self._extract_ast(p)
        recent_changes = self._get_git_history(p, project_dir)
        summary = self._generate_summary(p, classes, functions)
        from datetime import timezone
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        page = WikiPage(
            module_path=str(path),
            summary=summary,
            classes=classes,
            functions=functions,
            recent_changes=recent_changes,
            generated_at=generated_at,
        )
        self._save(page, project_dir)
        return page

    def load(self, path: str, project_dir: Path) -> WikiPage | None:
        p = self._wiki_path(path, project_dir)
        if not p.exists():
            return None
        text = p.read_text(encoding="utf-8")
        return self._parse_markdown(path, text)

    # ------------------------------------------------------------------

    def _wiki_path(self, module_path: str, project_dir: Path) -> Path:
        safe = module_path.replace("/", "_").replace("\\", "_").replace(".py", "")
        return project_dir / _WIKI_DIR / f"{safe}.md"

    def _extract_ast(self, p: Path) -> tuple[list[ClassDoc], list[FuncDoc]]:
        classes: list[ClassDoc] = []
        functions: list[FuncDoc] = []
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            return classes, functions

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cls = ClassDoc(
                    name=node.name,
                    docstring=ast.get_docstring(node) or "",
                    bases=[ast.unparse(b) for b in node.bases],
                    methods=[],
                )
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        cls.methods.append(self._func_doc(item))
                classes.append(cls)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Top-level only
                if not any(
                    isinstance(node, ast.ClassDef) for node in ast.walk(tree)
                    if hasattr(node, "body") and node is not tree  # type: ignore[comparison-overlap]
                ):
                    functions.append(self._func_doc(node))

        # Simpler top-level function extraction
        functions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._func_doc(node))

        return classes, functions

    def _func_doc(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> FuncDoc:
        args = ast.unparse(node.args) if hasattr(ast, "unparse") else "()"
        returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return FuncDoc(
            name=node.name,
            signature=f"({args}){returns}",
            docstring=ast.get_docstring(node) or "",
            is_async=isinstance(node, ast.AsyncFunctionDef),
        )

    def _get_git_history(self, p: Path, project_dir: Path) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"-{self._max_git_lines}", "--", str(p)],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                timeout=5,
            )
            lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            return lines[: self._max_git_lines]
        except Exception:
            return []

    def _generate_summary(
        self,
        p: Path,
        classes: list[ClassDoc],
        functions: list[FuncDoc],
    ) -> str:
        if self._llm:
            return self._llm_summary(p, classes, functions)
        # Heuristic: use module docstring + class/func count
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
            mod_doc = ast.get_docstring(tree) or ""
        except Exception:
            mod_doc = ""
        cls_names = ", ".join(c.name for c in classes[:5])
        fn_names = ", ".join(f.name for f in functions[:5])
        parts = []
        if mod_doc:
            parts.append(mod_doc.splitlines()[0])
        if cls_names:
            parts.append(f"Classes: {cls_names}.")
        if fn_names:
            parts.append(f"Functions: {fn_names}.")
        return " ".join(parts) or f"Module `{p.name}`."

    def _llm_summary(
        self,
        p: Path,
        classes: list[ClassDoc],
        functions: list[FuncDoc],
    ) -> str:
        items = [f"class {c.name}" for c in classes] + [f"def {f.name}" for f in functions]
        items_str = "\n".join(items[:30])
        messages = [
            {
                "role": "system",
                "content": "Summarize this Python module in 2-3 sentences.",
            },
            {
                "role": "user",
                "content": f"Module: {p.name}\n\nContents:\n{items_str}",
            },
        ]
        try:
            return self._llm(messages).strip()
        except Exception:
            return f"Module `{p.name}`."

    def _save(self, page: WikiPage, project_dir: Path) -> None:
        p = self._wiki_path(page.module_path, project_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(page.to_markdown(), encoding="utf-8")

    def _parse_markdown(self, module_path: str, text: str) -> WikiPage:
        """Minimal parse: extract summary block."""
        summary = ""
        in_summary = False
        for line in text.splitlines():
            if line.startswith("## Summary"):
                in_summary = True
                continue
            if line.startswith("## ") and in_summary:
                break
            if in_summary and line.strip():
                summary = line.strip()
                break
        return WikiPage(module_path=module_path, summary=summary)
