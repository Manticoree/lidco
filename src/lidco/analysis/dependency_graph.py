"""Module dependency graph builder — Task 343."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from collections import defaultdict, deque


@dataclass
class DependencyGraph:
    """Directed graph of module dependencies."""

    # module -> set of modules it imports
    edges: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_edge(self, from_module: str, to_module: str) -> None:
        self.edges[from_module].add(to_module)

    def dependencies_of(self, module: str) -> set[str]:
        """Direct dependencies of *module*."""
        return set(self.edges.get(module, set()))

    def all_modules(self) -> set[str]:
        modules: set[str] = set()
        for src, targets in self.edges.items():
            modules.add(src)
            modules.update(targets)
        return modules

    def transitive_deps(self, module: str) -> set[str]:
        """All transitive dependencies of *module* (BFS)."""
        visited: set[str] = set()
        queue = deque(self.edges.get(module, set()))
        while queue:
            dep = queue.popleft()
            if dep in visited:
                continue
            visited.add(dep)
            queue.extend(self.edges.get(dep, set()) - visited)
        return visited

    def find_cycles(self) -> list[list[str]]:
        """Return list of cycles (each as a list of module names)."""
        visited: set[str] = set()
        path: list[str] = []
        path_set: set[str] = set()
        cycles: list[list[str]] = []

        def dfs(node: str) -> None:
            if node in path_set:
                idx = path.index(node)
                cycles.append(path[idx:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            path_set.add(node)
            for neighbor in self.edges.get(node, set()):
                dfs(neighbor)
            path.pop()
            path_set.discard(node)

        for module in list(self.edges.keys()):
            dfs(module)

        return cycles

    def reverse(self) -> "DependencyGraph":
        """Return reversed graph (who imports whom)."""
        rev = DependencyGraph()
        for src, targets in self.edges.items():
            for tgt in targets:
                rev.add_edge(tgt, src)
        return rev


class DependencyGraphBuilder:
    """Build a DependencyGraph from Python source files."""

    def build(self, sources: dict[str, str]) -> DependencyGraph:
        """Build graph from ``{module_name: source_code}`` mapping."""
        graph = DependencyGraph()
        known = set(sources.keys())

        for module_name, source in sources.items():
            imports = self._extract_imports(source)
            for imp in imports:
                # Only add edges to known modules (internal deps)
                base = imp.split(".")[0]
                if base in known or imp in known:
                    graph.add_edge(module_name, imp if imp in known else base)

        return graph

    def build_from_files(self, files: dict[str, str]) -> DependencyGraph:
        """Build graph where keys are file paths (converted to module names)."""
        # Convert file paths to module-like names
        modules = {
            self._path_to_module(fp): src
            for fp, src in files.items()
        }
        return self.build(modules)

    def _extract_imports(self, source: str) -> list[str]:
        """Return list of imported module names from source."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    @staticmethod
    def _path_to_module(path: str) -> str:
        """Convert file path to module name: src/foo/bar.py → foo.bar."""
        path = path.replace("\\", "/")
        if path.endswith(".py"):
            path = path[:-3]
        # Remove common prefixes
        for prefix in ("src/", "lib/", "./"):
            if path.startswith(prefix):
                path = path[len(prefix):]
                break
        return path.replace("/", ".")
