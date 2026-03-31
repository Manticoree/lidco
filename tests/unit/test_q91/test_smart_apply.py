"""Tests for lidco.editing.smart_apply — SmartApply code block applier."""

import pytest
from pathlib import Path

from lidco.editing.smart_apply import SmartApply, ApplyCandidate, SmartApplyResult


# ---------------------------------------------------------------------------
# extract_code_blocks
# ---------------------------------------------------------------------------


def test_extract_code_blocks_single():
    sa = SmartApply()
    text = "Here is code:\n```python\nprint('hello')\n```"
    blocks = sa.extract_code_blocks(text)
    assert len(blocks) == 1
    assert blocks[0][0] == "python"
    assert "print" in blocks[0][1]


def test_extract_code_blocks_multiple():
    sa = SmartApply()
    text = "```python\ndef foo(): pass\n```\n```javascript\nconst x = 1;\n```"
    blocks = sa.extract_code_blocks(text)
    assert len(blocks) == 2
    assert blocks[0][0] == "python"
    assert blocks[1][0] == "javascript"


def test_extract_code_blocks_with_fence_info():
    sa = SmartApply()
    text = "```src/main.py\nx = 1\n```"
    blocks = sa.extract_code_blocks(text)
    assert blocks[0][0] == "src/main.py"


def test_extract_code_blocks_empty():
    sa = SmartApply()
    assert sa.extract_code_blocks("no code here") == []


def test_extract_code_blocks_no_fence_info():
    sa = SmartApply()
    text = "```\nraw code\n```"
    blocks = sa.extract_code_blocks(text)
    assert len(blocks) == 1
    assert blocks[0][0] == ""
    assert "raw code" in blocks[0][1]


def test_extract_code_blocks_multiline_code():
    sa = SmartApply()
    text = "```python\nline1\nline2\nline3\n```"
    blocks = sa.extract_code_blocks(text)
    assert len(blocks) == 1
    assert blocks[0][1].count("\n") >= 2


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


def test_detect_language_from_fence():
    sa = SmartApply()
    assert sa.detect_language("python", "") == "python"
    assert sa.detect_language("typescript", "") == "typescript"
    assert sa.detect_language("go", "") == "go"
    assert sa.detect_language("rust", "") == "rust"
    assert sa.detect_language("java", "") == "java"


def test_detect_language_from_fence_case_insensitive():
    sa = SmartApply()
    assert sa.detect_language("Python", "") == "python"
    assert sa.detect_language("JAVASCRIPT", "") == "javascript"


def test_detect_language_from_file_extension():
    sa = SmartApply()
    assert sa.detect_language("src/main.py", "") == "python"
    assert sa.detect_language("app.ts", "") == "typescript"


def test_detect_language_from_python_content():
    sa = SmartApply()
    code = "def my_func():\n    return 42"
    lang = sa.detect_language("", code)
    assert lang == "python"


def test_detect_language_from_js_content():
    sa = SmartApply()
    code = "const foo = () => bar"
    lang = sa.detect_language("", code)
    assert lang == "javascript"


def test_detect_language_unknown():
    sa = SmartApply()
    assert sa.detect_language("", "???") == "unknown"


# ---------------------------------------------------------------------------
# find_target_file
# ---------------------------------------------------------------------------


def test_find_target_file_from_fence_path(tmp_path):
    f = tmp_path / "src" / "main.py"
    f.parent.mkdir()
    f.write_text("x = 1")
    sa = SmartApply(str(tmp_path))
    candidate = sa.find_target_file("x = 1", "python", hint="src/main.py")
    assert candidate is not None
    assert candidate.confidence >= 0.9
    assert candidate.reason == "fence_path"


