"""Tests for DiagnosticsCollector — Q190, task 1065."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from lidco.lsp.diagnostics import (
    DiagnosticsCollector,
    Diagnostic,
    DiagnosticSeverity,
    _parse_diagnostics,
    _parse_raw_diagnostics,
)


class TestDiagnosticSeverity(unittest.TestCase):
    def test_values(self):
        self.assertEqual(DiagnosticSeverity.ERROR, 1)
        self.assertEqual(DiagnosticSeverity.WARNING, 2)
        self.assertEqual(DiagnosticSeverity.INFO, 3)
        self.assertEqual(DiagnosticSeverity.HINT, 4)

    def test_count(self):
        self.assertEqual(len(DiagnosticSeverity), 4)

    def test_name_lowercase(self):
        self.assertEqual(DiagnosticSeverity.ERROR.name.lower(), "error")


class TestDiagnostic(unittest.TestCase):
    def test_frozen(self):
        d = Diagnostic(file="a.py", line=1, column=0, severity=DiagnosticSeverity.ERROR, message="bad")
        with self.assertRaises(AttributeError):
            d.file = "b.py"  # type: ignore[misc]

    def test_defaults(self):
        d = Diagnostic(file="a.py", line=1, column=0, severity=DiagnosticSeverity.WARNING, message="warn")
        self.assertEqual(d.source, "")

    def test_with_source(self):
        d = Diagnostic(file="a.py", line=1, column=0, severity=DiagnosticSeverity.INFO, message="info", source="pyright")
        self.assertEqual(d.source, "pyright")

    def test_equality(self):
        a = Diagnostic(file="a.py", line=1, column=0, severity=DiagnosticSeverity.ERROR, message="x")
        b = Diagnostic(file="a.py", line=1, column=0, severity=DiagnosticSeverity.ERROR, message="x")
        self.assertEqual(a, b)


class TestDiagnosticsCollector(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.collector = DiagnosticsCollector(self.client)

    def test_collect_success(self):
        self.client.send_request.return_value = {
            "items": [
                {
                    "range": {"start": {"line": 5, "character": 2}},
                    "severity": 1,
                    "message": "Undefined variable",
                    "source": "pyright",
                },
            ]
        }
        diags = self.collector.collect("test.py")
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].severity, DiagnosticSeverity.ERROR)
        self.assertEqual(diags[0].message, "Undefined variable")
        self.assertEqual(diags[0].source, "pyright")

    def test_collect_empty(self):
        self.client.send_request.return_value = {"items": []}
        diags = self.collector.collect("test.py")
        self.assertEqual(diags, ())

    def test_collect_error(self):
        self.client.send_request.side_effect = RuntimeError("fail")
        diags = self.collector.collect("test.py")
        self.assertEqual(diags, ())

    def test_collect_updates_cache(self):
        self.client.send_request.return_value = {
            "items": [
                {"range": {"start": {"line": 0, "character": 0}}, "severity": 2, "message": "warn"},
            ]
        }
        self.collector.collect("a.py")
        counts = self.collector.severity_counts()
        self.assertEqual(counts.get("warning", 0), 1)

    def test_collect_all_success(self):
        self.client.send_request.return_value = {
            "items": [
                {
                    "uri": "file:///a.py",
                    "items": [
                        {"range": {"start": {"line": 1, "character": 0}}, "severity": 1, "message": "err"},
                    ],
                },
                {
                    "uri": "file:///b.py",
                    "items": [
                        {"range": {"start": {"line": 2, "character": 0}}, "severity": 2, "message": "warn"},
                    ],
                },
            ]
        }
        result = self.collector.collect_all()
        self.assertEqual(len(result), 2)

    def test_collect_all_empty(self):
        self.client.send_request.return_value = {"items": []}
        result = self.collector.collect_all()
        self.assertEqual(result, {})

    def test_collect_all_error(self):
        self.client.send_request.side_effect = ValueError("fail")
        result = self.collector.collect_all()
        self.assertEqual(result, {})

    def test_severity_counts_empty(self):
        counts = self.collector.severity_counts()
        self.assertEqual(counts, {})

    def test_severity_counts_mixed(self):
        self.client.send_request.side_effect = [
            {"items": [
                {"range": {"start": {"line": 0, "character": 0}}, "severity": 1, "message": "e1"},
                {"range": {"start": {"line": 1, "character": 0}}, "severity": 1, "message": "e2"},
                {"range": {"start": {"line": 2, "character": 0}}, "severity": 2, "message": "w1"},
            ]},
            {"items": [
                {"range": {"start": {"line": 0, "character": 0}}, "severity": 3, "message": "i1"},
            ]},
        ]
        self.collector.collect("a.py")
        self.collector.collect("b.py")
        counts = self.collector.severity_counts()
        self.assertEqual(counts["error"], 2)
        self.assertEqual(counts["warning"], 1)
        self.assertEqual(counts["info"], 1)

    def test_collect_all_no_items_key(self):
        self.client.send_request.return_value = {}
        result = self.collector.collect_all()
        self.assertEqual(result, {})

    def test_immutable_cache(self):
        """Cache uses immutable update pattern."""
        self.client.send_request.return_value = {
            "items": [
                {"range": {"start": {"line": 0, "character": 0}}, "severity": 1, "message": "x"},
            ]
        }
        self.collector.collect("a.py")
        old_cache = self.collector._cache
        self.client.send_request.return_value = {
            "items": [
                {"range": {"start": {"line": 0, "character": 0}}, "severity": 2, "message": "y"},
            ]
        }
        self.collector.collect("b.py")
        # Both files should be in cache
        self.assertIn("a.py", self.collector._cache)
        self.assertIn("b.py", self.collector._cache)


class TestParseDiagnostics(unittest.TestCase):
    def test_dict_with_items(self):
        result = _parse_diagnostics("a.py", {
            "items": [{"range": {"start": {"line": 0, "character": 0}}, "severity": 1, "message": "x"}]
        })
        self.assertEqual(len(result), 1)

    def test_list_input(self):
        result = _parse_diagnostics("a.py", [
            {"range": {"start": {"line": 0, "character": 0}}, "severity": 2, "message": "w"}
        ])
        self.assertEqual(len(result), 1)

    def test_none_input(self):
        self.assertEqual(_parse_diagnostics("a.py", None), ())

    def test_invalid_severity_defaults_to_error(self):
        result = _parse_raw_diagnostics("a.py", [
            {"range": {"start": {"line": 0, "character": 0}}, "severity": 99, "message": "x"}
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].severity, DiagnosticSeverity.ERROR)

    def test_skips_non_dict_items(self):
        result = _parse_raw_diagnostics("a.py", [None, "bad"])
        self.assertEqual(result, ())


if __name__ == "__main__":
    unittest.main()
