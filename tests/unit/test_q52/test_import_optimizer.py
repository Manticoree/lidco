"""Tests for ImportOptimizer — Task 354."""

from __future__ import annotations

import pytest

from lidco.analysis.import_optimizer import (
    ImportIssueKind, ImportOptimizer, ImportReport,
)


UNUSED_IMPORT = """\
import os
import sys

print(sys.version)
"""

STAR_IMPORT = """\
from os.path import *
from sys import *

x = join("/", "a")
"""

DUPLICATE_IMPORT = """\
import os
import os

print(os.getcwd())
"""

CLEAN_IMPORTS = """\
import sys

print(sys.version)
"""

SYNTAX_ERROR = "def broken(:"

MULTI_UNUSED = """\
import os
import sys
import re

x = 1
"""


class TestImportOptimizer:
    def setup_method(self):
        self.opt = ImportOptimizer()

    def test_empty_source(self):
        report = self.opt.analyze("")
        assert len(report.issues) == 0

    def test_syntax_error(self):
        report = self.opt.analyze(SYNTAX_ERROR)
        assert isinstance(report, ImportReport)

    def test_clean_imports_no_issues(self):
        report = self.opt.analyze(CLEAN_IMPORTS)
        unused = report.by_kind(ImportIssueKind.UNUSED_IMPORT)
        assert len(unused) == 0

    def test_unused_import_detected(self):
        report = self.opt.analyze(UNUSED_IMPORT)
        unused = report.by_kind(ImportIssueKind.UNUSED_IMPORT)
        names = {i.name for i in unused}
        assert "os" in names

    def test_used_import_not_flagged(self):
        report = self.opt.analyze(UNUSED_IMPORT)
        unused = report.by_kind(ImportIssueKind.UNUSED_IMPORT)
        names = {i.name for i in unused}
        assert "sys" not in names

    def test_star_import_detected(self):
        report = self.opt.analyze(STAR_IMPORT)
        assert report.star_count >= 1

    def test_star_import_suggestion(self):
        report = self.opt.analyze(STAR_IMPORT)
        stars = report.by_kind(ImportIssueKind.STAR_IMPORT)
        assert all("explicit" in i.suggestion.lower() for i in stars)

    def test_duplicate_import_detected(self):
        report = self.opt.analyze(DUPLICATE_IMPORT)
        dups = report.by_kind(ImportIssueKind.DUPLICATE_IMPORT)
        assert len(dups) >= 1

    def test_multiple_unused(self):
        report = self.opt.analyze(MULTI_UNUSED)
        unused = report.by_kind(ImportIssueKind.UNUSED_IMPORT)
        names = {i.name for i in unused}
        assert "os" in names
        assert "sys" in names
        assert "re" in names

    def test_file_path_recorded(self):
        report = self.opt.analyze(UNUSED_IMPORT, file_path="myfile.py")
        unused = report.by_kind(ImportIssueKind.UNUSED_IMPORT)
        assert all(i.file == "myfile.py" for i in unused)

    def test_line_number_recorded(self):
        report = self.opt.analyze(UNUSED_IMPORT)
        unused = report.by_kind(ImportIssueKind.UNUSED_IMPORT)
        os_issue = next(i for i in unused if i.name == "os")
        assert os_issue.line == 1

    def test_all_imports_tracked(self):
        report = self.opt.analyze(CLEAN_IMPORTS)
        assert len(report.all_imports) >= 1

    def test_unused_count_property(self):
        report = self.opt.analyze(MULTI_UNUSED)
        assert report.unused_count == 3
