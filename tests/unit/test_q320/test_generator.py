"""Tests for cicd.generator module."""

import os
import unittest
from unittest.mock import patch

from lidco.cicd.generator import (
    GeneratedPipeline,
    GeneratedStage,
    PipelineGenerator,
)


class TestGeneratedStage(unittest.TestCase):
    def test_frozen(self):
        s = GeneratedStage(name="build")
        with self.assertRaises(AttributeError):
            s.name = "x"  # type: ignore[misc]

    def test_defaults(self):
        s = GeneratedStage(name="test")
        self.assertEqual(s.commands, [])
        self.assertEqual(s.depends_on, [])
        self.assertEqual(s.cache_paths, [])
        self.assertEqual(s.image, "")
        self.assertEqual(s.condition, "")


class TestGeneratedPipeline(unittest.TestCase):
    def test_frozen(self):
        p = GeneratedPipeline(provider="github", language="python", stages=[], raw_config="")
        with self.assertRaises(AttributeError):
            p.provider = "x"  # type: ignore[misc]


class TestPipelineGeneratorDetect(unittest.TestCase):
    @patch("os.path.exists", return_value=False)
    def test_unknown_language(self, _):
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github")
        self.assertEqual(result.language, "unknown")

    @patch("os.path.exists")
    def test_detect_python(self, mock_exists):
        def side_effect(path):
            return "pyproject.toml" in path
        mock_exists.side_effect = side_effect
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github")
        self.assertEqual(result.language, "python")

    @patch("os.path.exists")
    def test_detect_node(self, mock_exists):
        def side_effect(path):
            return "package.json" in path
        mock_exists.side_effect = side_effect
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github")
        self.assertEqual(result.language, "node")

    @patch("os.path.exists")
    def test_detect_rust(self, mock_exists):
        def side_effect(path):
            return "Cargo.toml" in path
        mock_exists.side_effect = side_effect
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github")
        self.assertEqual(result.language, "rust")

    @patch("os.path.exists")
    def test_detect_go(self, mock_exists):
        def side_effect(path):
            return "go.mod" in path
        mock_exists.side_effect = side_effect
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github")
        self.assertEqual(result.language, "go")

    @patch("os.path.exists")
    def test_detect_java(self, mock_exists):
        def side_effect(path):
            return "pom.xml" in path
        mock_exists.side_effect = side_effect
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github")
        self.assertEqual(result.language, "java")


class TestPipelineGeneratorInvalidProvider(unittest.TestCase):
    def test_invalid_provider(self):
        gen = PipelineGenerator("/fake")
        with self.assertRaises(ValueError):
            gen.generate(provider="jenkins")


class TestPipelineGeneratorGitHub(unittest.TestCase):
    def test_python_github(self):
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github", language="python")
        self.assertEqual(result.provider, "github")
        self.assertEqual(result.language, "python")
        self.assertTrue(len(result.stages) >= 2)
        self.assertIn("jobs:", result.raw_config)
        self.assertIn("runs-on:", result.raw_config)
        self.assertIn("pytest", result.raw_config)

    def test_node_github(self):
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github", language="node")
        self.assertIn("npm", result.raw_config)

    def test_rust_github(self):
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github", language="rust")
        self.assertIn("cargo", result.raw_config)

    def test_go_github(self):
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github", language="go")
        self.assertIn("go test", result.raw_config)


class TestPipelineGeneratorGitLab(unittest.TestCase):
    def test_python_gitlab(self):
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="gitlab", language="python")
        self.assertEqual(result.provider, "gitlab")
        self.assertIn("stages:", result.raw_config)
        self.assertIn("script:", result.raw_config)

    def test_node_gitlab(self):
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="gitlab", language="node")
        self.assertIn("npm", result.raw_config)


class TestPipelineGeneratorCircleCI(unittest.TestCase):
    def test_python_circleci(self):
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="circleci", language="python")
        self.assertEqual(result.provider, "circleci")
        self.assertIn("version: 2.1", result.raw_config)
        self.assertIn("workflows:", result.raw_config)

    def test_stages_with_deps(self):
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="circleci", language="python")
        # build depends on lint/test -> should have requires
        self.assertIn("requires:", result.raw_config)


class TestPipelineGeneratorDefault(unittest.TestCase):
    def test_unknown_language_stages(self):
        gen = PipelineGenerator("/fake")
        result = gen.generate(provider="github", language="unknown")
        self.assertTrue(len(result.stages) >= 1)


if __name__ == "__main__":
    unittest.main()
