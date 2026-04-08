"""
Q322 CLI commands — /deploy-blue-green, /deploy-canary, /deploy-rolling, /feature-deploy

Registered via register_q322_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q322_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q322 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /deploy-blue-green — Blue-green deployment management
    # ------------------------------------------------------------------
    async def deploy_blue_green_handler(args: str) -> str:
        """
        Usage: /deploy-blue-green <version> [--rollback] [--status]
        """
        from lidco.deploy.blue_green import BlueGreenDeployer

        parts = shlex.split(args) if args.strip() else []
        do_rollback = "--rollback" in parts
        do_status = "--status" in parts
        parts = [p for p in parts if p not in ("--rollback", "--status")]
        version = parts[0] if parts else ""

        deployer = BlueGreenDeployer()

        if do_status:
            s = deployer.status()
            return (
                f"Blue-Green Status:\n"
                f"  Active slot: {s['active_slot']}\n"
                f"  Blue: {s['blue']['version'] or '(none)'} (healthy={s['blue']['healthy']})\n"
                f"  Green: {s['green']['version'] or '(none)'} (healthy={s['green']['healthy']})\n"
                f"  Deployments: {s['deployments']}"
            )

        if do_rollback:
            dep = deployer.rollback()
            return f"Rollback: state={dep.state.value}, slot={deployer.active_slot.value}"

        if not version:
            return "Usage: /deploy-blue-green <version> [--rollback] [--status]"

        dep = deployer.deploy(version)
        lines = [
            f"Blue-Green Deploy: {dep.state.value}",
            f"  Version: {dep.version}",
            f"  Active slot: {deployer.active_slot.value}",
            f"  Duration: {dep.duration_ms:.0f}ms",
        ]
        if dep.error:
            lines.append(f"  Error: {dep.error}")
        return "\n".join(lines)

    registry.register_async(
        "deploy-blue-green",
        "Blue-green deployment management",
        deploy_blue_green_handler,
    )

    # ------------------------------------------------------------------
    # /deploy-canary — Canary release management
    # ------------------------------------------------------------------
    async def deploy_canary_handler(args: str) -> str:
        """
        Usage: /deploy-canary <version> [--rollback] [--status] [--steps 5,25,50,100]
        """
        from lidco.deploy.canary import CanaryConfig, CanaryDeployer

        parts = shlex.split(args) if args.strip() else []
        do_rollback = "--rollback" in parts
        do_status = "--status" in parts
        steps_raw: str | None = None

        filtered: list[str] = []
        i = 0
        while i < len(parts):
            if parts[i] == "--rollback":
                i += 1
            elif parts[i] == "--status":
                i += 1
            elif parts[i] == "--steps" and i + 1 < len(parts):
                steps_raw = parts[i + 1]
                i += 2
            else:
                filtered.append(parts[i])
                i += 1

        version = filtered[0] if filtered else ""
        steps: list[float] | None = None
        if steps_raw:
            try:
                steps = [float(s) for s in steps_raw.split(",")]
            except ValueError:
                pass

        config = CanaryConfig(steps=steps) if steps else CanaryConfig()
        deployer = CanaryDeployer(config=config)

        if do_status:
            s = deployer.status()
            return (
                f"Canary Status: {s['state']}\n"
                f"  Version: {s['version'] or '(none)'}\n"
                f"  Canary %: {s['canary_pct']}\n"
                f"  Steps: {s['steps']}"
            )

        if do_rollback:
            dep = deployer.rollback()
            if dep is None:
                return "No active canary to rollback."
            return f"Canary rollback: state={dep.state.value}"

        if not version:
            return "Usage: /deploy-canary <version> [--rollback] [--status] [--steps 5,25,50,100]"

        dep = deployer.deploy(version)
        lines = [
            f"Canary Deploy: {dep.state.value}",
            f"  Version: {dep.version}",
            f"  Traffic: {dep.traffic.canary_pct}% canary / {dep.traffic.stable_pct}% stable",
            f"  Steps: {dep.steps_completed}/{dep.total_steps}",
            f"  Duration: {dep.duration_ms:.0f}ms",
        ]
        if dep.error:
            lines.append(f"  Error: {dep.error}")
        return "\n".join(lines)

    registry.register_async(
        "deploy-canary",
        "Canary release management",
        deploy_canary_handler,
    )

    # ------------------------------------------------------------------
    # /deploy-rolling — Rolling update management
    # ------------------------------------------------------------------
    async def deploy_rolling_handler(args: str) -> str:
        """
        Usage: /deploy-rolling <version> [--instances i1,i2,...] [--batch-size N] [--status]
        """
        from lidco.deploy.rolling import RollingConfig, RollingDeployer

        parts = shlex.split(args) if args.strip() else []
        do_status = "--status" in parts
        instances_raw: str | None = None
        batch_size = 1

        filtered: list[str] = []
        i = 0
        while i < len(parts):
            if parts[i] == "--status":
                i += 1
            elif parts[i] == "--instances" and i + 1 < len(parts):
                instances_raw = parts[i + 1]
                i += 2
            elif parts[i] == "--batch-size" and i + 1 < len(parts):
                try:
                    batch_size = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                filtered.append(parts[i])
                i += 1

        version = filtered[0] if filtered else ""
        instances = instances_raw.split(",") if instances_raw else [f"inst-{j}" for j in range(3)]

        config = RollingConfig(batch_size=batch_size)
        deployer = RollingDeployer(config=config)

        if do_status:
            s = deployer.status()
            return (
                f"Rolling Status: {s['state']}\n"
                f"  Version: {s['version'] or '(none)'}\n"
                f"  Progress: {s['progress']} ({s['progress_pct']}%)"
            )

        if not version:
            return "Usage: /deploy-rolling <version> [--instances i1,i2,...] [--batch-size N] [--status]"

        dep = deployer.deploy(version, instances)
        lines = [
            f"Rolling Deploy: {dep.state.value}",
            f"  Version: {dep.version}",
            f"  Progress: {dep.updated_instances}/{dep.total_instances} ({dep.progress_pct:.0f}%)",
            f"  Batches: {len(dep.batches)}",
            f"  Duration: {dep.duration_ms:.0f}ms",
        ]
        if dep.error:
            lines.append(f"  Error: {dep.error}")
        return "\n".join(lines)

    registry.register_async(
        "deploy-rolling",
        "Rolling update management",
        deploy_rolling_handler,
    )

    # ------------------------------------------------------------------
    # /feature-deploy — Feature flag-based deployment
    # ------------------------------------------------------------------
    async def feature_deploy_handler(args: str) -> str:
        """
        Usage: /feature-deploy <name> [--rollout] [--kill] [--enable] [--status]
               /feature-deploy <name> --target user1,user2
        """
        from lidco.deploy.feature_flags import FeatureFlagDeployer

        parts = shlex.split(args) if args.strip() else []
        do_rollout = "--rollout" in parts
        do_kill = "--kill" in parts
        do_enable = "--enable" in parts
        do_status = "--status" in parts
        target_raw: str | None = None

        filtered: list[str] = []
        i = 0
        while i < len(parts):
            if parts[i] in ("--rollout", "--kill", "--enable", "--status"):
                i += 1
            elif parts[i] == "--target" and i + 1 < len(parts):
                target_raw = parts[i + 1]
                i += 2
            else:
                filtered.append(parts[i])
                i += 1

        name = filtered[0] if filtered else ""
        deployer = FeatureFlagDeployer()

        if do_status:
            s = deployer.status()
            return (
                f"Feature Flags Status:\n"
                f"  Total: {s['total_flags']}\n"
                f"  Enabled: {s['enabled']}\n"
                f"  Gradual: {s['gradual']}\n"
                f"  Killed: {s['killed']}\n"
                f"  Active rollouts: {s['active_rollouts']}"
            )

        if not name:
            return "Usage: /feature-deploy <name> [--rollout] [--kill] [--enable] [--target users] [--status]"

        flag = deployer.create_flag(name)

        if do_kill:
            deployer.kill(flag.flag_id)
            return f"Feature '{name}': KILLED"

        if do_enable:
            deployer.enable(flag.flag_id)
            return f"Feature '{name}': ENABLED for all users"

        if target_raw:
            users = target_raw.split(",")
            deployer.set_targets(flag.flag_id, users=users)
            return f"Feature '{name}': targeted to {len(users)} user(s)"

        if do_rollout:
            plan = deployer.start_rollout(flag.flag_id)
            if plan is None:
                return f"Failed to start rollout for '{name}'"
            return (
                f"Feature '{name}': rollout started\n"
                f"  Phase: {plan.phase.value}\n"
                f"  Step: {plan.current_step}/{len(plan.steps)}\n"
                f"  Current %: {plan.progress_pct}"
            )

        return f"Feature '{name}' created (flag_id={flag.flag_id}, state={flag.state.value})"

    registry.register_async(
        "feature-deploy",
        "Feature flag-based deployment management",
        feature_deploy_handler,
    )
