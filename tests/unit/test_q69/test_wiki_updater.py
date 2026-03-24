"""Tests for Task 466: WikiUpdater."""
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from lidco.wiki.updater import WikiUpdater


def _write_py(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_text("x = 1\n", encoding="utf-8")
    return p


class TestWikiUpdater:
    def test_update_py_file_returns_path(self, tmp_path):
        _write_py(tmp_path, "mod.py")
        updater = WikiUpdater(debounce_s=0)
        from lidco.wiki.generator import WikiGenerator
        with patch.object(WikiGenerator, "generate_module", return_value=MagicMock(module_path="mod.py")), \
             patch.object(WikiGenerator, "_wiki_path", return_value=tmp_path / "mod.md"):
            result = updater.update_on_change(["mod.py"], tmp_path)
        assert len(result) == 1

    def test_non_py_files_skipped(self, tmp_path):
        updater = WikiUpdater(debounce_s=0)
        result = updater.update_on_change(["style.css", "config.json"], tmp_path)
        assert result == []

    def test_debounce_prevents_rapid_update(self, tmp_path):
        _write_py(tmp_path, "fast.py")
        updater = WikiUpdater(debounce_s=60)
        from lidco.wiki.generator import WikiGenerator
        call_count = [0]

        def fake_generate(path, project_dir):
            call_count[0] += 1
            return MagicMock(module_path=path)

        with patch.object(WikiGenerator, "generate_module", side_effect=fake_generate), \
             patch.object(WikiGenerator, "_wiki_path", return_value=tmp_path / "fast.md"):
            updater.update_on_change(["fast.py"], tmp_path)
            updater.update_on_change(["fast.py"], tmp_path)  # should be debounced
        assert call_count[0] == 1

    def test_force_update_bypasses_debounce(self, tmp_path):
        _write_py(tmp_path, "forced.py")
        updater = WikiUpdater(debounce_s=60)
        from lidco.wiki.generator import WikiGenerator
        call_count = [0]

        def fake_generate(path, project_dir):
            call_count[0] += 1
            return MagicMock(module_path=path)

        with patch.object(WikiGenerator, "generate_module", side_effect=fake_generate), \
             patch.object(WikiGenerator, "_wiki_path", return_value=tmp_path / "forced.md"):
            updater.update_on_change(["forced.py"], tmp_path)
            result = updater.force_update("forced.py", tmp_path)
        assert call_count[0] == 2

    def test_error_handling_does_not_crash(self, tmp_path):
        _write_py(tmp_path, "err.py")
        updater = WikiUpdater(debounce_s=0)
        from lidco.wiki.generator import WikiGenerator
        with patch.object(WikiGenerator, "generate_module", side_effect=RuntimeError("fail")):
            result = updater.update_on_change(["err.py"], tmp_path)
        assert result == []

    def test_empty_file_list(self, tmp_path):
        updater = WikiUpdater()
        assert updater.update_on_change([], tmp_path) == []
