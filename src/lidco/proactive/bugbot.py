"""Proactive bug detector (Bugbot) — Task 410."""

from __future__ import annotations

import ast
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class BugReport:
    """A single bug found in a file."""

    file: str
    line: int
    kind: str
    message: str
    severity: str  # "error" | "warning" | "info"


class BugbotAnalyzer:
    """AST-based bug pattern analyzer."""

    def analyze(self, source: str, file_path: str = "") -> list[BugReport]:
        """Analyze *source* and return a list of BugReport items."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        reports: list[BugReport] = []
        for node in ast.walk(tree):
            self._check_bare_except(node, file_path, reports)
            self._check_swallowed_exception(node, file_path, reports)
            self._check_mutable_default(node, file_path, reports)
            self._check_eq_none(node, file_path, reports)

        # unreachable code requires function-level analysis
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_unreachable(node, file_path, reports)

        return reports

    # ------------------------------------------------------------------ #
    # Individual checkers                                                  #
    # ------------------------------------------------------------------ #

    def _check_bare_except(
        self,
        node: ast.AST,
        file_path: str,
        reports: list[BugReport],
    ) -> None:
        if not isinstance(node, ast.ExceptHandler):
            return
        if node.type is None:  # bare except:
            reports.append(
                BugReport(
                    file=file_path,
                    line=node.lineno,
                    kind="bare_except",
                    message="Bare `except:` catches ALL exceptions including SystemExit/KeyboardInterrupt",
                    severity="warning",
                )
            )

    def _check_swallowed_exception(
        self,
        node: ast.AST,
        file_path: str,
        reports: list[BugReport],
    ) -> None:
        """Detect `except Exception as e: pass` (swallowed exception)."""
        if not isinstance(node, ast.ExceptHandler):
            return
        if node.type is None:
            return  # already reported as bare_except
        # Check body is just a single Pass statement
        body = node.body
        if len(body) == 1 and isinstance(body[0], ast.Pass):
            exc_name = ""
            if isinstance(node.type, ast.Name):
                exc_name = node.type.id
            reports.append(
                BugReport(
                    file=file_path,
                    line=node.lineno,
                    kind="swallowed_exception",
                    message=f"Exception `{exc_name}` is caught and silently ignored (pass)",
                    severity="warning",
                )
            )

    def _check_unreachable(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        reports: list[BugReport],
    ) -> None:
        """Detect unreachable code after return/raise in a function body."""
        self._scan_body_for_unreachable(node.body, file_path, reports)

    def _scan_body_for_unreachable(
        self,
        body: list[ast.stmt],
        file_path: str,
        reports: list[BugReport],
    ) -> None:
        terminators = (ast.Return, ast.Raise, ast.Continue, ast.Break)
        for i, stmt in enumerate(body):
            if isinstance(stmt, terminators) and i + 1 < len(body):
                next_stmt = body[i + 1]
                reports.append(
                    BugReport(
                        file=file_path,
                        line=next_stmt.lineno,
                        kind="unreachable_code",
                        message="Unreachable code after return/raise/continue/break",
                        severity="warning",
                    )
                )
                break
            # Recurse into nested blocks
            for child in ast.iter_child_nodes(stmt):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue  # handled separately
                if hasattr(child, "body") and isinstance(child.body, list):
                    self._scan_body_for_unreachable(child.body, file_path, reports)  # type: ignore[arg-type]

    def _check_mutable_default(
        self,
        node: ast.AST,
        file_path: str,
        reports: list[BugReport],
    ) -> None:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return
        for default in node.args.defaults + node.args.kw_defaults:
            if default is None:
                continue
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                kind_map = {ast.List: "list", ast.Dict: "dict", ast.Set: "set"}
                mtype = kind_map[type(default)]
                reports.append(
                    BugReport(
                        file=file_path,
                        line=node.lineno,
                        kind="mutable_default_arg",
                        message=(
                            f"Mutable default argument `{mtype}` in `{node.name}` — "
                            "use `None` and assign inside function"
                        ),
                        severity="error",
                    )
                )

    def _check_eq_none(
        self,
        node: ast.AST,
        file_path: str,
        reports: list[BugReport],
    ) -> None:
        """Detect `x == None` instead of `x is None`."""
        if not isinstance(node, ast.Compare):
            return
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comparator, ast.Constant) and comparator.value is None:
                op_str = "==" if isinstance(op, ast.Eq) else "!="
                replacement = "is not" if isinstance(op, ast.NotEq) else "is"
                reports.append(
                    BugReport(
                        file=file_path,
                        line=node.lineno,
                        kind="eq_none",
                        message=f"Use `{replacement} None` instead of `{op_str} None`",
                        severity="warning",
                    )
                )


class BugbotWatcher:
    """Poll a list of files for changes and run BugbotAnalyzer on save."""

    def __init__(
        self,
        files: list[str] | None = None,
        on_bugs_found: Callable[[list[BugReport]], None] | None = None,
        poll_interval: float = 2.0,
    ) -> None:
        self._files: list[str] = list(files or [])
        self._on_bugs_found = on_bugs_found
        self._poll_interval = poll_interval
        self._mtimes: dict[str, float] = {}
        self._analyzer = BugbotAnalyzer()
        self._running = False
        self._thread: threading.Thread | None = None
        self._enabled = True

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def add_file(self, path: str) -> None:
        if path not in self._files:
            self._files.append(path)

    def remove_file(self, path: str) -> None:
        self._files = [f for f in self._files if f != path]

    def analyze_file(self, file_path: str) -> list[BugReport]:
        """Run analysis on a single file, returning bug reports."""
        try:
            source = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return []
        return self._analyzer.analyze(source, file_path)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _poll_loop(self) -> None:
        while self._running:
            if self._enabled:
                for path in list(self._files):
                    self._check_file(path)
            time.sleep(self._poll_interval)

    def _check_file(self, path: str) -> None:
        try:
            mtime = Path(path).stat().st_mtime
        except OSError:
            return
        if self._mtimes.get(path) == mtime:
            return
        self._mtimes[path] = mtime
        reports = self.analyze_file(path)
        if reports and self._on_bugs_found:
            self._on_bugs_found(reports)
