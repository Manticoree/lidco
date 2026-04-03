"""Q260 CLI commands: /classify-data, /retention, /redact, /compliance-report."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q260 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /classify-data
    # ------------------------------------------------------------------

    async def classify_data_handler(args: str) -> str:
        from lidco.compliance.data_classifier import DataClassifier

        if "classifier" not in _state:
            _state["classifier"] = DataClassifier()

        classifier: DataClassifier = _state["classifier"]  # type: ignore[assignment]

        text = args.strip()
        if not text:
            return "Usage: /classify-data <text>"

        result = classifier.classify(text)
        lines = [
            f"Level: {result.level}",
            f"Confidence: {result.confidence}",
            f"Reasons: {', '.join(result.reasons)}",
        ]
        if result.pii_found:
            lines.append(f"PII found: {', '.join(result.pii_found)}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /retention
    # ------------------------------------------------------------------

    async def retention_handler(args: str) -> str:
        from lidco.compliance.retention import RetentionManager, RetentionPolicy

        if "retention" not in _state:
            _state["retention"] = RetentionManager()

        mgr: RetentionManager = _state["retention"]  # type: ignore[assignment]

        parts = args.strip().split()
        if not parts:
            return "Usage: /retention [list | add <name> <pattern> <days> | hold <name> | eval <resource> <age>]"

        sub = parts[0]

        if sub == "list":
            policies = mgr.policies()
            if not policies:
                return "No retention policies."
            lines = []
            for p in policies:
                hold = " [HELD]" if p.legal_hold else ""
                lines.append(f"  {p.name}: {p.resource_pattern} ({p.retention_days}d, {p.action}){hold}")
            return "Policies:\n" + "\n".join(lines)

        if sub == "add":
            if len(parts) < 4:
                return "Usage: /retention add <name> <pattern> <days> [delete|archive]"
            name = parts[1]
            pattern = parts[2]
            try:
                days = int(parts[3])
            except ValueError:
                return "Error: days must be an integer"
            action = parts[4] if len(parts) > 4 else "delete"
            policy = RetentionPolicy(name=name, resource_pattern=pattern, retention_days=days, action=action)
            mgr.add_policy(policy)
            return f"Added policy '{name}'."

        if sub == "hold":
            if len(parts) < 2:
                return "Usage: /retention hold <name>"
            name = parts[1]
            result = mgr.set_legal_hold(name, True)
            if result is None:
                return f"Policy '{name}' not found."
            return f"Legal hold set on '{name}'."

        if sub == "eval":
            if len(parts) < 3:
                return "Usage: /retention eval <resource> <age>"
            resource = parts[1]
            try:
                age = float(parts[2])
            except ValueError:
                return "Error: age must be a number"
            record = mgr.evaluate(resource, age)
            if record is None:
                return "No applicable policy."
            return f"Action: {record.action} (policy: {record.policy_name}, held: {record.held})"

        return "Unknown subcommand. Use: list, add, hold, eval"

    # ------------------------------------------------------------------
    # /redact
    # ------------------------------------------------------------------

    async def redact_handler(args: str) -> str:
        from lidco.compliance.redaction import RedactionEngine

        if "redactor" not in _state:
            _state["redactor"] = RedactionEngine()

        engine: RedactionEngine = _state["redactor"]  # type: ignore[assignment]

        text = args.strip()
        if not text:
            return "Usage: /redact <text>"

        result = engine.redact_pii(text)
        lines = [
            result.text,
            f"Redacted: {result.redacted_count} items",
        ]
        if result.redacted_types:
            lines.append(f"Types: {', '.join(result.redacted_types)}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /compliance-report
    # ------------------------------------------------------------------

    async def compliance_report_handler(args: str) -> str:
        from lidco.compliance.reporter import ComplianceReporter

        if "reporter" not in _state:
            _state["reporter"] = ComplianceReporter()

        reporter: ComplianceReporter = _state["reporter"]  # type: ignore[assignment]

        sub = args.strip().lower()
        # Use empty context for demo
        context: dict = {}

        if sub == "soc2":
            checks = reporter.check_soc2(context)
        elif sub == "gdpr":
            checks = reporter.check_gdpr(context)
        elif sub == "hipaa":
            checks = reporter.check_hipaa(context)
        elif sub in ("all", ""):
            summary = reporter.summary(context)
            lines = []
            for fw, counts in summary.items():
                lines.append(f"{fw.upper()}: {counts['pass']} pass, {counts['fail']} fail, {counts['warning']} warning")
            return "\n".join(lines)
        else:
            return "Usage: /compliance-report [soc2 | gdpr | hipaa | all]"

        lines = [f"{c.control}: {c.status}" + (f" — {c.recommendation}" if c.recommendation else "") for c in checks]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------

    registry.register(SlashCommand("classify-data", "Classify data sensitivity", classify_data_handler))
    registry.register(SlashCommand("retention", "Data retention management", retention_handler))
    registry.register(SlashCommand("redact", "Redact PII from text", redact_handler))
    registry.register(SlashCommand("compliance-report", "Run compliance checks", compliance_report_handler))
