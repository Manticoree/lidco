"""
Q318 CLI commands — /test-data, /test-fixtures, /mask-data, /seed-data

Registered via register_q318_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q318_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q318 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /test-data — Generate test data from a registered schema
    # ------------------------------------------------------------------
    async def test_data_handler(args: str) -> str:
        """
        Usage: /test-data <schema> [--count N] [--seed N]
        """
        from lidco.testdata.factory import DataFactory, FactorySchema, FieldSpec

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /test-data <schema> [--count N] [--seed N]"

        schema_name = parts[0]
        count = 5
        seed = 42
        i = 1
        while i < len(parts):
            if parts[i] == "--count" and i + 1 < len(parts):
                try:
                    count = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--seed" and i + 1 < len(parts):
                try:
                    seed = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        # Build a demo schema for common names
        demo_schemas = {
            "user": FactorySchema("user", (
                FieldSpec("id", "int", min_value=1, max_value=99999),
                FieldSpec("name", "name"),
                FieldSpec("email", "email"),
                FieldSpec("active", "bool"),
            )),
            "product": FactorySchema("product", (
                FieldSpec("id", "int", min_value=1, max_value=99999),
                FieldSpec("title", "string", min_value=12),
                FieldSpec("price", "float", min_value=0.01, max_value=9999.99),
            )),
        }

        schema = demo_schemas.get(schema_name)
        if not schema:
            available = ", ".join(sorted(demo_schemas))
            return f"Unknown schema: {schema_name}. Available: {available}"

        factory = DataFactory(seed=seed)
        factory = factory.register_schema(schema)
        result = factory.generate(schema_name, count=count)

        lines = [f"Generated {result.count} {schema_name} record(s) (seed={result.seed}):"]
        for rec in result.records:
            lines.append(f"  {rec.data}")
        return "\n".join(lines)

    registry.register_async(
        "test-data",
        "Generate test data from a schema",
        test_data_handler,
    )

    # ------------------------------------------------------------------
    # /test-fixtures — List / load test fixtures
    # ------------------------------------------------------------------
    async def test_fixtures_handler(args: str) -> str:
        """
        Usage: /test-fixtures [--file <path>] [--list]
        """
        from lidco.testdata.fixtures import FixtureManager

        parts = shlex.split(args) if args.strip() else []
        file_path: str | None = None
        list_mode = False
        i = 0
        while i < len(parts):
            if parts[i] == "--file" and i + 1 < len(parts):
                file_path = parts[i + 1]
                i += 2
            elif parts[i] == "--list":
                list_mode = True
                i += 1
            else:
                i += 1

        mgr = FixtureManager()

        if file_path:
            try:
                fset = mgr.load_file(file_path)
                lines = [f"Loaded {len(fset.fixtures)} fixture(s) from {fset.source}:"]
                for f in fset.fixtures:
                    deps = f", depends_on={list(f.depends_on)}" if f.depends_on else ""
                    lines.append(f"  {f.name} (scope={f.scope.value}, v{f.version}{deps})")
                return "\n".join(lines)
            except Exception as exc:
                return f"Error loading fixtures: {exc}"

        if list_mode:
            names = mgr.registered_names
            if not names:
                return "No fixtures registered."
            return "Registered fixtures:\n" + "\n".join(f"  {n}" for n in names)

        return "Usage: /test-fixtures [--file <path>] [--list]"

    registry.register_async(
        "test-fixtures",
        "Manage test fixtures",
        test_fixtures_handler,
    )

    # ------------------------------------------------------------------
    # /mask-data — Mask PII in text
    # ------------------------------------------------------------------
    async def mask_data_handler(args: str) -> str:
        """
        Usage: /mask-data <text>
        """
        from lidco.testdata.masking import DataMasker

        text = args.strip()
        if not text:
            return "Usage: /mask-data <text>"

        masker = DataMasker(consistent=True)
        masked = masker.mask_string(text)
        detected = masker.detect_pii(text)

        lines = [f"Masked: {masked}"]
        if detected:
            lines.append(f"PII types found: {', '.join(p.value for p in detected)}")
        else:
            lines.append("No PII detected.")
        return "\n".join(lines)

    registry.register_async(
        "mask-data",
        "Mask sensitive / PII data in text",
        mask_data_handler,
    )

    # ------------------------------------------------------------------
    # /seed-data — Seed data plan / execute
    # ------------------------------------------------------------------
    async def seed_data_handler(args: str) -> str:
        """
        Usage: /seed-data [--env <environment>] [--dry-run]
        """
        from lidco.testdata.fixtures import FixtureDef
        from lidco.testdata.seeder import DataSeeder

        parts = shlex.split(args) if args.strip() else []
        env = "development"
        dry_run = False
        i = 0
        while i < len(parts):
            if parts[i] == "--env" and i + 1 < len(parts):
                env = parts[i + 1]
                i += 2
            elif parts[i] == "--dry-run":
                dry_run = True
                i += 1
            else:
                i += 1

        # Demo with a sample fixture
        sample_fixture = FixtureDef(
            name="sample_users",
            data={"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]},
        )
        seeder = DataSeeder(environment=env)
        seeder = seeder.add_fixture("sample_users", "users", sample_fixture)

        plan = seeder.plan()
        if dry_run:
            lines = [f"Seed plan ({plan.environment}, idempotent={plan.idempotent}):"]
            for e in plan.entries:
                lines.append(f"  {e.fixture_name} -> {e.table} ({e.record_count} records)")
            return "\n".join(lines)

        result = seeder.execute(plan)
        if result.success:
            return f"Seeded {result.total_applied} record(s) in {env} environment."
        else:
            errors = "; ".join(f.error or "unknown" for f in result.failed)
            return f"Seeding failed: {errors}"

    registry.register_async(
        "seed-data",
        "Seed data from fixtures",
        seed_data_handler,
    )
