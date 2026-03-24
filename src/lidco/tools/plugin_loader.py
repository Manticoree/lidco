"""Load user-defined tool plugins from .lidco/tools/*.py files."""

import ast
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PluginInfo:
    """Metadata about a discovered plugin."""

    name: str
    description: str
    source_path: str
    loaded: bool
    error: str = ""


@dataclass
class PluginManifest:
    """Summary of all discovered plugins."""

    plugins: list = field(default_factory=list)
    total: int = 0
    loaded: int = 0
    failed: int = 0

    def format_summary(self) -> str:
        return f"Plugins: {self.loaded}/{self.total} loaded, {self.failed} failed"


class ToolPluginLoader:
    """Discovers and loads tool plugins from .lidco/tools/ and ~/.lidco/tools/.

    Project-level plugins (.lidco/tools/) override global ones (~/.lidco/tools/)
    when they share the same stem name.  Plugins are validated via AST before
    dynamic import to reject dangerous calls (eval, exec, os.system, etc.).
    """

    DANGEROUS_CALLS = {"eval", "exec", "compile", "__import__"}

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root)

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    def _project_tools_dir(self) -> Path:
        return self.project_root / ".lidco" / "tools"

    def _global_tools_dir(self) -> Path:
        return Path.home() / ".lidco" / "tools"

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[Path]:
        """Scan .lidco/tools/*.py (project) and ~/.lidco/tools/*.py (global).

        Project-level plugins override global ones with the same stem name.
        Results are sorted by stem for deterministic ordering.
        """
        project_dir = self._project_tools_dir()
        global_dir = self._global_tools_dir()

        # Collect global first, then project overrides
        plugins: dict[str, Path] = {}
        for d in [global_dir, project_dir]:
            if d.exists():
                for f in sorted(d.glob("*.py")):
                    plugins[f.stem] = f

        return list(dict(sorted(plugins.items())).values())

    # ------------------------------------------------------------------
    # Validation (AST-only, no execution)
    # ------------------------------------------------------------------

    def validate_plugin(self, path: Path) -> tuple[bool, str]:
        """AST-only validation.

        Checks:
        - Valid Python syntax
        - Has a ``register()`` function or a ``BaseTool`` subclass
        - No dangerous built-in calls at any level (eval, exec, compile,
          __import__, os.system, os.popen)
        """
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError) as exc:
            return False, f"Parse error: {exc}"

        # Scan for dangerous calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in self.DANGEROUS_CALLS:
                    return False, f"Dangerous call: {node.func.id}()"
                if isinstance(node.func, ast.Attribute):
                    value_id = getattr(node.func.value, "id", "")
                    if node.func.attr in {"system", "popen"} and value_id == "os":
                        full = f"{value_id}.{node.func.attr}"
                        return False, f"Dangerous call: {full}()"

        # Require register() function or BaseTool subclass
        has_register = any(
            isinstance(n, ast.FunctionDef) and n.name == "register"
            for n in ast.walk(tree)
        )
        has_base_tool = any(
            isinstance(n, ast.ClassDef)
            and any(
                (isinstance(b, ast.Attribute) and b.attr == "BaseTool")
                or (isinstance(b, ast.Name) and b.id == "BaseTool")
                for b in n.bases
            )
            for n in ast.walk(tree)
        )
        if not has_register and not has_base_tool:
            return False, "No register() function or BaseTool subclass found"

        return True, ""

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_plugin(self, path: Path) -> PluginInfo:
        """Validate then dynamically load a single plugin file.

        Returns a :class:`PluginInfo` regardless of success or failure.
        """
        valid, err = self.validate_plugin(path)
        if not valid:
            return PluginInfo(
                name=path.stem,
                description="",
                source_path=str(path),
                loaded=False,
                error=err,
            )
        try:
            spec = importlib.util.spec_from_file_location(
                f"lidco_plugin_{path.stem}", path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            desc = (
                getattr(module, "__description__", "")
                or getattr(module, "__doc__", "")
                or ""
            )
            return PluginInfo(
                name=path.stem,
                description=desc.strip(),
                source_path=str(path),
                loaded=True,
            )
        except Exception as exc:  # noqa: BLE001
            return PluginInfo(
                name=path.stem,
                description="",
                source_path=str(path),
                loaded=False,
                error=str(exc),
            )

    def load_all(self) -> PluginManifest:
        """Load all discovered plugins.  Failures are isolated per-plugin."""
        paths = self.discover()
        plugins = [self.load_plugin(p) for p in paths]
        loaded = sum(1 for p in plugins if p.loaded)
        failed = sum(1 for p in plugins if not p.loaded)
        return PluginManifest(
            plugins=plugins,
            total=len(plugins),
            loaded=loaded,
            failed=failed,
        )

    def get_tool_from_plugin(self, path: Path) -> Any:
        """Return an instance of the first ``BaseTool`` subclass in the module.

        Returns ``None`` if validation fails, no subclass is found, or
        instantiation raises.
        """
        info = self.load_plugin(path)
        if not info.loaded:
            return None
        try:
            spec = importlib.util.spec_from_file_location(
                f"lidco_plugin_tool_{path.stem}", path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (
                    isinstance(obj, type)
                    and obj.__name__ != "BaseTool"
                    and hasattr(obj, "__mro__")
                ):
                    for base in obj.__mro__:
                        if base.__name__ == "BaseTool":
                            return obj()
        except Exception:  # noqa: BLE001
            pass
        return None
