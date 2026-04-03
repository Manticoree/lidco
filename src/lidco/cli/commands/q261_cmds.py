"""Q261 CLI commands: /audit-events, /audit-query, /audit-anomaly, /audit-dashboard."""
from __future__ import annotations

_state: dict[str, object] = {}


def _get_store():
    from lidco.audit.event_store import AuditEventStore

    if "store" not in _state:
        _state["store"] = AuditEventStore()
    return _state["store"]


def _get_detector():
    from lidco.audit.anomaly import AnomalyDetector

    if "detector" not in _state:
        _state["detector"] = AnomalyDetector(_get_store())
    return _state["detector"]


def register(registry) -> None:
    """Register Q261 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /audit-events
    # ------------------------------------------------------------------

    async def audit_events_handler(args: str) -> str:
        from lidco.audit.event_store import AuditEventStore

        store: AuditEventStore = _get_store()  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            events = store.events()
            if not events:
                return "No audit events."
            lines = [f"Audit events ({store.count()}):"]
            for e in events[-20:]:
                lines.append(f"  {e.id[:8]} [{e.event_type}] {e.actor} {e.action} {e.resource}")
            return "\n".join(lines)

        if sub == "get":
            if not rest:
                return "Usage: /audit-events get <id>"
            event = store.get(rest)
            if event is None:
                return f"Event {rest} not found."
            import json
            from dataclasses import asdict
            return json.dumps(asdict(event), indent=2)

        if sub == "verify":
            valid, invalid = store.verify_all()
            return f"Verified: {valid} valid, {invalid} invalid"

        if sub == "export":
            fmt = rest if rest in ("json", "csv") else "json"
            return store.export(fmt)

        if sub == "summary":
            s = store.summary()
            return f"Events: {s['total_events']}, Actors: {s['unique_actors']}, Actions: {s['unique_actions']}"

        return "Usage: /audit-events <list|get <id>|verify|export [json|csv]|summary>"

    # ------------------------------------------------------------------
    # /audit-query
    # ------------------------------------------------------------------

    async def audit_query_handler(args: str) -> str:
        from lidco.audit.query_engine import AuditQueryEngine, QueryFilter

        store = _get_store()
        engine = AuditQueryEngine(store)  # type: ignore[arg-type]

        parts = args.strip().split()
        if not parts:
            return "Usage: /audit-query [actor=X] [action=Y] [since=T] [limit=N]"

        kwargs: dict[str, str | None] = {}
        limit = 100
        for part in parts:
            if "=" in part:
                key, val = part.split("=", 1)
                if key == "limit":
                    limit = int(val)
                elif key in ("actor", "action", "event_type", "resource_pattern", "since", "until"):
                    kwargs[key] = val

        # Convert numeric fields
        since = float(kwargs.pop("since")) if "since" in kwargs else None
        until = float(kwargs.pop("until")) if "until" in kwargs else None

        qf = QueryFilter(since=since, until=until, **kwargs)  # type: ignore[arg-type]
        results = engine.query(qf, limit=limit)

        if not results:
            return "No matching events."
        lines = [f"Found {len(results)} event(s):"]
        for e in results[:20]:
            lines.append(f"  {e.id[:8]} [{e.event_type}] {e.actor} {e.action} {e.resource}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /audit-anomaly
    # ------------------------------------------------------------------

    async def audit_anomaly_handler(args: str) -> str:
        from lidco.audit.anomaly import AnomalyDetector

        detector: AnomalyDetector = _get_detector()  # type: ignore[assignment]

        sub = args.strip().lower() or "detect"

        if sub == "detect":
            anomalies = detector.detect_all()
            if not anomalies:
                return "No anomalies detected."
            lines = [f"Detected {len(anomalies)} anomaly(ies):"]
            for a in anomalies:
                lines.append(f"  [{a.severity}] {a.type}: {a.description}")
            return "\n".join(lines)

        if sub == "privilege":
            results = detector.detect_privilege_escalation()
            if not results:
                return "No privilege escalation detected."
            lines = [f"{len(results)} escalation(s):"]
            for a in results:
                lines.append(f"  [{a.severity}] {a.description}")
            return "\n".join(lines)

        if sub == "off-hours":
            results = detector.detect_off_hours()
            if not results:
                return "No off-hours activity detected."
            lines = [f"{len(results)} off-hours pattern(s):"]
            for a in results:
                lines.append(f"  [{a.severity}] {a.description}")
            return "\n".join(lines)

        if sub == "bulk":
            results = detector.detect_bulk_operations()
            if not results:
                return "No bulk operations detected."
            lines = [f"{len(results)} bulk operation(s):"]
            for a in results:
                lines.append(f"  [{a.severity}] {a.description}")
            return "\n".join(lines)

        if sub == "summary":
            s = detector.summary()
            return f"Anomalies: {s['total_anomalies']}, By type: {s['by_type']}, By severity: {s['by_severity']}"

        return "Usage: /audit-anomaly <detect|privilege|off-hours|bulk|summary>"

    # ------------------------------------------------------------------
    # /audit-dashboard
    # ------------------------------------------------------------------

    async def audit_dashboard_handler(args: str) -> str:
        from lidco.audit.dashboard import AuditDashboard

        store = _get_store()
        detector = _get_detector()
        dashboard = AuditDashboard(store, detector)  # type: ignore[arg-type]

        sub = args.strip().lower() or "view"

        if sub == "view" or not sub:
            return dashboard.render_text()

        if sub == "risk":
            score = dashboard.risk_score()
            return f"Risk score: {score}/100"

        if sub == "summary":
            s = dashboard.summary()
            lines = [
                f"Events: {s['total_events']}",
                f"Actors: {s['active_actors']}",
                f"Risk: {s['risk_score']}/100",
                f"Anomalies: {s['anomaly_count']}",
            ]
            return "\n".join(lines)

        if sub.startswith("actor "):
            actor = sub[6:].strip()
            if not actor:
                return "Usage: /audit-dashboard actor <name>"
            info = dashboard.actor_activity(actor)
            lines = [
                f"Actor: {info['actor']}",
                f"Events: {info['event_count']}",
                f"Last active: {info['last_active']}",
            ]
            for action, count in info["top_actions"]:
                lines.append(f"  {action}: {count}")
            return "\n".join(lines)

        return "Usage: /audit-dashboard [view|risk|summary|actor <name>]"

    # ------------------------------------------------------------------
    # Register all
    # ------------------------------------------------------------------

    registry.register(SlashCommand("audit-events", "Manage audit event store", audit_events_handler))
    registry.register(SlashCommand("audit-query", "Query audit events with filters", audit_query_handler))
    registry.register(SlashCommand("audit-anomaly", "Detect audit anomalies", audit_anomaly_handler))
    registry.register(SlashCommand("audit-dashboard", "View audit dashboard", audit_dashboard_handler))
