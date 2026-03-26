"""Tests for T613 SqlTool."""
import pytest

from lidco.tools.sql_tool import SqlTool, SqlResult, TableInfo


# ---------------------------------------------------------------------------
# SqlResult
# ---------------------------------------------------------------------------

class TestSqlResult:
    def _make(self, columns=None, rows=None, rowcount=0, error=""):
        return SqlResult(
            query="SELECT 1",
            columns=columns or [],
            rows=rows or [],
            rowcount=rowcount,
            elapsed_ms=1.5,
            error=error,
        )

    def test_ok_when_no_error(self):
        assert self._make().ok is True

    def test_not_ok_when_error(self):
        assert self._make(error="syntax error").ok is False

    def test_as_dicts(self):
        result = self._make(
            columns=["id", "name"],
            rows=[(1, "alice"), (2, "bob")],
        )
        dicts = result.as_dicts()
        assert dicts[0] == {"id": 1, "name": "alice"}
        assert dicts[1] == {"id": 2, "name": "bob"}

    def test_format_table_with_rows(self):
        result = self._make(
            columns=["id", "val"],
            rows=[(1, "foo"), (2, "bar")],
            rowcount=2,
        )
        table = result.format_table()
        assert "id" in table
        assert "foo" in table
        assert "bar" in table

    def test_format_table_dml(self):
        result = SqlResult(
            query="INSERT INTO t VALUES (1)",
            columns=[],
            rows=[],
            rowcount=1,
            elapsed_ms=2.0,
        )
        s = result.format_table()
        assert "1" in s

    def test_format_table_error(self):
        result = self._make(error="no such table")
        assert "no such table" in result.format_table()

    def test_format_table_max_rows(self):
        rows = [(i, f"val{i}") for i in range(100)]
        result = self._make(columns=["id", "val"], rows=rows, rowcount=100)
        table = result.format_table(max_rows=10)
        assert "100" in table  # shows total count
        assert "showing first 10" in table


# ---------------------------------------------------------------------------
# SqlTool — in-memory SQLite
# ---------------------------------------------------------------------------

class TestSqlToolInMemory:
    def setup_method(self):
        self.tool = SqlTool(db_path=":memory:")
        self.tool.connect()
        self.tool.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")

    def teardown_method(self):
        self.tool.close()

    def test_create_table(self):
        # Setup already created table; just verify it exists
        tables = self.tool.list_tables()
        assert "users" in tables

    def test_insert_and_select(self):
        self.tool.execute("INSERT INTO users VALUES (1, 'Alice')")
        result = self.tool.execute("SELECT * FROM users")
        assert len(result.rows) == 1
        assert result.rows[0][1] == "Alice"

    def test_rowcount_on_insert(self):
        result = self.tool.execute("INSERT INTO users VALUES (2, 'Bob')")
        assert result.rowcount == 1

    def test_select_columns(self):
        self.tool.execute("INSERT INTO users VALUES (3, 'Carol')")
        result = self.tool.execute("SELECT id, name FROM users WHERE id=3")
        assert result.columns == ["id", "name"]

    def test_select_no_rows(self):
        result = self.tool.execute("SELECT * FROM users WHERE id=999")
        assert result.rows == []
        assert result.ok

    def test_invalid_sql_returns_error(self):
        result = self.tool.execute("NOT VALID SQL")
        assert not result.ok
        assert result.error != ""

    def test_parameterized_query(self):
        self.tool.execute("INSERT INTO users VALUES (4, 'Dave')")
        result = self.tool.execute("SELECT * FROM users WHERE id=?", (4,))
        assert len(result.rows) == 1
        assert result.rows[0][1] == "Dave"

    def test_execute_many(self):
        data = [(10, "Eve"), (11, "Frank"), (12, "Grace")]
        result = self.tool.execute_many("INSERT INTO users VALUES (?, ?)", data)
        assert result.ok
        count = self.tool.execute("SELECT COUNT(*) FROM users")
        assert count.rows[0][0] == 3

    def test_update_returns_rowcount(self):
        self.tool.execute("INSERT INTO users VALUES (5, 'Heidi')")
        result = self.tool.execute("UPDATE users SET name='Heidi2' WHERE id=5")
        assert result.rowcount == 1

    def test_delete_returns_rowcount(self):
        self.tool.execute("INSERT INTO users VALUES (6, 'Ivan')")
        result = self.tool.execute("DELETE FROM users WHERE id=6")
        assert result.rowcount == 1

    def test_context_manager(self):
        tool = SqlTool(db_path=":memory:")
        with tool as t:
            t.execute("CREATE TABLE t (x INT)")
            r = t.execute("SELECT COUNT(*) FROM t")
            assert r.rows[0][0] == 0


class TestSqlToolSchema:
    def test_list_tables_empty(self):
        tool = SqlTool(db_path=":memory:")
        tool.connect()
        assert tool.list_tables() == []
        tool.close()

    def test_list_tables(self):
        tool = SqlTool(db_path=":memory:")
        tool.connect()
        tool.execute("CREATE TABLE a (x INT)")
        tool.execute("CREATE TABLE b (y TEXT)")
        tables = tool.list_tables()
        assert "a" in tables
        assert "b" in tables
        tool.close()

    def test_table_info(self):
        tool = SqlTool(db_path=":memory:")
        tool.connect()
        tool.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        info = tool.table_info("items")
        assert info.name == "items"
        col_names = [c["name"] for c in info.columns]
        assert "id" in col_names
        assert "name" in col_names
        # PK column
        pk_cols = [c for c in info.columns if c["pk"]]
        assert any(c["name"] == "id" for c in pk_cols)
        tool.close()

    def test_table_info_row_count(self):
        tool = SqlTool(db_path=":memory:")
        tool.connect()
        tool.execute("CREATE TABLE t (v INT)")
        tool.execute("INSERT INTO t VALUES (1)")
        tool.execute("INSERT INTO t VALUES (2)")
        info = tool.table_info("t")
        assert info.row_count == 2
        tool.close()


class TestSqlToolFile:
    def test_execute_in_file_db(self, tmp_path):
        db = str(tmp_path / "test.db")
        tool = SqlTool(db_path=db)
        tool.connect()
        tool.execute("CREATE TABLE data (val TEXT)")
        tool.execute("INSERT INTO data VALUES ('hello')")
        tool.close()

        # Re-open and verify
        tool2 = SqlTool(db_path=db)
        tool2.connect()
        result = tool2.execute("SELECT * FROM data")
        assert result.rows[0][0] == "hello"
        tool2.close()

    def test_execute_script(self):
        tool = SqlTool(db_path=":memory:")
        tool.connect()
        script = "CREATE TABLE x (n INT); INSERT INTO x VALUES (42); INSERT INTO x VALUES (99);"
        result = tool.execute_script(script)
        assert result.ok
        count = tool.execute("SELECT COUNT(*) FROM x")
        assert count.rows[0][0] == 2
        tool.close()
