"""
Q344 CLI commands — /schema-validate, /config-guard, /session-validate, /cache-coherence

Registered via register_q344_commands(registry).
"""
from __future__ import annotations

import json


def register_q344_commands(registry) -> None:
    """Register Q344 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /schema-validate
    # ------------------------------------------------------------------
    async def schema_validate_handler(args: str) -> str:
        """
        Usage: /schema-validate <json>
               /schema-validate demo
               /schema-validate --help

        Validates a schema upgrade JSON with keys "old" and "new",
        each containing a "tables" mapping.
        """
        from lidco.stability.schema_migration import SchemaMigrationValidator

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /schema-validate <json>\n"
                "  Provide JSON with 'old' and 'new' schema objects.\n"
                "  Each schema has a 'tables' key mapping table names to column lists.\n"
                "  Column: {\"name\": str, \"type\": str, \"nullable\": bool}\n\n"
                "  Example: /schema-validate demo\n"
                "    Runs a built-in demo upgrade scenario."
            )

        validator = SchemaMigrationValidator()

        if stripped == "demo":
            old = {
                "tables": {
                    "users": [
                        {"name": "id", "type": "INT", "nullable": False},
                        {"name": "email", "type": "VARCHAR", "nullable": False},
                    ]
                }
            }
            new = {
                "tables": {
                    "users": [
                        {"name": "id", "type": "INT", "nullable": False},
                        {"name": "email", "type": "TEXT", "nullable": False},
                        {"name": "created_at", "type": "TIMESTAMP", "nullable": True},
                    ]
                }
            }
        else:
            try:
                payload = json.loads(stripped)
                old = payload.get("old", {})
                new = payload.get("new", {})
            except json.JSONDecodeError as exc:
                return f"Error: invalid JSON — {exc}"

        result = validator.validate_upgrade(old, new)
        compat_label = "COMPATIBLE" if result["compatible"] else "BREAKING"

        lines = [f"Schema Upgrade Validation [{compat_label}]"]
        if result["breaking_changes"]:
            lines.append(f"\nBreaking changes ({len(result['breaking_changes'])}):")
            for item in result["breaking_changes"]:
                lines.append(f"  - {item}")
        if result["additions"]:
            lines.append(f"\nAdditions ({len(result['additions'])}):")
            for item in result["additions"]:
                lines.append(f"  + {item}")
        if result["warnings"]:
            lines.append(f"\nWarnings ({len(result['warnings'])}):")
            for item in result["warnings"]:
                lines.append(f"  ! {item}")

        rollback = validator.generate_rollback(old, new)
        if rollback:
            lines.append(f"\nRollback SQL ({len(rollback)} statement(s)):")
            for stmt in rollback:
                lines.append(f"  {stmt}")

        return "\n".join(lines)

    registry.register_async(
        "schema-validate",
        "Validate database schema migration compatibility",
        schema_validate_handler,
    )

    # ------------------------------------------------------------------
    # /config-guard
    # ------------------------------------------------------------------
    async def config_guard_handler(args: str) -> str:
        """
        Usage: /config-guard detect <json|yaml> <content>
               /config-guard demo
               /config-guard --help
        """
        from lidco.stability.config_guard import ConfigCorruptionGuard

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /config-guard <subcommand>\n"
                "  detect <format> <content>  check if content is valid JSON/YAML\n"
                "  demo                        run a corruption detection demo\n\n"
                "  Formats: json, yaml"
            )

        guard = ConfigCorruptionGuard()
        parts = stripped.split(None, 2)
        subcmd = parts[0].lower()

        if subcmd == "demo":
            valid_json = '{"key": "value", "number": 42}'
            broken_json = '{"key": "value", "number": }'
            r1 = guard.detect_corruption(valid_json, "json")
            r2 = guard.detect_corruption(broken_json, "json")
            lines = [
                "Config Corruption Guard Demo",
                f"\nValid JSON: valid={r1['valid']}",
                f"Broken JSON: valid={r2['valid']}, error={r2['error']}, recoverable={r2['recoverable']}",
            ]
            return "\n".join(lines)

        if subcmd == "detect":
            if len(parts) < 3:
                return "Error: Usage: /config-guard detect <format> <content>"
            fmt = parts[1].lower()
            content = parts[2]
            result = guard.detect_corruption(content, fmt)
            lines = [
                "Config Corruption Detection",
                f"  format: {result['format']}",
                f"  valid: {result['valid']}",
            ]
            if result["error"]:
                lines.append(f"  error: {result['error']}")
                lines.append(f"  recoverable: {result['recoverable']}")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use detect/demo or --help."

    registry.register_async(
        "config-guard",
        "Detect config file corruption and perform safe atomic writes",
        config_guard_handler,
    )

    # ------------------------------------------------------------------
    # /session-validate
    # ------------------------------------------------------------------
    async def session_validate_handler(args: str) -> str:
        """
        Usage: /session-validate <json>
               /session-validate demo
               /session-validate --help
        """
        from lidco.stability.session_state import SessionStateValidator

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /session-validate <json>\n"
                "  Provide a session state JSON object to validate.\n"
                "  Required fields: session_id (str), created_at (number), status (str)\n\n"
                "  Example: /session-validate demo\n"
                "    Runs a built-in validation demo."
            )

        validator = SessionStateValidator()

        if stripped == "demo":
            import time as _time
            good_state = {
                "session_id": "sess-abc123",
                "created_at": _time.time() - 3600,
                "status": "active",
                "last_active_at": _time.time() - 60,
            }
            bad_state = {
                "session_id": "",
                "created_at": -1,
                "status": "unknown_state",
            }
            r1 = validator.validate_consistency(good_state)
            r2 = validator.validate_consistency(bad_state)
            lines = [
                "Session State Validation Demo",
                f"\nGood state: valid={r1['valid']}, warnings={len(r1['warnings'])}",
                f"Bad state: valid={r2['valid']}, errors={len(r2['errors'])}, warnings={len(r2['warnings'])}",
            ]
            for e in r2["errors"]:
                lines.append(f"  Error: {e}")
            for w in r2["warnings"]:
                lines.append(f"  Warning: {w}")
            return "\n".join(lines)

        try:
            state = json.loads(stripped)
        except json.JSONDecodeError as exc:
            return f"Error: invalid JSON — {exc}"

        result = validator.validate_consistency(state)
        integrity = validator.check_integrity(state)

        lines = [
            f"Session State Validation: {'VALID' if result['valid'] else 'INVALID'}",
            f"  Integrity OK: {integrity['integrity_ok']}",
            f"  Checksum: {integrity['checksum'][:16]}...",
        ]
        if result["errors"]:
            lines.append(f"  Errors ({len(result['errors'])}):")
            for e in result["errors"]:
                lines.append(f"    - {e}")
        if result["warnings"]:
            lines.append(f"  Warnings ({len(result['warnings'])}):")
            for w in result["warnings"]:
                lines.append(f"    ! {w}")

        return "\n".join(lines)

    registry.register_async(
        "session-validate",
        "Validate session state consistency and integrity",
        session_validate_handler,
    )

    # ------------------------------------------------------------------
    # /cache-coherence
    # ------------------------------------------------------------------
    async def cache_coherence_handler(args: str) -> str:
        """
        Usage: /cache-coherence <json>
               /cache-coherence demo
               /cache-coherence --help

        JSON payload: {"cache": {...}, "source": {...}}
        """
        from lidco.stability.cache_coherence import CacheCoherenceChecker

        stripped = args.strip()
        if not stripped or stripped in ("--help", "-h"):
            return (
                "Usage: /cache-coherence <json>\n"
                "  Provide JSON with 'cache' and 'source' dicts to compare.\n\n"
                "  Example: /cache-coherence demo\n"
                "    Runs a built-in coherence check demo."
            )

        checker = CacheCoherenceChecker()

        if stripped == "demo":
            cache = {"a": 1, "b": 99, "c": 3}
            source = {"a": 1, "b": 2, "d": 4}
            result = checker.check_consistency(cache, source)
            lines = [
                "Cache Coherence Demo",
                f"  consistent: {result['consistent']}",
                f"  stale_keys: {result['stale_keys']}",
                f"  missing_keys: {result['missing_keys']}",
                f"  extra_keys: {result['extra_keys']}",
            ]
            return "\n".join(lines)

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            return f"Error: invalid JSON — {exc}"

        cache = payload.get("cache", {})
        source = payload.get("source", {})
        result = checker.check_consistency(cache, source)

        label = "CONSISTENT" if result["consistent"] else "INCONSISTENT"
        lines = [
            f"Cache Coherence Check [{label}]",
            f"  stale_keys ({len(result['stale_keys'])}): {result['stale_keys']}",
            f"  missing_keys ({len(result['missing_keys'])}): {result['missing_keys']}",
            f"  extra_keys ({len(result['extra_keys'])}): {result['extra_keys']}",
        ]
        return "\n".join(lines)

    registry.register_async(
        "cache-coherence",
        "Check cache consistency against source data",
        cache_coherence_handler,
    )