def test_find_target_file_exact_path_confidence(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("pass")
    sa = SmartApply(str(tmp_path))
    candidate = sa.find_target_file("pass", "python", hint="app.py")
    assert candidate is not None
    assert candidate.confidence == 1.0
    assert candidate.reason == "fence_path"


def test_find_target_file_from_function_match(tmp_path):
    f = tmp_path / "utils.py"
    f.write_text("def my_helper():\n    pass\n")
    sa = SmartApply(str(tmp_path))
    candidate = sa.find_target_file(
        "def my_helper():\n    return 42", "python", hint=""
    )
    assert candidate is not None
    assert "utils.py" in candidate.file_path
    assert candidate.confidence >= 0.5
    assert candidate.reason == "function_match"


def test_find_target_file_extension_match(tmp_path):
    f = tmp_path / "something.py"
    f.write_text("# placeholder")
    sa = SmartApply(str(tmp_path))
    candidate = sa.find_target_file("x = 1", "python", hint="")
    assert candidate is not None
    assert candidate.confidence == 0.3
    assert candidate.reason == "extension_match"


def test_find_target_file_no_match_returns_none(tmp_path):
    sa = SmartApply(str(tmp_path))
    candidate = sa.find_target_file("some random text", "unknown", hint="")
    assert candidate is None


def test_find_target_file_no_files_returns_none(tmp_path):
    sa = SmartApply(str(tmp_path))
    candidate = sa.find_target_file("def foo(): pass", "python", hint="")
    assert candidate is None


# ---------------------------------------------------------------------------
# apply_block
# ---------------------------------------------------------------------------


def test_apply_block_dry_run(tmp_path):
    f = tmp_path / "foo.py"
    f.write_text("x = 1\n")
    sa = SmartApply(str(tmp_path))
    result = sa.apply_block("x = 2\n", str(f), dry_run=True)
    assert result.applied is False
    assert f.read_text() == "x = 1\n"  # unchanged
    assert result.diff_preview != ""


def test_apply_block_writes_file(tmp_path):
    f = tmp_path / "foo.py"
    f.write_text("x = 1\n")
    sa = SmartApply(str(tmp_path))
    result = sa.apply_block("x = 2\n", str(f), dry_run=False)
    assert result.applied is True
    assert f.read_text() == "x = 2\n"


def test_apply_block_creates_parent_dirs(tmp_path):
    target = tmp_path / "deep" / "nested" / "file.py"
    sa = SmartApply(str(tmp_path))
    result = sa.apply_block("new content\n", str(target), dry_run=False)
    assert result.applied is True
    assert target.exists()
    assert target.read_text() == "new content\n"


def test_apply_block_new_file_has_diff(tmp_path):
    target = tmp_path / "new.py"
    sa = SmartApply(str(tmp_path))
    result = sa.apply_block("x = 1\n", str(target), dry_run=True)
    assert result.diff_preview != ""


def test_apply_block_outside_root_rejected(tmp_path):
    sa = SmartApply(str(tmp_path))
    result = sa.apply_block("evil", "/etc/passwd", dry_run=False)
    assert result.applied is False
    assert result.error != ""


def test_apply_block_diff_preview_content(tmp_path):
    f = tmp_path / "foo.py"
    f.write_text("line1\nline2\n")
    sa = SmartApply(str(tmp_path))
    result = sa.apply_block("line1\nline3\n", str(f), dry_run=True)
    assert "line2" in result.diff_preview
    assert "line3" in result.diff_preview


# ---------------------------------------------------------------------------
# apply_all
# ---------------------------------------------------------------------------


def test_apply_all_skips_empty_blocks(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("pass")
    sa = SmartApply(str(tmp_path))
    text = "```python\n   \n```"
    results = sa.apply_all(text, dry_run=True)
    assert len(results) == 0


def test_apply_all_skips_low_confidence(tmp_path):
    sa = SmartApply(str(tmp_path))
    # No Python files in project, no fence hint -> no candidate
    text = "```python\nprint('hi')\n```"
    results = sa.apply_all(text, dry_run=True)
    assert all(not r.applied for r in results)


def test_apply_all_dry_run_does_not_write(tmp_path):
    f = tmp_path / "target.py"
    f.write_text("original")
    sa = SmartApply(str(tmp_path))
    text = "```target.py\nnew content\n```"
    results = sa.apply_all(text, dry_run=True)
    assert f.read_text() == "original"


def test_apply_all_processes_multiple_blocks(tmp_path):
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("def foo(): pass")
    f2.write_text("def bar(): pass")
    sa = SmartApply(str(tmp_path))
    text = "```a.py\ndef foo(): return 1\n```\n```b.py\ndef bar(): return 2\n```"
    results = sa.apply_all(text, dry_run=False)
    assert len(results) == 2
    assert all(r.applied for r in results)


# ---------------------------------------------------------------------------
# dataclass fields
# ---------------------------------------------------------------------------


def test_apply_candidate_fields():
    c = ApplyCandidate("foo.py", 0.8, "fence_path", "python")
    assert c.file_path == "foo.py"
    assert c.confidence == 0.8
    assert c.reason == "fence_path"
    assert c.language == "python"


def test_apply_result_default_error():
    r = SmartApplyResult("foo.py", True, "diff")
    assert r.error == ""


def test_apply_result_with_error():
    r = SmartApplyResult("foo.py", False, "", "something went wrong")
    assert r.error == "something went wrong"
    assert r.applied is False
