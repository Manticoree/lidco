"""Tests for ContextExcludeFile (.lidcoignore support)."""

import os
import time

from pathlib import Path

from lidco.context.exclude_file import ContextExcludeFile, ExcludePattern, ExcludeResult


def test_load_patterns_from_lidcoignore(tmp_path):
    (tmp_path / ".lidcoignore").write_text("*.pyc\n__pycache__/\n")
    ef = ContextExcludeFile(tmp_path)
    patterns = ef.load()
    assert len(patterns) == 2
    assert patterns[0].pattern == "*.pyc"
    assert patterns[0].negated is False
    assert patterns[1].pattern == "__pycache__/"
    assert patterns[1].source == str(tmp_path / ".lidcoignore")


def test_load_fallback_to_lidco_ignore(tmp_path):
    d = tmp_path / ".lidco"
    d.mkdir()
    (d / "ignore").write_text("dist/\n")
    ef = ContextExcludeFile(tmp_path)
    patterns = ef.load()
    assert len(patterns) == 1
    assert patterns[0].pattern == "dist/"
    assert patterns[0].source == str(d / "ignore")


def test_primary_takes_precedence_over_secondary(tmp_path):
    """When both .lidcoignore and .lidco/ignore exist, primary wins."""
    (tmp_path / ".lidcoignore").write_text("*.pyc\n")
    d = tmp_path / ".lidco"
    d.mkdir()
    (d / "ignore").write_text("*.log\n")
    ef = ContextExcludeFile(tmp_path)
    patterns = ef.load()
    assert len(patterns) == 1
    assert patterns[0].pattern == "*.pyc"


def test_is_excluded_glob_match(tmp_path):
    (tmp_path / ".lidcoignore").write_text("*.pyc\n")
    ef = ContextExcludeFile(tmp_path)
    result = ef.is_excluded(str(tmp_path / "foo.pyc"))
    assert result.excluded is True
    assert result.matched_pattern == "*.pyc"


def test_is_excluded_not_matched(tmp_path):
    (tmp_path / ".lidcoignore").write_text("*.pyc\n")
    ef = ContextExcludeFile(tmp_path)
    result = ef.is_excluded(str(tmp_path / "foo.py"))
    assert result.excluded is False
    assert result.matched_pattern == ""


def test_is_excluded_double_star(tmp_path):
    (tmp_path / ".lidcoignore").write_text("**/node_modules/**\n")
    ef = ContextExcludeFile(tmp_path)
    result = ef.is_excluded("frontend/node_modules/react/index.js")
    assert result.excluded is True


def test_negation_pattern_re_includes(tmp_path):
    (tmp_path / ".lidcoignore").write_text("*.log\n!important.log\n")
    ef = ContextExcludeFile(tmp_path)
    assert ef.is_excluded("debug.log").excluded is True
    assert ef.is_excluded("important.log").excluded is False


def test_negation_pattern_parsed_correctly(tmp_path):
    (tmp_path / ".lidcoignore").write_text("!keep_me.txt\n")
    ef = ContextExcludeFile(tmp_path)
    patterns = ef.load()
    assert len(patterns) == 1
    assert patterns[0].negated is True
    assert patterns[0].pattern == "keep_me.txt"


def test_comments_and_blank_lines_skipped(tmp_path):
    (tmp_path / ".lidcoignore").write_text("# comment\n\n*.tmp\n  \n# another\n")
    ef = ContextExcludeFile(tmp_path)
    patterns = ef.load()
    assert len(patterns) == 1
    assert patterns[0].pattern == "*.tmp"


def test_filter_paths_returns_non_excluded(tmp_path):
    (tmp_path / ".lidcoignore").write_text("*.pyc\n")
    ef = ContextExcludeFile(tmp_path)
    paths = ["foo.py", "bar.pyc", "baz.py"]
    filtered = ef.filter_paths(paths)
    assert "bar.pyc" not in filtered
    assert "foo.py" in filtered
    assert "baz.py" in filtered


def test_filter_paths_empty_input(tmp_path):
    (tmp_path / ".lidcoignore").write_text("*.pyc\n")
    ef = ContextExcludeFile(tmp_path)
    assert ef.filter_paths([]) == []


def test_directory_pattern_trailing_slash(tmp_path):
    (tmp_path / ".lidcoignore").write_text("build/\n")
    ef = ContextExcludeFile(tmp_path)
    assert ef.is_excluded("build/output.js").excluded is True


def test_directory_pattern_matches_dir_itself(tmp_path):
    (tmp_path / ".lidcoignore").write_text("build/\n")
    ef = ContextExcludeFile(tmp_path)
    assert ef.is_excluded("build").excluded is True


def test_add_pattern_appends_to_file(tmp_path):
    ef = ContextExcludeFile(tmp_path)
    ef.add_pattern("*.log")
    content = (tmp_path / ".lidcoignore").read_text()
    assert "*.log" in content


