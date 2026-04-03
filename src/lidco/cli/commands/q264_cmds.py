"""Q264 CLI commands: /tenant, /tenant-quota, /tenant-stats, /tenant-config."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def _get_manager():
    from lidco.tenant.manager import TenantManager

    if "manager" not in _state:
        _state["manager"] = TenantManager()
    return _state["manager"]


def _get_enforcer():
    from lidco.tenant.quota import QuotaEnforcer

    if "enforcer" not in _state:
        _state["enforcer"] = QuotaEnforcer()
    return _state["enforcer"]


def _get_analytics():
    from lidco.tenant.analytics import TenantAnalytics

    if "analytics" not in _state:
        _state["analytics"] = TenantAnalytics()
    return _state["analytics"]


def register(registry) -> None:
    """Register Q264 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /tenant [create <name> | list | get <id> | delete <id> | config <id> <json>]
    # ------------------------------------------------------------------
    async def tenant_handler(args: str) -> str:
        from lidco.tenant.manager import TenantManager

        manager: TenantManager = _get_manager()  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /tenant [create <name> | list | get <id> | delete <id> | config <id> <json>]"

        sub = parts[0]

        if sub == "create":
            if len(parts) < 2:
                return "Usage: /tenant create <name>"
            name = parts[1]
            config = json.loads(parts[2]) if len(parts) > 2 else None
            t = manager.create(name, config=config)
            return f"Created tenant '{t.name}' ({t.id})"

        if sub == "list":
            tenants = manager.all_tenants(include_inactive="--all" in args)
            if not tenants:
                return "No tenants."
            lines = [f"  {t.id}  {t.name}  active={t.active}" for t in tenants]
            return f"{len(tenants)} tenant(s):\n" + "\n".join(lines)

        if sub == "get":
            if len(parts) < 2:
                return "Usage: /tenant get <id>"
            t = manager.get(parts[1])
            if t is None:
                return f"Tenant '{parts[1]}' not found."
            return f"Tenant {t.id}: name={t.name}, active={t.active}, config={json.dumps(t.config)}"

        if sub == "delete":
            if len(parts) < 2:
                return "Usage: /tenant delete <id>"
            ok = manager.delete(parts[1])
            return f"Deleted tenant '{parts[1]}'." if ok else f"Tenant '{parts[1]}' not found."

        if sub == "config":
            if len(parts) < 3:
                return "Usage: /tenant config <id> <json>"
            tid = parts[1]
            cfg = json.loads(parts[2])
            t = manager.update_config(tid, cfg)
            if t is None:
                return f"Tenant '{tid}' not found."
            return f"Updated config for '{tid}': {json.dumps(t.config)}"

        return "Unknown sub-command. Usage: /tenant [create|list|get|delete|config]"

    registry.register(SlashCommand("tenant", "Manage tenants", tenant_handler))

    # ------------------------------------------------------------------
    # /tenant-quota [set <tenant> <resource> <soft> <hard> | check <tenant> <resource> <amount> | usage]
    # ------------------------------------------------------------------
    async def tenant_quota_handler(args: str) -> str:
        from lidco.tenant.quota import QuotaEnforcer

        enforcer: QuotaEnforcer = _get_enforcer()  # type: ignore[assignment]
        parts = args.strip().split()
        if not parts:
            return "Usage: /tenant-quota [set <tenant> <resource> <soft> <hard> | check <tenant> <resource> <amount> | usage]"

        sub = parts[0]

        if sub == "set":
            if len(parts) < 5:
                return "Usage: /tenant-quota set <tenant> <resource> <soft> <hard>"
            q = enforcer.set_quota(parts[1], parts[2], float(parts[3]), float(parts[4]))
            return f"Quota set: {q.tenant_id}/{q.resource} soft={q.soft_limit} hard={q.hard_limit}"

        if sub == "check":
            if len(parts) < 4:
                return "Usage: /tenant-quota check <tenant> <resource> <amount>"
            r = enforcer.check(parts[1], parts[2], float(parts[3]))
            status = "allowed" if r.allowed else "denied"
            return f"Check {status}: usage={r.usage}/{r.limit}, overage={r.overage}"

        if sub == "usage":
            quotas = enforcer.all_quotas()
            if not quotas:
                return "No quotas configured."
            lines = [
                f"  {q.tenant_id}/{q.resource}: {q.current_usage}/{q.hard_limit} (soft={q.soft_limit})"
                for q in quotas
            ]
            return f"{len(quotas)} quota(s):\n" + "\n".join(lines)

        return "Unknown sub-command. Usage: /tenant-quota [set|check|usage]"

    registry.register(SlashCommand("tenant-quota", "Manage tenant quotas", tenant_quota_handler))

    # ------------------------------------------------------------------
    # /tenant-stats [total <tenant> | compare <t1,t2> <resource> | top <resource>]
    # ------------------------------------------------------------------
    async def tenant_stats_handler(args: str) -> str:
        from lidco.tenant.analytics import TenantAnalytics

        analytics: TenantAnalytics = _get_analytics()  # type: ignore[assignment]
        parts = args.strip().split()
        if not parts:
            return json.dumps(analytics.summary())

        sub = parts[0]

        if sub == "total":
            if len(parts) < 2:
                return "Usage: /tenant-stats total <tenant>"
            totals = analytics.total(parts[1])
            if not totals:
                return f"No stats for '{parts[1]}'."
            lines = [f"  {k}: {v}" for k, v in totals.items()]
            return f"Totals for {parts[1]}:\n" + "\n".join(lines)

        if sub == "compare":
            if len(parts) < 3:
                return "Usage: /tenant-stats compare <t1,t2,...> <resource>"
            tids = parts[1].split(",")
            resource = parts[2]
            result = analytics.compare(tids, resource)
            lines = [f"  {k}: {v}" for k, v in result.items()]
            return f"Comparison ({resource}):\n" + "\n".join(lines)

        if sub == "top":
            if len(parts) < 2:
                return "Usage: /tenant-stats top <resource>"
            top = analytics.top_consumers(parts[1])
            if not top:
                return f"No data for '{parts[1]}'."
            lines = [f"  {tid}: {val}" for tid, val in top]
            return "Top consumers:\n" + "\n".join(lines)

        return "Unknown sub-command. Usage: /tenant-stats [total|compare|top]"

    registry.register(SlashCommand("tenant-stats", "Tenant usage statistics", tenant_stats_handler))

    # ------------------------------------------------------------------
    # /tenant-config <tenant_id> — show resolved config
    # ------------------------------------------------------------------
    async def tenant_config_handler(args: str) -> str:
        from lidco.tenant.manager import TenantManager

        manager: TenantManager = _get_manager()  # type: ignore[assignment]
        tid = args.strip()
        if not tid:
            return "Usage: /tenant-config <tenant_id>"
        resolved = manager.resolve_config(tid)
        if not resolved:
            return f"No config resolved for '{tid}'."
        return f"Resolved config for {tid}: {json.dumps(resolved)}"

    registry.register(SlashCommand("tenant-config", "Show resolved tenant config", tenant_config_handler))
