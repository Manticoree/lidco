"""Token usage heatmap — Task 439."""

from __future__ import annotations

from typing import Any


class TokenHeatmap:
    """Tracks per-file and per-function token costs."""

    def __init__(self) -> None:
        self._files: dict[str, int] = {}
        self._functions: dict[str, int] = {}

    # ── recording ────────────────────────────────────────────────────────────

    def record_file_access(self, file_path: str, token_cost: int) -> None:
        """Accumulate *token_cost* tokens for *file_path*."""
        self._files[file_path] = self._files.get(file_path, 0) + token_cost

    def record_function_access(self, qualified_name: str, token_cost: int) -> None:
        """Accumulate *token_cost* tokens for *qualified_name*."""
        self._functions[qualified_name] = (
            self._functions.get(qualified_name, 0) + token_cost
        )

    # ── querying ─────────────────────────────────────────────────────────────

    def top_files(self, n: int = 10) -> list[tuple[str, int]]:
        """Return top-*n* files by token cost, sorted descending."""
        return sorted(self._files.items(), key=lambda x: x[1], reverse=True)[:n]

    def top_functions(self, n: int = 10) -> list[tuple[str, int]]:
        """Return top-*n* functions by token cost, sorted descending."""
        return sorted(self._functions.items(), key=lambda x: x[1], reverse=True)[:n]

    # ── rendering ────────────────────────────────────────────────────────────

    def render_heatmap(self, items: list[tuple[str, int]], title: str = "Token Heatmap") -> Any:
        """Return a Rich Table with colour-coded token column.

        Tokens are coloured green→yellow→red based on relative magnitude.
        """
        from rich.style import Style
        from rich.table import Table

        if not items:
            from rich.text import Text
            table = Table(title=title)
            table.add_column("Name")
            table.add_column("Tokens", justify="right")
            return table

        max_tokens = max(t for _, t in items) or 1

        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Name", no_wrap=False)
        table.add_column("Tokens", justify="right")

        for name, tokens in items:
            ratio = tokens / max_tokens
            if ratio < 0.33:
                style = Style(color="green")
            elif ratio < 0.66:
                style = Style(color="yellow")
            else:
                style = Style(color="red")

            table.add_row(name, f"{tokens:,}", style=style)

        return table
