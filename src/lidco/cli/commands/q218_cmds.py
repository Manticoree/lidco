"""Q218 CLI commands: /gen-actions, /pipeline, /deploy, /cloud."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q218 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /gen-actions
    # ------------------------------------------------------------------

    async def gen_actions_handler(args: str) -> str:
        from lidco.ecosystem.actions_generator import ActionsGenerator

        project_type = args.strip() or "python"
        gen = ActionsGenerator()
        jobs = [
            gen.generate_test_job(project_type),
            gen.generate_lint_job(project_type),
            gen.generate_build_job(project_type),
        ]
        return gen.to_yaml(jobs)

    # ------------------------------------------------------------------
    # /pipeline
    # ------------------------------------------------------------------

    async def pipeline_handler(args: str) -> str:
        from lidco.ecosystem.pipeline_manager import PipelineManager, PipelineProvider

        parts = args.strip().split()
        if not parts:
            return "Usage: /pipeline <trigger|status|list> [args]"
        mgr = PipelineManager()
        sub = parts[0]
        if sub == "trigger":
            provider_name = parts[1] if len(parts) > 1 else "github_actions"
            branch = parts[2] if len(parts) > 2 else "main"
            try:
                provider = PipelineProvider(provider_name)
            except ValueError:
                return f"Unknown provider: {provider_name}"
            run = mgr.trigger_build(provider, branch=branch)
            return f"Triggered {run.id} on {run.provider.value} ({run.branch})"
        if sub == "status":
            run_id = parts[1] if len(parts) > 1 else ""
            if not run_id:
                return "Usage: /pipeline status <run_id>"
            run = mgr.get_status(run_id)
            if run is None:
                return f"Run {run_id} not found."
            return f"{run.id}: {run.status.value}"
        if sub == "list":
            runs = mgr.list_runs()
            return mgr.summary()
        return f"Unknown subcommand: {sub}"

    # ------------------------------------------------------------------
    # /deploy
    # ------------------------------------------------------------------

    async def deploy_handler(args: str) -> str:
        from lidco.ecosystem.deploy_automator import DeployAutomator, DeployTarget

        parts = args.strip().split()
        if not parts:
            return "Usage: /deploy <env_name> [commit]"
        env_name = parts[0]
        commit = parts[1] if len(parts) > 1 else "HEAD"
        automator = DeployAutomator()
        automator.add_environment(env_name, DeployTarget.VERCEL)
        dep = automator.deploy(env_name, commit=commit)
        if dep is None:
            return f"Environment '{env_name}' not found."
        return f"Deployed {dep.id} to {dep.environment} (commit: {dep.commit})"

    # ------------------------------------------------------------------
    # /cloud
    # ------------------------------------------------------------------

    async def cloud_handler(args: str) -> str:
        from lidco.ecosystem.cloud_connector import CloudConnector

        parts = args.strip().split()
        if not parts:
            return "Usage: /cloud <list|logs|invoke> [args]"
        connector = CloudConnector()
        sub = parts[0]
        if sub == "list":
            resources = connector.list_resources()
            return connector.summary()
        if sub == "logs":
            source = parts[1] if len(parts) > 1 else None
            logs = connector.tail_logs(source=source)
            if not logs:
                return "No logs."
            return "\n".join(f"[{lg.level}] {lg.message}" for lg in logs)
        if sub == "invoke":
            resource_id = parts[1] if len(parts) > 1 else ""
            if not resource_id:
                return "Usage: /cloud invoke <resource_id>"
            result = connector.invoke_function(resource_id)
            return f"Invoked {result['resource']}: {result['status']}"
        return f"Unknown subcommand: {sub}"

    registry.register(
        SlashCommand("gen-actions", "Generate GitHub Actions workflow", gen_actions_handler)
    )
    registry.register(
        SlashCommand("pipeline", "CI/CD pipeline management", pipeline_handler)
    )
    registry.register(
        SlashCommand("deploy", "Deploy to environment", deploy_handler)
    )
    registry.register(
        SlashCommand("cloud", "Cloud resource management", cloud_handler)
    )
