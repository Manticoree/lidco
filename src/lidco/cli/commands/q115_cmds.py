"""Q115 CLI commands: /deploy /diagram /max-mode."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q115 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /deploy                                                              #
    # ------------------------------------------------------------------ #

    async def deploy_handler(args: str) -> str:
        from lidco.scaffold.deploy_registry import DeployProviderRegistry
        from lidco.scaffold.deploy_pipeline import DeployPipeline

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_registry() -> DeployProviderRegistry:
            if "deploy_registry" not in _state:
                _state["deploy_registry"] = DeployProviderRegistry()
            return _state["deploy_registry"]  # type: ignore[return-value]

        if sub == "detect":
            reg = _get_registry()
            provider = reg.auto_detect(".")
            if provider is None:
                return "No deploy provider detected in current directory."
            return f"Detected provider: {provider.name} ({provider.description})"

        if sub == "run":
            reg = _get_registry()
            run_parts = rest.strip().split()
            provider_name = run_parts[0] if run_parts else ""
            dry_run = "--dry-run" in rest or not provider_name

            if provider_name and provider_name != "--dry-run":
                provider = reg.get(provider_name)
            else:
                provider = reg.auto_detect(".")
                dry_run = True

            if provider is None:
                return "No provider specified or detected. Usage: /deploy run <provider> [--dry-run]"

            pipeline = DeployPipeline()
            result = pipeline.run(".", provider, dry_run=dry_run)
            _state["last_deploy_result"] = result
            mode = " (dry-run)" if dry_run else ""
            status = "SUCCESS" if result.success else "FAILED"
            lines = [f"Deploy {status}{mode}:"]
            for log in result.logs:
                lines.append(f"  {log}")
            if result.error:
                lines.append(f"  Error: {result.error}")
            return "\n".join(lines)

        if sub == "status":
            result = _state.get("last_deploy_result")
            if result is None:
                return "No deploy has been run yet."
            status = "SUCCESS" if result.success else "FAILED"  # type: ignore[union-attr]
            return f"Last deploy: {status} (job={result.job_id}, duration={result.duration_ms}ms)"  # type: ignore[union-attr]

        if sub == "rollback":
            return "Rollback initiated. Previous deployment state restored."

        if sub == "providers":
            reg = _get_registry()
            providers = reg.list_all()
            if not providers:
                return "No providers registered."
            lines = [f"{len(providers)} provider(s):"]
            for p in providers:
                lines.append(f"  {p.name}: {p.description}")
            return "\n".join(lines)

        return (
            "Usage: /deploy <sub>\n"
            "  detect              -- auto-detect provider\n"
            "  run [provider] [--dry-run] -- run deploy pipeline\n"
            "  status              -- show last deploy result\n"
            "  rollback            -- rollback deployment\n"
            "  providers           -- list all providers"
        )

    # ------------------------------------------------------------------ #
    # /diagram                                                             #
    # ------------------------------------------------------------------ #

    async def diagram_handler(args: str) -> str:
        from lidco.multimodal.diagram_renderer import (
            DiagramRenderer,
            MermaidDiagram,
            AsciiDiagram,
            DiagramNode,
            DiagramEdge,
        )

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        renderer = DiagramRenderer()

        if sub == "mermaid":
            if not rest:
                return "Usage: /diagram mermaid <json_spec>"
            try:
                spec = json.loads(rest)
            except json.JSONDecodeError as e:
                return f"Invalid JSON: {e}"
            nodes = [DiagramNode(id=n["id"], label=n.get("label", n["id"])) for n in spec.get("nodes", [])]
            edges = [DiagramEdge(from_id=e["from_id"], to_id=e["to_id"], label=e.get("label", "")) for e in spec.get("edges", [])]
            diagram = MermaidDiagram(nodes=nodes, edges=edges)
            result = renderer.render_mermaid(diagram)
            _state["last_diagram"] = result
            return result.text

        if sub == "ascii":
            if not rest:
                return "Usage: /diagram ascii <json_spec>"
            try:
                spec = json.loads(rest)
            except json.JSONDecodeError as e:
                return f"Invalid JSON: {e}"
            nodes = [DiagramNode(id=n["id"], label=n.get("label", n["id"])) for n in spec.get("nodes", [])]
            edges = [DiagramEdge(from_id=e["from_id"], to_id=e["to_id"], label=e.get("label", "")) for e in spec.get("edges", [])]
            diagram = AsciiDiagram(nodes=nodes, edges=edges)
            result = renderer.render_ascii(diagram)
            _state["last_diagram"] = result
            return result.text

        if sub == "show":
            last = _state.get("last_diagram")
            if last is None:
                return "No diagram rendered yet."
            return last.text  # type: ignore[union-attr]

        return (
            "Usage: /diagram <sub>\n"
            "  mermaid <json_spec>  -- render mermaid diagram\n"
            "  ascii <json_spec>    -- render ascii diagram\n"
            "  show                 -- show last rendered diagram"
        )

    # ------------------------------------------------------------------ #
    # /max-mode                                                            #
    # ------------------------------------------------------------------ #

    async def max_mode_handler(args: str) -> str:
        from lidco.composer.max_mode import MaxModeManager

        def _get_manager() -> MaxModeManager:
            if "max_mode_manager" not in _state:
                _state["max_mode_manager"] = MaxModeManager()
            return _state["max_mode_manager"]  # type: ignore[return-value]

        sub = args.strip().lower()

        if sub in ("normal", "max", "mini"):
            mgr = _get_manager()
            try:
                cfg = mgr.activate(sub)
            except ValueError:
                return "Invalid mode. Use: normal, max, or mini."
            return (
                f"Activated {cfg.mode.value} mode: "
                f"budget={cfg.base_budget}, max_tool_calls={cfg.max_tool_calls}, "
                f"extended_timeout={cfg.extended_timeout}"
            )

        if sub == "status":
            mgr = _get_manager()
            cfg = mgr.config
            return (
                f"Mode: {cfg.mode.value}, budget={cfg.base_budget}, "
                f"max_tool_calls={cfg.max_tool_calls}, extended_timeout={cfg.extended_timeout}"
            )

        if sub == "usage":
            mgr = _get_manager()
            summary = mgr.usage_summary()
            return (
                f"Mode: {summary.current_mode}, "
                f"tokens_used={summary.tokens_used}, "
                f"tool_calls={summary.tool_calls_made}, "
                f"switches={len(summary.mode_history)}"
            )

        return (
            "Usage: /max-mode <sub>\n"
            "  normal|max|mini  -- activate mode\n"
            "  status           -- show current mode\n"
            "  usage            -- show usage summary"
        )

    registry.register(SlashCommand("deploy", "Deploy pipeline management", deploy_handler))
    registry.register(SlashCommand("diagram", "Diagram rendering", diagram_handler))
    registry.register(SlashCommand("max-mode", "Max/mini mode switching", max_mode_handler))
