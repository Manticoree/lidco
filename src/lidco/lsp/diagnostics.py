"""LSP diagnostics collection — Q190, task 1065."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

from lidco.lsp.client import LSPClient


class DiagnosticSeverity(enum.IntEnum):
    """LSP diagnostic severity levels."""

    ERROR = 1
    WARNING = 2
    INFO = 3
    HINT = 4


@dataclass(frozen=True)
class Diagnostic:
    """A single diagnostic message from the LSP server."""

    file: str
    line: int
    column: int
    severity: DiagnosticSeverity
    message: str
    source: str = ""


class DiagnosticsCollector:
    """Collect and query diagnostics from an LSP server."""

    def __init__(self, client: LSPClient) -> None:
        self._client = client
        self._cache: dict[str, tuple[Diagnostic, ...]] = {}

    def collect(self, file: str) -> tuple[Diagnostic, ...]:
        """Collect diagnostics for a single file.

        Sends a textDocument/diagnostic request and returns parsed results.
        """
        try:
            result = self._client.send_request("textDocument/diagnostic", {
                "textDocument": {"uri": _file_uri(file)},
            })
        except (RuntimeError, ValueError):
            return ()

        diagnostics = _parse_diagnostics(file, result)
        self._cache = {**self._cache, file: diagnostics}
        return diagnostics

    def collect_all(self) -> dict[str, tuple[Diagnostic, ...]]:
        """Collect diagnostics for all open files via workspace/diagnostic.

        Returns a mapping of file path to diagnostics tuple.
        """
        try:
            result = self._client.send_request("workspace/diagnostic", {})
        except (RuntimeError, ValueError):
            return {}

        items = result.get("items", [])
        if not isinstance(items, list):
            return {}

        collected: dict[str, tuple[Diagnostic, ...]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            uri = item.get("uri", "")
            file_path = uri.replace("file://", "")
            raw_diags = item.get("items", item.get("diagnostics", []))
            parsed = _parse_raw_diagnostics(file_path, raw_diags)
            if parsed:
                collected[file_path] = parsed

        self._cache = {**self._cache, **collected}
        return collected

    def severity_counts(self) -> dict[str, int]:
        """Return counts of cached diagnostics grouped by severity name.

        The keys are lowercase severity names: 'error', 'warning', 'info', 'hint'.
        """
        counts: dict[str, int] = {}
        for diags in self._cache.values():
            for d in diags:
                name = d.severity.name.lower()
                counts[name] = counts.get(name, 0) + 1
        return counts


def _file_uri(path: str) -> str:
    """Convert a file path to a file:// URI."""
    clean = path.replace("\\", "/")
    if not clean.startswith("/"):
        clean = "/" + clean
    return f"file://{clean}"


def _parse_diagnostics(file: str, result: Any) -> tuple[Diagnostic, ...]:
    """Parse a textDocument/diagnostic response."""
    if isinstance(result, dict):
        items = result.get("items", result.get("diagnostics", []))
    elif isinstance(result, list):
        items = result
    else:
        return ()

    return _parse_raw_diagnostics(file, items)


def _parse_raw_diagnostics(file: str, items: list) -> tuple[Diagnostic, ...]:
    """Parse a list of raw LSP diagnostic dicts into Diagnostic tuples."""
    if not isinstance(items, list):
        return ()

    diagnostics: list[Diagnostic] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rng = item.get("range", {})
        start = rng.get("start", {})
        sev_raw = item.get("severity", DiagnosticSeverity.ERROR)
        try:
            severity = DiagnosticSeverity(sev_raw)
        except (ValueError, KeyError):
            severity = DiagnosticSeverity.ERROR

        diagnostics.append(Diagnostic(
            file=file,
            line=start.get("line", 0),
            column=start.get("character", 0),
            severity=severity,
            message=item.get("message", ""),
            source=item.get("source", ""),
        ))

    return tuple(diagnostics)
