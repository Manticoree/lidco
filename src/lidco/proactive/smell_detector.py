"""Code smell detector — Q126."""
from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class Smell:
    kind: str  # "long_method"/"large_class"/"duplicate_code"/"dead_code"/"god_object"
    location: str  # "file:line" or "file"
    description: str
    severity: str  # "low"/"medium"/"high"


class SmellDetector:
    """Detect code smells via AST heuristics."""

    def detect(self, source: str, filename: str = "") -> list[Smell]:
        smells: list[Smell] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return smells

        all_names: set[str] = set()
        called_names: set[str] = set()

        # Collect all call names
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called_names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called_names.add(func.attr)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                all_names.add(node.name)
                end = getattr(node, "end_lineno", node.lineno)
                length = end - node.lineno
                if length > 30:
                    smells.append(
                        Smell(
                            kind="long_method",
                            location=f"{filename}:{node.lineno}",
                            description=f"Function '{node.name}' is {length} lines (>30).",
                            severity="medium" if length <= 60 else "high",
                        )
                    )
                # dead_code: private functions never called
                if node.name.startswith("_") and not node.name.startswith("__"):
                    if node.name not in called_names:
                        smells.append(
                            Smell(
                                kind="dead_code",
                                location=f"{filename}:{node.lineno}",
                                description=f"Private function '{node.name}' never called.",
                                severity="low",
                            )
                        )

            elif isinstance(node, ast.ClassDef):
                end = getattr(node, "end_lineno", node.lineno)
                length = end - node.lineno
                methods = [
                    n for n in ast.iter_child_nodes(node)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if length > 200:
                    smells.append(
                        Smell(
                            kind="large_class",
                            location=f"{filename}:{node.lineno}",
                            description=f"Class '{node.name}' is {length} lines (>200).",
                            severity="medium",
                        )
                    )
                if len(methods) > 10:
                    smells.append(
                        Smell(
                            kind="god_object",
                            location=f"{filename}:{node.lineno}",
                            description=f"Class '{node.name}' has {len(methods)} methods (>10).",
                            severity="high",
                        )
                    )

        return smells

    def detect_duplicates(self, sources: dict[str, str]) -> list[Smell]:
        """Detect identical 5+ line blocks across files."""
        smells: list[Smell] = []
        # Build block sets per file
        file_blocks: dict[str, list[str]] = {}
        for fname, source in sources.items():
            lines = source.splitlines()
            blocks = []
            for i in range(len(lines) - 4):
                block = "\n".join(lines[i:i + 5]).strip()
                if block:
                    blocks.append(block)
            file_blocks[fname] = blocks

        seen: dict[str, str] = {}
        reported: set[str] = set()
        for fname, blocks in file_blocks.items():
            for block in blocks:
                if block in seen:
                    key = tuple(sorted([fname, seen[block]]))
                    if key not in reported:
                        reported.add(key)
                        smells.append(
                            Smell(
                                kind="duplicate_code",
                                location=f"{seen[block]} / {fname}",
                                description="Identical 5-line block detected in multiple files.",
                                severity="medium",
                            )
                        )
                else:
                    seen[block] = fname

        return smells

    def summary(self, smells: list[Smell]) -> dict:
        counts: dict[str, int] = {}
        for s in smells:
            counts[s.severity] = counts.get(s.severity, 0) + 1
        return counts
