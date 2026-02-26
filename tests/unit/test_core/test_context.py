"""Tests for project context compaction."""

from unittest.mock import patch

from lidco.core.context import GitInfo, ProjectContext, ProjectDependencies, RecentChanges


class TestFormatDependencies:
    """Tests for compact dependency formatting."""

    def test_few_deps_shown_inline(self):
        deps = ProjectDependencies(
            production={"react": "^18", "next": "^14", "zod": "^3"},
            development={"typescript": "^5"},
        )
        result = ProjectContext._format_dependencies(deps)

        assert "Production:" in result
        assert "3 packages" in result
        assert "Development:" in result
        assert "1 packages" in result

    def test_many_prod_deps_truncated(self):
        production = {f"pkg-{i:03d}": "1.0" for i in range(50)}
        deps = ProjectDependencies(production=production)
        result = ProjectContext._format_dependencies(deps)

        assert "Production:" in result
        assert "50 packages" in result

    def test_many_dev_deps_truncated(self):
        development = {f"dev-{i:03d}": "1.0" for i in range(20)}
        deps = ProjectDependencies(development=development)
        result = ProjectContext._format_dependencies(deps)

        assert "Development:" in result
        assert "20 packages" in result

    def test_no_versions_in_compact_output(self):
        deps = ProjectDependencies(
            production={"react": "^18.2.0", "next": "^14.1.0"},
        )
        result = ProjectContext._format_dependencies(deps)
        # Compact format shows counts only, no versions
        assert "^18.2.0" not in result
        assert "2 packages" in result


class TestFormatGitInfo:
    """Tests for compact git info formatting."""

    def test_dirty_files_limited_to_5(self):
        dirty = tuple(f"M  src/file{i}.py" for i in range(20))
        gi = GitInfo(
            branch="main",
            remote="origin",
            recent_commits=("abc1234 commit 1",),
            dirty_files=dirty,
        )
        result = ProjectContext._format_git_info(gi)

        assert "Dirty Files:** 20" in result
        assert "file0" in result
        assert "file4" in result
        assert "15 more" in result
        # file5 should NOT be listed individually
        assert "`M  src/file5.py`" not in result

    def test_few_dirty_files_all_shown(self):
        dirty = tuple(f"M  src/file{i}.py" for i in range(3))
        gi = GitInfo(branch="dev", dirty_files=dirty)
        result = ProjectContext._format_git_info(gi)

        assert "file0" in result
        assert "file2" in result
        assert "more" not in result


class TestFormatRecentChanges:
    """Tests for recent git changes formatting."""

    def test_format_includes_commit_hash(self):
        changes = RecentChanges(
            diff_stat="src/foo.py | 5 +++++",
            last_commit_hash="abc1234",
            last_commit_msg="feat: add caching",
        )
        result = ProjectContext._format_recent_changes(changes)
        assert "abc1234" in result
        assert "feat: add caching" in result

    def test_format_includes_diff_stat(self):
        changes = RecentChanges(diff_stat="src/bar.py | 3 +++\n1 file changed")
        result = ProjectContext._format_recent_changes(changes)
        assert "src/bar.py" in result
        assert "1 file changed" in result

    def test_format_in_code_block(self):
        changes = RecentChanges(diff_stat="src/foo.py | 2 ++")
        result = ProjectContext._format_recent_changes(changes)
        assert "```" in result

    def test_no_changes_empty_string(self):
        changes = RecentChanges(diff_stat="")
        # _format_recent_changes still works; build_context_string skips it
        result = ProjectContext._format_recent_changes(changes)
        assert isinstance(result, str)


class TestGetRecentChanges:
    """Tests for ProjectContext.get_recent_changes()."""

    def test_empty_when_git_unavailable(self, tmp_path):
        ctx = ProjectContext(tmp_path)
        # No .git dir → git commands fail → empty result
        changes = ctx.get_recent_changes()
        assert changes.diff_stat == ""
        assert changes.last_commit_hash == ""

    def test_parses_commit_hash_and_message(self, tmp_path):
        ctx = ProjectContext(tmp_path)
        with patch.object(ctx, "_run_git") as mock_git:
            mock_git.side_effect = lambda *args: (
                "src/foo.py | 3 +++\n1 file changed, 3 insertions(+)"
                if args[0] == "diff"
                else "abc1234 feat: add feature"
            )
            changes = ctx.get_recent_changes()

        assert changes.last_commit_hash == "abc1234"
        assert changes.last_commit_msg == "feat: add feature"
        assert "src/foo.py" in changes.diff_stat

    def test_truncates_long_diff_stat(self, tmp_path):
        ctx = ProjectContext(tmp_path)
        many_files = "\n".join(f"src/file{i}.py | 1 +" for i in range(30))
        summary = "30 files changed"
        with patch.object(ctx, "_run_git") as mock_git:
            mock_git.side_effect = lambda *args: (
                f"{many_files}\n{summary}" if args[0] == "diff" else "abc feat"
            )
            changes = ctx.get_recent_changes(max_stat_lines=10)

        stat_lines = changes.diff_stat.splitlines()
        assert len(stat_lines) <= 11  # 10 files + "... (N more)" line
        assert "more files" in changes.diff_stat
