"""Tests for StringAnalyzer — Task 356."""

from __future__ import annotations

import pytest

from lidco.analysis.string_analyzer import (
    StringAnalyzer, StringIssueKind, StringReport,
)


URL_SOURCE = '''\
BASE_URL = "https://api.example.com/v1/users"
'''

IP_SOURCE = '''\
HOST = "192.168.1.100"
'''

LOCALHOST_SOURCE = '''\
HOST = "127.0.0.1"
WILDCARD = "0.0.0.0"
'''

PATH_SOURCE = '''\
CONFIG = "/etc/myapp/config.yaml"
'''

WINDOWS_PATH = '''\
CONFIG = "C:\\\\Users\\\\myapp\\\\config.yaml"
'''

LONG_STRING_SOURCE = '''\
MSG = "This is a very long string literal that definitely exceeds one hundred and twenty characters in total length for testing purposes"
'''

TODO_SOURCE = '''\
x = "TODO: fix this before release"
'''

FIXME_SOURCE = '''\
x = "FIXME: this is broken"
'''

CLEAN_SOURCE = '''\
greeting = "Hello, world!"
name = "Alice"
'''

SYNTAX_ERROR = "def broken(:"

MULTI_ISSUE = '''\
URL = "https://api.example.com"
IP = "10.0.0.1"
PATH = "/usr/local/bin/app"
'''


class TestStringAnalyzer:
    def setup_method(self):
        self.analyzer = StringAnalyzer()

    def test_empty_source(self):
        report = self.analyzer.analyze("")
        assert len(report.issues) == 0

    def test_syntax_error(self):
        report = self.analyzer.analyze(SYNTAX_ERROR)
        assert isinstance(report, StringReport)

    def test_clean_source_no_issues(self):
        report = self.analyzer.analyze(CLEAN_SOURCE)
        assert len(report.issues) == 0

    def test_url_detected(self):
        report = self.analyzer.analyze(URL_SOURCE)
        urls = report.by_kind(StringIssueKind.HARDCODED_URL)
        assert len(urls) >= 1

    def test_url_detail(self):
        report = self.analyzer.analyze(URL_SOURCE)
        urls = report.by_kind(StringIssueKind.HARDCODED_URL)
        assert any("http" in i.detail.lower() or "url" in i.detail.lower() for i in urls)

    def test_ip_detected(self):
        report = self.analyzer.analyze(IP_SOURCE)
        ips = report.by_kind(StringIssueKind.HARDCODED_IP)
        assert len(ips) >= 1

    def test_ip_detail_has_address(self):
        report = self.analyzer.analyze(IP_SOURCE)
        ips = report.by_kind(StringIssueKind.HARDCODED_IP)
        assert "192.168.1.100" in ips[0].detail

    def test_localhost_not_flagged(self):
        report = self.analyzer.analyze(LOCALHOST_SOURCE)
        ips = report.by_kind(StringIssueKind.HARDCODED_IP)
        assert len(ips) == 0

    def test_abs_path_detected(self):
        report = self.analyzer.analyze(PATH_SOURCE)
        paths = report.by_kind(StringIssueKind.HARDCODED_PATH)
        assert len(paths) >= 1

    def test_long_string_detected(self):
        report = self.analyzer.analyze(LONG_STRING_SOURCE)
        long = report.by_kind(StringIssueKind.LONG_STRING)
        assert len(long) >= 1

    def test_long_string_detail_has_char_count(self):
        report = self.analyzer.analyze(LONG_STRING_SOURCE)
        long = report.by_kind(StringIssueKind.LONG_STRING)
        assert any(str(i) in long[0].detail for i in range(121, 999))

    def test_todo_in_string_detected(self):
        report = self.analyzer.analyze(TODO_SOURCE)
        todos = report.by_kind(StringIssueKind.TODO_FIXME)
        assert len(todos) >= 1

    def test_fixme_in_string_detected(self):
        report = self.analyzer.analyze(FIXME_SOURCE)
        todos = report.by_kind(StringIssueKind.TODO_FIXME)
        assert len(todos) >= 1

    def test_string_literal_count(self):
        report = self.analyzer.analyze(CLEAN_SOURCE)
        assert report.string_literals >= 2

    def test_multi_issue_source(self):
        report = self.analyzer.analyze(MULTI_ISSUE)
        assert len(report.issues) >= 3

    def test_file_path_recorded(self):
        report = self.analyzer.analyze(URL_SOURCE, file_path="app.py")
        assert all(i.file == "app.py" for i in report.issues)

    def test_line_number_recorded(self):
        report = self.analyzer.analyze(URL_SOURCE)
        urls = report.by_kind(StringIssueKind.HARDCODED_URL)
        assert urls[0].line >= 1

    def test_value_truncated(self):
        long_url = "https://" + "a" * 100 + ".com"
        source = f'x = "{long_url}"'
        report = self.analyzer.analyze(source)
        urls = report.by_kind(StringIssueKind.HARDCODED_URL)
        assert len(urls[0].value) <= 85  # 80 + ellipsis

    def test_by_kind_filter(self):
        report = self.analyzer.analyze(MULTI_ISSUE)
        urls = report.by_kind(StringIssueKind.HARDCODED_URL)
        assert all(i.kind == StringIssueKind.HARDCODED_URL for i in urls)
