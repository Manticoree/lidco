"""Tool registry for managing available tools."""

from __future__ import annotations

from typing import Any

from lidco.tools.base import BaseTool


class ToolRegistry:
    """Registry for discovering and managing tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._schema_cache: list[dict[str, Any]] | None = None
        self._schema_version: int = 0

    @property
    def schema_version(self) -> int:
        """Monotonically increasing counter — bumped on every ``register()`` call.

        Consumers (e.g. ``BaseAgent``) can compare this value between calls to
        detect when the tool set has changed and cached schema payloads are stale.
        """
        return self._schema_version

    def register(self, tool: BaseTool) -> None:
        """Register a tool and invalidate any cached schemas."""
        self._tools[tool.name] = tool
        self._schema_cache = None
        self._schema_version += 1

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """List all tool names."""
        return list(self._tools.keys())

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry. Returns True if found and removed."""
        if name in self._tools:
            del self._tools[name]
            self._schema_cache = None
            self._schema_version += 1
            return True
        return False

    def get_openai_schemas(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        """Get OpenAI function schemas for specified tools (or all).

        When ``tool_names`` is ``None`` the result is cached and reused until the
        next ``register()`` call.  Filtered requests bypass the cache because the
        subset varies per caller.
        """
        if tool_names is not None:
            tools = [self._tools[n] for n in tool_names if n in self._tools]
            return [t.to_openai_schema() for t in tools]

        if self._schema_cache is None:
            self._schema_cache = [t.to_openai_schema() for t in self._tools.values()]
        return list(self._schema_cache)

    @staticmethod
    def create_default_registry() -> ToolRegistry:
        """Create a registry with all built-in tools."""
        from lidco.tools.arch_diagram import ArchDiagramTool
        from lidco.tools.code_runner import CodeRunnerTool
        from lidco.tools.coverage_guard import CoverageGuardTool
        from lidco.tools.docker_sandbox import DockerSandboxTool
        from lidco.tools.flake_guard import FlakeGuardTool
        from lidco.tools.trace_inspector import TraceInspectorTool
        from lidco.tools.ask_user import AskUserTool
        from lidco.tools.ast_checker import ASTBugCheckerTool
        from lidco.tools.dep_checker import DependencyCheckerTool
        from lidco.tools.import_analyzer import ImportAnalyzerTool
        from lidco.tools.bash import BashTool
        from lidco.tools.diff import DiffTool
        from lidco.tools.file_edit import FileEditTool
        from lidco.tools.file_read import FileReadTool
        from lidco.tools.file_write import FileWriteTool
        from lidco.tools.gh_pr import GHPRTool
        from lidco.tools.git import GitTool
        from lidco.tools.glob import GlobTool
        from lidco.tools.grep import GrepTool
        from lidco.tools.profiler import ProfilerTool
        from lidco.tools.regression_guard import RegressionGuardTool
        from lidco.tools.rename import RenameSymbolTool
        from lidco.tools.repro_generator import ReproGeneratorTool
        from lidco.tools.static_analyzer import StaticAnalyzerTool
        from lidco.tools.test_autopilot import TestAutopilotTool
        from lidco.tools.test_gap import TestGapTool
        from lidco.tools.test_inspector import TestInspectorTool
        from lidco.tools.test_runner import RunTestsTool
        from lidco.tools.tree import TreeTool
        from lidco.tools.web_fetch import WebFetchTool
        from lidco.tools.web_search import WebSearchTool

        registry = ToolRegistry()
        for tool in [
            FileReadTool(),
            FileWriteTool(),
            FileEditTool(),
            BashTool(),
            GlobTool(),
            GrepTool(),
            GitTool(),
            AskUserTool(),
            WebSearchTool(),
            WebFetchTool(),
            DiffTool(),
            TreeTool(),
            GHPRTool(),
            ProfilerTool(),
            RunTestsTool(),
            RenameSymbolTool(),
            TestGapTool(),
            ArchDiagramTool(),
            # Q19-Q22 debug tools
            ImportAnalyzerTool(),
            DependencyCheckerTool(),
            TestAutopilotTool(),
            StaticAnalyzerTool(),
            ASTBugCheckerTool(),
            TestInspectorTool(),
            RegressionGuardTool(),
            ReproGeneratorTool(),
            # Q24 flaky test intelligence
            FlakeGuardTool(),
            # Q25 coverage-guided debug intelligence
            CoverageGuardTool(),
            # Q26 execution trace recorder
            TraceInspectorTool(),
            # Q59 code execution & runtime
            CodeRunnerTool(),
            DockerSandboxTool(),
        ]:
            registry.register(tool)
        return registry
