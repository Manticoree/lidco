"""Dead Feature Finder — find dead features, unused code paths, and stale flags.

Provides ``DeadFeatureFinder`` that scans source files for unreachable
code, feature flags that are never enabled, dead endpoints, and unused
code paths.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Any


class DeadKind(enum.Enum):
    """Kind of dead feature."""

    UNUSED_FUNCTION = "unused_function"
    DEAD_ENDPOINT = "dead_endpoint"
    STALE_FLAG = "stale_flag"
    UNREACHABLE_CODE = "unreachable_code"
    UNUSED_IMPORT = "unused_import"
    DEAD_CLASS = "dead_class"


@dataclass(frozen=True)
class DeadFeature:
    """A single detected dead feature or unused code path."""

    kind: DeadKind
    name: str
    file: str
    line: int
    confidence: float = 0.5  # 0.0–1.0
    reason: str = ""

    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.7

    def label(self) -> str:
        conf = f"{self.confidence:.0%}"
        return f"[{self.kind.value}] {self.name} at {self.file}:{self.line} ({conf})"


@dataclass
class DeadFeatureReport:
    """Report of all dead features found."""

    features: list[DeadFeature] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def count(self) -> int:
        return len(self.features)

    @property
    def high_confidence_count(self) -> int:
        return sum(1 for f in self.features if f.is_high_confidence())

    def by_kind(self, kind: DeadKind) -> list[DeadFeature]:
        return [f for f in self.features if f.kind == kind]

    def by_file(self, path: str) -> list[DeadFeature]:
        return [f for f in self.features if f.file == path]

    def summary(self) -> str:
        lines = [
            f"Dead Feature Report: {self.count} items in {self.files_scanned} files",
            f"High confidence: {self.high_confidence_count}",
        ]
        by_kind: dict[str, int] = {}
        for feat in self.features:
            by_kind[feat.kind.value] = by_kind.get(feat.kind.value, 0) + 1
        for kind, cnt in sorted(by_kind.items()):
            lines.append(f"  {kind}: {cnt}")
        return "\n".join(lines)


class DeadFeatureFinder:
    """Find dead features and unused code paths.

    Parameters
    ----------
    files:
        Mapping of file path to source content.
    flag_names:
        Known feature flag names.  Flags not referenced in code are
        considered stale.
    endpoint_paths:
        Known endpoint paths (e.g. ``/api/users``).  Endpoints not
        referenced in route definitions are considered dead.
    """

    def __init__(
        self,
        files: dict[str, str] | None = None,
        flag_names: list[str] | None = None,
        endpoint_paths: list[str] | None = None,
    ) -> None:
        self._files: dict[str, str] = dict(files) if files else {}
        self._flags: list[str] = list(flag_names) if flag_names else []
        self._endpoints: list[str] = list(endpoint_paths) if endpoint_paths else []

    @property
    def file_count(self) -> int:
        return len(self._files)

    def add_file(self, path: str, content: str) -> None:
        self._files[path] = content

    def scan(self) -> DeadFeatureReport:
        """Run all detectors and return a unified report."""
        features: list[DeadFeature] = []
        features.extend(self._find_unused_functions())
        features.extend(self._find_stale_flags())
        features.extend(self._find_dead_endpoints())
        features.extend(self._find_unreachable_code())
        features.extend(self._find_unused_imports())
        return DeadFeatureReport(features=features, files_scanned=len(self._files))

    # -- detectors --

    def _find_unused_functions(self) -> list[DeadFeature]:
        """Find functions defined but never called elsewhere."""
        # Collect all function definitions
        defs: list[tuple[str, str, int]] = []  # (name, file, line)
        for path, content in self._files.items():
            for i, line in enumerate(content.splitlines(), 1):
                m = re.match(r"^(?:async\s+)?def\s+(\w+)\s*\(", line)
                if m:
                    fname = m.group(1)
                    if not fname.startswith("_"):
                        defs.append((fname, path, i))

        # Check which names appear elsewhere (simple text search)
        all_text = "\n".join(self._files.values())
        results: list[DeadFeature] = []
        for fname, fpath, fline in defs:
            # Count occurrences: definition + calls
            count = len(re.findall(r"\b" + re.escape(fname) + r"\b", all_text))
            if count <= 1:
                results.append(
                    DeadFeature(
                        kind=DeadKind.UNUSED_FUNCTION,
                        name=fname,
                        file=fpath,
                        line=fline,
                        confidence=0.7,
                        reason="Function defined but not referenced elsewhere",
                    )
                )
        return results

    def _find_stale_flags(self) -> list[DeadFeature]:
        """Find feature flags that are never referenced in code."""
        if not self._flags:
            return []
        all_text = "\n".join(self._files.values())
        results: list[DeadFeature] = []
        for flag in self._flags:
            if flag not in all_text:
                results.append(
                    DeadFeature(
                        kind=DeadKind.STALE_FLAG,
                        name=flag,
                        file="<flags>",
                        line=0,
                        confidence=0.9,
                        reason="Feature flag never referenced in scanned code",
                    )
                )
        return results

    def _find_dead_endpoints(self) -> list[DeadFeature]:
        """Find endpoint paths not registered in route definitions."""
        if not self._endpoints:
            return []
        all_text = "\n".join(self._files.values())
        results: list[DeadFeature] = []
        for ep in self._endpoints:
            if ep not in all_text:
                results.append(
                    DeadFeature(
                        kind=DeadKind.DEAD_ENDPOINT,
                        name=ep,
                        file="<endpoints>",
                        line=0,
                        confidence=0.8,
                        reason="Endpoint path not found in scanned code",
                    )
                )
        return results

    def _find_unreachable_code(self) -> list[DeadFeature]:
        """Find code after return/raise/break/continue statements."""
        results: list[DeadFeature] = []
        for path, content in self._files.items():
            lines = content.splitlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if re.match(r"^(return|raise|break|continue)\b", stripped):
                    # Check if next non-blank line at same indent is code
                    indent = len(line) - len(line.lstrip())
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j]
                        if not next_line.strip():
                            continue
                        next_indent = len(next_line) - len(next_line.lstrip())
                        if next_indent == indent and not next_line.strip().startswith(
                            ("except", "finally", "elif", "else", "}", "#")
                        ):
                            results.append(
                                DeadFeature(
                                    kind=DeadKind.UNREACHABLE_CODE,
                                    name=next_line.strip()[:60],
                                    file=path,
                                    line=j + 1,
                                    confidence=0.6,
                                    reason=f"Code after {stripped.split()[0]} statement",
                                )
                            )
                        break
        return results

    def _find_unused_imports(self) -> list[DeadFeature]:
        """Find imports that are never used after the import line."""
        results: list[DeadFeature] = []
        for path, content in self._files.items():
            lines = content.splitlines()
            for i, line in enumerate(lines, 1):
                m = re.match(
                    r"^(?:from\s+\S+\s+)?import\s+(\w+)(?:\s+as\s+(\w+))?",
                    line.strip(),
                )
                if m:
                    name = m.group(2) or m.group(1)
                    rest = "\n".join(lines[i:])  # everything after import
                    if not re.search(r"\b" + re.escape(name) + r"\b", rest):
                        results.append(
                            DeadFeature(
                                kind=DeadKind.UNUSED_IMPORT,
                                name=name,
                                file=path,
                                line=i,
                                confidence=0.8,
                                reason="Import not referenced after import line",
                            )
                        )
        return results
