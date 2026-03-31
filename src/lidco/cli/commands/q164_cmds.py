"""Q164 CLI commands: /sandbox."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q164 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def sandbox_handler(args: str) -> str:
        from lidco.sandbox.policy import SandboxPolicy
        from lidco.sandbox.fs_jail import FsJail
        from lidco.sandbox.net_restrictor import NetworkRestrictor
        from lidco.sandbox.runner import SandboxRunner

        # Lazy init
        if "policy" not in _state:
            _state["policy"] = SandboxPolicy.with_defaults()
        if "enabled" not in _state:
            _state["enabled"] = False

        policy: SandboxPolicy = _state["policy"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "on":
            _state["enabled"] = True
            # Initialize components
            _state["fs_jail"] = FsJail(policy)
            _state["net_restrictor"] = NetworkRestrictor(policy)
            _state["runner"] = SandboxRunner(
                policy,
                _state["fs_jail"],  # type: ignore[arg-type]
                _state["net_restrictor"],  # type: ignore[arg-type]
            )
            return "Sandbox mode enabled."

        if sub == "off":
            _state["enabled"] = False
            return "Sandbox mode disabled."

        if sub == "status":
            enabled = _state.get("enabled", False)
            status = "enabled" if enabled else "disabled"
            return f"Sandbox: {status}"

        if sub == "policy":
            info = {
                "allowed_paths": policy.allowed_paths,
                "denied_paths": policy.denied_paths,
                "allowed_domains": policy.allowed_domains,
                "deny_all_network": policy.deny_all_network,
                "max_memory_mb": policy.max_memory_mb,
                "max_time_seconds": policy.max_time_seconds,
                "allow_subprocesses": policy.allow_subprocesses,
            }
            return json.dumps(info, indent=2)

        if sub == "violations":
            runner: SandboxRunner | None = _state.get("runner")  # type: ignore[assignment]
            if runner is None:
                return "No sandbox runner active. Use /sandbox on first."
            violations = runner.all_violations()
            if not violations:
                return "No violations recorded."
            lines = [f"Violations ({len(violations)}):"]
            for v in violations:
                lines.append(f"  [{v.violation_type}] {v.detail} (blocked={v.blocked})")
            return "\n".join(lines)

        return (
            "Usage: /sandbox <sub>\n"
            "  on        -- enable sandbox mode\n"
            "  off       -- disable sandbox mode\n"
            "  status    -- show sandbox status\n"
            "  policy    -- show current policy\n"
            "  violations -- show violation log"
        )

    registry.register(SlashCommand("sandbox", "OS-level sandboxing & secure execution (Q164)", sandbox_handler))
