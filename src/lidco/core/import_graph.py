"""AST-based Python import dependency graph with cycle detection.

Usage::

    from lidco.core.import_graph import build_graph

    graph = build_graph(Path("."))
    cycles = graph.find_cycles()
    print(graph.summary())
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


# Maximum path depth when searching for cycles (guards against combinatorial blowup).
_MAX_CYCLE_DEPTH = 15

# Maximum file size to read during graph construction (guards against OOM).
_MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportEdge:
    """A single import statement extracted from a Python file.

    Attributes:
        source_file: Path relative to the graph root (POSIX separators).
        module:      Resolved absolute module name (e.g. ``"lidco.core.session"``).
        names:       Names imported from the module.  Empty tuple for plain
                     ``import X`` statements.  ``("*",)`` for star imports.
        line:        Line number in *source_file*.
        is_relative: ``True`` when the original statement used leading dots.
    """

    source_file: str
    module: str
    names: tuple[str, ...]
    line: int
    is_relative: bool


@dataclass
class ImportGraph:
    """Directed import dependency graph for a Python project.

    Built by :func:`build_graph`.  Provides cycle detection and a Markdown
    summary of the dependency structure.
    """

    root: Path
    edges: list[ImportEdge] = field(default_factory=list)
    # Internal: populated by build_graph()
    _file_to_module: dict[str, str] = field(default_factory=dict, repr=False)
    _module_to_file: dict[str, str] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_imports_for(self, file: str) -> list[ImportEdge]:
        """Return all import edges whose ``source_file`` equals *file*."""
        return [e for e in self.edges if e.source_file == file]

    def get_files(self) -> list[str]:
        """Return a sorted list of unique source files present in the graph."""
        return sorted({e.source_file for e in self.edges})

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    def find_cycles(self) -> list[list[str]]:
        """Detect circular imports among *project-internal* modules.

        External dependencies (``os``, ``pathlib``, third-party packages) are
        ignored — only imports that resolve to a scanned ``.py`` file are
        considered.

        Returns:
            A list of cycles.  Each cycle is a list of distinct module names
            forming the loop, e.g. ``["lidco.core.session", "lidco.agents.graph"]``
            for a two-module cycle.  Duplicate cycles (same nodes, different
            starting point) are de-duplicated.
        """
        adjacency: dict[str, list[str]] = {}
        for edge in self.edges:
            src = self._file_to_module.get(edge.source_file)
            if src is None:
                continue
            if edge.module not in self._module_to_file:
                continue  # external dependency — skip
            adjacency.setdefault(src, []).append(edge.module)

        return _find_cycles(adjacency)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary(
        self, _precomputed_cycles: list[list[str]] | None = None
    ) -> str:
        """Return a Markdown summary of the import graph analysis.

        Args:
            _precomputed_cycles: Pass the result of a previous :meth:`find_cycles`
                call to avoid recomputing cycles.  When ``None`` (default) the
                cycles are computed here.
        """
        files_count = len({e.source_file for e in self.edges})
        total_imports = len(self.edges)
        internal = sum(1 for e in self.edges if e.module in self._module_to_file)
        external = total_imports - internal

        cycles = _precomputed_cycles if _precomputed_cycles is not None else self.find_cycles()

        lines: list[str] = [
            "## Import Graph Analysis",
            "",
            f"Files scanned: **{files_count}**",
            f"Total imports: **{total_imports}**"
            f" ({internal} internal, {external} external)",
            "",
        ]

        if not cycles:
            lines.append("[OK] **No circular imports detected**")
        else:
            lines.append(f"[WARNING] **{len(cycles)} circular import(s) detected:**")
            lines.append("")
            for i, cycle in enumerate(cycles, 1):
                chain = " → ".join(cycle) + f" → {cycle[0]}"
                lines.append(f"  {i}. {chain}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module path helpers
# ---------------------------------------------------------------------------


def _module_from_path(path: Path, root: Path) -> str:
    """Convert a file path to a dotted Python module name.

    Rules applied in order:

    1. Make *path* relative to *root*.
    2. Strip a leading ``src`` component (common project layout).
    3. Remove the ``.py`` extension from the last component.
    4. Convert ``__init__`` → package name (drop the last component).
    5. Join the remaining parts with dots.

    Returns an empty string when the conversion fails.
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        return path.stem

    parts = list(rel.parts)

    # Strip leading "src" directory
    if parts and parts[0] == "src":
        parts = parts[1:]

    if not parts:
        return ""

    # Strip .py extension
    last = parts[-1]
    if last.endswith(".py"):
        parts[-1] = last[:-3]

    # __init__.py → package name (drop the __init__ component)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Import statement parser
# ---------------------------------------------------------------------------


