"""Q198 CLI commands: /init, /onboard, /project-type, /setup-check."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q198 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /init
    # ------------------------------------------------------------------

    async def init_handler(args: str) -> str:
        from lidco.onboarding.detector import ProjectDetector
        from lidco.onboarding.wizard import InitWizard

        path = args.strip() or "."
        detector = ProjectDetector()
        info = detector.detect(path)
        wizard = InitWizard(info)
        result = wizard.run({})
        return (
            f"Project detected: {info.project_type.value}\n"
            f"Steps completed: {len(result.steps_completed)}\n"
            f"---\n{result.claude_md}"
        )

    # ------------------------------------------------------------------
    # /onboard
    # ------------------------------------------------------------------

    async def onboard_handler(args: str) -> str:
        from lidco.onboarding.state import OnboardingState, OnboardingStep, StepStatus

        default_steps = (
            OnboardingStep(name="detect_project", status=StepStatus.PENDING, completed_at=None),
            OnboardingStep(name="configure", status=StepStatus.PENDING, completed_at=None),
            OnboardingStep(name="generate_claude_md", status=StepStatus.PENDING, completed_at=None),
            OnboardingStep(name="verify_setup", status=StepStatus.PENDING, completed_at=None),
        )
        state = OnboardingState(default_steps)
        pending = state.pending()
        return (
            f"Onboarding progress: {state.progress():.0%}\n"
            f"Pending steps: {', '.join(pending)}"
        )

    # ------------------------------------------------------------------
    # /project-type
    # ------------------------------------------------------------------

    async def project_type_handler(args: str) -> str:
        from lidco.onboarding.detector import ProjectDetector

        path = args.strip() or "."
        detector = ProjectDetector()
        ptype = detector.detect_type(path)
        frameworks = detector.detect_frameworks(path)
        mono = detector.is_monorepo(path)

        lines = [f"Project type: {ptype.value}"]
        if frameworks:
            lines.append(f"Frameworks: {', '.join(fw.name for fw in frameworks)}")
        if mono:
            lines.append("Monorepo: yes")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /setup-check
    # ------------------------------------------------------------------

    async def setup_check_handler(args: str) -> str:
        from lidco.onboarding.detector import ProjectDetector
        from lidco.onboarding.state import OnboardingState, OnboardingStep, StepStatus

        import os

        path = args.strip() or "."
        detector = ProjectDetector()
        info = detector.detect(path)

        checks: list[OnboardingStep] = []

        # Check project detected
        if info.project_type.value != "unknown":
            checks.append(OnboardingStep("project_detected", StepStatus.DONE, None))
        else:
            checks.append(OnboardingStep("project_detected", StepStatus.PENDING, None))

        # Check CLAUDE.md exists
        claude_md = os.path.join(os.path.abspath(path), "CLAUDE.md")
        if os.path.isfile(claude_md):
            checks.append(OnboardingStep("claude_md", StepStatus.DONE, None))
        else:
            checks.append(OnboardingStep("claude_md", StepStatus.PENDING, None))

        state = OnboardingState(tuple(checks))
        lines = [f"Setup check: {state.progress():.0%} complete"]
        for step in state.steps:
            marker = "[x]" if step.status == StepStatus.DONE else "[ ]"
            lines.append(f"  {marker} {step.name}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    registry.register(SlashCommand("init", "Initialize project with wizard", init_handler))
    registry.register(SlashCommand("onboard", "Show onboarding progress", onboard_handler))
    registry.register(SlashCommand("project-type", "Detect project type", project_type_handler))
    registry.register(SlashCommand("setup-check", "Verify project setup", setup_check_handler))
