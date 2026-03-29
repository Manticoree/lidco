"""Tests for src/lidco/editing/patch_parser.py."""
from lidco.editing.patch_parser import PatchParser, PatchFile, PatchHunk


SIMPLE_DIFF = """\
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 line1
-line2
+line2_modified
+line3_new
 line4
"""

MULTIFILE_DIFF = """\
--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,2 @@
-old
+new
 context
--- a/bar.py
+++ b/bar.py
@@ -1,1 +1,1 @@
-bar_old
+bar_new
"""

NEW_FILE_DIFF = """\
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,2 @@
+line1
+line2
"""

DELETED_FILE_DIFF = """\
--- a/old_file.py
+++ /dev/null
@@ -1,2 +0,0 @@
-line1
-line2
"""


class TestPatchHunk:
    def test_dataclass_fields(self):
        hunk = PatchHunk(old_start=1, old_count=3, new_start=1, new_count=4, lines=[])
        assert hunk.old_start == 1
        assert hunk.old_count == 3
        assert hunk.new_start == 1
        assert hunk.new_count == 4

    def test_lines_default_empty(self):
        hunk = PatchHunk(old_start=1, old_count=1, new_start=1, new_count=1)
        assert hunk.lines == []

    def test_lines_stored(self):
        hunk = PatchHunk(1, 1, 1, 1, ["-old", "+new"])
        assert len(hunk.lines) == 2


class TestPatchFile:
    def test_dataclass_fields(self):
        pf = PatchFile(old_path="a/foo.py", new_path="b/foo.py")
        assert pf.old_path == "a/foo.py"
        assert pf.new_path == "b/foo.py"

    def test_is_new_file_true(self):
        pf = PatchFile(old_path="/dev/null", new_path="new.py")
        assert pf.is_new_file is True

    def test_is_new_file_false(self):
        pf = PatchFile(old_path="old.py", new_path="new.py")
        assert pf.is_new_file is False

    def test_is_deleted_true(self):
        pf = PatchFile(old_path="old.py", new_path="/dev/null")
        assert pf.is_deleted is True

    def test_is_deleted_false(self):
        pf = PatchFile(old_path="old.py", new_path="new.py")
        assert pf.is_deleted is False

    def test_hunks_default_empty(self):
        pf = PatchFile(old_path="a", new_path="b")
        assert pf.hunks == []


class TestPatchParser:
    def test_parse_simple_diff(self):
        parser = PatchParser()
        files = parser.parse(SIMPLE_DIFF)
        assert len(files) == 1

    def test_parse_correct_paths(self):
        parser = PatchParser()
        files = parser.parse(SIMPLE_DIFF)
        assert files[0].old_path == "foo.py"
        assert files[0].new_path == "foo.py"

    def test_parse_hunk_count(self):
        parser = PatchParser()
        files = parser.parse(SIMPLE_DIFF)
        assert len(files[0].hunks) == 1

    def test_parse_hunk_header(self):
        parser = PatchParser()
        files = parser.parse(SIMPLE_DIFF)
        h = files[0].hunks[0]
        assert h.old_start == 1
        assert h.new_start == 1

    def test_parse_hunk_lines(self):
        parser = PatchParser()
        files = parser.parse(SIMPLE_DIFF)
        h = files[0].hunks[0]
        assert any(l.startswith("-") for l in h.lines)
        assert any(l.startswith("+") for l in h.lines)

    def test_parse_multifile(self):
        parser = PatchParser()
        files = parser.parse(MULTIFILE_DIFF)
        assert len(files) == 2

    def test_parse_multifile_paths(self):
        parser = PatchParser()
        files = parser.parse(MULTIFILE_DIFF)
        names = [f.old_path for f in files]
        assert "foo.py" in names
        assert "bar.py" in names

    def test_parse_new_file(self):
        parser = PatchParser()
        files = parser.parse(NEW_FILE_DIFF)
        assert files[0].is_new_file

    def test_parse_deleted_file(self):
        parser = PatchParser()
        files = parser.parse(DELETED_FILE_DIFF)
        assert files[0].is_deleted

    def test_parse_empty_string(self):
        parser = PatchParser()
        files = parser.parse("")
        assert files == []

    def test_parse_file_returns_first(self):
        parser = PatchParser()
        pf = parser.parse_file(MULTIFILE_DIFF)
        assert isinstance(pf, PatchFile)
        assert pf.old_path == "foo.py"

    def test_parse_file_empty(self):
        parser = PatchParser()
        pf = parser.parse_file("")
        assert isinstance(pf, PatchFile)

    def test_summary_single_file(self):
        parser = PatchParser()
        files = parser.parse(SIMPLE_DIFF)
        s = parser.summary(files)
        assert "1 file" in s
        assert "+" in s
        assert "-" in s

    def test_summary_multifile(self):
        parser = PatchParser()
        files = parser.parse(MULTIFILE_DIFF)
        s = parser.summary(files)
        assert "2 files" in s

    def test_summary_empty(self):
        parser = PatchParser()
        s = parser.summary([])
        assert "0 files" in s or "0 file" in s

    def test_summary_added_count(self):
        parser = PatchParser()
        files = parser.parse(SIMPLE_DIFF)
        s = parser.summary(files)
        # SIMPLE_DIFF has 2 added lines (+line2_modified, +line3_new)
        assert "+2" in s

    def test_summary_removed_count(self):
        parser = PatchParser()
        files = parser.parse(SIMPLE_DIFF)
        s = parser.summary(files)
        assert "-1" in s
