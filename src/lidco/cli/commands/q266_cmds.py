"""Q266 CLI commands: /fleet, /distribute-config, /aggregate-usage, /enterprise-dashboard."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q266 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /fleet
    # ------------------------------------------------------------------

    async def fleet_handler(args: str) -> str:
        from lidco.enterprise.fleet import FleetManager

        if "fleet" not in _state:
            _state["fleet"] = FleetManager()

        fm: FleetManager = _state["fleet"]  # type: ignore[assignment]
        parts = args.strip().split()

        if not parts or parts[0] == "list":
            instances = fm.all_instances()
            if not instances:
                return "No instances registered."
            lines = [f"  {i.id}  {i.name}  v{i.version}  [{i.status}]" for i in instances]
            return "Fleet instances:\n" + "\n".join(lines)

        if parts[0] == "register" and len(parts) >= 3:
            name = parts[1]
            version = parts[2]
            inst = fm.register(name, version)
            return f"Registered instance {inst.id} ({inst.name} v{inst.version})."

        if parts[0] == "health":
            health = fm.check_health()
            return (
                f"Health: {health['healthy']} healthy, "
                f"{health['degraded']} degraded, "
                f"{health['offline']} offline."
            )

        if parts[0] == "status" and len(parts) >= 2:
            filtered = fm.by_status(parts[1])
            if not filtered:
                return f"No instances with status '{parts[1]}'."
            lines = [f"  {i.id}  {i.name}  [{i.status}]" for i in filtered]
            return "\n".join(lines)

        return "Usage: /fleet [list | register <name> <version> | health | status <filter>]"

    # ------------------------------------------------------------------
    # /distribute-config
    # ------------------------------------------------------------------

    async def distribute_config_handler(args: str) -> str:
        from lidco.enterprise.distributor import ConfigDistributor

        if "distributor" not in _state:
            _state["distributor"] = ConfigDistributor()

        cd: ConfigDistributor = _state["distributor"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)

        if not parts:
            return "Usage: /distribute-config [publish <json> | versions | diff <v1> <v2> | rollout <version> <targets>]"

        if parts[0] == "publish" and len(parts) >= 2:
            try:
                config = json.loads(parts[1])
            except json.JSONDecodeError as exc:
                return f"Invalid JSON: {exc}"
            ver = cd.publish(config)
            return f"Published config version {ver.version}."

        if parts[0] == "versions":
            versions = cd.versions()
            if not versions:
                return "No versions published."
            lines = [f"  v{v.version} by {v.author} — {v.description or '(no description)'}" for v in versions]
            return "Config versions:\n" + "\n".join(lines)

        if parts[0] == "diff":
            nums = (parts[1] if len(parts) > 1 else "").split()
            if len(nums) < 2:
                return "Usage: /distribute-config diff <v1> <v2>"
            try:
                v1, v2 = int(nums[0]), int(nums[1])
            except ValueError:
                return "Version numbers must be integers."
            d = cd.diff(v1, v2)
            return json.dumps(d, indent=2)

        if parts[0] == "rollout" and len(parts) >= 2:
            rollout_parts = parts[1].split()
            if len(rollout_parts) < 2:
                return "Usage: /distribute-config rollout <version> <target1> [target2 ...]"
            try:
                version = int(rollout_parts[0])
            except ValueError:
                return "Version must be an integer."
            targets = rollout_parts[1:]
            status = cd.rollout(version, targets)
            return f"Rollout v{status.version}: {status.applied_count}/{status.target_count} applied ({status.status})."

        return "Usage: /distribute-config [publish <json> | versions | diff <v1> <v2> | rollout <version> <targets>]"

    # ------------------------------------------------------------------
    # /aggregate-usage
    # ------------------------------------------------------------------

    async def aggregate_usage_handler(args: str) -> str:
        from lidco.enterprise.aggregator import UsageAggregator

        if "aggregator" not in _state:
            _state["aggregator"] = UsageAggregator()

        agg: UsageAggregator = _state["aggregator"]  # type: ignore[assignment]
        cmd = args.strip().split()[0] if args.strip() else ""

        if cmd == "by-team":
            data = agg.by_team()
            if not data:
                return "No usage recorded."
            return json.dumps(data, indent=2)

        if cmd == "by-project":
            data = agg.by_project()
            if not data:
                return "No usage recorded."
            return json.dumps(data, indent=2)

        if cmd == "total":
            return json.dumps(agg.total(), indent=2)

        if cmd == "top":
            top = agg.top_teams()
            if not top:
                return "No usage recorded."
            lines = [f"  {t}: ${c:.2f}" for t, c in top]
            return "Top teams by cost:\n" + "\n".join(lines)

        if cmd == "export":
            parts = args.strip().split()
            fmt = parts[1] if len(parts) > 1 else "json"
            return agg.export(fmt)

        return "Usage: /aggregate-usage [by-team | by-project | total | top | export [json|csv]]"

    # ------------------------------------------------------------------
    # /enterprise-dashboard
    # ------------------------------------------------------------------

    async def enterprise_dashboard_handler(args: str) -> str:
        from lidco.enterprise.aggregator import UsageAggregator
        from lidco.enterprise.dashboard_v2 import EnterpriseDashboard
        from lidco.enterprise.fleet import FleetManager

        if "fleet" not in _state:
            _state["fleet"] = FleetManager()
        if "aggregator" not in _state:
            _state["aggregator"] = UsageAggregator()

        fleet: FleetManager = _state["fleet"]  # type: ignore[assignment]
        aggregator: UsageAggregator = _state["aggregator"]  # type: ignore[assignment]
        dash = EnterpriseDashboard(fleet, aggregator)

        cmd = args.strip().split()[0] if args.strip() else ""

        if cmd == "metrics":
            return json.dumps(dash.summary(), indent=2)

        if cmd == "roi":
            parts = args.strip().split()
            rate = float(parts[1]) if len(parts) > 1 else 75.0
            roi = dash.roi_estimate(developer_hourly_rate=rate)
            return f"Estimated ROI: ${roi:.2f}"

        if cmd == "summary":
            return dash.executive_summary()

        return dash.render_text()

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------

    registry.register(SlashCommand("fleet", "Manage LIDCO fleet instances", fleet_handler))
    registry.register(SlashCommand("distribute-config", "Distribute config across fleet", distribute_config_handler))
    registry.register(SlashCommand("aggregate-usage", "Aggregate usage across fleet", aggregate_usage_handler))
    registry.register(SlashCommand("enterprise-dashboard", "Enterprise org-wide dashboard", enterprise_dashboard_handler))
