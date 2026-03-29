"""Q123 CLI commands: /gen."""
from __future__ import annotations

_state: dict = {}


def register(registry) -> None:
    """Register Q123 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def gen_handler(args: str) -> str:
        from lidco.codegen.registry import CodegenRegistry
        from lidco.codegen.class_template import ClassTemplate, ClassConfig
        from lidco.codegen.test_template import TestTemplate, TestConfig
        from lidco.codegen.module_template import ModuleTemplate, ModuleConfig

        if "codegen" not in _state:
            _state["codegen"] = CodegenRegistry.with_defaults()
        codegen: CodegenRegistry = _state["codegen"]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "class":
            name = rest.strip() or "MyClass"
            config = ClassConfig(name=name, fields=[("value", "str")])
            ct = ClassTemplate()
            content = ct.render(config)
            return f"Generated class '{name}':\n{content}"

        if sub == "test":
            name = rest.strip() or "MyModule"
            config = TestConfig(
                module_name=name,
                class_names=[name],
                methods=["init", "basic_operation"],
                import_path=f"lidco.{name.lower()}",
            )
            tt = TestTemplate()
            content = tt.render(config)
            return f"Generated test for '{name}':\n{content}"

        if sub == "module":
            name = rest.strip() or "my_module"
            config = ModuleConfig(
                name=name,
                description=f"{name} module",
                imports=["from __future__ import annotations"],
                exports=[],
                docstring=f"{name} — auto-generated module.",
            )
            mt = ModuleTemplate()
            content = mt.render(config)
            return f"Generated module '{name}':\n{content}"

        if sub == "list":
            templates = codegen.list_templates()
            if not templates:
                return "No templates registered."
            return "Available templates:\n" + "\n".join(f"  {t}" for t in templates)

        return (
            "Usage: /gen <sub>\n"
            "  class <name>   -- generate Python class\n"
            "  test <name>    -- generate pytest test file\n"
            "  module <name>  -- generate Python module\n"
            "  list           -- list available templates"
        )

    registry.register(SlashCommand("gen", "Code generation templates", gen_handler))
