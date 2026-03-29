"""Tests for src/lidco/editing/edit_diff.py."""
from lidco.editing.edit_diff import EditDiff, DiffLine


OLD_TEXT = "line1\nline2\nline3\n"
NEW_TEXT = "line1\nline2_modified\nline3\nline4\n"


class TestDiffLine:
    def test_fields(self):
        dl = DiffLine(tag="+", content="new line")
        assert dl.tag == "+"
        assert dl.content == "new line"

    def test_minus_tag(self):
        dl = DiffLine(tag="-", content="old line")
        assert dl.tag == "-"

    def test_space_tag(self):
        dl = DiffLine(tag=" ", content="context")
        assert dl.tag == " "


class TestEditDiff:
    def test_diff_lines_returns_list(self):
        ed = EditDiff()
        result = ed.diff_lines(OLD_TEXT, NEW_TEXT)
        assert isinstance(result, list)

    def test_diff_lines_all_diff_lines(self):
        ed = EditDiff()
        result = ed.diff_lines(OLD_TEXT, NEW_TEXT)
        assert all(isinstance(dl, DiffLine) for dl in result)

    def test_diff_lines_has_added(self):
        ed = EditDiff()
        result = ed.diff_lines(OLD_TEXT, NEW_TEXT)
        added = [dl for dl in result if dl.tag == "+"]
        assert len(added) >= 1

    def test_diff_lines_has_removed(self):
        ed = EditDiff()
        result = ed.diff_lines(OLD_TEXT, NEW_TEXT)
        removed = [dl for dl in result if dl.tag == "-"]
        assert len(removed) >= 1

    def test_diff_lines_has_unchanged(self):
        ed = EditDiff()
        result = ed.diff_lines(OLD_TEXT, NEW_TEXT)
        unchanged = [dl for dl in result if dl.tag == " "]
        assert len(unchanged) >= 1

    def test_diff_lines_identical(self):
        ed = EditDiff()
        result = ed.diff_lines(OLD_TEXT, OLD_TEXT)
        added = [dl for dl in result if dl.tag == "+"]
        removed = [dl for dl in result if dl.tag == "-"]
        assert added == []
        assert removed == []

    def test_unified_diff_returns_str(self):
        ed = EditDiff()
        result = ed.unified_diff(OLD_TEXT, NEW_TEXT, filename="test.py")
        assert isinstance(result, str)

    def test_unified_diff_contains_filename(self):
        ed = EditDiff()
        result = ed.unified_diff(OLD_TEXT, NEW_TEXT, filename="test.py")
        assert "test.py" in result

    def test_unified_diff_has_hunks(self):
        ed = EditDiff()
        result = ed.unified_diff(OLD_TEXT, NEW_TEXT, filename="test.py")
        assert "@@" in result

    def test_unified_diff_empty_if_identical(self):
        ed = EditDiff()
        result = ed.unified_diff(OLD_TEXT, OLD_TEXT)
        assert result == ""

    def test_unified_diff_no_filename(self):
        ed = EditDiff()
        result = ed.unified_diff(OLD_TEXT, NEW_TEXT)
        assert isinstance(result, str)

    def test_unified_diff_context_lines(self):
        ed = EditDiff()
        result = ed.unified_diff(OLD_TEXT, NEW_TEXT, context=0)
        assert isinstance(result, str)

    def test_stats_returns_dict(self):
        ed = EditDiff()
        s = ed.stats(OLD_TEXT, NEW_TEXT)
        assert isinstance(s, dict)

    def test_stats_keys(self):
        ed = EditDiff()
        s = ed.stats(OLD_TEXT, NEW_TEXT)
        assert "added" in s
        assert "removed" in s
        assert "unchanged" in s

    def test_stats_added_positive(self):
        ed = EditDiff()
        s = ed.stats(OLD_TEXT, NEW_TEXT)
        assert s["added"] >= 1

    def test_stats_removed_positive(self):
        ed = EditDiff()
        s = ed.stats(OLD_TEXT, NEW_TEXT)
        assert s["removed"] >= 1

    def test_stats_identical(self):
        ed = EditDiff()
        s = ed.stats(OLD_TEXT, OLD_TEXT)
        assert s["added"] == 0
        assert s["removed"] == 0

    def test_is_identical_true(self):
        ed = EditDiff()
        assert ed.is_identical(OLD_TEXT, OLD_TEXT) is True

    def test_is_identical_false(self):
        ed = EditDiff()
        assert ed.is_identical(OLD_TEXT, NEW_TEXT) is False

    def test_is_identical_empty(self):
        ed = EditDiff()
        assert ed.is_identical("", "") is True

    def test_diff_lines_empty(self):
        ed = EditDiff()
        result = ed.diff_lines("", "")
        assert result == []

    def test_stats_unchanged_count(self):
        ed = EditDiff()
        s = ed.stats("a\nb\nc\n", "a\nb\nd\n")
        assert s["unchanged"] >= 2  # a and b are unchanged
