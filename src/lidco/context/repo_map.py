"""RepoMap — repository import-graph PageRank for context prioritisation."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RepoMapEntry:
    file: str
    symbols: list[str]
    rank: float
    token_estimate: int


class RepoMap:
    """Build a ranked map of repository files using AST import analysis."""

    def __init__(
        self,
        project_dir: Path | None = None,
        token_budget: int = 4096,
    ) -> None:
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.token_budget = token_budget

    # ------------------------------------------------------------------
    # Graph building
    # ------------------------------------------------------------------

    def _path_to_module(self, path: Path) -> str:
        """Convert a file path to a dot-separated module name relative to project_dir."""
        try:
            rel = path.relative_to(self.project_dir)
        except ValueError:
            return path.stem
        parts = list(rel.parts)
        if parts and parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        return ".".join(parts)

    def _module_to_path_key(self, module: str) -> str:
        """Return a normalised key for a module name."""
        return module.replace("/", ".").replace("\\", ".")

    def build_import_graph(self) -> dict[str, list[str]]:
        """Parse all .py files; return adjacency dict module -> [imported modules]."""
        py_files = list(self.project_dir.rglob("*.py"))
        if not py_files:
            return {}

        # Build module->file mapping
        module_names: dict[str, str] = {}  # module -> file path str
        for p in py_files:
            mod = self._path_to_module(p)
            module_names[mod] = str(p)

        graph: dict[str, list[str]] = {}
        for p in py_files:
            mod = self._path_to_module(p)
            try:
                source = p.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(p))
            except SyntaxError:
                graph[mod] = []
                continue
            except OSError:
                graph[mod] = []
                continue

            imports: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            # Keep only imports that map to project modules
            resolved: list[str] = []
            for imp in imports:
                if imp in module_names:
                    resolved.append(imp)
                else:
                    # Try prefix match (e.g. "lidco.cli" -> "lidco/cli/__init__")
                    for known in module_names:
                        if known == imp or known.startswith(imp + "."):
                            resolved.append(known)
                            break
            graph[mod] = resolved

        return graph

    # ------------------------------------------------------------------
    # PageRank
    # ------------------------------------------------------------------

    def compute_ranks(self, graph: dict[str, list[str]]) -> dict[str, float]:
        """PageRank with damping=0.85, max 50 iterations."""
        if not graph:
            return {}

        nodes = list(graph.keys())
        n = len(nodes)
        if n == 0:
            return {}

        damping = 0.85
        ranks: dict[str, float] = {node: 1.0 / n for node in nodes}

        # Build reverse graph (who links to me)
        in_links: dict[str, list[str]] = {node: [] for node in nodes}
        for src, targets in graph.items():
            for tgt in targets:
                if tgt in in_links:
                    in_links[tgt].append(src)

        out_count: dict[str, int] = {node: len(targets) for node, targets in graph.items()}

        for _ in range(50):
            new_ranks: dict[str, float] = {}
            # Handle dangling nodes (no outbound links)
            dangling_sum = sum(ranks[node] for node in nodes if out_count[node] == 0)
            dangling_contrib = damping * dangling_sum / n

            for node in nodes:
                rank_sum = 0.0
                for src in in_links[node]:
                    if out_count[src] > 0:
                        rank_sum += ranks[src] / out_count[src]
                new_ranks[node] = (1.0 - damping) / n + damping * rank_sum + dangling_contrib

            # Check convergence
            delta = sum(abs(new_ranks[nd] - ranks[nd]) for nd in nodes)
            ranks = new_ranks
            if delta < 1e-6:
                break

        return dict(ranks)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        changed_files: list[str] | None = None,
        token_budget: int | None = None,
    ) -> str:
        """Build graph, rank files, apply boosts, format within budget."""
        graph = self.build_import_graph()
        if not graph:
            return ""

        ranks = self.compute_ranks(graph)

        # Apply 2x boost for changed files
        if changed_files:
            boosted: dict[str, float] = {}
            for node, rank in ranks.items():
                # Check if any changed file corresponds to this node
                boosted_rank = rank
                for cf in changed_files:
                    cf_norm = cf.replace("\\", "/")
                    node_norm = node.replace(".", "/")
                    if cf_norm == node_norm or cf_norm.endswith(node_norm + ".py") or node_norm in cf_norm:
                        boosted_rank = rank * 2
                        break
                boosted[node] = boosted_rank
            ranks = boosted

        entries = self._build_entries(ranks)
        return self.format_for_prompt(entries, token_budget or self.token_budget)

    def _extract_symbols(self, file_path: str) -> list[str]:
        """Extract top-level function and class names from a Python file."""
        p = Path(file_path)
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=file_path)
        except (SyntaxError, OSError):
            return []
        symbols: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append(node.name)
        return symbols

    def _build_entries(self, ranks: dict[str, float]) -> list[RepoMapEntry]:
        """Build RepoMapEntry list sorted by rank descending."""
        # Map module names back to file paths
        module_to_path: dict[str, str] = {}
        for p in self.project_dir.rglob("*.py"):
            mod = self._path_to_module(p)
            module_to_path[mod] = str(p)

        entries: list[RepoMapEntry] = []
        for mod, rank in ranks.items():
            file_path = module_to_path.get(mod)
            if file_path is None:
                continue
            symbols = self._extract_symbols(file_path)
            # Rough token estimate: symbols line length
            text = f"{mod} (rank {rank:.4f}): {', '.join(symbols)}\n"
            token_est = len(text) // 4
            entries.append(RepoMapEntry(
                file=file_path,
                symbols=symbols,
                rank=rank,
                token_estimate=token_est,
            ))
        entries.sort(key=lambda e: e.rank, reverse=True)
        return entries

    def ranked_entries(self) -> list[RepoMapEntry]:
        """Return RepoMapEntry list sorted by rank descending."""
        graph = self.build_import_graph()
        if not graph:
            return []
        ranks = self.compute_ranks(graph)
        return self._build_entries(ranks)

    def format_for_prompt(
        self,
        entries: list[RepoMapEntry] | None = None,
        budget: int | None = None,
    ) -> str:
        """Format entries as repo map block, truncating at token budget."""
        if entries is None:
            entries = self.ranked_entries()
        if not entries:
            return ""

        effective_budget = (budget or self.token_budget) * 4  # chars

        lines: list[str] = ["# Repo Map\n"]
        used = len(lines[0])

        for entry in entries:
            # Use relative path if possible
            try:
                rel = str(Path(entry.file).relative_to(self.project_dir))
            except ValueError:
                rel = entry.file
            rel = rel.replace("\\", "/")
            symbols_str = ", ".join(entry.symbols) if entry.symbols else ""
            line = f"{rel} (rank {entry.rank:.2f}): {symbols_str}\n"
            if used + len(line) > effective_budget:
                break
            lines.append(line)
            used += len(line)

        return "".join(lines)
