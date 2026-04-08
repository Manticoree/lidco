"""Tests for Q320 CLI commands."""

import asyncio
import unittest
from unittest.mock import patch, MagicMock

from lidco.cicd.analyzer import PipelineAnalysis, StageInfo, Bottleneck
from lidco.cicd.generator import GeneratedPipeline, GeneratedStage
from lidco.cicd.optimizer import OptimizationResult, Optimization
from lidco.cicd.monitor import PipelineRun


class _FakeRegistry:
    """Minimal registry to capture registrations."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = handler


def _build_registry() -> _FakeRegistry:
    from lidco.cli.commands.q320_cmds import register_q320_commands
    reg = _FakeRegistry()
    register_q320_commands(reg)
    return reg


class TestQ320Registration(unittest.TestCase):
    def test_registers_pipeline_analyze(self):
        reg = _build_registry()
        self.assertIn("pipeline-analyze", reg.commands)

    def test_registers_pipeline_gen(self):
        reg = _build_registry()
        self.assertIn("pipeline-gen", reg.commands)

    def test_registers_pipeline_optimize(self):
        reg = _build_registry()
        self.assertIn("pipeline-optimize", reg.commands)

    def test_registers_pipeline_monitor(self):
        reg = _build_registry()
        self.assertIn("pipeline-monitor", reg.commands)


class TestPipelineAnalyzeCommand(unittest.TestCase):
    @patch("lidco.cicd.analyzer.PipelineAnalyzer.analyze")
    def test_analyze_default(self, mock_analyze):
        mock_analyze.return_value = PipelineAnalysis(
            provider="github",
            total_stages=2,
            stages=[
                StageInfo(name="lint", steps=["ruff"]),
                StageInfo(name="test", steps=["pytest"]),
            ],
            bottlenecks=[
                Bottleneck(
                    stage="test", kind="no-cache",
                    description="No cache in test",
                    suggestion="Add cache",
                ),
            ],
            cache_opportunities=["Cache deps in test"],
            parallelization_suggestions=["Run lint, test in parallel"],
            estimated_total_duration=120.0,
        )
        reg = _build_registry()
        result = asyncio.run(reg.commands["pipeline-analyze"](""))
        self.assertIn("Pipeline Analysis (github)", result)
        self.assertIn("2 stages", result)
        self.assertIn("Bottlenecks:", result)
        self.assertIn("no-cache", result)
        self.assertIn("Cache opportunities:", result)
        self.assertIn("Parallelization:", result)

    @patch("lidco.cicd.analyzer.PipelineAnalyzer.analyze")
    def test_analyze_no_config(self, mock_analyze):
        mock_analyze.return_value = PipelineAnalysis(
            provider="unknown", total_stages=0, stages=[], bottlenecks=[],
            cache_opportunities=[], parallelization_suggestions=[],
            estimated_total_duration=0.0,
        )
        reg = _build_registry()
        result = asyncio.run(reg.commands["pipeline-analyze"](""))
        self.assertIn("No CI pipeline config detected", result)


class TestPipelineGenCommand(unittest.TestCase):
    @patch("lidco.cicd.generator.PipelineGenerator.generate")
    def test_gen_default(self, mock_gen):
        mock_gen.return_value = GeneratedPipeline(
            provider="github", language="python",
            stages=[GeneratedStage(name="test", commands=["pytest"])],
            raw_config="name: CI\njobs:\n  test:\n    run: pytest",
        )
        reg = _build_registry()
        result = asyncio.run(reg.commands["pipeline-gen"](""))
        self.assertIn("Generated github pipeline for python", result)
        self.assertIn("Stages: 1", result)
        self.assertIn("name: CI", result)

    @patch("lidco.cicd.generator.PipelineGenerator.generate")
    def test_gen_with_provider(self, mock_gen):
        mock_gen.return_value = GeneratedPipeline(
            provider="gitlab", language="node",
            stages=[GeneratedStage(name="test")],
            raw_config="stages:\n  - test",
        )
        reg = _build_registry()
        result = asyncio.run(reg.commands["pipeline-gen"]("--provider gitlab --language node"))
        self.assertIn("gitlab", result)

    @patch("lidco.cicd.generator.PipelineGenerator.generate")
    def test_gen_invalid_provider(self, mock_gen):
        mock_gen.side_effect = ValueError("Unsupported provider: jenkins")
        reg = _build_registry()
        result = asyncio.run(reg.commands["pipeline-gen"]("--provider jenkins"))
        self.assertIn("Error:", result)


class TestPipelineOptimizeCommand(unittest.TestCase):
    @patch("lidco.cicd.optimizer.PipelineOptimizer.optimize")
    @patch("lidco.cicd.analyzer.PipelineAnalyzer.analyze")
    def test_optimize_default(self, mock_analyze, mock_optimize):
        mock_analyze.return_value = PipelineAnalysis(
            provider="github", total_stages=2,
            stages=[
                StageInfo(name="lint", steps=["ruff"], estimated_duration=30.0),
                StageInfo(name="test", steps=["pytest"], estimated_duration=120.0),
            ],
            bottlenecks=[], cache_opportunities=[], parallelization_suggestions=[],
            estimated_total_duration=150.0,
        )
        mock_optimize.return_value = OptimizationResult(
            optimizations=[
                Optimization(kind="cache", stage="test", description="Add cache", estimated_savings=36.0),
            ],
            total_estimated_savings=36.0,
            original_duration=150.0,
            optimized_duration=114.0,
            skip_unchanged_paths=["tests/"],
        )
        reg = _build_registry()
        result = asyncio.run(reg.commands["pipeline-optimize"](""))
        self.assertIn("Pipeline Optimization (github)", result)
        self.assertIn("Original duration: 150s", result)
        self.assertIn("Optimized duration: 114s", result)
        self.assertIn("Estimated savings: 36s", result)
        self.assertIn("[cache]", result)
        self.assertIn("tests/", result)

    @patch("lidco.cicd.analyzer.PipelineAnalyzer.analyze")
    def test_optimize_no_config(self, mock_analyze):
        mock_analyze.return_value = PipelineAnalysis(
            provider="unknown", total_stages=0, stages=[], bottlenecks=[],
            cache_opportunities=[], parallelization_suggestions=[],
            estimated_total_duration=0.0,
        )
        reg = _build_registry()
        result = asyncio.run(reg.commands["pipeline-optimize"](""))
        self.assertIn("No CI pipeline config detected", result)


class TestPipelineMonitorCommand(unittest.TestCase):
    @patch("lidco.cicd.monitor.PipelineMonitor.get_runs")
    def test_monitor_no_runs(self, mock_runs):
        mock_runs.return_value = []
        reg = _build_registry()
        result = asyncio.run(reg.commands["pipeline-monitor"](""))
        self.assertIn("No pipeline runs recorded", result)

    @patch("lidco.cicd.monitor.PipelineMonitor.get_runs")
    def test_monitor_with_runs(self, mock_runs):
        mock_runs.return_value = [
            PipelineRun(run_id="1", pipeline="ci", status="success", started_at=100.0, duration=30.0),
            PipelineRun(run_id="2", pipeline="ci", status="failure", started_at=200.0, duration=25.0),
        ]
        reg = _build_registry()
        result = asyncio.run(reg.commands["pipeline-monitor"](""))
        self.assertIn("Pipeline Monitor:", result)
        self.assertIn("[success]", result)
        self.assertIn("[failure]", result)

    @patch("lidco.cicd.monitor.PipelineMonitor.get_stats")
    @patch("lidco.cicd.monitor.PipelineMonitor.get_runs")
    def test_monitor_with_pipeline_filter(self, mock_runs, mock_stats):
        from lidco.cicd.monitor import PipelineStats
        mock_runs.return_value = [
            PipelineRun(run_id="1", pipeline="ci", status="success", started_at=100.0, duration=30.0),
        ]
        mock_stats.return_value = PipelineStats(
            pipeline="ci", total_runs=10, success_count=8, failure_count=2,
            success_rate=0.8, avg_duration=25.0,
        )
        reg = _build_registry()
        result = asyncio.run(reg.commands["pipeline-monitor"]("--pipeline ci"))
        self.assertIn("Pipeline: ci", result)
        self.assertIn("Total runs: 10", result)
        self.assertIn("Success rate: 80%", result)


if __name__ == "__main__":
    unittest.main()
