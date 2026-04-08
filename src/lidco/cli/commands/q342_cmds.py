"""
Q342 CLI commands — /exception-audit, /error-messages, /degradation-check, /recovery-paths

Registered via register_q342_commands(registry).
"""
from __future__ import annotations

import json


def register_q342_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q342 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /exception-audit — Runs ExceptionChainAnalyzer on source code
    # ------------------------------------------------------------------
    async def exception_audit_handler(args: str) -> str:
        """
        Usage: /exception-audit <source-code>
               /exception-audit --help
        """
        from lidco.stability.exception_chain import ExceptionChainAnalyzer

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /exception-audit <source-code>\n"
                "\n"
                "Analyzes Python source code for exception handling patterns:\n"
                "  - Propagation paths (caught/raised/reraised)\n"
                "  - Unhandled raise statements\n"
                "  - Catch-all patterns (bare except, except Exception)\n"
                "  - Missing raise...from chaining"
            )

        source = args
        analyzer = ExceptionChainAnalyzer()

        propagation = analyzer.trace_propagation(source)
        unhandled = analyzer.find_unhandled(source)
        catch_all = analyzer.audit_catch_all(source)
        chaining = analyzer.check_chain_completeness(source)

        lines: list[str] = [
            "Exception Chain Audit Report",
            "=" * 50,
        ]

        lines.append(f"\nPropagation paths: {len(propagation)}")
        for p in propagation:
            lines.append(
                f"  Line {p['line']}: {p['exception_type']} — {p['action']}"
                + (f" (handler at line {p['handler_line']})" if p.get("handler_line") else "")
            )

        if unhandled:
            lines.append(f"\nUnhandled raises: {len(unhandled)}")
            for u in unhandled:
                lines.append(
                    f"  Line {u['line']}: {u['exception_type']} in {u['context']}"
                )
        else:
            lines.append("\nNo unhandled raise statements detected.")

        if catch_all:
            lines.append(f"\nCatch-all patterns: {len(catch_all)}")
            for c in catch_all:
                lines.append(
                    f"  Line {c['line']}: [{c['severity']}] {c['pattern']}\n"
                    f"    → {c['suggestion']}"
                )
        else:
            lines.append("No catch-all patterns detected.")

        missing_chain = [c for c in chaining if not c["has_from"]]
        if missing_chain:
            lines.append(f"\nMissing raise...from: {len(missing_chain)}")
            for mc in missing_chain:
                lines.append(
                    f"  Line {mc['line']}: {mc['suggestion']}"
                )
        else:
            lines.append("All chained raises use 'from' correctly.")

        total_issues = len(unhandled) + len(catch_all) + len(missing_chain)
        lines.append(f"\nTotal issues: {total_issues}")
        return "\n".join(lines)

    registry.register_async(
        "exception-audit",
        "Audit exception propagation, catch-all patterns, and raise...from chaining",
        exception_audit_handler,
    )

    # ------------------------------------------------------------------
    # /error-messages — Runs ErrorMessageStandardizer on source code
    # ------------------------------------------------------------------
    async def error_messages_handler(args: str) -> str:
        """
        Usage: /error-messages <source-code>
               /error-messages --help
        """
        from lidco.stability.error_messages import ErrorMessageStandardizer

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /error-messages <source-code>\n"
                "\n"
                "Audits error/exception messages for:\n"
                "  - Consistency (capitalization, punctuation)\n"
                "  - i18n readiness\n"
                "  - Suggested error codes"
            )

        source = args
        std = ErrorMessageStandardizer()

        audit = std.audit_messages(source)
        i18n = std.check_i18n_readiness(source)
        codes = std.assign_error_codes(source)

        lines: list[str] = [
            "Error Message Standardization Report",
            "=" * 50,
        ]

        if audit:
            lines.append(f"\nMessage audit ({len(audit)} messages found):")
            for a in audit:
                issue_str = ", ".join(a["issues"]) if a["issues"] else "OK"
                lines.append(
                    f"  Line {a['line']}: \"{a['message'][:60]}\" — {issue_str}"
                )
        else:
            lines.append("\nNo error messages found.")

        not_ready = [r for r in i18n if not r["i18n_ready"] and r.get("suggestion")]
        if not_ready:
            lines.append(f"\ni18n issues ({len(not_ready)}):")
            for r in not_ready:
                lines.append(
                    f"  Line {r['line']}: {r['suggestion']}"
                )
        else:
            lines.append("All messages are i18n-ready.")

        if codes:
            lines.append(f"\nSuggested error codes ({len(codes)}):")
            for c in codes:
                lines.append(
                    f"  {c['suggested_code']} — {c['exception_type']} at line {c['line']}"
                    + (f": \"{c['message'][:40]}\"" if c["message"] else "")
                )

        return "\n".join(lines)

    registry.register_async(
        "error-messages",
        "Audit and standardize error messages, check i18n readiness, suggest error codes",
        error_messages_handler,
    )

    # ------------------------------------------------------------------
    # /degradation-check — Runs GracefulDegradationChecker on source code
    # ------------------------------------------------------------------
    async def degradation_check_handler(args: str) -> str:
        """
        Usage: /degradation-check <source-code>
               /degradation-check --help
        """
        from lidco.stability.degradation import GracefulDegradationChecker

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /degradation-check <source-code>\n"
                "\n"
                "Checks Python source code for graceful degradation:\n"
                "  - Fallbacks for optional features\n"
                "  - Optional dependency import guards\n"
                "  - Network calls without timeout/retry\n"
                "  - Timeout value correctness"
            )

        source = args
        checker = GracefulDegradationChecker()

        fallbacks = checker.check_fallbacks(source)
        opt_deps = checker.check_optional_deps(source)
        network = checker.check_network_resilience(source)
        timeouts = checker.check_timeout_behavior(source)

        lines: list[str] = [
            "Graceful Degradation Report",
            "=" * 50,
        ]

        missing_fallbacks = [f for f in fallbacks if not f["has_fallback"]]
        if missing_fallbacks:
            lines.append(f"\nMissing fallbacks ({len(missing_fallbacks)}):")
            for f in missing_fallbacks:
                lines.append(
                    f"  Line {f['line']}: {f['suggestion']}"
                )
        else:
            lines.append(f"\nFallback checks: {len(fallbacks)} OK")

        bad_deps = [d for d in opt_deps if not d["fallback_correct"]]
        if bad_deps:
            lines.append(f"\nOptional dependency issues ({len(bad_deps)}):")
            for d in bad_deps:
                status = "no fallback" if not d["has_fallback"] else "fallback incorrect"
                lines.append(
                    f"  Line {d['line']}: '{d['module']}' — {status}"
                )
        else:
            lines.append(f"Optional dep checks: {len(opt_deps)} OK")

        risky_network = [n for n in network if not n["has_timeout"] or not n["has_retry"]]
        if risky_network:
            lines.append(f"\nNetwork resilience issues ({len(risky_network)}):")
            for n in risky_network:
                lines.append(
                    f"  Line {n['line']}: '{n['call']}' — {n['suggestion']}"
                )
        else:
            lines.append(f"Network resilience checks: {len(network)} OK")

        timeout_issues = [t for t in timeouts if t["suggestion"]]
        if timeout_issues:
            lines.append(f"\nTimeout issues ({len(timeout_issues)}):")
            for t in timeout_issues:
                lines.append(
                    f"  Line {t['line']}: '{t['operation']}' timeout={t['timeout_value']} — {t['suggestion']}"
                )
        else:
            lines.append(f"Timeout checks: {len(timeouts)} OK")

        total = len(missing_fallbacks) + len(bad_deps) + len(risky_network) + len(timeout_issues)
        lines.append(f"\nTotal issues: {total}")
        return "\n".join(lines)

    registry.register_async(
        "degradation-check",
        "Check graceful degradation: fallbacks, optional deps, network resilience, timeouts",
        degradation_check_handler,
    )

    # ------------------------------------------------------------------
    # /recovery-paths — Runs RecoveryPathValidator on source code
    # ------------------------------------------------------------------
    async def recovery_paths_handler(args: str) -> str:
        """
        Usage: /recovery-paths <source-code>
               /recovery-paths --help
        """
        from lidco.stability.recovery_paths import RecoveryPathValidator

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /recovery-paths <source-code>\n"
                "\n"
                "Validates error recovery paths:\n"
                "  - try/except recovery strategies\n"
                "  - Retry logic (max retries, backoff)\n"
                "  - State restoration on failure\n"
                "  - Data integrity (transactions, atomic writes)"
            )

        source = args
        validator = RecoveryPathValidator()

        recovery = validator.validate_recovery(source)
        retry = validator.check_retry_logic(source)
        state = validator.check_state_restoration(source)
        integrity = validator.check_data_integrity(source)

        lines: list[str] = [
            "Recovery Path Validation Report",
            "=" * 50,
        ]

        invalid_recovery = [r for r in recovery if not r["valid"]]
        if invalid_recovery:
            lines.append(f"\nInvalid recovery paths ({len(invalid_recovery)}):")
            for r in invalid_recovery:
                issues_str = "; ".join(r["issues"])
                lines.append(
                    f"  Line {r['line']}: [{r['recovery_type']}] — {issues_str}"
                )
        else:
            lines.append(f"\nRecovery validation: {len(recovery)} blocks checked, all valid")

        retry_issues = [r for r in retry if not r["has_max_retries"] or not r["has_backoff"]]
        if retry_issues:
            lines.append(f"\nRetry logic issues ({len(retry_issues)}):")
            for r in retry_issues:
                lines.append(
                    f"  Line {r['line']}: {r['suggestion']}"
                )
        else:
            lines.append(f"Retry logic: {len(retry)} loops checked, all OK")

        state_issues = [s for s in state if not s["has_rollback"]]
        if state_issues:
            lines.append(f"\nState restoration issues ({len(state_issues)}):")
            for s in state_issues:
                lines.append(
                    f"  Line {s['line']}: {s['suggestion']}"
                )
        else:
            lines.append(f"State restoration: {len(state)} mutations checked, all have rollback")

        integrity_issues = [i for i in integrity if not i["has_integrity_check"]]
        if integrity_issues:
            lines.append(f"\nData integrity issues ({len(integrity_issues)}):")
            for i in integrity_issues:
                lines.append(
                    f"  Line {i['line']}: '{i['operation']}' — {i['suggestion']}"
                )
        else:
            lines.append(f"Data integrity: {len(integrity)} operations checked, all OK")

        total = len(invalid_recovery) + len(retry_issues) + len(state_issues) + len(integrity_issues)
        lines.append(f"\nTotal issues: {total}")
        return "\n".join(lines)

    registry.register_async(
        "recovery-paths",
        "Validate error recovery paths, retry logic, state restoration, and data integrity",
        recovery_paths_handler,
    )
