"""File reading tool."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult

if TYPE_CHECKING:
    from lidco.index.context_enricher import IndexContextEnricher

# Compress files larger than this many characters when reading from the start.
_COMPRESS_THRESHOLD = 4_000
# Show this many chars of the raw content in compressed output.
_COMPRESS_HEAD_CHARS = 2_000

# ── In-session read cache ────────────────────────────────────────────────────
# Key: (path_str, offset, limit, mtime_ns) — the mtime component means the
# entry is automatically stale when the file is modified on disk.
_CACHE_MAX = 100
_read_cache: OrderedDict[tuple[str, int, int, int], str] = OrderedDict()


def _cache_get(key: tuple[str, int, int, int]) -> str | None:
    if key in _read_cache:
        _read_cache.move_to_end(key)
        return _read_cache[key]
    return None


def _cache_set(key: tuple[str, int, int, int], value: str) -> None:
    _read_cache[key] = value
    _read_cache.move_to_end(key)
    if len(_read_cache) > _CACHE_MAX:
        _read_cache.popitem(last=False)  # evict LRU entry


class FileReadTool(BaseTool):
    """Read file contents."""

    def __init__(
        self,
        enricher: "IndexContextEnricher | None" = None,
        project_dir: Path | None = None,
    ) -> None:
        # Optional injected enricher — used directly (skips lazy load).
        # project_dir overrides Path.cwd() for relative-path computation.
        self._enricher: IndexContextEnricher | None = enricher
        self._enricher_loaded: bool = enricher is not None
        self._project_dir = project_dir

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "Read file with line numbers."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Absolute or relative path to the file to read.",
            ),
            ToolParameter(
                name="offset",
                type="integer",
                description="Line number to start reading from (1-based).",
                required=False,
                default=1,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Maximum number of lines to read.",
                required=False,
                default=2000,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    def _get_enricher(self) -> "IndexContextEnricher | None":
        """Return the enricher, loading it lazily from the project dir on first call."""
        if not self._enricher_loaded:
            from lidco.index.context_enricher import IndexContextEnricher

            self._enricher = IndexContextEnricher.from_project_dir(
                self._project_dir or Path.cwd()
            )
            self._enricher_loaded = True
        return self._enricher

    async def _run(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"]).resolve()
        offset = kwargs.get("offset", 1)
        limit = kwargs.get("limit", 2000)

        if not path.exists():
            parent_exists = path.parent.exists()
            hint = (
                f" (parent directory '{path.parent}' exists — check the filename)"
                if parent_exists
                else f" (parent directory '{path.parent}' does not exist — check the path)"
            )
            return ToolResult(
                output="",
                success=False,
                error=f"File not found: {path}{hint}",
                metadata={"path": str(path), "parent_exists": parent_exists},
            )

        if not path.is_file():
            kind = "directory" if path.is_dir() else "special file"
            return ToolResult(
                output="",
                success=False,
                error=f"Not a file: {path} (it is a {kind})",
                metadata={"path": str(path), "is_dir": path.is_dir()},
            )

        # Build cache key using mtime_ns — auto-invalidates when file changes on disk
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            mtime_ns = 0
        cache_key = (str(path), offset, limit, mtime_ns)
        cached = _cache_get(cache_key)
        if cached is not None:
            return ToolResult(output=cached, metadata={"path": str(path), "cached": True})

        text = path.read_text(encoding="utf-8", errors="replace")

        # Smart compression: only when reading from the start of a large file
        # and the project index has structural info about it.
        is_full_read = offset == 1 and limit >= 50
        if is_full_read and len(text) > _COMPRESS_THRESHOLD:
            compressed = self._try_compress(path, text)
            if compressed is not None:
                _cache_set(cache_key, compressed.output)
                return compressed

        lines = text.splitlines()
        start = max(0, offset - 1)
        end = start + limit
        selected = lines[start:end]

        numbered = [f"{start + i + 1:>6}\t{line}" for i, line in enumerate(selected)]
        output = "\n".join(numbered)
        _cache_set(cache_key, output)

        return ToolResult(
            output=output,
            metadata={"path": str(path), "total_lines": len(lines), "shown": len(selected)},
        )

    def _try_compress(self, path: Path, text: str) -> ToolResult | None:
        """Return a compressed ToolResult if the index has info for *path*, else None."""
        enricher = self._get_enricher()
        if enricher is None:
            return None

        project_dir = self._project_dir or Path.cwd()
        try:
            rel_path = str(path.relative_to(project_dir))
        except ValueError:
            return None

        summary = enricher.get_file_symbol_summary(rel_path)
        if not summary:
            return None

        head = text[:_COMPRESS_HEAD_CHARS]
        remaining = len(text) - _COMPRESS_HEAD_CHARS
        output = (
            f"{summary}\n\n"
            f"## Full content (first {_COMPRESS_HEAD_CHARS} chars)\n"
            f"{head}\n\n"
            f"[... {remaining} more chars — use offset/limit to read specific sections]"
        )
        return ToolResult(
            output=output,
            metadata={
                "path": str(path),
                "total_lines": len(text.splitlines()),
                "shown": _COMPRESS_HEAD_CHARS,
                "compressed": True,
            },
        )
