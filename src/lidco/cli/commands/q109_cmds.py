"""Q109 CLI commands: /annotate /stash /fixture /liveness."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q109 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /annotate — type annotation suggester                                #
    # ------------------------------------------------------------------ #

    async def annotate_handler(args: str) -> str:
        from lidco.typing_.annotator import TypeAnnotator, AnnotatorError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_ann() -> TypeAnnotator:
            min_conf = float(_state.get("annotate_confidence", 0.5))
            return TypeAnnotator(min_confidence=min_conf)

        if sub == "demo":
            source = (
                "def process(name, count=0, verbose=False):\n"
                "    if verbose:\n"
                "        print(name)\n"
                "    return name * count\n\n"
                "def is_valid(url, timeout=30):\n"
                "    return True\n"
            )
            ann = _get_ann()
            suggestions = ann.annotate(source)
            lines = ["Type annotation suggestions:", ""]
            for s in suggestions:
                lines.append(f"# line {s.lineno}")
                lines.append(f"  {s.signature()}")
                for p in s.params:
                    lines.append(f"    {p.name}: {p.suggested_type} "
                                 f"(confidence: {p.confidence:.0%}, reason: {p.reason})")
                if s.return_type:
                    lines.append(f"    -> {s.return_type} "
                                 f"(confidence: {s.return_confidence:.0%})")
                lines.append("")
            return "\n".join(lines)

        if sub == "analyze":
            if not rest:
                return "Usage: /annotate analyze <python source>"
            try:
                ann = _get_ann()
                suggestions = ann.annotate(rest)
                if not suggestions:
                    return "No annotation suggestions (source may already be annotated)."
                lines = []
                for s in suggestions:
                    lines.append(f"  def {s.name}() → {s.signature()}")
                return "\n".join(lines)
            except AnnotatorError as exc:
                return f"Error: {exc}"

        if sub == "coverage":
            if not rest:
                return "Usage: /annotate coverage <python source>"
            try:
                ann = _get_ann()
                cov = ann.coverage(rest)
                param_pct = cov["param_coverage"] * 100
                ret_pct = cov["return_coverage"] * 100
                return (
                    f"Type annotation coverage:\n"
                    f"  Params:  {param_pct:.0f}% "
                    f"({cov['annotated_params']}/{cov['total_params']})\n"
                    f"  Returns: {ret_pct:.0f}% "
                    f"({cov['annotated_returns']}/{cov['total_returns']})"
                )
            except AnnotatorError as exc:
                return f"Error: {exc}"

        if sub == "suggest":
            if not rest:
                return "Usage: /annotate suggest <name>"
            # Use the annotator's naming heuristic
            ann = _get_ann()
            # Build a tiny snippet to test
            source = f"def f({rest}): pass\n"
            try:
                suggestions = ann.annotate(source)
                if suggestions and suggestions[0].params:
                    p = suggestions[0].params[0]
                    return f"{rest}: {p.suggested_type} ({p.confidence:.0%} confidence — {p.reason})"
                return f"{rest}: No suggestion (no naming convention matched)"
            except AnnotatorError as exc:
                return f"Error: {exc}"

        if sub == "confidence":
            if not rest:
                return f"Min confidence: {_state.get('annotate_confidence', 0.5)}"
            try:
                _state["annotate_confidence"] = float(rest)
                return f"Min confidence set to {rest}"
            except ValueError:
                return f"Invalid confidence: {rest!r} (must be 0.0–1.0)"

        return (
            "Usage: /annotate <sub>\n"
            "  demo                — show annotation demo\n"
            "  analyze <source>    — suggest annotations for source\n"
            "  coverage <source>   — show annotation coverage %\n"
            "  suggest <param>     — suggest type for a param name\n"
            "  confidence [N]      — get/set min confidence threshold"
        )

    # ------------------------------------------------------------------ #
    # /stash — git stash manager                                           #
    # ------------------------------------------------------------------ #

    async def stash_handler(args: str) -> str:
        from lidco.git.stash_manager import StashManager, StashError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_mgr() -> StashManager:
            if "stash_mgr" not in _state:
                _state["stash_mgr"] = StashManager()
            return _state["stash_mgr"]  # type: ignore[return-value]

        if sub == "demo":
            lines = [
                "Git Stash Manager demo:",
                "",
                "Commands:",
                "  /stash list                 — list all stashes",
                "  /stash push [message]       — stash current changes",
                "  /stash pop [index]          — apply + remove stash",
                "  /stash apply [ref]          — apply without removing",
                "  /stash drop [index]         — drop a stash",
                "  /stash show [index]         — show stash diff",
                "  /stash summary              — count + list",
            ]
            return "\n".join(lines)

        if sub == "list":
            try:
                mgr = _get_mgr()
                entries = mgr.list()
                if not entries:
                    return "No stashes found."
                return "\n".join(str(e) for e in entries)
            except StashError as exc:
                return f"Error: {exc}"

        if sub == "push":
            msg = rest.strip()
            try:
                mgr = _get_mgr()
                result = mgr.push(message=msg)
                if result.success:
                    entry_info = str(result.entry) if result.entry else ""
                    return f"Stashed: {entry_info or result.output}"
                return f"Failed: {result.output}"
            except StashError as exc:
                return f"Error: {exc}"

        if sub == "pop":
            idx = int(rest) if rest.isdigit() else 0
            try:
                mgr = _get_mgr()
                result = mgr.pop(idx)
                return result.output if result.success else f"Failed: {result.output}"
            except StashError as exc:
                return f"Error: {exc}"

        if sub == "apply":
            ref = rest or "stash@{0}"
            try:
                mgr = _get_mgr()
                result = mgr.apply(ref)
                return result.output if result.success else f"Failed: {result.output}"
            except StashError as exc:
                return f"Error: {exc}"

        if sub == "drop":
            idx = int(rest) if rest.isdigit() else 0
            try:
                mgr = _get_mgr()
                result = mgr.drop(idx)
                return result.output if result.success else f"Failed: {result.output}"
            except StashError as exc:
                return f"Error: {exc}"

        if sub == "show":
            idx = int(rest) if rest.isdigit() else 0
            try:
                mgr = _get_mgr()
                return mgr.show(idx) or "(empty diff)"
            except StashError as exc:
                return f"Error: {exc}"

        if sub == "summary":
            try:
                mgr = _get_mgr()
                s = mgr.summary()
                lines = [f"Total stashes: {s['count']}"]
                for entry in s["stashes"]:
                    lines.append(f"  {entry}")
                return "\n".join(lines)
            except StashError as exc:
                return f"Error: {exc}"

        if sub == "count":
            try:
                mgr = _get_mgr()
                return f"Stash count: {mgr.count()}"
            except StashError as exc:
                return f"Error: {exc}"

        return (
            "Usage: /stash <sub>\n"
            "  demo              — show command overview\n"
            "  list              — list all stashes\n"
            "  push [message]    — stash current changes\n"
            "  pop [index]       — apply + remove stash\n"
            "  apply [ref]       — apply without removing\n"
            "  drop [index]      — drop a stash\n"
            "  show [index]      — show stash diff\n"
            "  summary           — stash count + list\n"
            "  count             — number of stashes"
        )

    # ------------------------------------------------------------------ #
    # /fixture — pytest fixture generator                                  #
    # ------------------------------------------------------------------ #

    async def fixture_handler(args: str) -> str:
        from lidco.testing.fixture_gen import FixtureGenerator, FixtureGenError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_gen() -> FixtureGenerator:
            scope = str(_state.get("fixture_scope", "function"))
            return FixtureGenerator(scope=scope)

        if sub == "demo":
            source = (
                "from dataclasses import dataclass\n\n"
                "@dataclass\n"
                "class User:\n"
                "    name: str\n"
                "    age: int\n"
                "    email: str = ''\n"
                "    is_active: bool = True\n\n"
                "@dataclass\n"
                "class Product:\n"
                "    title: str\n"
                "    price: float\n"
                "    count: int = 0\n"
            )
            gen = _get_gen()
            module_code = gen.generate_module(source)
            return f"Generated fixtures:\n\n{module_code}"

        if sub == "generate":
            if not rest:
                return "Usage: /fixture generate <python source>"
            try:
                gen = _get_gen()
                module_code = gen.generate_module(rest)
                return module_code
            except FixtureGenError as exc:
                return f"Error: {exc}"

        if sub == "class":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /fixture class <ClassName> <python source>"
            class_name, source = tokens[0], tokens[1]
            try:
                gen = _get_gen()
                fixture = gen.generate_for_class(source, class_name)
                if fixture is None:
                    return f"Class not found: {class_name!r}"
                return fixture.code
            except FixtureGenError as exc:
                return f"Error: {exc}"

        if sub == "parse":
            if not rest:
                return "Usage: /fixture parse <python source>"
            try:
                gen = _get_gen()
                classes = gen.parse_classes(rest)
                if not classes:
                    return "No classes found."
                lines = []
                for cls in classes:
                    fields_info = ", ".join(
                        f"{f.name}: {f.type_annotation or '?'}" for f in cls.fields
                    )
                    lines.append(f"  {cls.name}({fields_info})")
                return "\n".join(lines)
            except FixtureGenError as exc:
                return f"Error: {exc}"

        if sub == "scope":
            if not rest:
                return f"Current scope: {_state.get('fixture_scope', 'function')}"
            if rest not in ("function", "class", "module", "session"):
                return f"Invalid scope: {rest!r}. Options: function, class, module, session"
            _state["fixture_scope"] = rest
            return f"Fixture scope set to: {rest}"

        return (
            "Usage: /fixture <sub>\n"
            "  demo                        — show fixture demo\n"
            "  generate <source>           — generate fixtures for all classes\n"
            "  class <Name> <source>       — generate fixture for one class\n"
            "  parse <source>              — parse class fields\n"
            "  scope [function|module|...] — get/set fixture scope"
        )

    # ------------------------------------------------------------------ #
    # /liveness — service health checker                                   #
    # ------------------------------------------------------------------ #

    async def liveness_handler(args: str) -> str:
        from lidco.liveness.checker import LivenessChecker, CheckError, CheckResult, CheckStatus

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_checker() -> LivenessChecker:
            if "liveness" not in _state:
                _state["liveness"] = LivenessChecker(timeout=3.0)
            return _state["liveness"]  # type: ignore[return-value]

        if sub == "demo":
            checker = LivenessChecker(timeout=1.0)
            checker.add_custom("always-up", lambda: CheckResult(
                name="always-up", status=CheckStatus.UP, latency_ms=1.2,
                message="custom check passed"))
            checker.add_custom("always-down", lambda: CheckResult(
                name="always-down", status=CheckStatus.DOWN, latency_ms=0.5,
                message="simulated failure"))
            report = checker.run_all()
            return report.format()

        if sub == "add-http":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /liveness add-http <name> <url>"
            name, url = tokens[0], tokens[1]
            try:
                checker = _get_checker()
                checker.add_http(name, url)
                return f"HTTP check added: {name} → {url}"
            except CheckError as exc:
                return f"Error: {exc}"

        if sub == "add-tcp":
            tokens = rest.split()
            if len(tokens) < 3:
                return "Usage: /liveness add-tcp <name> <host> <port>"
            name, host, port_s = tokens[0], tokens[1], tokens[2]
            try:
                checker = _get_checker()
                checker.add_tcp(name, host, int(port_s))
                return f"TCP check added: {name} → {host}:{port_s}"
            except (CheckError, ValueError) as exc:
                return f"Error: {exc}"

        if sub == "check":
            name = rest.strip()
            if not name:
                return "Usage: /liveness check <name>"
            checker = _get_checker()
            try:
                result = checker.run(name)
                return result.format()
            except CheckError as exc:
                return f"Error: {exc}"

        if sub == "run":
            checker = _get_checker()
            if len(checker) == 0:
                return "No checks registered. Use '/liveness add-http' or '/liveness add-tcp'."
            report = checker.run_all()
            return report.format()

        if sub == "list":
            checker = _get_checker()
            checks = checker.list_checks()
            if not checks:
                return "No checks registered."
            return "Registered checks:\n" + "\n".join(f"  - {c}" for c in checks)

        if sub == "remove":
            if not rest:
                return "Usage: /liveness remove <name>"
            checker = _get_checker()
            if checker.remove(rest):
                return f"Removed: {rest}"
            return f"Check not found: {rest!r}"

        if sub == "reset":
            _state.pop("liveness", None)
            return "Liveness checker reset."

        return (
            "Usage: /liveness <sub>\n"
            "  demo                       — run demo checks\n"
            "  add-http <name> <url>      — add HTTP check\n"
            "  add-tcp <name> <host> <p>  — add TCP check\n"
            "  check <name>               — run one check\n"
            "  run                        — run all checks\n"
            "  list                       — list registered checks\n"
            "  remove <name>              — remove a check\n"
            "  reset                      — clear all checks"
        )

    registry.register(SlashCommand("annotate", "Type annotation suggester", annotate_handler))
    registry.register(SlashCommand("stash", "Git stash manager", stash_handler))
    registry.register(SlashCommand("fixture", "Pytest fixture generator", fixture_handler))
    registry.register(SlashCommand("liveness", "Service liveness checker", liveness_handler))
