"""Q223 CLI commands: /escalate, /session-perms, /perm-audit, /trust-level."""
from __future__ import annotations


def register(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q223 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /escalate <scope> <resource> <reason>
    # ------------------------------------------------------------------

    async def escalate_handler(args: str) -> str:
        from lidco.permissions.escalation import EscalationManager

        parts = args.strip().split(maxsplit=2)
        if len(parts) < 3:
            return "Usage: /escalate <scope> <resource> <reason>"
        scope, resource, reason = parts[0], parts[1], parts[2]
        mgr = EscalationManager()
        req = mgr.request(scope, resource, reason)
        grant = mgr.approve(req.id)
        return (
            f"Escalation granted: {scope}/{resource} "
            f"(expires in {int(grant.expires_at - grant.granted_at)}s)"
        )

    # ------------------------------------------------------------------
    # /session-perms [set scope resource action | list | reset]
    # ------------------------------------------------------------------

    async def session_perms_handler(args: str) -> str:
        from lidco.permissions.session_perms import SessionPermissions

        perms = SessionPermissions()
        parts = args.strip().split()
        if not parts or parts[0] == "list":
            items = perms.decisions()
            if not items:
                return "No session permissions set."
            lines = [
                f"  {d.scope}/{d.resource}: {d.action}"
                + (" [sticky]" if d.sticky else "")
                for d in items
            ]
            return "Session permissions:\n" + "\n".join(lines)
        if parts[0] == "set":
            if len(parts) < 4:
                return "Usage: /session-perms set <scope> <resource> <action>"
            scope, resource, action = parts[1], parts[2], parts[3]
            sticky = len(parts) > 4 and parts[4] == "sticky"
            d = perms.set(scope, resource, action, sticky=sticky)
            return f"Permission set: {d.scope}/{d.resource} -> {d.action}"
        if parts[0] == "reset":
            count = perms.reset_all()
            return f"Reset {count} session permissions."
        return "Usage: /session-perms [set scope resource action | list | reset]"

    # ------------------------------------------------------------------
    # /perm-audit [query actor=X | summary | clear]
    # ------------------------------------------------------------------

    async def perm_audit_handler(args: str) -> str:
        from lidco.permissions.audit import PermissionAudit

        audit = PermissionAudit()
        parts = args.strip().split()
        if not parts or parts[0] == "summary":
            s = audit.summary()
            return (
                f"PermissionAudit: {s['total']} entries, "
                f"by_result={s['by_result']}, by_actor={s['by_actor']}"
            )
        if parts[0] == "clear":
            count = audit.clear()
            return f"Cleared {count} audit entries."
        if parts[0] == "query":
            actor = None
            for p in parts[1:]:
                if p.startswith("actor="):
                    actor = p.split("=", 1)[1]
            entries = audit.query(actor=actor)
            if not entries:
                return "No audit entries found."
            lines = [
                f"  [{e.result}] {e.actor}: {e.action} on {e.scope}/{e.resource}"
                for e in entries
            ]
            return "Audit entries:\n" + "\n".join(lines)
        return "Usage: /perm-audit [query actor=X | summary | clear]"

    # ------------------------------------------------------------------
    # /trust-level [entity [level] | list | summary]
    # ------------------------------------------------------------------

    async def trust_level_handler(args: str) -> str:
        from lidco.permissions.trust_levels import TrustManager

        mgr = TrustManager()
        parts = args.strip().split()
        if not parts or parts[0] == "list":
            entries = mgr.all_entries()
            if not entries:
                return "No trust entries."
            lines = [f"  {e.entity}: level={e.level}" for e in entries]
            return "Trust entries:\n" + "\n".join(lines)
        if parts[0] == "summary":
            s = mgr.summary()
            return f"TrustManager summary: {s}"
        entity = parts[0]
        if len(parts) >= 2:
            try:
                level = int(parts[1])
            except ValueError:
                return "Level must be an integer."
            mgr.set_level(entity, level)
            return f"Trust level for {entity} set to {level}."
        level = mgr.get_level(entity)
        return f"Trust level for {entity}: {level}"

    registry.register(SlashCommand("escalate", "Request elevated permissions", escalate_handler))
    registry.register(SlashCommand("session-perms", "Manage session permissions", session_perms_handler))
    registry.register(SlashCommand("perm-audit", "Permission audit log", perm_audit_handler))
    registry.register(SlashCommand("trust-level", "Manage trust levels", trust_level_handler))
