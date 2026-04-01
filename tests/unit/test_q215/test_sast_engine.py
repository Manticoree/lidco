"""Tests for sec_intel.sast_engine — SASTEngine, TaintSource, TaintSink, SASTFinding."""
from __future__ import annotations

import unittest

from lidco.sec_intel.sast_engine import SASTEngine, SASTFinding, TaintSink, TaintSource
from lidco.sec_intel.vuln_scanner import Severity


class TestTaintSource(unittest.TestCase):
    def test_frozen(self):
        s = TaintSource(name="user_input")
        with self.assertRaises(AttributeError):
            s.name = "x"  # type: ignore[misc]

    def test_defaults(self):
        s = TaintSource(name="n")
        self.assertEqual(s.file, "")
        self.assertEqual(s.line, 0)
        self.assertEqual(s.source_type, "input")


class TestTaintSink(unittest.TestCase):
    def test_frozen(self):
        s = TaintSink(name="db_query")
        with self.assertRaises(AttributeError):
            s.name = "x"  # type: ignore[misc]

    def test_defaults(self):
        s = TaintSink(name="n")
        self.assertEqual(s.file, "")
        self.assertEqual(s.line, 0)
        self.assertEqual(s.sink_type, "execute")


class TestSASTFinding(unittest.TestCase):
    def test_frozen(self):
        f = SASTFinding(source=TaintSource(name="a"), sink=TaintSink(name="b"))
        with self.assertRaises(AttributeError):
            f.rule = "x"  # type: ignore[misc]

    def test_defaults(self):
        f = SASTFinding(source=TaintSource(name="a"), sink=TaintSink(name="b"))
        self.assertEqual(f.path, ())
        self.assertEqual(f.severity, Severity.HIGH)
        self.assertEqual(f.rule, "")


class TestSASTEngineAnalyze(unittest.TestCase):
    def setUp(self):
        self.engine = SASTEngine()

    def test_default_rule_match(self):
        sources = [TaintSource(name="user_input", source_type="input")]
        sinks = [TaintSink(name="db_exec", sink_type="execute")]
        findings = self.engine.analyze(sources, sinks)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].source.name, "user_input")
        self.assertEqual(findings[0].sink.name, "db_exec")

    def test_no_match_different_types(self):
        sources = [TaintSource(name="config", source_type="config")]
        sinks = [TaintSink(name="db", sink_type="execute")]
        findings = self.engine.analyze(sources, sinks)
        self.assertEqual(len(findings), 0)

    def test_custom_rule(self):
        self.engine.add_rule("file-write", "input", "file_write", Severity.MEDIUM)
        sources = [TaintSource(name="user", source_type="input")]
        sinks = [TaintSink(name="write_file", sink_type="file_write")]
        findings = self.engine.analyze(sources, sinks)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "file-write")
        self.assertEqual(findings[0].severity, Severity.MEDIUM)

    def test_multiple_sources_sinks(self):
        sources = [
            TaintSource(name="input1", source_type="input"),
            TaintSource(name="input2", source_type="input"),
        ]
        sinks = [
            TaintSink(name="exec1", sink_type="execute"),
            TaintSink(name="exec2", sink_type="execute"),
        ]
        findings = self.engine.analyze(sources, sinks)
        self.assertEqual(len(findings), 4)


class TestSASTEngineAddSourceSink(unittest.TestCase):
    def test_add_source(self):
        engine = SASTEngine()
        src = TaintSource(name="a")
        engine.add_source(src)
        self.assertEqual(len(engine._sources), 1)

    def test_add_sink(self):
        engine = SASTEngine()
        snk = TaintSink(name="b")
        engine.add_sink(snk)
        self.assertEqual(len(engine._sinks), 1)


class TestSASTEngineToSarif(unittest.TestCase):
    def test_sarif_structure(self):
        engine = SASTEngine()
        finding = SASTFinding(
            source=TaintSource(name="input", file="app.py", line=10),
            sink=TaintSink(name="exec", file="app.py", line=20),
            rule="sql-injection",
            severity=Severity.CRITICAL,
        )
        sarif = engine.to_sarif([finding])
        self.assertEqual(sarif["version"], "2.1.0")
        self.assertEqual(len(sarif["runs"]), 1)
        self.assertEqual(len(sarif["runs"][0]["results"]), 1)
        result = sarif["runs"][0]["results"][0]
        self.assertEqual(result["ruleId"], "sql-injection")
        self.assertEqual(result["level"], "error")

    def test_sarif_empty(self):
        engine = SASTEngine()
        sarif = engine.to_sarif([])
        self.assertEqual(len(sarif["runs"][0]["results"]), 0)

    def test_sarif_warning_level(self):
        engine = SASTEngine()
        finding = SASTFinding(
            source=TaintSource(name="a"),
            sink=TaintSink(name="b"),
            severity=Severity.LOW,
            rule="info-rule",
        )
        sarif = engine.to_sarif([finding])
        self.assertEqual(sarif["runs"][0]["results"][0]["level"], "warning")


class TestSASTEngineSummary(unittest.TestCase):
    def test_empty(self):
        engine = SASTEngine()
        self.assertEqual(engine.summary([]), "No taint flows detected.")

    def test_with_findings(self):
        engine = SASTEngine()
        findings = [
            SASTFinding(source=TaintSource(name="a"), sink=TaintSink(name="b"), severity=Severity.HIGH),
            SASTFinding(source=TaintSource(name="c"), sink=TaintSink(name="d"), severity=Severity.CRITICAL),
        ]
        result = engine.summary(findings)
        self.assertIn("SAST findings: 2", result)
        self.assertIn("HIGH: 1", result)
        self.assertIn("CRITICAL: 1", result)


if __name__ == "__main__":
    unittest.main()
