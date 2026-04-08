"""Tests for cicd.analyzer module."""

import json
import os
import unittest
from unittest.mock import patch, MagicMock

from lidco.cicd.analyzer import (
    Bottleneck,
    PipelineAnalysis,
    PipelineAnalyzer,
    StageInfo,
)


class TestStageInfo(unittest.TestCase):
    def test_frozen(self):
        s = StageInfo(name="build", steps=["npm run build"])
        with self.assertRaises(AttributeError):
            s.name = "other"  # type: ignore[misc]

    def test_defaults(self):
        s = StageInfo(name="test")
        self.assertEqual(s.steps, [])
        self.assertEqual(s.depends_on, [])
        self.assertEqual(s.estimated_duration, 0.0)
        self.assertFalse(s.has_cache)
        self.assertFalse(s.parallelisable)


class TestBottleneck(unittest.TestCase):
    def test_frozen(self):
        b = Bottleneck(stage="x", kind="no-cache", description="d", suggestion="s")
        with self.assertRaises(AttributeError):
            b.stage = "y"  # type: ignore[misc]


class TestPipelineAnalysis(unittest.TestCase):
    def test_frozen(self):
        a = PipelineAnalysis(
            provider="github",
            total_stages=0,
            stages=[],
            bottlenecks=[],
            cache_opportunities=[],
            parallelization_suggestions=[],
            estimated_total_duration=0.0,
        )
        with self.assertRaises(AttributeError):
            a.provider = "x"  # type: ignore[misc]


class TestPipelineAnalyzerDetect(unittest.TestCase):
    @patch("os.path.isdir", return_value=False)
    @patch("os.path.isfile", return_value=False)
    def test_no_config_detected(self, mock_isfile, mock_isdir):
        analyzer = PipelineAnalyzer("/fake")
        result = analyzer.analyze()
        self.assertEqual(result.provider, "unknown")
        self.assertEqual(result.total_stages, 0)

    def test_detect_provider_github(self):
        self.assertEqual(PipelineAnalyzer._detect_provider(".github/workflows/ci.yml"), "github")

    def test_detect_provider_gitlab(self):
        self.assertEqual(PipelineAnalyzer._detect_provider(".gitlab-ci.yml"), "gitlab")

    def test_detect_provider_circleci(self):
        self.assertEqual(PipelineAnalyzer._detect_provider(".circleci/config.yml"), "circleci")

    def test_detect_provider_unknown(self):
        self.assertEqual(PipelineAnalyzer._detect_provider("Makefile"), "unknown")