def _parse_imports(
    source: str,
    filepath: str,
    pkg_name: str,
) -> list[ImportEdge]:
    """Parse a Python source string and return all :class:`ImportEdge` instances.

    Args:
        source:    Raw Python source text.
        filepath:  Relative file path used as ``ImportEdge.source_file``.
        pkg_name:  Dotted module name of *filepath* (used to resolve relative
                   imports).  Pass an empty string when unknown.

    Returns:
        A list of :class:`ImportEdge` objects, one per logical import target.
        For ``from . import a, b`` two edges are produced.  Returns an empty
        list when *source* has a :exc:`SyntaxError`.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    edges: list[ImportEdge] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                edges.append(
                    ImportEdge(
                        source_file=filepath,
                        module=alias.name,
                        names=(),
                        line=node.lineno,
                        is_relative=False,
                    )
                )

        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            is_relative = level > 0

            if is_relative and pkg_name:
                # Resolve relative import to an absolute module name.
                #
                # Python's relative import levels count packages, not modules:
                #   level=1 means "current package"
                #   level=2 means "parent package"
                #
                # For a regular module (e.g. pkg_name="lidco.core.session"):
                #   level=1 → base="lidco.core"  (strip the module component)
                #   level=2 → base="lidco"
                #
                # For a package __init__.py (e.g. pkg_name="lidco.core"):
                #   level=1 → base="lidco.core"  (strip 0 components — the
                #              package IS the namespace for its own relative imports)
                #   level=2 → base="lidco"
                #
                # The filepath check distinguishes the two cases.
                _fp_norm = filepath.replace("\\", "/")
                _is_package = _fp_norm.split("/")[-1] == "__init__.py"
                pkg_parts = pkg_name.split(".")
                if _is_package:
                    # Strip (level-1) components from the package name.
                    strip = max(0, level - 1)
                else:
                    # Strip (level) components from the module name.
                    strip = level
                base_parts = pkg_parts[:-strip] if strip and strip < len(pkg_parts) else ([] if strip >= len(pkg_parts) else pkg_parts)
                base = ".".join(base_parts)

                if node.module:
                    # from .utils import func
                    resolved = f"{base}.{node.module}" if base else node.module
                    names = tuple(alias.name for alias in node.names)
                    edges.append(
                        ImportEdge(
                            source_file=filepath,
                            module=resolved,
                            names=names,
                            line=node.lineno,
                            is_relative=True,
                        )
                    )
                else:
                    # from . import a, b  → each name is a potential submodule
                    for alias in node.names:
                        submodule = f"{base}.{alias.name}" if base else alias.name
                        edges.append(
                            ImportEdge(
                                source_file=filepath,
                                module=submodule,
                                names=(alias.name,),
                                line=node.lineno,
                                is_relative=True,
                            )
                        )
            else:
                # Absolute import: "from os.path import join" or unresolvable relative
                mod = node.module or ""
                names = tuple(alias.name for alias in node.names)
                edges.append(
                    ImportEdge(
                        source_file=filepath,
                        module=mod,
                        names=names,
                        line=node.lineno,
                        is_relative=is_relative,
                    )
                )

    return edges


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def _find_cycles(adjacency: dict[str, list[str]]) -> list[list[str]]:
    """Find all simple cycles in a directed graph.

    Uses a DFS that tracks the current path from a given start node.  When a
    neighbor equals the start node we have found a cycle.  Only
    project-internal modules (those present as keys in *adjacency*) are
    followed.

    Duplicate cycles (same set of nodes reached from different starting
    points) are de-duplicated via :class:`frozenset` keys.

    Args:
        adjacency: Mapping of ``module_name → [imported_module_names]``.
                   Only modules present as keys are explored.

    Returns:
        A list of cycles.  Each cycle is a list of distinct node names
        (the starting node is **not** repeated at the end).
    """
    cycles: list[list[str]] = []
    seen_keys: set[frozenset[str]] = set()

    def dfs(
        start: str,
        current: str,
        path: list[str],
        path_set: set[str],
    ) -> None:
        if len(path) > _MAX_CYCLE_DEPTH:
            return
        for neighbor in adjacency.get(current, []):
            if neighbor == start and len(path) >= 1:
                # Back-edge to start — cycle found
                key = frozenset(path)
                if key not in seen_keys:
                    seen_keys.add(key)
                    cycles.append(list(path))
            elif neighbor not in path_set and neighbor in adjacency:
                # Continue DFS only for project-internal nodes not yet on path
                path.append(neighbor)
                path_set.add(neighbor)
                dfs(start, neighbor, path, path_set)
                path.pop()
                path_set.discard(neighbor)

    for start_node in list(adjacency.keys()):
        dfs(start_node, start_node, [start_node], {start_node})

    return cycles


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(root: Path) -> ImportGraph:
    """Scan all Python files under *root* and build an :class:`ImportGraph`.

    Algorithm:

    1. Walk the directory tree collecting all ``*.py`` files.
    2. Build a bidirectional mapping between relative file paths and dotted
       module names (``_module_from_path``).
    3. Parse every file with :func:`_parse_imports`, collecting
       :class:`ImportEdge` objects.

    Files that cannot be read or contain :exc:`SyntaxError` are silently
    skipped.

    Args:
        root: Project root directory.  All paths in the returned graph are
              relative to this directory and use POSIX separators.

    Returns:
        A populated :class:`ImportGraph`.
    """
    resolved_root = root.resolve()
    # Collect .py files that are not symlinks and resolve to within the root.
    # This prevents path traversal via symlinks pointing outside the project.
    py_files: list[Path] = []
    for p in sorted(root.rglob("*.py")):
        try:
            if p.is_symlink():
                continue
            if not p.resolve().is_relative_to(resolved_root):
                continue
        except (OSError, ValueError):
            continue
        py_files.append(p)

    file_to_module: dict[str, str] = {}
    module_to_file: dict[str, str] = {}

    # First pass: build file ↔ module name mappings
    for py_file in py_files:
        module = _module_from_path(py_file, root)
        if not module:
            continue
        # Use POSIX separators so paths are consistent across platforms.
        rel = py_file.relative_to(root).as_posix()
        file_to_module[rel] = module
        module_to_file[module] = rel

    # Second pass: parse import statements
    all_edges: list[ImportEdge] = []
    for py_file in py_files:
        rel = py_file.relative_to(root).as_posix()
        pkg_name = file_to_module.get(rel, "")
        try:
            if py_file.stat().st_size > _MAX_FILE_BYTES:
                continue
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        edges = _parse_imports(source, rel, pkg_name)
        all_edges.extend(edges)

    return ImportGraph(
        root=root,
        edges=all_edges,
        _file_to_module=file_to_module,
        _module_to_file=module_to_file,
    )
