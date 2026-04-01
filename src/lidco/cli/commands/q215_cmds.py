"""Q215 CLI commands: /vuln-scan, /audit-deps, /detect-secrets, /sast."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q215 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /vuln-scan
    # ------------------------------------------------------------------

    async def vuln_scan_handler(args: str) -> str:
        from lidco.sec_intel.vuln_scanner import VulnScanner

        source = args.strip()
        if not source:
            return "Usage: /vuln-scan <source_code>"
        scanner = VulnScanner()
        findings = scanner.scan(source)
        if not findings:
            return "No vulnerabilities found."
        lines = [scanner.summary(findings), ""]
        for f in findings:
            lines.append(f"  [{f.severity.value}] {f.rule} at line {f.line}: {f.description}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /audit-deps
    # ------------------------------------------------------------------

    async def audit_deps_handler(args: str) -> str:
        from lidco.sec_intel.dep_auditor import DepAuditor

        text = args.strip()
        if not text:
            return "Usage: /audit-deps <requirements_text>"
        auditor = DepAuditor()
        reqs = auditor.parse_requirements(text)
        if not reqs:
            return "No valid requirements found."
        findings = auditor.audit(reqs)
        return auditor.summary(findings)

    # ------------------------------------------------------------------
    # /detect-secrets
    # ------------------------------------------------------------------

    async def detect_secrets_handler(args: str) -> str:
        from lidco.sec_intel.secret_detector import SecretDetector

        source = args.strip()
        if not source:
            return "Usage: /detect-secrets <source_code>"
        detector = SecretDetector()
        findings = detector.scan(source)
        if not findings:
            return "No secrets detected."
        lines = [detector.summary(findings), ""]
        for f in findings:
            lines.append(f"  [{f.pattern_name}] line {f.line}: entropy={f.entropy:.2f} fp={f.false_positive_likelihood}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /sast
    # ------------------------------------------------------------------

    async def sast_handler(args: str) -> str:
        from lidco.sec_intel.sast_engine import SASTEngine, TaintSource, TaintSink

        text = args.strip()
        if not text:
            return "Usage: /sast <description>"
        engine = SASTEngine()
        # Demo: parse simple "source->sink" notation
        parts = text.split("->")
        if len(parts) == 2:
            src = TaintSource(name=parts[0].strip())
            snk = TaintSink(name=parts[1].strip())
            findings = engine.analyze([src], [snk])
            return engine.summary(findings)
        return "Provide taint flow as: source_name -> sink_name"

    # ------------------------------------------------------------------
    # Register all
    # ------------------------------------------------------------------

    registry.register(SlashCommand("vuln-scan", "Scan source for OWASP vulnerabilities", vuln_scan_handler))
    registry.register(SlashCommand("audit-deps", "Audit dependencies for known vulnerabilities", audit_deps_handler))
    registry.register(SlashCommand("detect-secrets", "Detect secrets in source code", detect_secrets_handler))
    registry.register(SlashCommand("sast", "Static application security testing", sast_handler))