class TestPipelineAnalyzerGitHub(unittest.TestCase):
    _GITHUB_CONFIG = {
        "jobs": {
            "lint": {
                "steps": [
                    {"name": "Checkout", "uses": "actions/checkout@v4"},
                    {"run": "npm run lint"},
                ],
            },
            "test": {
                "steps": [
                    {"name": "Checkout", "uses": "actions/checkout@v4"},
                    {"run": "npm ci"},
                    {"run": "npm test"},
                ],
                "needs": ["lint"],
            },
            "build": {
                "steps": [
                    {"name": "Checkout", "uses": "actions/checkout@v4"},
                    {"run": "npm run build"},
                    {"name": "Cache", "uses": "actions/cache@v4"},
                ],
                "needs": ["test"],
            },
        }
    }

    @patch("lidco.cicd.analyzer.PipelineAnalyzer._detect_config")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._read_file")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._parse_config")
    def test_analyze_github(self, mock_parse, mock_read, mock_detect):
        mock_detect.return_value = ".github/workflows/ci.yml"
        mock_read.return_value = ""
        mock_parse.return_value = self._GITHUB_CONFIG

        analyzer = PipelineAnalyzer("/fake")
        result = analyzer.analyze()

        self.assertEqual(result.provider, "github")
        self.assertEqual(result.total_stages, 3)
        names = [s.name for s in result.stages]
        self.assertIn("lint", names)
        self.assertIn("test", names)
        self.assertIn("build", names)

    @patch("lidco.cicd.analyzer.PipelineAnalyzer._detect_config")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._read_file")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._parse_config")
    def test_bottleneck_no_cache(self, mock_parse, mock_read, mock_detect):
        mock_detect.return_value = ".github/workflows/ci.yml"
        mock_read.return_value = ""
        mock_parse.return_value = self._GITHUB_CONFIG

        analyzer = PipelineAnalyzer("/fake")
        result = analyzer.analyze()

        no_cache = [b for b in result.bottlenecks if b.kind == "no-cache"]
        # test has 3 steps and no cache
        self.assertTrue(any(b.stage == "test" for b in no_cache))

    @patch("lidco.cicd.analyzer.PipelineAnalyzer._detect_config")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._read_file")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._parse_config")
    def test_sequential_bottleneck(self, mock_parse, mock_read, mock_detect):
        mock_detect.return_value = ".github/workflows/ci.yml"
        mock_read.return_value = ""
        mock_parse.return_value = self._GITHUB_CONFIG

        analyzer = PipelineAnalyzer("/fake")
        result = analyzer.analyze()

        seq = [b for b in result.bottlenecks if b.kind == "sequential"]
        self.assertTrue(len(seq) > 0)

    @patch("lidco.cicd.analyzer.PipelineAnalyzer._detect_config")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._read_file")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._parse_config")
    def test_cache_opportunity_install(self, mock_parse, mock_read, mock_detect):
        mock_detect.return_value = ".github/workflows/ci.yml"
        mock_read.return_value = ""
        config = {
            "jobs": {
                "setup": {
                    "steps": [
                        {"run": "npm install"},
                        {"run": "npm test"},
                        {"run": "npm build"},
                    ],
                },
            },
        }
        mock_parse.return_value = config

        analyzer = PipelineAnalyzer("/fake")
        result = analyzer.analyze()

        self.assertTrue(any("install" in c.lower() or "npm" in c.lower() for c in result.cache_opportunities))


class TestPipelineAnalyzerGitLab(unittest.TestCase):
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._read_file")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._parse_config")
    def test_gitlab_stages(self, mock_parse, mock_read):
        mock_read.return_value = ""
        mock_parse.return_value = {
            "stages": ["lint", "test"],
            "lint_job": {"stage": "lint", "script": ["ruff check ."]},
            "test_job": {"stage": "test", "script": ["pytest"], "needs": ["lint_job"]},
        }
        analyzer = PipelineAnalyzer("/fake")
        result = analyzer.analyze(config_path=".gitlab-ci.yml")

        self.assertEqual(result.provider, "gitlab")
        self.assertEqual(result.total_stages, 2)


class TestPipelineAnalyzerCircleCI(unittest.TestCase):
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._read_file")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer._parse_config")
    def test_circleci_stages(self, mock_parse, mock_read):
        mock_read.return_value = ""
        mock_parse.return_value = {
            "jobs": {
                "build": {
                    "steps": ["checkout", {"run": {"command": "make build"}}],
                },
                "test": {
                    "steps": ["checkout", "restore_cache", {"run": {"command": "make test"}}],
                },
            },
        }
        analyzer = PipelineAnalyzer("/fake")
        result = analyzer.analyze(config_path=".circleci/config.yml")

        self.assertEqual(result.provider, "circleci")
        self.assertEqual(result.total_stages, 2)
        test_stage = [s for s in result.stages if s.name == "test"][0]
        self.assertTrue(test_stage.has_cache)


class TestMinimalYamlParse(unittest.TestCase):
    def test_basic_parse(self):
        raw = "name: CI\non:\njobs:"
        result = PipelineAnalyzer._minimal_yaml_parse(raw)
        self.assertEqual(result["name"], "CI")
        self.assertIn("jobs", result)


if __name__ == "__main__":
    unittest.main()
