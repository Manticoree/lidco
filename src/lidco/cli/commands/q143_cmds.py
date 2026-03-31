"""Q143 CLI commands: /diag."""

from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q143 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def diag_handler(args: str) -> str:
        from lidco.diagnostics.env_checker import EnvironmentChecker
        from lidco.diagnostics.dep_checker import DependencyChecker
        from lidco.diagnostics.benchmark import PerfBenchmark
        from lidco.diagnostics.system_info import SystemInfo

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "env":
            checker = EnvironmentChecker()
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "var":
                var_name = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                if not var_name:
                    return "Usage: /diag env var <NAME>"
                result = checker.check_env_var(var_name)
                return f"[{result.status}] {result.name}: {result.message}"
            if action == "dir":
                dir_path = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                if not dir_path:
                    return "Usage: /diag env dir <PATH>"
                result = checker.check_directory(dir_path)
                return f"[{result.status}] {result.name}: {result.message}"
            if action == "python":
                ver = sub_parts[1].strip() if len(sub_parts) > 1 else "3.10"
                result = checker.check_python_version(ver)
                return f"[{result.status}] {result.name}: {result.message}"
            # default: run all checks
            checker.check_all()
            return checker.summary()

        if sub == "deps":
            dep_checker = DependencyChecker()
            sub_parts = rest.split()
            if sub_parts:
                results = dep_checker.check_all(sub_parts)
                return dep_checker.summary()
            # default: check common deps
            dep_checker.check_all(["rich", "litellm", "langgraph"])
            return dep_checker.summary()

        if sub == "bench":
            bench = PerfBenchmark()
            # Built-in quick benchmark
            import hashlib
            result = bench.run("hashlib_md5", lambda: hashlib.md5(b"hello world").hexdigest(), iterations=1000)
            return bench.format_result(result)

        if sub == "system":
            info = SystemInfo()
            report = info.collect()
            warnings = info.check_compatibility()
            text = info.format_report(report)
            if warnings:
                text += "\nWarnings:\n" + "\n".join(f"  - {w}" for w in warnings)
            return text

        return "Usage: /diag <env|deps|bench|system>"

    registry.register(SlashCommand("diag", "System diagnostics & health checks", diag_handler))