def test_add_pattern_to_existing_file(tmp_path):
    (tmp_path / ".lidcoignore").write_text("*.pyc\n")
    ef = ContextExcludeFile(tmp_path)
    ef.add_pattern("*.log")
    content = (tmp_path / ".lidcoignore").read_text()
    assert "*.pyc" in content
    assert "*.log" in content


def test_add_pattern_ensures_newline_separator(tmp_path):
    # File without trailing newline
    (tmp_path / ".lidcoignore").write_text("*.pyc")
    ef = ContextExcludeFile(tmp_path)
    ef.add_pattern("*.log")
    content = (tmp_path / ".lidcoignore").read_text()
    assert "*.pyc\n*.log\n" == content


def test_remove_pattern_deletes_from_file(tmp_path):
    (tmp_path / ".lidcoignore").write_text("*.pyc\n*.log\n")
    ef = ContextExcludeFile(tmp_path)
    removed = ef.remove_pattern("*.log")
    assert removed is True
    content = (tmp_path / ".lidcoignore").read_text()
    assert "*.log" not in content
    assert "*.pyc" in content


def test_remove_pattern_not_found(tmp_path):
    (tmp_path / ".lidcoignore").write_text("*.pyc\n")
    ef = ContextExcludeFile(tmp_path)
    removed = ef.remove_pattern("*.log")
    assert removed is False


def test_remove_pattern_no_file(tmp_path):
    ef = ContextExcludeFile(tmp_path)
    assert ef.remove_pattern("*.log") is False


def test_no_exclude_file_returns_all_included(tmp_path):
    ef = ContextExcludeFile(tmp_path)
    result = ef.is_excluded("anything.py")
    assert result.excluded is False
    assert result.matched_pattern == ""


def test_no_exclude_file_load_returns_empty(tmp_path):
    ef = ContextExcludeFile(tmp_path)
    assert ef.load() == []


def test_list_patterns_returns_cached(tmp_path):
    (tmp_path / ".lidcoignore").write_text("*.pyc\n*.log\n")
    ef = ContextExcludeFile(tmp_path)
    listed = ef.list_patterns()
    assert len(listed) == 2
    assert listed[0].pattern == "*.pyc"
    assert listed[1].pattern == "*.log"


def test_cache_invalidation_on_mtime_change(tmp_path):
    f = tmp_path / ".lidcoignore"
    f.write_text("*.pyc\n")
    ef = ContextExcludeFile(tmp_path)
    assert ef.is_excluded("foo.pyc").excluded is True
    assert ef.is_excluded("bar.log").excluded is False
    # Modify file and force new mtime
    time.sleep(0.01)
    f.write_text("*.pyc\n*.log\n")
    t = time.time()
    os.utime(f, (t, t + 1))
    assert ef.is_excluded("bar.log").excluded is True


def test_cache_not_reloaded_when_mtime_same(tmp_path):
    f = tmp_path / ".lidcoignore"
    f.write_text("*.pyc\n")
    ef = ContextExcludeFile(tmp_path)
    ef.load()
    original_patterns = ef._patterns
    # Access again without changing mtime
    patterns = ef._get_patterns()
    assert patterns is original_patterns


def test_exclude_pattern_dataclass():
    ep = ExcludePattern(pattern="*.pyc", source="/path/.lidcoignore", negated=False)
    assert ep.pattern == "*.pyc"
    assert ep.source == "/path/.lidcoignore"
    assert ep.negated is False


def test_exclude_result_dataclass():
    er = ExcludeResult(excluded=True, matched_pattern="*.pyc")
    assert er.excluded is True
    assert er.matched_pattern == "*.pyc"


def test_multiple_negation_last_wins(tmp_path):
    """Last matching pattern wins: exclude, re-include, exclude again."""
    (tmp_path / ".lidcoignore").write_text("*.log\n!*.log\n*.log\n")
    ef = ContextExcludeFile(tmp_path)
    # Last pattern is *.log (exclude), so it should be excluded
    assert ef.is_excluded("debug.log").excluded is True


def test_oserror_on_load_returns_empty(tmp_path):
    """If file disappears between find and read, return empty."""
    ef = ContextExcludeFile(tmp_path)
    # No file exists
    assert ef.load() == []


def test_relative_path_input(tmp_path):
    """Paths not under project_root are handled gracefully."""
    (tmp_path / ".lidcoignore").write_text("*.pyc\n")
    ef = ContextExcludeFile(tmp_path)
    # Pass a relative path that can't be resolved under project root
    result = ef.is_excluded("some/relative/foo.pyc")
    assert result.excluded is True


def test_backslash_paths_normalized(tmp_path):
    """Windows-style backslash paths are normalized."""
    (tmp_path / ".lidcoignore").write_text("*.pyc\n")
    ef = ContextExcludeFile(tmp_path)
    result = ef.is_excluded("src\\models\\cache.pyc")
    assert result.excluded is True
