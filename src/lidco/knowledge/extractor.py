"""Q329 — Knowledge Extractor: extract concepts, patterns, rules from code."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConceptType(Enum):
    """Types of knowledge concepts extracted from code."""

    DESIGN_PATTERN = "design_pattern"
    ARCHITECTURE_DECISION = "architecture_decision"
    BUSINESS_RULE = "business_rule"
    INVARIANT = "invariant"
    API_ENDPOINT = "api_endpoint"
    DATA_MODEL = "data_model"
    ALGORITHM = "algorithm"
    CONFIGURATION = "configuration"


@dataclass(frozen=True)
class Concept:
    """A knowledge concept extracted from code."""

    name: str
    concept_type: ConceptType
    description: str
    source_file: str
    line_number: int = 0
    confidence: float = 1.0
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches(self, query: str) -> bool:
        """Check if concept matches a search query (case-insensitive)."""
        q = query.lower()
        return (
            q in self.name.lower()
            or q in self.description.lower()
            or any(q in t.lower() for t in self.tags)
        )


@dataclass
class ExtractionResult:
    """Result of knowledge extraction from one or more files."""

    concepts: list[Concept] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def concept_count(self) -> int:
        return len(self.concepts)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def by_type(self, concept_type: ConceptType) -> list[Concept]:
        return [c for c in self.concepts if c.concept_type == concept_type]


# Heuristic patterns for detecting design patterns in code
_PATTERN_HINTS: dict[str, str] = {
    "Singleton": r"_instance\s*=\s*None|__new__\s*\(",
    "Factory": r"def\s+create_|class\s+\w*Factory",
    "Observer": r"subscribe|notify|on_event|add_listener",
    "Strategy": r"class\s+\w*Strategy|set_strategy",
    "Builder": r"class\s+\w*Builder|def\s+build\(",
    "Decorator": r"def\s+__call__\(|@\w+\ndef\s+\w+",
    "Repository": r"class\s+\w*Repository|find_all|find_by_id",
    "Command": r"class\s+\w*Command|def\s+execute\(",
}

# Heuristic patterns for detecting business rules / invariants
_RULE_HINTS: list[tuple[str, str]] = [
    (r"assert\s+", "assertion-based invariant"),
    (r"raise\s+ValueError\(", "validation rule"),
    (r"if\s+not\s+\w+:\s*\n\s*raise", "guard clause"),
    (r"@validate|@validator", "decorated validation"),
]


class KnowledgeExtractor:
    """Extract knowledge concepts from Python source files."""

    def __init__(self) -> None:
        self._custom_patterns: dict[str, str] = {}

    def add_pattern(self, name: str, regex: str) -> None:
        """Register a custom pattern to detect."""
        self._custom_patterns[name] = regex

    def extract_from_source(self, source: str, file_path: str = "<unknown>") -> ExtractionResult:
        """Extract concepts from Python source code string."""
        result = ExtractionResult()

        # AST-based extraction
        try:
            tree = ast.parse(source)
            self._extract_classes(tree, source, file_path, result)
            self._extract_functions(tree, source, file_path, result)
        except SyntaxError as exc:
            result.errors.append(f"SyntaxError in {file_path}: {exc}")

        # Regex-based pattern detection
        self._detect_design_patterns(source, file_path, result)
        self._detect_rules(source, file_path, result)
        self._detect_custom_patterns(source, file_path, result)

        return result

    def extract_from_file(self, file_path: str) -> ExtractionResult:
        """Extract concepts from a Python file on disk."""
        try:
            with open(file_path, encoding="utf-8") as fh:
                source = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            return ExtractionResult(errors=[f"Cannot read {file_path}: {exc}"])
        return self.extract_from_source(source, file_path)

    # ------------------------------------------------------------------
    # Internal extraction helpers
    # ------------------------------------------------------------------

    def _extract_classes(
        self,
        tree: ast.Module,
        source: str,
        file_path: str,
        result: ExtractionResult,
    ) -> None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            docstring = ast.get_docstring(node) or ""
            bases = [self._name_of(b) for b in node.bases]
            concept_type = ConceptType.DATA_MODEL
            if any("Error" in b or "Exception" in b for b in bases):
                continue  # skip exception classes
            if any("ABC" in b or "Protocol" in b for b in bases):
                concept_type = ConceptType.ARCHITECTURE_DECISION
            result.concepts.append(
                Concept(
                    name=node.name,
                    concept_type=concept_type,
                    description=docstring.split("\n")[0] if docstring else f"Class {node.name}",
                    source_file=file_path,
                    line_number=node.lineno,
                    tags=tuple(bases),
                )
            )

    def _extract_functions(
        self,
        tree: ast.Module,
        source: str,
        file_path: str,
        result: ExtractionResult,
    ) -> None:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue  # skip private
            docstring = ast.get_docstring(node) or ""
            tags: list[str] = []
            if isinstance(node, ast.AsyncFunctionDef):
                tags.append("async")
            # Detect API endpoint hints
            concept_type = ConceptType.ALGORITHM
            for deco in node.decorator_list:
                deco_name = self._name_of(deco)
                if any(k in deco_name.lower() for k in ("route", "get", "post", "put", "delete")):
                    concept_type = ConceptType.API_ENDPOINT
                    tags.append("http")
                    break
            result.concepts.append(
                Concept(
                    name=node.name,
                    concept_type=concept_type,
                    description=docstring.split("\n")[0] if docstring else f"Function {node.name}",
                    source_file=file_path,
                    line_number=node.lineno,
                    tags=tuple(tags),
                )
            )

    def _detect_design_patterns(
        self, source: str, file_path: str, result: ExtractionResult
    ) -> None:
        all_patterns = {**_PATTERN_HINTS, **self._custom_patterns}
        for pattern_name, regex in all_patterns.items():
            matches = list(re.finditer(regex, source))
            if matches:
                line_no = source[: matches[0].start()].count("\n") + 1
                result.concepts.append(
                    Concept(
                        name=pattern_name,
                        concept_type=ConceptType.DESIGN_PATTERN,
                        description=f"Detected {pattern_name} pattern",
                        source_file=file_path,
                        line_number=line_no,
                        confidence=min(1.0, 0.5 + 0.1 * len(matches)),
                        tags=("pattern", pattern_name.lower()),
                    )
                )

    def _detect_rules(self, source: str, file_path: str, result: ExtractionResult) -> None:
        for regex, rule_desc in _RULE_HINTS:
            matches = list(re.finditer(regex, source))
            if matches:
                line_no = source[: matches[0].start()].count("\n") + 1
                result.concepts.append(
                    Concept(
                        name=rule_desc,
                        concept_type=ConceptType.BUSINESS_RULE
                        if "rule" in rule_desc
                        else ConceptType.INVARIANT,
                        description=f"{rule_desc} ({len(matches)} occurrence(s))",
                        source_file=file_path,
                        line_number=line_no,
                        confidence=min(1.0, 0.4 + 0.15 * len(matches)),
                        tags=("rule",),
                    )
                )

    def _detect_custom_patterns(
        self, source: str, file_path: str, result: ExtractionResult
    ) -> None:
        # Custom patterns already handled in _detect_design_patterns merged dict
        pass

    @staticmethod
    def _name_of(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return KnowledgeExtractor._name_of(node.func)
        return ""
