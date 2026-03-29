"""Tests for src/lidco/editing/patch_applier.py."""
from lidco.editing.patch_parser import PatchParser, PatchFile, PatchHunk
from lidco.editing.patch_applier import PatchApplier, ApplyResult, ApplyError


SIMPLE_DIFF = """\
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,3 @@
 line1
-line2
+line2_modified
 line3
"""

NEW_FILE_DIFF = """\
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,2 @@
+alpha
+beta
"""

ORIGINAL = "line1\nline2\nline3\n"


class TestApplyResult:
    def test_success_fields(self):
        r = ApplyResult(success=True, result_text="hello")
        assert r.success is True
        assert r.result_text == "hello"
        assert r.error == ""

    def test_failure_fields(self):
        r = ApplyResult(success=False, result_text="", error="mismatch")
        assert r.success is False
        assert r.error == "mismatch"


class TestPatchApplier:
    def _parse(self, diff_text):
        return PatchParser().parse_file(diff_text)

    def test_apply_simple_diff(self):
        applier = PatchApplier()
        pf = self._parse(SIMPLE_DIFF)
        result = applier.apply(ORIGINAL, pf)
        assert result.success
        assert "line2_modified" in result.result_text

    def test_apply_removes_old_line(self):
        applier = PatchApplier()
        pf = self._parse(SIMPLE_DIFF)
        result = applier.apply(ORIGINAL, pf)
        assert "line2\n" not in result.result_text

    def test_apply_preserves_context(self):
        applier = PatchApplier()
        pf = self._parse(SIMPLE_DIFF)
        result = applier.apply(ORIGINAL, pf)
        assert "line1" in result.result_text
        assert "line3" in result.result_text

    def test_apply_new_file(self):
        applier = PatchApplier()
        pf = self._parse(NEW_FILE_DIFF)
        result = applier.apply("", pf)
        assert result.success
        assert "alpha" in result.result_text

    def test_apply_returns_apply_result(self):
        applier = PatchApplier()
        pf = self._parse(SIMPLE_DIFF)
        result = applier.apply(ORIGINAL, pf)
        assert isinstance(result, ApplyResult)

    def test_apply_empty_patch(self):
        applier = PatchApplier()
        pf = PatchFile(old_path="a", new_path="b", hunks=[])
        result = applier.apply(ORIGINAL, pf)
        assert result.success
        assert result.result_text == ORIGINAL

    def test_dry_run_does_not_change_original(self):
        applier = PatchApplier()
        pf = self._parse(SIMPLE_DIFF)
        original = "line1\nline2\nline3\n"
        result = applier.dry_run(original, pf)
        # original variable should be unchanged
        assert original == "line1\nline2\nline3\n"

    def test_dry_run_returns_result(self):
        applier = PatchApplier()
        pf = self._parse(SIMPLE_DIFF)
        result = applier.dry_run(ORIGINAL, pf)
        assert isinstance(result, ApplyResult)

    def test_dry_run_success(self):
        applier = PatchApplier()
        pf = self._parse(SIMPLE_DIFF)
        result = applier.dry_run(ORIGINAL, pf)
        assert result.success

    def test_apply_multiline_addition(self):
        diff = """\
--- a/file.py
+++ b/file.py
@@ -1,1 +1,3 @@
 first
+second
+third
"""
        applier = PatchApplier()
        pf = self._parse(diff)
        result = applier.apply("first\n", pf)
        assert result.success
        assert "second" in result.result_text
        assert "third" in result.result_text

    def test_apply_fuzzy_match(self):
        # Content with slight offset — fuzzy should still work
        diff = """\
--- a/file.py
+++ b/file.py
@@ -2,3 +2,3 @@
 context_a
-old_line
+new_line
 context_b
"""
        applier = PatchApplier()
        pf = self._parse(diff)
        original = "extra\ncontext_a\nold_line\ncontext_b\n"
        result = applier.apply(original, pf)
        assert result.success
        assert "new_line" in result.result_text

    def test_apply_strict_mode(self):
        applier = PatchApplier()
        pf = self._parse(SIMPLE_DIFF)
        result = applier.apply(ORIGINAL, pf, strict=True)
        assert isinstance(result, ApplyResult)

    def test_apply_error_field_on_success(self):
        applier = PatchApplier()
        pf = PatchFile(old_path="a", new_path="b", hunks=[])
        result = applier.apply(ORIGINAL, pf)
        assert result.error == ""

    def test_apply_error_instance(self):
        e = ApplyError("test error")
        assert str(e) == "test error"
        assert isinstance(e, Exception)
