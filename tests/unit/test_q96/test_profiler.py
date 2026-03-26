"""Tests for T614 CodeProfiler."""
import pytest
from pathlib import Path

from lidco.profiling.profiler import CodeProfiler, ProfileReport, FunctionStat


# ---------------------------------------------------------------------------
# FunctionStat
# ---------------------------------------------------------------------------

class TestFunctionStat:
    def _make(self, ncalls=10, tottime=0.1, cumtime=0.5):
        return FunctionStat(
            module="mymodule.py",
            function="myfunc",
            line=42,
            ncalls=ncalls,
            tottime=tottime,
            cumtime=cumtime,
            percall_tot=tottime / ncalls,
            percall_cum=cumtime / ncalls,
        )

    def test_qualified_name(self):
        s = self._make()
        assert "mymodule.py" in s.qualified_name
        assert "myfunc" in s.qualified_name
        assert "42" in s.qualified_name


# ---------------------------------------------------------------------------
# ProfileReport
# ---------------------------------------------------------------------------

class TestProfileReport:
    def _make(self, stats=None, error=""):
        return ProfileReport(
            label="test",
            total_calls=100,
            primitive_calls=90,
            elapsed_ms=250.0,
            stats=stats or [],
            raw_text="some raw output",
            error=error,
        )

    def test_ok_when_no_error(self):
        assert self._make().ok is True

    def test_not_ok_with_error(self):
        assert self._make(error="oops").ok is False

    def test_top_hotspots(self):
        stats = [
            FunctionStat("m.py", f"func{i}", i, 5, 0.1 * i, 0.5 * i, 0.02, 0.1)
            for i in range(20)
        ]
        # Sort by cumtime desc (highest i first)
        stats.sort(key=lambda s: s.cumtime, reverse=True)
        report = self._make(stats=stats)
        top5 = report.top_hotspots(5)
        assert len(top5) == 5
        assert top5[0].cumtime >= top5[1].cumtime

    def test_format_table_with_error(self):
        report = self._make(error="syntax error in code")
        s = report.format_table()
        assert "error" in s.lower()

    def test_format_table_normal(self):
        stats = [
            FunctionStat("m.py", "slow_func", 10, 100, 1.0, 2.0, 0.01, 0.02),
        ]
        report = self._make(stats=stats)
        s = report.format_table(n=5)
        assert "slow_func" in s
        assert "100" in s  # ncalls

    def test_summary(self):
        stats = [FunctionStat("m.py", "hot", 5, 10, 0.5, 1.0, 0.1, 0.2)]
        report = self._make(stats=stats)
        s = report.summary()
        assert "100" in s  # total_calls
        assert "hot" in s


# ---------------------------------------------------------------------------
# CodeProfiler
# ---------------------------------------------------------------------------

class TestProfileCallable:
    def test_simple_function(self):
        def work():
            return sum(range(1000))

        profiler = CodeProfiler()
        report = profiler.profile_callable(work)
        assert report.ok
        assert report.total_calls > 0
        assert report.elapsed_ms >= 0

    def test_label_used(self):
        profiler = CodeProfiler()
        report = profiler.profile_callable(lambda: None, label="my_label")
        assert report.label == "my_label"

    def test_function_with_args(self):
        def add(a, b):
            return a + b

        profiler = CodeProfiler()
        report = profiler.profile_callable(add, 2, 3)
        assert report.ok

    def test_function_raising_error(self):
        def bad():
            raise ValueError("intentional error")

        profiler = CodeProfiler()
        report = profiler.profile_callable(bad)
        assert not report.ok
        assert "intentional error" in report.error

    def test_stats_populated(self):
        def nested():
            x = 0
            for i in range(100):
                x += i
            return x

        profiler = CodeProfiler()
        report = profiler.profile_callable(nested)
        assert len(report.stats) > 0

    def test_stats_sorted_by_cumtime(self):
        def outer():
            return inner()

        def inner():
            return sum(range(500))

        profiler = CodeProfiler()
        report = profiler.profile_callable(outer)
        if len(report.stats) >= 2:
            assert report.stats[0].cumtime >= report.stats[1].cumtime


class TestProfileCode:
    def test_profile_code_string(self):
        profiler = CodeProfiler()
        report = profiler.profile_code("x = sum(range(1000))", label="my_snippet")
        assert report.ok
        assert report.label == "my_snippet"

    def test_profile_code_with_function(self):
        code = """
def compute(n):
    return [i**2 for i in range(n)]
result = compute(500)
"""
        profiler = CodeProfiler()
        report = profiler.profile_code(code)
        assert report.ok
        assert report.total_calls > 0

    def test_profile_code_syntax_error(self):
        profiler = CodeProfiler()
        report = profiler.profile_code("def broken(:")
        assert not report.ok
        assert report.error != ""

    def test_format_table_shows_lines(self):
        profiler = CodeProfiler()
        report = profiler.profile_code("y = 1 + 1")
        table = report.format_table()
        assert "ncalls" in table.lower() or "Profile" in table


class TestProfileFile:
    def test_profile_file(self, tmp_path):
        script = tmp_path / "script.py"
        script.write_text("result = sum(range(1000))\n")
        profiler = CodeProfiler()
        report = profiler.profile_file(str(script))
        assert report.ok
        assert report.label == "script.py"
        assert report.total_calls > 0

    def test_profile_nonexistent_file(self):
        profiler = CodeProfiler()
        report = profiler.profile_file("/nonexistent/path/script.py")
        assert not report.ok
        assert "not found" in report.error.lower()

    def test_profile_file_with_error(self, tmp_path):
        script = tmp_path / "bad.py"
        script.write_text("raise RuntimeError('oops')\n")
        profiler = CodeProfiler()
        report = profiler.profile_file(str(script))
        assert not report.ok
        assert "oops" in report.error

    def test_custom_label(self, tmp_path):
        script = tmp_path / "s.py"
        script.write_text("pass\n")
        profiler = CodeProfiler()
        report = profiler.profile_file(str(script), label="my_script")
        assert report.label == "my_script"

    def test_sort_by_tottime(self, tmp_path):
        script = tmp_path / "perf.py"
        script.write_text("x = [i*2 for i in range(1000)]\n")
        profiler = CodeProfiler(sort_by="tottime")
        report = profiler.profile_file(str(script))
        assert report.ok
