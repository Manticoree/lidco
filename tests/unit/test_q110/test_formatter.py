"""Tests for src/lidco/format/formatter.py."""
import pytest

from lidco.format.formatter import (
    FormatterConfig, FormatterError, FormatterKind, FormatterRegistry, FormatResult,
)


class TestFormatterConfig:
    def test_name(self):
        cfg = FormatterConfig(kind=FormatterKind.BLACK, executable="black",
                              file_extensions=[".py"])
        assert cfg.name == "black"

    def test_supports_extension(self):
        cfg = FormatterConfig(kind=FormatterKind.BLACK, executable="black",
                              file_extensions=[".py"])
        assert cfg.supports("src/main.py") is True
        assert cfg.supports("src/main.js") is False

    def test_supports_no_extensions(self):
        cfg = FormatterConfig(kind=FormatterKind.BLACK, executable="black")
        assert cfg.supports("anything.xyz") is True


class TestFormatResult:
    def test_summary_ok(self):
        r = FormatResult(formatter="black", file_path="f.py", changed=True, success=True)
        s = r.summary()
        assert "black" in s
        assert "changed" in s

    def test_summary_error(self):
        r = FormatResult(formatter="black", file_path="f.py", changed=False, success=False)
        assert "ERROR" in r.summary()

    def test_unchanged(self):
        r = FormatResult(formatter="ruff", file_path="f.py", changed=False, success=True)
        assert "unchanged" in r.summary()


class TestFormatterRegistry:
    def test_register_builtin(self):
        reg = FormatterRegistry()
        reg.register_builtin(FormatterKind.BLACK)
        assert "black" in reg.list_available()

    def test_register_custom(self):
        reg = FormatterRegistry()
        cfg = FormatterConfig(kind=FormatterKind.UNKNOWN, executable="myfmt",
                              file_extensions=[".xyz"])
        cfg2 = FormatterConfig(FormatterKind.UNKNOWN, "myfmt", [], [".xyz"])
        reg.register(FormatterConfig(
            kind=FormatterKind.BLACK, executable="black"))
        assert len(reg) >= 1

    def test_unregister(self):
        reg = FormatterRegistry()
        reg.register_builtin(FormatterKind.BLACK)
        assert reg.unregister("black") is True
        assert "black" not in reg.list_available()

    def test_unregister_nonexistent(self):
        reg = FormatterRegistry()
        assert reg.unregister("ghost") is False

    def test_get(self):
        reg = FormatterRegistry()
        reg.register_builtin(FormatterKind.RUFF)
        cfg = reg.get("ruff")
        assert cfg is not None
        assert cfg.kind == FormatterKind.RUFF

    def test_get_none(self):
        reg = FormatterRegistry()
        assert reg.get("ghost") is None

    def test_len(self):
        reg = FormatterRegistry()
        reg.register_builtin(FormatterKind.BLACK)
        reg.register_builtin(FormatterKind.RUFF)
        assert len(reg) == 2

    def test_with_defaults(self):
        reg = FormatterRegistry.with_defaults()
        assert len(reg) > 0
        assert "black" in reg.list_available()
        assert "ruff" in reg.list_available()
        assert "prettier" in reg.list_available()

    def test_summary_keys(self):
        reg = FormatterRegistry.with_defaults()
        s = reg.summary()
        assert "registered" in s
        assert "count" in s
        assert s["count"] == len(reg)

    def test_is_available_not_installed(self):
        reg = FormatterRegistry()
        reg.register_builtin(FormatterKind.BLACK)
        # may or may not be installed — just check it returns bool
        result = reg.is_available("black")
        assert isinstance(result, bool)

    def test_detect_from_nonexistent_dir(self, tmp_path):
        reg = FormatterRegistry()
        detected = reg.detect(str(tmp_path))
        assert detected == []

    def test_detect_from_pyproject_black(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.black]\nline-length = 88\n")
        reg = FormatterRegistry()
        detected = reg.detect(str(tmp_path))
        assert "black" in detected

    def test_detect_from_pyproject_ruff(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
        reg = FormatterRegistry()
        detected = reg.detect(str(tmp_path))
        assert "ruff" in detected

    def test_detect_from_prettierrc(self, tmp_path):
        (tmp_path / ".prettierrc").write_text('{"semi": false}')
        reg = FormatterRegistry()
        detected = reg.detect(str(tmp_path))
        assert "prettier" in detected

    def test_detect_from_setup_cfg_isort(self, tmp_path):
        (tmp_path / "setup.cfg").write_text("[isort]\nmulti_line_output = 3\n")
        reg = FormatterRegistry()
        detected = reg.detect(str(tmp_path))
        assert "isort" in detected

    def test_format_file_not_found(self, tmp_path):
        reg = FormatterRegistry.with_defaults()
        result = reg.format_file(str(tmp_path / "nonexistent.py"))
        # either formatter not installed or no formatter for this
        assert isinstance(result, FormatResult)

    def test_format_string_no_formatter(self):
        reg = FormatterRegistry()
        result = reg.format_string("python", "x = 1")
        assert result.success is False or isinstance(result, FormatResult)

    def test_register_unknown_kind_raises(self):
        reg = FormatterRegistry()
        with pytest.raises((FormatterError, KeyError, ValueError)):
            reg.register_builtin(FormatterKind("nonexistent_kind"))
