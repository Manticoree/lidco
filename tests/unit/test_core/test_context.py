"""Tests for project context compaction."""

from lidco.core.context import GitInfo, ProjectContext, ProjectDependencies


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
