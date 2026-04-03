"""Q252 CLI commands: /generate, /scaffold, /crud, /generate-migration."""
from __future__ import annotations


def register(registry) -> None:  # type: ignore[type-arg]
    """Register Q252 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /generate
    # ------------------------------------------------------------------

    async def generate_handler(args: str) -> str:
        from lidco.codegen.template_v2 import Template, TemplateEngineV2

        engine = TemplateEngineV2()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "register":
            # /generate register <name> <lang> <body>
            tokens = rest.split(maxsplit=2)
            if len(tokens) < 3:
                return "Usage: /generate register <name> <language> <body>"
            tpl = Template(name=tokens[0], language=tokens[1], body=tokens[2])
            engine.register(tpl)
            return f"Registered template: {tpl.name}"

        if sub == "render":
            return "Usage: /generate render <name> — requires registered templates."

        if sub == "list":
            templates = engine.list_templates()
            if not templates:
                return "No templates registered."
            return "\n".join(f"- {t.name} ({t.language})" for t in templates)

        return (
            "Usage: /generate <subcommand>\n"
            "  register <name> <lang> <body>\n"
            "  render <name>\n"
            "  list"
        )

    # ------------------------------------------------------------------
    # /scaffold
    # ------------------------------------------------------------------

    async def scaffold_handler(args: str) -> str:
        from lidco.codegen.scaffold import ScaffoldGenerator

        gen = ScaffoldGenerator()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "create":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /scaffold create <type> <name>"
            project_type, name = tokens[0], tokens[1]
            try:
                spec = gen.from_type(project_type, name)
            except ValueError as exc:
                return str(exc)
            files = gen.generate(spec)
            return f"Generated {len(files)} files for {name} ({project_type})."

        if sub == "preview":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /scaffold preview <type> <name>"
            project_type, name = tokens[0], tokens[1]
            try:
                spec = gen.from_type(project_type, name)
            except ValueError as exc:
                return str(exc)
            return gen.preview(spec)

        return (
            "Usage: /scaffold <subcommand>\n"
            "  create <type> <name>  — generate scaffold\n"
            "  preview <type> <name> — preview file tree"
        )

    # ------------------------------------------------------------------
    # /crud
    # ------------------------------------------------------------------

    async def crud_handler(args: str) -> str:
        from lidco.codegen.crud import CRUDGenerator, ModelDef

        gen = CRUDGenerator()
        parts = args.strip().split(maxsplit=1)
        name = parts[0] if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if not name:
            return "Usage: /crud <ModelName> [field:type ...]"

        fields: list[dict[str, str]] = []
        if rest:
            for token in rest.split():
                if ":" in token:
                    fname, ftype = token.split(":", 1)
                    fields.append({"name": fname, "type": ftype})
                else:
                    fields.append({"name": token, "type": "str"})

        model = ModelDef(name=name, fields=fields)
        result = gen.generate(model)
        lines = [f"Generated {len(result)} files:"]
        for path in sorted(result):
            lines.append(f"  {path}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /generate-migration
    # ------------------------------------------------------------------

    async def migration_handler(args: str) -> str:
        from lidco.codegen.migration_gen import Change, MigrationGenerator

        gen = MigrationGenerator()
        parts = args.strip().split()
        if len(parts) < 2:
            return (
                "Usage: /generate-migration <change_type> <table> [column] [type]\n"
                "  change_type: add_column, drop_column, create_table, drop_table"
            )

        change_type = parts[0]
        table = parts[1]
        column = parts[2] if len(parts) > 2 else ""
        col_type = parts[3] if len(parts) > 3 else ""

        change = Change(type=change_type, table=table, column=column, column_type=col_type)
        migration = gen.generate([change])
        return migration

    registry.register(SlashCommand("generate", "Code generation templates", generate_handler))
    registry.register(SlashCommand("scaffold", "Project scaffolding", scaffold_handler))
    registry.register(SlashCommand("crud", "Generate CRUD boilerplate", crud_handler))
    registry.register(SlashCommand("generate-migration", "Generate DB migration", migration_handler))
