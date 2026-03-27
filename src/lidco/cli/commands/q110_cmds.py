"""Q110 CLI commands: /semver /mock /conflict /format."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q110 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /semver                                                               #
    # ------------------------------------------------------------------ #

    async def semver_handler(args: str) -> str:
        from lidco.versioning.semver import (
            Version, VersionRange, SemVerError,
            parse, compare, sort_versions, latest, satisfies,
        )

        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "demo":
            v = Version.parse("1.2.3-alpha.1")
            lines = [
                "SemVer demo:",
                f"  parse '1.2.3-alpha.1' → {v}",
                f"  bump_major → {v.bump_major()}",
                f"  bump_minor → {v.bump_minor()}",
                f"  bump_patch → {v.bump_patch()}",
                f"  is_stable → {Version.parse('1.0.0').is_stable()}",
                f"  is_prerelease → {v.is_prerelease()}",
                "",
                "Range matching:",
                f"  '1.2.5' satisfies '^1.2.0' → {satisfies('1.2.5', '^1.2.0')}",
                f"  '2.0.0' satisfies '^1.2.0' → {satisfies('2.0.0', '^1.2.0')}",
                f"  '1.2.3' satisfies '~1.2.0' → {satisfies('1.2.3', '~1.2.0')}",
                f"  '1.3.0' satisfies '~1.2.0' → {satisfies('1.3.0', '~1.2.0')}",
                "",
                "Sorting:",
                f"  {sort_versions(['2.0.0','1.0.0','1.2.3','0.9.0'])}",
            ]
            return "\n".join(lines)

        if sub == "parse":
            ver = parts[1] if len(parts) > 1 else ""
            if not ver:
                return "Usage: /semver parse <version>"
            try:
                v = Version.parse(ver)
                return (
                    f"Version: {v}\n"
                    f"  major={v.major}, minor={v.minor}, patch={v.patch}\n"
                    f"  pre={v.pre!r}, build={v.build!r}\n"
                    f"  stable={v.is_stable()}, prerelease={v.is_prerelease()}"
                )
            except SemVerError as exc:
                return f"Error: {exc}"

        if sub == "bump":
            ver = parts[1] if len(parts) > 1 else ""
            part = parts[2] if len(parts) > 2 else "patch"
            if not ver:
                return "Usage: /semver bump <version> [major|minor|patch]"
            try:
                v = Version.parse_loose(ver)
                bumped = {"major": v.bump_major, "minor": v.bump_minor,
                          "patch": v.bump_patch}.get(part.lower(), v.bump_patch)()
                return f"{ver} → {bumped} ({part})"
            except SemVerError as exc:
                return f"Error: {exc}"

        if sub == "compare":
            a = parts[1] if len(parts) > 1 else ""
            b = parts[2] if len(parts) > 2 else ""
            if not a or not b:
                return "Usage: /semver compare <v1> <v2>"
            try:
                result = compare(a, b)
                sym = {-1: "<", 0: "==", 1: ">"}[result]
                return f"{a} {sym} {b}"
            except SemVerError as exc:
                return f"Error: {exc}"

        if sub == "satisfies":
            ver = parts[1] if len(parts) > 1 else ""
            spec = parts[2] if len(parts) > 2 else ""
            if not ver or not spec:
                return "Usage: /semver satisfies <version> <range>"
            try:
                result = satisfies(ver, spec)
                return f"'{ver}' satisfies '{spec}': {result}"
            except SemVerError as exc:
                return f"Error: {exc}"

        if sub == "sort":
            vers = parts[1:]
            if not vers:
                return "Usage: /semver sort <v1> <v2> ..."
            # flatten remaining args
            all_args = args.split()[1:]
            try:
                return " ".join(sort_versions(all_args))
            except SemVerError as exc:
                return f"Error: {exc}"

        if sub == "latest":
            all_args = args.split()[1:]
            if not all_args:
                return "Usage: /semver latest <v1> <v2> ..."
            try:
                return latest(all_args) or "(none)"
            except SemVerError as exc:
                return f"Error: {exc}"

        if sub == "next":
            ver = parts[1] if len(parts) > 1 else ""
            if not ver:
                return "Usage: /semver next <version>"
            try:
                v = Version.parse_loose(ver)
                nexts = v.next_versions()
                return "\n".join(f"  {k}: {nv}" for k, nv in nexts.items())
            except SemVerError as exc:
                return f"Error: {exc}"

        return (
            "Usage: /semver <sub>\n"
            "  demo                      — show full demo\n"
            "  parse <ver>               — parse and inspect version\n"
            "  bump <ver> [major|minor|patch] — bump version\n"
            "  compare <v1> <v2>         — compare two versions\n"
            "  satisfies <ver> <range>   — check range satisfaction\n"
            "  sort <v1> <v2> ...        — sort versions\n"
            "  latest <v1> <v2> ...      — find latest\n"
            "  next <ver>                — show all next versions"
        )

    # ------------------------------------------------------------------ #
    # /mock                                                                 #
    # ------------------------------------------------------------------ #

    async def mock_handler(args: str) -> str:
        from lidco.testing.mock_gen import MockGenerator, MockGenError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "demo":
            source = (
                "class UserService:\n"
                "    def get_user(self, user_id: int) -> dict:\n"
                "        ...\n"
                "    def create_user(self, name: str) -> bool:\n"
                "        ...\n"
                "    async def fetch_remote(self) -> list:\n"
                "        ...\n"
            )
            gen = MockGenerator()
            mocks = gen.generate(source)
            lines = ["Mock generation demo:", ""]
            for m in mocks:
                lines.append(f"# Setup for {m.class_name}")
                lines.append(m.setup_code)
                lines.append("")
                lines.append("# Pytest fixture:")
                lines.append(m.fixture_code)
            return "\n".join(lines)

        if sub == "generate":
            if not rest:
                return "Usage: /mock generate <python source>"
            try:
                gen = MockGenerator()
                mocks = gen.generate(rest)
                if not mocks:
                    return "No classes found."
                return "\n\n".join(m.setup_code for m in mocks)
            except MockGenError as exc:
                return f"Error: {exc}"

        if sub == "fixture":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /mock fixture <ClassName> <python source>"
            class_name, source = tokens[0], tokens[1]
            try:
                gen = MockGenerator()
                m = gen.generate_for_class(source, class_name)
                if m is None:
                    return f"Class not found: {class_name!r}"
                return m.fixture_code
            except MockGenError as exc:
                return f"Error: {exc}"

        if sub == "patch":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /mock patch <ClassName> <python source>"
            class_name, source = tokens[0], tokens[1]
            try:
                gen = MockGenerator()
                return gen.generate_patch_test(source, class_name)
            except MockGenError as exc:
                return f"Error: {exc}"

        if sub == "parse":
            if not rest:
                return "Usage: /mock parse <python source>"
            try:
                gen = MockGenerator()
                specs = gen.parse_classes(rest)
                if not specs:
                    return "No classes found."
                lines = []
                for spec in specs:
                    methods = [m.name for m in spec.methods]
                    lines.append(f"  {spec.class_name}: {methods}")
                return "\n".join(lines)
            except MockGenError as exc:
                return f"Error: {exc}"

        return (
            "Usage: /mock <sub>\n"
            "  demo                        — show mock generation demo\n"
            "  generate <source>           — generate setup for all classes\n"
            "  fixture <Name> <source>     — generate pytest fixture\n"
            "  patch <Name> <source>       — generate patch test\n"
            "  parse <source>              — parse class structure"
        )

    # ------------------------------------------------------------------ #
    # /conflict                                                             #
    # ------------------------------------------------------------------ #

    async def conflict_handler(args: str) -> str:
        from lidco.git.conflict_resolver import ConflictResolver, Resolution, ConflictError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "demo":
            content = (
                "# module.py\n"
                "<<<<<<< HEAD\n"
                "VERSION = '2.0.0'\n"
                "=======\n"
                "VERSION = '1.9.0'\n"
                ">>>>>>> feature/upgrade\n"
                "\n"
                "<<<<<<< HEAD\n"
                "=======\n"
                "# Added by feature branch\n"
                "EXTRA = True\n"
                ">>>>>>> feature/upgrade\n"
            )
            resolver = ConflictResolver()
            conflicts = resolver.parse(content)
            lines = [f"Found {len(conflicts)} conflict(s):", ""]
            for c in conflicts:
                lines.append(f"  {c.summary()}")
            result = resolver.auto_resolve(content)
            lines.append("")
            lines.append(f"Auto-resolve: {result.summary()}")
            lines.append("")
            lines.append("Resolved content:")
            lines.append(result.content)
            return "\n".join(lines)

        if sub == "parse":
            if not rest:
                return "Usage: /conflict parse <file content with conflict markers>"
            resolver = ConflictResolver()
            conflicts = resolver.parse(rest)
            if not conflicts:
                return "No conflicts found."
            return "\n".join(c.summary() for c in conflicts)

        if sub == "count":
            if not rest:
                return "Usage: /conflict count <file content>"
            resolver = ConflictResolver()
            n = resolver.count(rest)
            return f"{n} conflict(s) found"

        if sub == "resolve":
            if not rest:
                return "Usage: /conflict resolve <file content>"
            resolver = ConflictResolver()
            result = resolver.auto_resolve(rest)
            return f"{result.summary()}\n\n{result.content}"

        if sub == "check":
            if not rest:
                return "Usage: /conflict check <file content>"
            resolver = ConflictResolver()
            has = resolver.has_conflicts(rest)
            return f"Has conflicts: {has}"

        if sub == "summary":
            if not rest:
                return "Usage: /conflict summary <file content>"
            resolver = ConflictResolver()
            conflicts = resolver.parse(rest)
            s = resolver.diff_summary(conflicts)
            lines = [f"Conflicts: {s['total']}",
                     f"Auto-resolvable: {s['auto_resolvable']}",
                     f"By type: {s['by_type']}",
                     f"By suggestion: {s['by_suggestion']}"]
            return "\n".join(lines)

        return (
            "Usage: /conflict <sub>\n"
            "  demo              — show conflict resolution demo\n"
            "  parse <content>   — parse conflict markers\n"
            "  count <content>   — count conflicts\n"
            "  check <content>   — check if conflicts exist\n"
            "  resolve <content> — auto-resolve and show result\n"
            "  summary <content> — show conflict analysis"
        )

    # ------------------------------------------------------------------ #
    # /format                                                               #
    # ------------------------------------------------------------------ #

    async def format_handler(args: str) -> str:
        from lidco.format.formatter import FormatterRegistry, FormatterKind, FormatterError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_reg() -> FormatterRegistry:
            if "fmt_registry" not in _state:
                _state["fmt_registry"] = FormatterRegistry.with_defaults()
            return _state["fmt_registry"]  # type: ignore[return-value]

        if sub == "demo":
            reg = FormatterRegistry.with_defaults()
            s = reg.summary()
            lines = [
                "Formatter Registry demo:",
                f"  Registered formatters: {len(reg)}",
                "",
                "Available formatters:",
            ]
            for name in s["registered"]:
                cfg = reg.get(name)
                exts = ", ".join(cfg.file_extensions) if cfg else ""
                lines.append(f"  {name} — files: {exts or 'all'}")
            lines.append("")
            lines.append("Use '/format available <name>' to check if installed.")
            return "\n".join(lines)

        if sub == "list":
            reg = _get_reg()
            names = reg.list_available()
            if not names:
                return "No formatters registered."
            return "Formatters: " + ", ".join(names)

        if sub == "available":
            name = rest.strip()
            if not name:
                reg = _get_reg()
                results = []
                for n in reg.list_available():
                    avail = reg.is_available(n)
                    results.append(f"  {n}: {'✓ installed' if avail else '✗ not found'}")
                return "Formatter availability:\n" + "\n".join(results)
            reg = _get_reg()
            avail = reg.is_available(name)
            return f"{name}: {'installed' if avail else 'not found'}"

        if sub == "detect":
            root = rest.strip() or "."
            reg = FormatterRegistry()
            detected = reg.detect(root)
            if not detected:
                return f"No formatters detected in {root!r}"
            return f"Detected: {', '.join(detected)}"

        if sub == "summary":
            reg = _get_reg()
            s = reg.summary()
            return f"Registered: {s['count']} — {', '.join(s['registered'])}"

        if sub == "reset":
            _state.pop("fmt_registry", None)
            return "Formatter registry reset."

        return (
            "Usage: /format <sub>\n"
            "  demo              — show formatter registry demo\n"
            "  list              — list registered formatters\n"
            "  available [name]  — check if formatter(s) installed\n"
            "  detect [path]     — detect formatters from config files\n"
            "  summary           — show registry summary\n"
            "  reset             — reset registry"
        )

    registry.register(SlashCommand("semver", "Semantic version tool", semver_handler))
    registry.register(SlashCommand("mock", "Mock generator for tests", mock_handler))
    registry.register(SlashCommand("conflict", "Git conflict resolver", conflict_handler))
    registry.register(SlashCommand("format", "Code formatter registry", format_handler))
