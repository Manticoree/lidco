"""Tests for src/lidco/editing/batch_editor.py."""
from lidco.editing.patch_parser import PatchParser, PatchFile
from lidco.editing.patch_applier import PatchApplier, PatchApplyResult
from lidco.editing.batch_editor import BatchEditor, BatchEditResult


DIFF_A = """\
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
-old_a
+new_a
 context
"""

DIFF_B = """\
--- a/b.py
+++ b/b.py
@@ -1,2 +1,2 @@
-old_b
+new_b
 ctx
"""


def parse(diff_text):
    return PatchParser().parse_file(diff_text)


class TestBatchEditResult:
    def test_fields(self):
        r = BatchEditResult(applied=2, failed=0, results={})
        assert r.applied == 2
        assert r.failed == 0
        assert r.results == {}

    def test_results_dict(self):
        ar = PatchApplyResult(success=True, result_text="ok")
        r = BatchEditResult(applied=1, failed=0, results={"f": ar})
        assert "f" in r.results


class TestBatchEditor:
    def test_init_default_applier(self):
        be = BatchEditor()
        assert be._applier is not None

    def test_init_custom_applier(self):
        applier = PatchApplier()
        be = BatchEditor(applier=applier)
        assert be._applier is applier

    def test_apply_all_two_files(self):
        be = BatchEditor()
        patches = {
            "a.py": ("old_a\ncontext\n", parse(DIFF_A)),
            "b.py": ("old_b\nctx\n", parse(DIFF_B)),
        }
        result = be.apply_all(patches)
        assert isinstance(result, BatchEditResult)
        assert result.applied == 2
        assert result.failed == 0

    def test_apply_all_results_populated(self):
        be = BatchEditor()
        patches = {"a.py": ("old_a\ncontext\n", parse(DIFF_A))}
        result = be.apply_all(patches)
        assert "a.py" in result.results

    def test_apply_all_success_content(self):
        be = BatchEditor()
        patches = {"a.py": ("old_a\ncontext\n", parse(DIFF_A))}
        result = be.apply_all(patches)
        assert result.results["a.py"].success
        assert "new_a" in result.results["a.py"].result_text

    def test_apply_all_empty(self):
        be = BatchEditor()
        result = be.apply_all({})
        assert result.applied == 0
        assert result.failed == 0

    def test_apply_all_stop_on_error(self):
        be = BatchEditor()
        # Create a patch that will fail (bad hunk)
        from lidco.editing.patch_parser import PatchHunk
        bad_patch = PatchFile(
            old_path="x.py",
            new_path="x.py",
            hunks=[PatchHunk(old_start=999, old_count=1, new_start=999, new_count=1, lines=["-nonexistent", "+new"])]
        )
        patches = {
            "bad.py": ("short text\n", bad_patch),
            "a.py": ("old_a\ncontext\n", parse(DIFF_A)),
        }
        result = be.apply_all(patches, stop_on_error=True)
        # At least one was processed
        assert len(result.results) >= 1

    def test_apply_all_no_stop_on_error(self):
        be = BatchEditor()
        patches = {
            "a.py": ("old_a\ncontext\n", parse(DIFF_A)),
            "b.py": ("old_b\nctx\n", parse(DIFF_B)),
        }
        result = be.apply_all(patches, stop_on_error=False)
        assert result.applied == 2

    def test_rollback_returns_originals_for_failed(self):
        be = BatchEditor()
        # Make a result with a failed entry
        failed_result = PatchApplyResult(success=False, result_text="original_content", error="err")
        batch = BatchEditResult(applied=0, failed=1, results={"fail.py": failed_result})
        originals = be.rollback(batch)
        assert "fail.py" in originals
        assert originals["fail.py"] == "original_content"

    def test_rollback_empty_if_all_success(self):
        be = BatchEditor()
        success_result = PatchApplyResult(success=True, result_text="new_content")
        batch = BatchEditResult(applied=1, failed=0, results={"ok.py": success_result})
        originals = be.rollback(batch)
        assert originals == {}

    def test_apply_all_single_file_success(self):
        be = BatchEditor()
        pf = PatchFile(old_path="c.py", new_path="c.py", hunks=[])
        patches = {"c.py": ("content", pf)}
        result = be.apply_all(patches)
        assert result.applied == 1

    def test_batch_edit_result_defaults(self):
        r = BatchEditResult(applied=0, failed=0)
        assert r.results == {}
