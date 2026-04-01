"""Q237 CLI commands: /doctor, /doctor-api, /doctor-models, /doctor-env."""
from __future__ import annotations


def register(registry) -> None:  # noqa: ANN001
    """Register Q237 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /doctor
    # ------------------------------------------------------------------

    async def doctor_handler(args: str) -> str:
        from lidco.doctor.system_checker import SystemChecker

        checker = SystemChecker()
        results = checker.run_all()
        return checker.summary(results)

    # ------------------------------------------------------------------
    # /doctor-api
    # ------------------------------------------------------------------

    async def doctor_api_handler(args: str) -> str:
        from lidco.doctor.api_validator import ApiValidator

        validator = ApiValidator()
        results = validator.validate_all()
        return validator.summary(results)

    # ------------------------------------------------------------------
    # /doctor-models
    # ------------------------------------------------------------------

    async def doctor_models_handler(args: str) -> str:
        from lidco.doctor.model_checker import ModelChecker

        checker = ModelChecker()
        budget = args.strip() or "medium"
        recommended = checker.recommend(budget)
        all_models = checker.check_all()
        lines = [
            f"Recommended ({budget}): {checker.summary(recommended)}",
            f"All known: {checker.summary(all_models)}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /doctor-env
    # ------------------------------------------------------------------

    async def doctor_env_handler(args: str) -> str:
        from lidco.doctor.env_reporter import EnvReporter

        reporter = EnvReporter()
        report = reporter.generate()
        return reporter.format_report(report)

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------

    registry.register(SlashCommand("doctor", "Run system health checks", doctor_handler))
    registry.register(SlashCommand("doctor-api", "Validate API keys", doctor_api_handler))
    registry.register(SlashCommand("doctor-models", "Check model availability", doctor_models_handler))
    registry.register(SlashCommand("doctor-env", "Show environment report", doctor_env_handler))
