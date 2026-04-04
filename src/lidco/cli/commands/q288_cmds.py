"""Q288 CLI commands — /verify-logic, /verify-code, /link-evidence, /verification-report

Registered via register_q288_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q288_commands(registry) -> None:
    """Register Q288 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /verify-logic <statement1> | <statement2> | ...
    # ------------------------------------------------------------------
    async def verify_logic_handler(args: str) -> str:
        from lidco.verify.logic import LogicVerifier

        raw = args.strip()
        if not raw:
            return "Usage: /verify-logic <stmt1> | <stmt2> | ..."

        statements = [s.strip() for s in raw.split("|") if s.strip()]
        if len(statements) < 2:
            return "Provide at least two statements separated by |"

        verifier = LogicVerifier()
        result = verifier.verify(statements)
        lines = [f"Valid: {result.is_valid}"]
        if result.issues:
            lines.append("Issues:")
            for issue in result.issues:
                lines.append(f"  - {issue}")
        else:
            lines.append("No issues found.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /verify-code <old_code> | <new_code>
    # ------------------------------------------------------------------
    async def verify_code_handler(args: str) -> str:
        from lidco.verify.code_proof import CodeProofChecker

        raw = args.strip()
        if not raw:
            return "Usage: /verify-code <old_code> | <new_code>"

        parts = raw.split("|", 1)
        if len(parts) < 2:
            return "Provide old and new code separated by |"

        old_code = parts[0].strip()
        new_code = parts[1].strip()

        checker = CodeProofChecker()
        result = checker.verify_change(old_code, new_code)
        lines = [
            f"Valid: {result.is_valid}",
            f"Preconditions met: {result.preconditions_met}",
            f"Postconditions met: {result.postconditions_met}",
            f"Invariants held: {result.invariants_held}",
        ]
        if result.issues:
            lines.append("Issues:")
            for issue in result.issues:
                lines.append(f"  - {issue}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /link-evidence <claim> | <source>:<content> [| <source>:<content> ...]
    # ------------------------------------------------------------------
    async def link_evidence_handler(args: str) -> str:
        from lidco.verify.evidence import EvidenceLinker

        raw = args.strip()
        if not raw:
            return "Usage: /link-evidence <claim> | <source>:<content> ..."

        parts = [p.strip() for p in raw.split("|") if p.strip()]
        if len(parts) < 2:
            return "Provide a claim and at least one source:content pair separated by |"

        claim = parts[0]
        linker = EvidenceLinker()
        for part in parts[1:]:
            if ":" in part:
                source, content = part.split(":", 1)
                linker.add_evidence(source.strip(), content.strip())
            else:
                linker.add_evidence("unknown", part)

        link = linker.link(claim)
        if link is None:
            return f"No evidence found for claim: {claim}"
        return (
            f"Claim: {link.claim}\n"
            f"Source: {link.source}\n"
            f"Strength: {link.strength}"
        )

    # ------------------------------------------------------------------
    # /verification-report [add <name> <finding> | score | generate]
    # ------------------------------------------------------------------
    _report_instance = None

    async def verification_report_handler(args: str) -> str:
        from lidco.verify.report import VerificationReport

        nonlocal _report_instance
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "generate"

        if _report_instance is None:
            _report_instance = VerificationReport()

        if subcmd == "add":
            name = parts[1] if len(parts) > 1 else "default"
            findings = parts[2:] if len(parts) > 2 else []
            _report_instance.add_section(name, findings)
            return f"Added section '{name}' with {len(findings)} finding(s)."

        if subcmd == "score":
            return f"Confidence: {_report_instance.confidence_score()}"

        if subcmd == "generate":
            result = _report_instance.generate()
            lines = [f"Score: {result.score}"]
            for sec in result.sections:
                lines.append(f"  [{sec.name}] {len(sec.findings)} finding(s)")
            if result.recommendations:
                lines.append("Recommendations:")
                for r in result.recommendations:
                    lines.append(f"  - {r}")
            # Reset for next use
            _report_instance = None
            return "\n".join(lines)

        if subcmd == "reset":
            _report_instance = None
            return "Report reset."

        return (
            "Usage: /verification-report <subcommand>\n"
            "  add <name> [findings...]   add section\n"
            "  score                      show confidence\n"
            "  generate                   produce report\n"
            "  reset                      clear report"
        )

    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("verify-logic", "Verify logical consistency", verify_logic_handler))
    registry.register(SlashCommand("verify-code", "Verify code change proofs", verify_code_handler))
    registry.register(SlashCommand("link-evidence", "Link claims to evidence", link_evidence_handler))
    registry.register(SlashCommand("verification-report", "Generate verification report", verification_report_handler))
