"""Q330 CLI commands — /tour, /explain-concept, /setup-dev, /contrib-guide

Registered via register_q330_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q330_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q330 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /tour — Guided codebase tour
    # ------------------------------------------------------------------
    async def tour_handler(args: str) -> str:
        """
        Usage: /tour start [root_dir]
               /tour add <name> <path> <description> [--category CAT] [--order N]
               /tour visit <name>
               /tour next
               /tour list [category]
               /tour overview
               /tour progress
        """
        from lidco.onboard.tour import CodebaseTour, TourStop

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /tour <subcommand>\n"
                "  start [root_dir]           start a new tour\n"
                "  add <name> <path> <desc>   add a stop\n"
                "  visit <name>               visit a stop\n"
                "  next                       show next unvisited stop\n"
                "  list [category]            list stops\n"
                "  overview                   architecture overview\n"
                "  progress                   show progress"
            )

        subcmd = parts[0].lower()

        if subcmd == "start":
            root = parts[1] if len(parts) > 1 else "."
            tour = CodebaseTour(root_dir=root)
            return f"Tour started for '{root}'. Add stops with /tour add."

        if subcmd == "add":
            if len(parts) < 4:
                return "Usage: /tour add <name> <path> <description> [--category CAT] [--order N]"
            name, path, desc = parts[1], parts[2], parts[3]
            category = "general"
            order = 0
            i = 4
            while i < len(parts):
                if parts[i] == "--category" and i + 1 < len(parts):
                    category = parts[i + 1]
                    i += 2
                elif parts[i] == "--order" and i + 1 < len(parts):
                    try:
                        order = int(parts[i + 1])
                    except ValueError:
                        return f"Invalid order: {parts[i + 1]}"
                    i += 2
                else:
                    i += 1
            stop = TourStop(name=name, path=path, description=desc, category=category, order=order)
            return f"Added stop '{stop.name}' at {stop.path} (category={stop.category}, order={stop.order})"

        if subcmd == "visit":
            if len(parts) < 2:
                return "Usage: /tour visit <name>"
            tour = CodebaseTour()
            stop = tour.visit(parts[1])
            if stop:
                return f"Visited: {stop.name} — {stop.description}"
            return f"Stop '{parts[1]}' not found."

        if subcmd == "next":
            tour = CodebaseTour()
            stop = tour.next_stop()
            if stop:
                return f"Next: {stop.name} — {stop.description} ({stop.path})"
            return "All stops visited or no stops added."

        if subcmd == "list":
            category = parts[1] if len(parts) > 1 else None
            tour = CodebaseTour()
            if category:
                stops = tour.stops_by_category(category)
            else:
                stops = tour.stops
            if not stops:
                return "No stops found."
            lines = [f"Tour stops ({len(stops)}):"]
            for s in stops:
                lines.append(f"  [{s.order}] {s.name}: {s.description} ({s.path})")
            return "\n".join(lines)

        if subcmd == "overview":
            tour = CodebaseTour()
            ov = tour.architecture_overview()
            lines = [f"Architecture: {ov.name}", ov.description]
            for layer in ov.layers:
                lines.append(f"  Layer: {layer['name']} — {layer['description']}")
            return "\n".join(lines)

        if subcmd == "progress":
            tour = CodebaseTour()
            return tour.summary()

        return f"Unknown subcommand '{subcmd}'. Use start/add/visit/next/list/overview/progress."

    registry.register_async("tour", "Guided codebase tour with progress tracking", tour_handler)

    # ------------------------------------------------------------------
    # /explain-concept — Explain project concepts
    # ------------------------------------------------------------------
    async def explain_concept_handler(args: str) -> str:
        """
        Usage: /explain-concept list [difficulty]
               /explain-concept show <name>
               /explain-concept quiz <name>
               /explain-concept search <query>
               /explain-concept glossary [term]
               /explain-concept path
        """
        from lidco.onboard.explainer import ConceptExplainer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /explain-concept <subcommand>\n"
                "  list [difficulty]    list concepts\n"
                "  show <name>         explain a concept\n"
                "  quiz <name>         show quiz for concept\n"
                "  search <query>      search concepts\n"
                "  glossary [term]     look up glossary\n"
                "  path                progressive learning path"
            )

        subcmd = parts[0].lower()

        if subcmd == "list":
            explainer = ConceptExplainer()
            concepts = explainer.list_concepts()
            if not concepts:
                return "No concepts defined."
            lines = [f"Concepts ({len(concepts)}):"]
            for c in concepts:
                lines.append(f"  [{c.difficulty.value}] {c.name}: {c.summary}")
            return "\n".join(lines)

        if subcmd == "show":
            if len(parts) < 2:
                return "Usage: /explain-concept show <name>"
            explainer = ConceptExplainer()
            text = explainer.explain(parts[1])
            if text:
                return text
            return f"Concept '{parts[1]}' not found."

        if subcmd == "quiz":
            if len(parts) < 2:
                return "Usage: /explain-concept quiz <name>"
            explainer = ConceptExplainer()
            questions = explainer.quiz(parts[1])
            if not questions:
                return f"No quiz for '{parts[1]}'."
            lines = [f"Quiz: {parts[1]}"]
            for i, q in enumerate(questions):
                lines.append(f"  Q{i + 1}: {q.question}")
                for j, choice in enumerate(q.choices):
                    lines.append(f"    {j + 1}) {choice}")
            return "\n".join(lines)

        if subcmd == "search":
            if len(parts) < 2:
                return "Usage: /explain-concept search <query>"
            explainer = ConceptExplainer()
            results = explainer.search_concepts(parts[1])
            if not results:
                return f"No concepts matching '{parts[1]}'."
            lines = [f"Search results ({len(results)}):"]
            for c in results:
                lines.append(f"  {c.name}: {c.summary}")
            return "\n".join(lines)

        if subcmd == "glossary":
            explainer = ConceptExplainer()
            if len(parts) > 1:
                entry = explainer.get_glossary(parts[1])
                if entry:
                    result = f"{entry.term}: {entry.definition}"
                    if entry.see_also:
                        result += f"\nSee also: {', '.join(entry.see_also)}"
                    return result
                return f"Glossary term '{parts[1]}' not found."
            entries = explainer.list_glossary()
            if not entries:
                return "Glossary is empty."
            lines = [f"Glossary ({len(entries)} terms):"]
            for e in entries:
                lines.append(f"  {e.term}: {e.definition}")
            return "\n".join(lines)

        if subcmd == "path":
            explainer = ConceptExplainer()
            path = explainer.progressive_path()
            if not path:
                return "No concepts for learning path."
            lines = ["Learning path:"]
            for i, c in enumerate(path, 1):
                lines.append(f"  {i}. [{c.difficulty.value}] {c.name}")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use list/show/quiz/search/glossary/path."

    registry.register_async("explain-concept", "Explain project concepts interactively", explain_concept_handler)

    # ------------------------------------------------------------------
    # /setup-dev — Guided dev environment setup
    # ------------------------------------------------------------------
    async def setup_dev_handler(args: str) -> str:
        """
        Usage: /setup-dev check [command]
               /setup-dev python [min_version]
               /setup-dev file <path>
               /setup-dev run-all
               /setup-dev config list
               /setup-dev config generate <name> [--var KEY=VAL ...]
               /setup-dev verify
        """
        from lidco.onboard.setup import SetupAssistant

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /setup-dev <subcommand>\n"
                "  check [command]              check if command exists\n"
                "  python [min_version]         check Python version\n"
                "  file <path>                  check file exists\n"
                "  run-all                      run all registered checks\n"
                "  config list                  list config templates\n"
                "  config generate <name>       generate config file\n"
                "  verify                       full verification"
            )

        subcmd = parts[0].lower()
        assistant = SetupAssistant()

        if subcmd == "check":
            if len(parts) < 2:
                return "Usage: /setup-dev check <command>"
            result = assistant.check_command_exists(parts[1])
            status = result.status.value.upper()
            msg = result.message
            if result.fix_hint:
                msg += f"\nHint: {result.fix_hint}"
            return f"[{status}] {result.name}: {msg}"

        if subcmd == "python":
            min_ver = parts[1] if len(parts) > 1 else "3.10"
            result = assistant.check_python_version(min_ver)
            return f"[{result.status.value.upper()}] {result.message}"

        if subcmd == "file":
            if len(parts) < 2:
                return "Usage: /setup-dev file <path>"
            result = assistant.check_file_exists(parts[1])
            status = result.status.value.upper()
            msg = result.message
            if result.fix_hint:
                msg += f"\nHint: {result.fix_hint}"
            return f"[{status}] {result.name}: {msg}"

        if subcmd == "run-all":
            report = assistant.run_all_checks()
            if not report.results:
                return "No checks registered."
            lines = [f"Setup checks: {report.passed} passed, {report.failed} failed, {report.warnings} warnings"]
            for r in report.results:
                lines.append(f"  [{r.status.value.upper()}] {r.name}: {r.message}")
            return "\n".join(lines)

        if subcmd == "config":
            if len(parts) < 2:
                return "Usage: /setup-dev config list | config generate <name>"
            config_sub = parts[1].lower()
            if config_sub == "list":
                templates = assistant.list_config_templates()
                if not templates:
                    return "No config templates registered."
                return "Config templates: " + ", ".join(templates)
            if config_sub == "generate":
                if len(parts) < 3:
                    return "Usage: /setup-dev config generate <name> [--var KEY=VAL ...]"
                name = parts[2]
                variables: dict[str, str] = {}
                i = 3
                while i < len(parts):
                    if parts[i] == "--var" and i + 1 < len(parts):
                        kv = parts[i + 1]
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            variables[k] = v
                        i += 2
                    else:
                        i += 1
                result = assistant.generate_config(name, variables)
                if result is None:
                    return f"Template '{name}' not found."
                return f"Generated config '{name}':\n{result}"
            return f"Unknown config subcommand '{config_sub}'."

        if subcmd == "verify":
            return assistant.summary()

        return f"Unknown subcommand '{subcmd}'. Use check/python/file/run-all/config/verify."

    registry.register_async("setup-dev", "Guided dev environment setup", setup_dev_handler)

    # ------------------------------------------------------------------
    # /contrib-guide — Generate contribution guide
    # ------------------------------------------------------------------
    async def contrib_guide_handler(args: str) -> str:
        """
        Usage: /contrib-guide generate [project_name]
               /contrib-guide default [project_name]
               /contrib-guide summary
        """
        from lidco.onboard.contrib import ContributionGuideGenerator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /contrib-guide <subcommand>\n"
                "  generate [project_name]     generate guide from config\n"
                "  default [project_name]      generate default guide\n"
                "  summary                     show generator summary"
            )

        subcmd = parts[0].lower()

        if subcmd == "generate":
            name = parts[1] if len(parts) > 1 else "project"
            gen = ContributionGuideGenerator(project_name=name)
            guide = gen.generate()
            return guide.render()

        if subcmd == "default":
            name = parts[1] if len(parts) > 1 else "project"
            gen = ContributionGuideGenerator(project_name=name)
            guide = gen.generate_default()
            return guide.render()

        if subcmd == "summary":
            gen = ContributionGuideGenerator()
            return gen.summary()

        return f"Unknown subcommand '{subcmd}'. Use generate/default/summary."

    registry.register_async("contrib-guide", "Generate contribution guide", contrib_guide_handler)
