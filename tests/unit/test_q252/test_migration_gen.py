"""Tests for lidco.codegen.migration_gen."""
from __future__ import annotations

from lidco.codegen.migration_gen import Change, MigrationGenerator


class TestChange:
    """Tests for the Change dataclass."""

    def test_defaults(self) -> None:
        c = Change(type="add_column", table="users")
        assert c.column == ""
        assert c.column_type == ""

    def test_full(self) -> None:
        c = Change(type="add_column", table="users", column="email", column_type="str")
        assert c.table == "users"
        assert c.column == "email"


class TestMigrationGeneratorGenerate:
    """Tests for generate."""

    def test_alembic_create_table(self) -> None:
        gen = MigrationGenerator()
        changes = [Change(type="create_table", table="users")]
        result = gen.generate(changes, framework="alembic")
        assert "def upgrade()" in result
        assert 'op.create_table("users")' in result

    def test_alembic_add_column(self) -> None:
        gen = MigrationGenerator()
        changes = [Change(type="add_column", table="users", column="email", column_type="str")]
        result = gen.generate(changes)
        assert 'op.add_column("users"' in result
        assert '"email"' in result

    def test_alembic_drop_table(self) -> None:
        gen = MigrationGenerator()
        changes = [Change(type="drop_table", table="old")]
        result = gen.generate(changes)
        assert 'op.drop_table("old")' in result

    def test_alembic_drop_column(self) -> None:
        gen = MigrationGenerator()
        changes = [Change(type="drop_column", table="t", column="c")]
        result = gen.generate(changes)
        assert 'op.drop_column("t", "c")' in result

    def test_alembic_empty_changes(self) -> None:
        gen = MigrationGenerator()
        result = gen.generate([])
        assert "pass" in result

    def test_raw_create_table(self) -> None:
        gen = MigrationGenerator()
        changes = [Change(type="create_table", table="users")]
        result = gen.generate(changes, framework="raw")
        assert "CREATE TABLE users" in result

    def test_raw_add_column(self) -> None:
        gen = MigrationGenerator()
        changes = [Change(type="add_column", table="t", column="c", column_type="int")]
        result = gen.generate(changes, framework="raw")
        assert "ALTER TABLE t ADD COLUMN c int" in result

    def test_raw_drop_table(self) -> None:
        gen = MigrationGenerator()
        changes = [Change(type="drop_table", table="old")]
        result = gen.generate(changes, framework="raw")
        assert "DROP TABLE old;" in result

    def test_raw_drop_column(self) -> None:
        gen = MigrationGenerator()
        changes = [Change(type="drop_column", table="t", column="c")]
        result = gen.generate(changes, framework="raw")
        assert "DROP COLUMN c" in result


class TestMigrationGeneratorDetectChanges:
    """Tests for detect_changes."""

    def test_new_table(self) -> None:
        gen = MigrationGenerator()
        old: list[dict] = []
        new = [{"name": "users", "columns": []}]
        changes = gen.detect_changes(old, new)
        assert len(changes) == 1
        assert changes[0].type == "create_table"
        assert changes[0].table == "users"

    def test_dropped_table(self) -> None:
        gen = MigrationGenerator()
        old = [{"name": "users", "columns": []}]
        new: list[dict] = []
        changes = gen.detect_changes(old, new)
        assert len(changes) == 1
        assert changes[0].type == "drop_table"

    def test_added_column(self) -> None:
        gen = MigrationGenerator()
        old = [{"name": "users", "columns": [{"name": "id", "type": "int"}]}]
        new = [
            {
                "name": "users",
                "columns": [
                    {"name": "id", "type": "int"},
                    {"name": "email", "type": "str"},
                ],
            }
        ]
        changes = gen.detect_changes(old, new)
        assert len(changes) == 1
        assert changes[0].type == "add_column"
        assert changes[0].column == "email"

    def test_dropped_column(self) -> None:
        gen = MigrationGenerator()
        old = [
            {
                "name": "users",
                "columns": [
                    {"name": "id", "type": "int"},
                    {"name": "email", "type": "str"},
                ],
            }
        ]
        new = [{"name": "users", "columns": [{"name": "id", "type": "int"}]}]
        changes = gen.detect_changes(old, new)
        assert len(changes) == 1
        assert changes[0].type == "drop_column"
        assert changes[0].column == "email"

    def test_no_changes(self) -> None:
        gen = MigrationGenerator()
        models = [{"name": "users", "columns": [{"name": "id", "type": "int"}]}]
        changes = gen.detect_changes(models, models)
        assert changes == []

    def test_multiple_changes(self) -> None:
        gen = MigrationGenerator()
        old = [{"name": "a", "columns": []}, {"name": "b", "columns": []}]
        new = [{"name": "b", "columns": []}, {"name": "c", "columns": []}]
        changes = gen.detect_changes(old, new)
        types = {c.type for c in changes}
        assert "drop_table" in types
        assert "create_table" in types


class TestMigrationGeneratorReversible:
    """Tests for reversible."""

    def test_appends_downgrade(self) -> None:
        gen = MigrationGenerator()
        migration = gen.generate([Change(type="create_table", table="t")])
        result = gen.reversible(migration)
        assert "def downgrade()" in result
        assert "def upgrade()" in result

    def test_idempotent_content(self) -> None:
        gen = MigrationGenerator()
        original = "def upgrade():\n    pass\n"
        result = gen.reversible(original)
        assert result.count("def upgrade()") == 1
        assert result.count("def downgrade()") == 1
