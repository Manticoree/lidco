"""Tests for T605 EnvValidator."""
from pathlib import Path

import pytest

from lidco.env.validator import (
    EnvValidator,
    ValidationResult,
    _parse_env_file,
    _parse_schema_file,
)


# ---------------------------------------------------------------------------
# _parse_env_file
# ---------------------------------------------------------------------------

class TestParseEnvFile:
    def test_basic_key_value(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("DATABASE_URL=postgres://localhost/db\n")
        vars_ = _parse_env_file(f)
        assert len(vars_) == 1
        assert vars_[0].name == "DATABASE_URL"
        assert vars_[0].value == "postgres://localhost/db"

    def test_empty_value_marks_required(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("SECRET_KEY=\n")
        vars_ = _parse_env_file(f)
        assert vars_[0].required is True

    def test_comment_lines_skipped(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("# comment\nFOO=bar\n")
        vars_ = _parse_env_file(f)
        assert len(vars_) == 1
        assert vars_[0].name == "FOO"

    def test_comment_above_line_captured(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("# The database URL\nDATABASE_URL=postgres://\n")
        vars_ = _parse_env_file(f)
        assert vars_[0].comment == "The database URL"

    def test_secret_detection_by_name(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("API_KEY=abc123\nLOG_LEVEL=info\n")
        vars_ = _parse_env_file(f)
        api_key = next(v for v in vars_ if v.name == "API_KEY")
        log_level = next(v for v in vars_ if v.name == "LOG_LEVEL")
        assert api_key.is_secret is True
        assert log_level.is_secret is False

    def test_inline_comment_stripped(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("PORT=8080 # default port\n")
        vars_ = _parse_env_file(f)
        assert vars_[0].value == "8080"

    def test_empty_file(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("")
        assert _parse_env_file(f) == []

    def test_blank_lines_ignored(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("\nFOO=bar\n\nBAZ=qux\n")
        vars_ = _parse_env_file(f)
        assert len(vars_) == 2


# ---------------------------------------------------------------------------
# _parse_schema_file
# ---------------------------------------------------------------------------

class TestParseSchemaFile:
    def test_required_var(self, tmp_path):
        f = tmp_path / ".env.schema"
        f.write_text("DATABASE_URL=required\n")
        vars_ = _parse_schema_file(f)
        assert vars_[0].required is True

    def test_optional_var(self, tmp_path):
        f = tmp_path / ".env.schema"
        f.write_text("LOG_LEVEL=optional:info\n")
        vars_ = _parse_schema_file(f)
        assert vars_[0].required is False
        assert vars_[0].value == "info"

    def test_secret_tag(self, tmp_path):
        f = tmp_path / ".env.schema"
        f.write_text("SECRET_KEY=required:secret\n")
        vars_ = _parse_schema_file(f)
        assert vars_[0].is_secret is True

    def test_comment_skipped(self, tmp_path):
        f = tmp_path / ".env.schema"
        f.write_text("# Schema file\nFOO=required\n")
        vars_ = _parse_schema_file(f)
        assert len(vars_) == 1


# ---------------------------------------------------------------------------
# EnvValidator
# ---------------------------------------------------------------------------

class TestEnvValidator:
    def _write(self, tmp_path, name, content):
        f = tmp_path / name
        f.write_text(content)
        return f

    def test_missing_env_file_error(self, tmp_path):
        self._write(tmp_path, ".env.example", "DATABASE_URL=\n")
        validator = EnvValidator(project_root=str(tmp_path))
        result = validator.validate()
        errors = [i for i in result.issues if i.issue_type == "missing" and i.var_name == ""]
        assert len(errors) >= 1

    def test_valid_env_no_issues(self, tmp_path):
        self._write(tmp_path, ".env", "DATABASE_URL=postgres://localhost/db\n")
        self._write(tmp_path, ".env.example", "DATABASE_URL=postgres://localhost/testdb\n")
        validator = EnvValidator(project_root=str(tmp_path))
        result = validator.validate()
        assert result.is_valid

    def test_missing_required_var(self, tmp_path):
        self._write(tmp_path, ".env", "LOG_LEVEL=info\n")
        self._write(tmp_path, ".env.example", "DATABASE_URL=\nLOG_LEVEL=info\n")
        validator = EnvValidator(project_root=str(tmp_path))
        result = validator.validate()
        missing = [i for i in result.issues if i.issue_type == "missing" and i.var_name == "DATABASE_URL"]
        assert len(missing) >= 1
        assert missing[0].severity == "error"

    def test_extra_var_reported_as_info(self, tmp_path):
        self._write(tmp_path, ".env", "DATABASE_URL=x\nEXTRA_VAR=y\n")
        self._write(tmp_path, ".env.example", "DATABASE_URL=\n")
        validator = EnvValidator(project_root=str(tmp_path))
        result = validator.validate()
        extras = [i for i in result.issues if i.issue_type == "extra"]
        assert any(i.var_name == "EXTRA_VAR" for i in extras)
        assert all(i.severity == "info" for i in extras)

    def test_empty_required_var_is_error(self, tmp_path):
        self._write(tmp_path, ".env", "SECRET_KEY=\n")
        self._write(tmp_path, ".env.example", "SECRET_KEY=\n")
        validator = EnvValidator(project_root=str(tmp_path))
        result = validator.validate()
        empty = [i for i in result.issues if i.issue_type == "empty_required"]
        assert len(empty) >= 1
        assert empty[0].severity == "error"

    def test_example_placeholder_value_warning(self, tmp_path):
        self._write(tmp_path, ".env", "API_KEY=your-api-key-here\n")
        self._write(tmp_path, ".env.example", "API_KEY=your-api-key-here\n")
        validator = EnvValidator(project_root=str(tmp_path))
        result = validator.validate()
        example_issues = [i for i in result.issues if i.issue_type == "example_value"]
        assert len(example_issues) >= 1

    def test_example_check_disabled(self, tmp_path):
        self._write(tmp_path, ".env", "API_KEY=your-api-key-here\n")
        self._write(tmp_path, ".env.example", "API_KEY=your-api-key-here\n")
        validator = EnvValidator(
            project_root=str(tmp_path), check_example_values=False
        )
        result = validator.validate()
        example_issues = [i for i in result.issues if i.issue_type == "example_value"]
        assert len(example_issues) == 0

    def test_template_discovery_precedence(self, tmp_path):
        # Creates .env.example and .env.template — should pick .env.example first
        self._write(tmp_path, ".env", "FOO=bar\n")
        self._write(tmp_path, ".env.example", "FOO=\n")
        self._write(tmp_path, ".env.template", "FOO=\nEXTRA=\n")
        validator = EnvValidator(project_root=str(tmp_path))
        result = validator.validate()
        # .env.example has 1 var, .env.template has 2
        assert result.template_file.endswith(".env.example")

    def test_explicit_template_file(self, tmp_path):
        self._write(tmp_path, ".env", "FOO=bar\n")
        self._write(tmp_path, "custom.env", "FOO=\nBAR=\n")
        validator = EnvValidator(
            project_root=str(tmp_path),
            template_file="custom.env",
        )
        result = validator.validate()
        template_names = {v.name for v in result.template_vars}
        assert "FOO" in template_names
        assert "BAR" in template_names

    def test_schema_file_used_when_present(self, tmp_path):
        self._write(tmp_path, ".env.schema", "DATABASE_URL=required\nLOG_LEVEL=optional:info\n")
        self._write(tmp_path, ".env", "DATABASE_URL=postgres://\n")
        validator = EnvValidator(project_root=str(tmp_path))
        result = validator.validate()
        # LOG_LEVEL is optional → missing but only warning
        warnings = [i for i in result.issues if i.var_name == "LOG_LEVEL"]
        if warnings:
            assert all(i.severity == "warning" for i in warnings)

    def test_no_template_no_issues(self, tmp_path):
        self._write(tmp_path, ".env", "FOO=bar\n")
        validator = EnvValidator(project_root=str(tmp_path))
        result = validator.validate()
        # No template → no missing issues
        missing = [i for i in result.issues if i.issue_type == "missing" and i.var_name]
        assert len(missing) == 0

    def test_summary_format(self, tmp_path):
        self._write(tmp_path, ".env", "FOO=bar\n")
        self._write(tmp_path, ".env.example", "FOO=\n")
        validator = EnvValidator(project_root=str(tmp_path))
        result = validator.validate()
        summary = result.summary()
        assert "vars" in summary.lower()
        assert "error" in summary.lower()

    def test_generate_template_strips_secrets(self, tmp_path):
        self._write(tmp_path, ".env", "API_KEY=super-secret\nLOG_LEVEL=debug\n")
        validator = EnvValidator(project_root=str(tmp_path))
        out = validator.generate_template()
        content = Path(out).read_text()
        # Secret should be stripped
        assert "super-secret" not in content
        # Non-secret value preserved
        assert "debug" in content

    def test_generate_template_no_env_raises(self, tmp_path):
        validator = EnvValidator(project_root=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            validator.generate_template()
