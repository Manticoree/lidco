"""Static application security testing engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from lidco.sec_intel.vuln_scanner import Severity


@dataclass(frozen=True)
class TaintSource:
    """A taint source (untrusted data origin)."""

    name: str
    file: str = ""
    line: int = 0
    source_type: str = "input"


@dataclass(frozen=True)
class TaintSink:
    """A taint sink (dangerous data consumer)."""

    name: str
    file: str = ""
    line: int = 0
    sink_type: str = "execute"


@dataclass(frozen=True)
class SASTFinding:
    """A SAST finding linking a taint source to a sink."""

    source: TaintSource
    sink: TaintSink
    path: tuple[str, ...] = ()
    severity: Severity = Severity.HIGH
    rule: str = ""


class SASTEngine:
    """Static application security testing via taint analysis."""

    def __init__(self) -> None:
        self._sources: list[TaintSource] = []
        self._sinks: list[TaintSink] = []
        self._rules: list[dict[str, object]] = []

    def add_source(self, source: TaintSource) -> None:
        """Register a taint source."""
        self._sources.append(source)

    def add_sink(self, sink: TaintSink) -> None:
        """Register a taint sink."""
        self._sinks.append(sink)

    def analyze(self, sources: list[TaintSource], sinks: list[TaintSink]) -> list[SASTFinding]:
        """Analyze taint flow from *sources* to *sinks*.

        Default matching: a source flows to a sink when source.source_type
        matches a rule's source_type and sink.sink_type matches the rule's
        sink_type. If no custom rules exist, any ``input`` source reaching
        an ``execute`` sink is flagged.
        """
        findings: list[SASTFinding] = []
        rules = self._rules if self._rules else [
            {"name": "default-taint", "source_type": "input", "sink_type": "execute", "severity": Severity.HIGH},
        ]

        for src in sources:
            for snk in sinks:
                for rule in rules:
                    if src.source_type == rule["source_type"] and snk.sink_type == rule["sink_type"]:
                        findings.append(SASTFinding(
                            source=src,
                            sink=snk,
                            path=(src.name, snk.name),
                            severity=rule["severity"],  # type: ignore[arg-type]
                            rule=rule["name"],  # type: ignore[arg-type]
                        ))
        return findings

    def to_sarif(self, findings: list[SASTFinding]) -> dict[str, Any]:
        """Export *findings* in SARIF-like format."""
        results: list[dict[str, Any]] = []
        for f in findings:
            results.append({
                "ruleId": f.rule,
                "level": "error" if f.severity in (Severity.CRITICAL, Severity.HIGH) else "warning",
                "message": {
                    "text": f"Taint flow from {f.source.name} to {f.sink.name}",
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": f.source.file or "unknown"},
                            "region": {"startLine": f.source.line},
                        },
                    },
                ],
            })
        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "lidco-sast", "version": "1.0.0"}},
                    "results": results,
                },
            ],
        }

    def add_rule(self, name: str, source_type: str, sink_type: str, severity: Severity) -> None:
        """Register a custom taint-flow rule."""
        self._rules.append({
            "name": name,
            "source_type": source_type,
            "sink_type": sink_type,
            "severity": severity,
        })

    def summary(self, findings: list[SASTFinding]) -> str:
        """Return a human-readable summary of *findings*."""
        if not findings:
            return "No taint flows detected."
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        lines = [f"SAST findings: {len(findings)}"]
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            if sev in counts:
                lines.append(f"  {sev}: {counts[sev]}")
        return "\n".join(lines)
