"""Q295 CLI commands: /db-schema, /db-optimize, /db-migrate, /db-seed."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q295 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /db-schema
    # ------------------------------------------------------------------

    async def db_schema_handler(args: str) -> str:
        from lidco.database.schema import Column, SchemaAnalyzer

        if "schema" not in _state:
            _state["schema"] = SchemaAnalyzer()
        sa: SchemaAnalyzer = _state["schema"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "summary"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            if not rest:
                return "Usage: /db-schema add <table> <col1:type,col2:type,...>"
            tp = rest.split(maxsplit=1)
            tname = tp[0]
            cols: list[Column] = []
            if len(tp) > 1:
                for spec in tp[1].split(","):
                    spec = spec.strip()
                    cparts = spec.split(":")
                    cname = cparts[0].strip()
                    ctype = cparts[1].strip() if len(cparts) > 1 else "TEXT"
                    pk = cname.lower() == "id"
                    cols.append(Column(name=cname, type=ctype, primary_key=pk))
            sa.add_table(tname, cols)
            return f"Added table '{tname}' with {len(cols)} columns."

        if sub == "relationships":
            rels = sa.relationships()
            if not rels:
                return "No relationships detected."
            lines = [f"- {r.source_table}.{r.source_column} -> {r.target_table}.{r.target_column} ({r.type})" for r in rels]
            return "\n".join(lines)

        if sub == "indexes":
            idxs = sa.indexes()
            if not idxs:
                return "No indexes suggested."
            lines = [f"- {i.name}: {i.table}({', '.join(i.columns)}) unique={i.unique}" for i in idxs]
            return "\n".join(lines)

        if sub == "anomalies":
            anoms = sa.anomalies()
            if not anoms:
                return "No anomalies detected."
            lines = [f"- [{a.severity}] {a.table}: {a.message}" for a in anoms]
            return "\n".join(lines)

        if sub == "diagram":
            return sa.er_diagram()

        if sub == "summary":
            s = sa.summary()
            return (
                f"Tables: {s['table_count']}, "
                f"Relationships: {s['relationship_count']}, "
                f"Indexes: {s['index_count']}, "
                f"Anomalies: {s['anomaly_count']}"
            )

        return "Usage: /db-schema [summary | add <table> <cols> | relationships | indexes | anomalies | diagram]"

    # ------------------------------------------------------------------
    # /db-optimize
    # ------------------------------------------------------------------

    async def db_optimize_handler(args: str) -> str:
        from lidco.database.optimizer import QueryOptimizer2

        if "opt" not in _state:
            _state["opt"] = QueryOptimizer2()
        opt: QueryOptimizer2 = _state["opt"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "analyze":
            if not rest:
                return "Usage: /db-optimize analyze <SQL>"
            result = opt.analyze(rest)
            lines = [f"Cost: {result.estimated_cost}, Index: {result.uses_index}"]
            if result.issues:
                lines.append("Issues: " + "; ".join(result.issues))
            if result.suggestions:
                lines.append("Suggestions: " + "; ".join(result.suggestions))
            return "\n".join(lines)

        if sub == "suggest":
            if not rest:
                return "Usage: /db-optimize suggest <SQL>"
            idxs = opt.suggest_indexes(rest)
            if not idxs:
                return "No index suggestions."
            lines = [f"- {i.table}({', '.join(i.columns)}): {i.reason}" for i in idxs]
            return "\n".join(lines)

        if sub == "rewrite":
            if not rest:
                return "Usage: /db-optimize rewrite <SQL>"
            return opt.rewrite(rest)

        if sub == "explain":
            if not rest:
                return "Usage: /db-optimize explain <SQL>"
            plan = opt.explain(rest)
            return f"Tables: {plan['tables']}, Scan: {plan['scan_type']}, Join: {plan['has_join']}, Sort: {plan['has_sort']}"

        return "Usage: /db-optimize [analyze <SQL> | suggest <SQL> | rewrite <SQL> | explain <SQL>]"

    # ------------------------------------------------------------------
    # /db-migrate
    # ------------------------------------------------------------------

    async def db_migrate_handler(args: str) -> str:
        from lidco.database.migration_planner import MigrationPlanner2, SchemaSnapshot

        if "mig" not in _state:
            _state["mig"] = MigrationPlanner2()
        mp: MigrationPlanner2 = _state["mig"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "plan":
            # Demo: create a sample migration
            old = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}, "name": {"type": "TEXT"}}})
            new = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}, "name": {"type": "TEXT"}, "email": {"type": "TEXT"}}})
            plan = mp.plan(old, new)
            lines = [f"Steps: {len(plan.steps)}"]
            for s in plan.steps:
                lines.append(f"  - {s.operation} {s.table}.{s.column} breaking={s.breaking}")
            return "\n".join(lines)

        if sub == "breaking":
            if not mp.history:
                return "No migration plans. Run /db-migrate plan first."
            breaking = mp.detect_breaking(mp.history[-1])
            if not breaking:
                return "No breaking changes."
            lines = [f"- {s.operation} {s.table}.{s.column}" for s in breaking]
            return "\n".join(lines)

        if sub == "rollback":
            if not mp.history:
                return "No migration plans. Run /db-migrate plan first."
            return mp.generate_rollback(mp.history[-1])

        if sub == "safe":
            if not mp.history:
                return "No migration plans. Run /db-migrate plan first."
            safe = mp.is_safe(mp.history[-1])
            return f"Migration is {'safe' if safe else 'NOT safe (has breaking changes)'}."

        return "Usage: /db-migrate [plan | breaking | rollback | safe]"

    # ------------------------------------------------------------------
    # /db-seed
    # ------------------------------------------------------------------

    async def db_seed_handler(args: str) -> str:
        from lidco.database.seeder import DataSeeder, SeedColumn

        if "seed" not in _state:
            _state["seed"] = DataSeeder()
        ds: DataSeeder = _state["seed"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            if not rest:
                return "Usage: /db-seed add <table> <col1:type,col2:type,...>"
            tp = rest.split(maxsplit=1)
            tname = tp[0]
            cols: list[SeedColumn] = []
            if len(tp) > 1:
                for spec in tp[1].split(","):
                    spec = spec.strip()
                    cparts = spec.split(":")
                    cname = cparts[0].strip()
                    ctype = cparts[1].strip() if len(cparts) > 1 else "text"
                    cols.append(SeedColumn(name=cname, type=ctype))
            ds.add_table(tname, cols)
            return f"Registered table '{tname}' with {len(cols)} columns for seeding."

        if sub == "generate":
            tp = rest.split(maxsplit=1)
            if not tp:
                return "Usage: /db-seed generate <table> [count]"
            tname = tp[0]
            count = int(tp[1]) if len(tp) > 1 else 10
            try:
                rows = ds.generate(tname, count)
            except ValueError as e:
                return str(e)
            return f"Generated {len(rows)} rows for '{tname}'. First row: {rows[0] if rows else '{}'}"

        if sub == "seed":
            ds.deterministic(int(rest) if rest else 42)
            return f"Seed set to {rest or '42'}."

        return "Usage: /db-seed [add <table> <cols> | generate <table> [count] | seed [number]]"

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------
    registry.register(SlashCommand("db-schema", "Analyze database schema", db_schema_handler))
    registry.register(SlashCommand("db-optimize", "Optimize SQL queries", db_optimize_handler))
    registry.register(SlashCommand("db-migrate", "Plan database migrations", db_migrate_handler))
    registry.register(SlashCommand("db-seed", "Generate seed data", db_seed_handler))
