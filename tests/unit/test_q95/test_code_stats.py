"""Tests for T607 CodeStats."""
from pathlib import Path
import pytest

from lidco.stats.code_stats import (
    CodeStats,
    CodeStatsReport,
    FileStat,
    LanguageStat,
    _count_lines,
    LANGUAGE_MAP,
)


# ---------------------------------------------------------------------------
# _count_lines
# ---------------------------------------------------------------------------

class TestCountLines:
    def _py(self):
        return LANGUAGE_MAP[".py"]

    def _js(self):
        return LANGUAGE_MAP[".js"]

    def test_pure_code(self):
        code, comment, blank = _count_lines("x = 1\ny = 2\n", self._py())
        assert code == 2
        assert comment == 0
        assert blank == 0

    def test_blank_lines(self):
        code, comment, blank = _count_lines("x = 1\n\ny = 2\n", self._py())
        assert blank == 1

    def test_single_line_comment(self):
        code, comment, blank = _count_lines("# comment\nx = 1\n", self._py())
        assert comment == 1
        assert code == 1

    def test_block_comment_js(self):
        src = "/* start\n   middle\n   end */\nconst x = 1;\n"
        code, comment, blank = _count_lines(src, self._js())
        assert comment >= 2
        assert code >= 1

    def test_mixed(self):
        src = "x = 1\n# comment\n\ny = 2\n"
        code, comment, blank = _count_lines(src, self._py())
        assert code == 2
        assert comment == 1
        assert blank == 1

    def test_empty_string(self):
        code, comment, blank = _count_lines("", self._py())
        assert code == 0
        assert comment == 0
        assert blank == 0


# ---------------------------------------------------------------------------
# LANGUAGE_MAP coverage
# ---------------------------------------------------------------------------

class TestLanguageMap:
    def test_python_registered(self):
        assert ".py" in LANGUAGE_MAP
        assert LANGUAGE_MAP[".py"].name == "Python"

    def test_typescript_registered(self):
        assert ".ts" in LANGUAGE_MAP
        assert LANGUAGE_MAP[".ts"].name == "TypeScript"

    def test_rust_registered(self):
        assert ".rs" in LANGUAGE_MAP

    def test_go_registered(self):
        assert ".go" in LANGUAGE_MAP

    def test_yaml_registered(self):
        assert ".yaml" in LANGUAGE_MAP
        assert ".yml" in LANGUAGE_MAP


# ---------------------------------------------------------------------------
# CodeStats.analyze
# ---------------------------------------------------------------------------

class TestCodeStats:
    def _setup(self, tmp_path, files: dict[str, str]):
        for name, content in files.items():
            p = tmp_path / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        return tmp_path

    def test_empty_directory(self, tmp_path):
        report = CodeStats(project_root=str(tmp_path)).analyze()
        assert report.total_files == 0
        assert report.total_code == 0

    def test_counts_python_file(self, tmp_path):
        self._setup(tmp_path, {"main.py": "x = 1\ny = 2\n"})
        report = CodeStats(project_root=str(tmp_path)).analyze()
        assert report.total_files == 1
        assert "Python" in report.by_language
        assert report.by_language["Python"].code_lines == 2

    def test_skips_node_modules(self, tmp_path):
        self._setup(tmp_path, {
            "main.py": "x = 1\n",
            "node_modules/lib/index.js": "const x = 1;\n",
        })
        report = CodeStats(project_root=str(tmp_path)).analyze()
        js_stat = report.by_language.get("JavaScript")
        assert js_stat is None or js_stat.files == 0

    def test_skips_venv(self, tmp_path):
        self._setup(tmp_path, {
            "main.py": "x = 1\n",
            ".venv/lib/helper.py": "pass\n",
        })
        report = CodeStats(project_root=str(tmp_path)).analyze()
        # Only 1 py file (main.py), not 2
        assert report.by_language.get("Python", LanguageStat("Python")).files <= 1

    def test_multiple_languages(self, tmp_path):
        self._setup(tmp_path, {
            "main.py": "x = 1\n",
            "app.ts": "const x = 1;\n",
            "style.css": "body { }\n",
        })
        report = CodeStats(project_root=str(tmp_path)).analyze()
        assert "Python" in report.by_language
        assert "TypeScript" in report.by_language
        assert "CSS" in report.by_language

    def test_summary_contains_total(self, tmp_path):
        self._setup(tmp_path, {"main.py": "x = 1\n"})
        report = CodeStats(project_root=str(tmp_path)).analyze()
        summary = report.summary()
        assert "file" in summary.lower()
        assert "loc" in summary.lower() or "code" in summary.lower()

    def test_top_languages_sorted_by_loc(self, tmp_path):
        self._setup(tmp_path, {
            "big.py": "x = 1\n" * 100,
            "small.ts": "const x = 1;\n",
        })
        report = CodeStats(project_root=str(tmp_path)).analyze()
        top = report.top_languages(2)
        assert top[0].code_lines >= top[1].code_lines

    def test_unknown_extension_ignored(self, tmp_path):
        self._setup(tmp_path, {"file.xyz": "some content\n"})
        report = CodeStats(project_root=str(tmp_path)).analyze()
        assert report.total_files == 0

    def test_blank_and_comment_counted(self, tmp_path):
        self._setup(tmp_path, {"main.py": "# comment\n\nx = 1\n"})
        report = CodeStats(project_root=str(tmp_path)).analyze()
        py = report.by_language["Python"]
        assert py.comment_lines == 1
        assert py.blank_lines == 1
        assert py.code_lines == 1

    def test_totals_are_sum_of_languages(self, tmp_path):
        self._setup(tmp_path, {
            "a.py": "x = 1\n",
            "b.py": "y = 2\n",
        })
        report = CodeStats(project_root=str(tmp_path)).analyze()
        py = report.by_language["Python"]
        assert report.total_code == py.code_lines
        assert report.total_files == py.files


# ---------------------------------------------------------------------------
# CodeStatsReport
# ---------------------------------------------------------------------------

class TestCodeStatsReport:
    def _make(self):
        return CodeStatsReport(
            by_language={
                "Python": LanguageStat("Python", files=5, total_lines=500, code_lines=400, comment_lines=50, blank_lines=50),
                "TypeScript": LanguageStat("TypeScript", files=2, total_lines=200, code_lines=180, comment_lines=10, blank_lines=10),
            },
            file_stats=[],
            total_files=7,
            total_lines=700,
            total_code=580,
            total_comments=60,
            total_blank=60,
        )

    def test_top_languages_returns_sorted(self):
        report = self._make()
        top = report.top_languages(2)
        assert top[0].language == "Python"  # more LOC
        assert top[1].language == "TypeScript"

    def test_top_languages_n_limit(self):
        report = self._make()
        top = report.top_languages(1)
        assert len(top) == 1

    def test_summary_str(self):
        report = self._make()
        s = report.summary()
        assert "7" in s  # total_files
        assert "580" in s  # total_code
