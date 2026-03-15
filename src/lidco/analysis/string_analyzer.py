"""String literal analysis — Task 356."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum


class StringIssueKind(Enum):
    HARDCODED_URL = "hardcoded_url"
    HARDCODED_IP = "hardcoded_ip"
    HARDCODED_PATH = "hardcoded_path"
    LONG_STRING = "long_string"           # > 120 chars in code
    TODO_FIXME = "todo_fixme"             # TODO/FIXME in string literals


@dataclass(frozen=True)
class StringIssue:
    kind: StringIssueKind
    value: str         # truncated
    file: str
    line: int
    detail: str


@dataclass
class StringReport:
    issues: list[StringIssue] = field(default_factory=list)
    string_literals: int = 0

    def by_kind(self, kind: StringIssueKind) -> list[StringIssue]:
        return [i for i in self.issues if i.kind == kind]


_URL_RE = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_ABS_PATH_RE = re.compile(r"^(/[a-zA-Z0-9._/-]{4,}|[A-Za-z]:\\[^\"']{4,})")
_TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)


class StringAnalyzer:
    """Analyze string literals in Python source for potential issues."""

    def analyze(self, source: str, file_path: str = "") -> StringReport:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return StringReport()

        report = StringReport()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            if not isinstance(node.value, str):
                continue

            value = node.value
            report.string_literals += 1
            trunc = value[:80] + ("…" if len(value) > 80 else "")

            # Hardcoded URL
            if _URL_RE.search(value):
                report.issues.append(StringIssue(
                    kind=StringIssueKind.HARDCODED_URL,
                    value=trunc,
                    file=file_path,
                    line=node.lineno,
                    detail=f"Hardcoded URL in source: {value[:60]}",
                ))

            # Hardcoded IP (skip 127.0.0.1 and 0.0.0.0)
            ip_match = _IP_RE.search(value)
            if ip_match and ip_match.group() not in ("127.0.0.1", "0.0.0.0", "255.255.255.255"):
                report.issues.append(StringIssue(
                    kind=StringIssueKind.HARDCODED_IP,
                    value=trunc,
                    file=file_path,
                    line=node.lineno,
                    detail=f"Hardcoded IP address: {ip_match.group()}",
                ))

            # Hardcoded absolute path
            if _ABS_PATH_RE.match(value):
                report.issues.append(StringIssue(
                    kind=StringIssueKind.HARDCODED_PATH,
                    value=trunc,
                    file=file_path,
                    line=node.lineno,
                    detail=f"Hardcoded absolute path: {value[:60]}",
                ))

            # Long string
            if len(value) > 120:
                report.issues.append(StringIssue(
                    kind=StringIssueKind.LONG_STRING,
                    value=trunc,
                    file=file_path,
                    line=node.lineno,
                    detail=f"String literal is {len(value)} chars (threshold: 120)",
                ))

            # TODO/FIXME in strings
            if _TODO_RE.search(value):
                report.issues.append(StringIssue(
                    kind=StringIssueKind.TODO_FIXME,
                    value=trunc,
                    file=file_path,
                    line=node.lineno,
                    detail=f"TODO/FIXME found in string literal",
                ))

        return report
