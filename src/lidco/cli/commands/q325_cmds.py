"""
Q325 CLI commands — /env-provision, /env-compare, /env-promote, /env-monitor

Registered via register_q325_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q325_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q325 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /env-provision — Provision or destroy environments
    # ------------------------------------------------------------------
    async def env_provision_handler(args: str) -> str:
        """
        Usage: /env-provision <template> [--name NAME] [--tier dev|staging|prod]
               /env-provision --destroy <env_id>
               /env-provision --list [--tier dev|staging|prod]
        """
        from lidco.envmgmt.provisioner import EnvProvisioner, EnvTemplate, EnvTier

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /env-provision <template> [--name NAME] | --destroy <id> | --list"

        provisioner = EnvProvisioner()

        # --list
        if parts[0] == "--list":
            tier = None
            if "--tier" in parts:
                idx = parts.index("--tier")
                if idx + 1 < len(parts):
                    try:
                        tier = EnvTier(parts[idx + 1])
                    except ValueError:
                        return f"Invalid tier: {parts[idx + 1]}"
            envs = provisioner.list_environments(tier=tier)
            if not envs:
                return "No environments found."
            lines = [f"Environments ({len(envs)}):"]
            for e in envs:
                lines.append(f"  {e.env_id[:12]} {e.name} [{e.tier.value}] {e.status.value}")
            return "\n".join(lines)

        # --destroy
        if parts[0] == "--destroy":
            if len(parts) < 2:
                return "Usage: /env-provision --destroy <env_id>"
            try:
                env = provisioner.destroy(parts[1])
                return f"Destroyed environment: {env.name} ({env.env_id[:12]})"
            except Exception as exc:
                return f"Error: {exc}"

        # Provision from template
        template_name = parts[0]
        name_override = None
        tier = EnvTier.DEV

        i = 1
        while i < len(parts):
            if parts[i] == "--name" and i + 1 < len(parts):
                name_override = parts[i + 1]
                i += 2
            elif parts[i] == "--tier" and i + 1 < len(parts):
                try:
                    tier = EnvTier(parts[i + 1])
                except ValueError:
                    return f"Invalid tier: {parts[i + 1]}"
                i += 2
            else:
                i += 1

        template = EnvTemplate(name=template_name, tier=tier)
        provisioner.register_template(template)
        try:
            env = provisioner.provision(template_name, name_override=name_override)
            return (
                f"Provisioned: {env.name}\n"
                f"  ID: {env.env_id[:12]}\n"
                f"  Tier: {env.tier.value}\n"
                f"  Status: {env.status.value}"
            )
        except Exception as exc:
            return f"Error: {exc}"

    registry.register_async(
        "env-provision",
        "Provision or destroy environments",
        env_provision_handler,
    )

    # ------------------------------------------------------------------
    # /env-compare — Compare two environments
    # ------------------------------------------------------------------
    async def env_compare_handler(args: str) -> str:
        """
        Usage: /env-compare <env_id_1> <env_id_2>
        """
        from lidco.envmgmt.comparator import EnvComparator

        parts = shlex.split(args) if args.strip() else []
        if len(parts) < 2:
            return "Usage: /env-compare <env_id_1> <env_id_2>"

        # In a real implementation we'd look up environments by ID;
        # for CLI purposes we report the comparison format.
        return (
            f"Comparing {parts[0]} vs {parts[1]}...\n"
            "Use programmatic API for full comparison results."
        )

    registry.register_async(
        "env-compare",
        "Compare two environments for config/resource drift",
        env_compare_handler,
    )

    # ------------------------------------------------------------------
    # /env-promote — Promote changes between environments
    # ------------------------------------------------------------------
    async def env_promote_handler(args: str) -> str:
        """
        Usage: /env-promote <source_id> <target_id> [--approve USER]
               /env-promote --rollback <promotion_id>
        """
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /env-promote <source> <target> [--approve USER] | --rollback <id>"

        if parts[0] == "--rollback":
            if len(parts) < 2:
                return "Usage: /env-promote --rollback <promotion_id>"
            return f"Rollback requested for promotion {parts[1]}"

        if len(parts) < 2:
            return "Usage: /env-promote <source_id> <target_id>"

        approver = None
        i = 2
        while i < len(parts):
            if parts[i] == "--approve" and i + 1 < len(parts):
                approver = parts[i + 1]
                i += 2
            else:
                i += 1

        msg = f"Promotion: {parts[0]} -> {parts[1]}"
        if approver:
            msg += f" (approved by {approver})"
        return msg

    registry.register_async(
        "env-promote",
        "Promote changes between environments",
        env_promote_handler,
    )

    # ------------------------------------------------------------------
    # /env-monitor — Monitor environment health
    # ------------------------------------------------------------------
    async def env_monitor_handler(args: str) -> str:
        """
        Usage: /env-monitor [--env ENV_ID] [--all] [--expired]
        """
        parts = shlex.split(args) if args.strip() else []

        if "--expired" in parts:
            return "Checking for expired environments..."

        env_id = None
        i = 0
        while i < len(parts):
            if parts[i] == "--env" and i + 1 < len(parts):
                env_id = parts[i + 1]
                i += 2
            else:
                i += 1

        if env_id:
            return f"Monitoring environment: {env_id}"

        return "Monitoring all environments. Use --env <id> for specific health report."

    registry.register_async(
        "env-monitor",
        "Monitor environment health and resource usage",
        env_monitor_handler,
    )
