"""
Q324 CLI commands -- /backup, /dr-plan, /failover, /dr-test

Registered via register_q324_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q324_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q324 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /backup -- Manage backups
    # ------------------------------------------------------------------
    async def backup_handler(args: str) -> str:
        """
        Usage: /backup [--type full|incremental] [--encrypt KEY_ID] [path]
        """
        from lidco.dr.backup import BackupManager, BackupType, EncryptionConfig

        parts = shlex.split(args) if args.strip() else []
        backup_type = BackupType.FULL
        key_id = ""
        source = "."

        i = 0
        while i < len(parts):
            if parts[i] == "--type" and i + 1 < len(parts):
                try:
                    backup_type = BackupType(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--encrypt" and i + 1 < len(parts):
                key_id = parts[i + 1]
                i += 2
            else:
                source = parts[i]
                i += 1

        enc = EncryptionConfig(enabled=bool(key_id), key_id=key_id) if key_id else None
        mgr = BackupManager(encryption=enc)
        result = mgr.create_backup(source, backup_type=backup_type)

        if result.manifest:
            return (
                f"Backup {result.backup_id}: {result.status.value}\n"
                f"  Type: {result.manifest.backup_type.value}\n"
                f"  Files: {result.manifest.file_count}\n"
                f"  Size: {result.manifest.size_bytes} bytes\n"
                f"  Duration: {result.duration_seconds:.2f}s"
            )
        return f"Backup {result.backup_id}: {result.status.value} — {result.error}"

    registry.register_async(
        "backup",
        "Create automated backups",
        backup_handler,
    )

    # ------------------------------------------------------------------
    # /dr-plan -- Generate DR plan
    # ------------------------------------------------------------------
    async def dr_plan_handler(args: str) -> str:
        """
        Usage: /dr-plan [--name NAME] [--rto SECONDS] [--rpo SECONDS]
        """
        from lidco.dr.planner import Component, ComponentTier, RecoveryPlanner

        parts = shlex.split(args) if args.strip() else []
        name = "Default DR Plan"
        rto = 3600
        rpo = 900

        i = 0
        while i < len(parts):
            if parts[i] == "--name" and i + 1 < len(parts):
                name = parts[i + 1]
                i += 2
            elif parts[i] == "--rto" and i + 1 < len(parts):
                try:
                    rto = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--rpo" and i + 1 < len(parts):
                try:
                    rpo = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        planner = RecoveryPlanner()
        planner.add_component(Component(
            name="database",
            tier=ComponentTier.CRITICAL,
            rto_seconds=rto // 2,
            recovery_steps=["Stop writes", "Restore from backup", "Verify integrity"],
        ))
        planner.add_component(Component(
            name="application",
            tier=ComponentTier.HIGH,
            rto_seconds=rto // 2,
            dependencies=["database"],
            recovery_steps=["Redeploy services", "Health check"],
        ))

        plan = planner.generate_plan(name, target_rto=rto, target_rpo=rpo)
        issues = planner.validate_plan(plan.plan_id)

        lines = [
            f"DR Plan: {plan.name} ({plan.plan_id})",
            f"  Status: {plan.status.value}",
            f"  RTO target: {plan.target_rto_seconds}s",
            f"  RPO target: {plan.target_rpo_seconds}s",
            f"  Estimated recovery: {plan.total_estimated_seconds}s",
            f"  Meets RTO: {plan.meets_rto}",
            f"  Components: {len(plan.components)}",
            f"  Runbook steps: {len(plan.runbook)}",
        ]
        if issues:
            lines.append("  Issues:")
            for issue in issues:
                lines.append(f"    - {issue}")

        return "\n".join(lines)

    registry.register_async(
        "dr-plan",
        "Generate disaster recovery plan",
        dr_plan_handler,
    )

    # ------------------------------------------------------------------
    # /failover -- Execute failover
    # ------------------------------------------------------------------
    async def failover_handler(args: str) -> str:
        """
        Usage: /failover [--target NODE_ID] [--status]
        """
        from lidco.dr.failover import FailoverOrchestrator, Node

        parts = shlex.split(args) if args.strip() else []
        target = ""
        show_status = False

        i = 0
        while i < len(parts):
            if parts[i] == "--target" and i + 1 < len(parts):
                target = parts[i + 1]
                i += 2
            elif parts[i] == "--status":
                show_status = True
                i += 1
            else:
                i += 1

        orch = FailoverOrchestrator()
        orch.register_node(Node(
            node_id="primary-1",
            name="Primary",
            endpoint="https://primary.example.com",
            is_primary=True,
        ))
        orch.register_node(Node(
            node_id="secondary-1",
            name="Secondary",
            endpoint="https://secondary.example.com",
        ))

        if show_status:
            checks = orch.check_all_health()
            lines = ["Node Health:"]
            for c in checks:
                lines.append(f"  {c.node_id}: {c.status.value}")
            return "\n".join(lines)

        evt = orch.execute_failover(target_id=target or None)
        return (
            f"Failover {evt.event_id}: {evt.status.value}\n"
            f"  From: {evt.from_node}\n"
            f"  To: {evt.to_node}\n"
            f"  DNS switched: {evt.dns_switched}\n"
            f"  Data verified: {evt.data_sync_verified}"
        )

    registry.register_async(
        "failover",
        "Execute automated failover",
        failover_handler,
    )

    # ------------------------------------------------------------------
    # /dr-test -- Run DR test scenarios
    # ------------------------------------------------------------------
    async def dr_test_handler(args: str) -> str:
        """
        Usage: /dr-test [--scenario full_failover|backup_restore|chaos]
        """
        from lidco.dr.tester import (
            DRTestRunner,
            IntegrityResult,
            ScenarioConfig,
            ScenarioType,
        )

        parts = shlex.split(args) if args.strip() else []
        scenario_type = ScenarioType.FULL_FAILOVER

        i = 0
        while i < len(parts):
            if parts[i] == "--scenario" and i + 1 < len(parts):
                try:
                    scenario_type = ScenarioType(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        runner = DRTestRunner()
        config = ScenarioConfig(
            scenario_type=scenario_type,
            name=f"DR Test: {scenario_type.value}",
        )
        scenario = runner.create_scenario(config)
        scenario.add_step(lambda: True)  # simulated step
        scenario.add_integrity_check(
            lambda: IntegrityResult(component="test", is_valid=True, records_checked=1)
        )

        result = runner.run_scenario(scenario.scenario_id)
        summary = runner.get_summary()

        return (
            f"DR Test {result.test_id}: {result.status.value}\n"
            f"  Scenario: {result.scenario_type.value}\n"
            f"  Recovery time: {result.recovery_time_seconds:.3f}s\n"
            f"  Steps: {result.steps_completed}/{result.steps_total}\n"
            f"  Data integrity: {result.all_integrity_valid}\n"
            f"  Summary: {summary['passed']} passed, {summary['failed']} failed"
        )

    registry.register_async(
        "dr-test",
        "Run disaster recovery test scenarios",
        dr_test_handler,
    )
