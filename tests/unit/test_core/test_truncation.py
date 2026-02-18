"""Tests for tool result truncation."""

from lidco.core.truncation import truncate_tool_result


class TestTruncateToolResult:
    """Tests for the main truncate_tool_result dispatcher."""

    def test_short_output_unchanged(self):
        output = "hello world"
        result = truncate_tool_result("file_read", output)
        assert result == output

    def test_short_output_at_limit(self):
        output = "x" * 12000
        result = truncate_tool_result("file_read", output, max_chars=12000)
        assert result == output

    def test_custom_max_chars(self):
        output = "x" * 200
        result = truncate_tool_result("unknown_tool", output, max_chars=50)
        assert "truncated" in result
        assert len(result) < len(output) + 100


class TestFileReadTruncation:
    """Tests for file_read truncation strategy."""

    def test_large_file_keeps_head_and_tail(self):
        lines = [f"line {i}" for i in range(500)]
        output = "\n".join(lines)
        result = truncate_tool_result("file_read", output, max_chars=100)

        assert "line 0" in result
        assert "line 79" in result
        assert "line 499" in result
        assert "line 480" in result
        assert "400 lines omitted" in result

    def test_file_within_head_tail_range(self):
        lines = [f"line {i}" for i in range(95)]
        output = "\n".join(lines)
        # 95 lines < 80 + 20 = 100, so no truncation by lines
        result = truncate_tool_result("file_read", output, max_chars=100)
        assert result == output

    def test_exactly_at_boundary(self):
        lines = [f"line {i}" for i in range(100)]
        output = "\n".join(lines)
        result = truncate_tool_result("file_read", output, max_chars=100)
        assert result == output


class TestSearchTruncation:
    """Tests for grep/glob truncation strategy."""

    def test_grep_truncates_many_results(self):
        lines = [f"src/file{i}.py:10: match" for i in range(100)]
        output = "\n".join(lines)
        result = truncate_tool_result("grep", output, max_chars=100)

        assert "file0" in result
        assert "file29" in result
        assert "70 more matches" in result

    def test_glob_truncates_many_results(self):
        lines = [f"src/file{i}.py" for i in range(60)]
        output = "\n".join(lines)
        result = truncate_tool_result("glob", output, max_chars=100)

        assert "file0" in result
        assert "30 more matches" in result

    def test_few_results_unchanged(self):
        lines = [f"src/file{i}.py" for i in range(10)]
        output = "\n".join(lines)
        result = truncate_tool_result("grep", output, max_chars=100)
        assert result == output


class TestBashTruncation:
    """Tests for bash output truncation strategy."""

    def test_large_bash_output(self):
        lines = [f"output line {i}" for i in range(300)]
        output = "\n".join(lines)
        result = truncate_tool_result("bash", output, max_chars=100)

        assert "output line 0" in result
        assert "output line 99" in result
        assert "output line 299" in result
        assert "180 lines omitted" in result


class TestGitTruncation:
    """Tests for git output truncation strategy."""

    def test_large_git_diff(self):
        lines = [f"diff line {i}" for i in range(300)]
        output = "\n".join(lines)
        result = truncate_tool_result("git", output, max_chars=100)

        assert "diff line 0" in result
        assert "diff line 99" in result
        assert "diff line 299" in result
        assert "180 lines omitted" in result

    def test_small_git_output_unchanged(self):
        output = "On branch main\nnothing to commit"
        result = truncate_tool_result("git", output)
        assert result == output


class TestPlainTruncation:
    """Tests for unknown tool fallback truncation."""

    def test_unknown_tool_hard_truncates(self):
        output = "a" * 20000
        result = truncate_tool_result("unknown_tool", output, max_chars=12000)

        assert result.startswith("a" * 12000)
        assert "truncated" in result
        assert "8000 chars omitted" in result
