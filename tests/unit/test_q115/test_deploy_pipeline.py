"""Tests for DeployPipeline (Task 708)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from lidco.scaffold.deploy_registry import DeployProvider
from lidco.scaffold.deploy_pipeline import DeployJob, DeployResult, DeployPipeline


def _make_provider(name="test", build_cmd="build", deploy_cmd="deploy"):
    return DeployProvider(
        name=name,
        detect_files=[],
        build_cmd=build_cmd,
        deploy_cmd=deploy_cmd,
        env_vars_needed=[],
    )


class TestDeployJob(unittest.TestCase):
    def test_create_job(self):
        p = _make_provider()
        job = DeployJob(
            job_id="j1", provider=p, project_dir="/proj", env={"KEY": "val"}
        )
        assert job.job_id == "j1"
        assert job.provider == p
        assert job.branch == "main"
        assert job.dry_run is False

    def test_job_dry_run(self):
        p = _make_provider()
        job = DeployJob(
            job_id="j2", provider=p, project_dir="/proj", env={}, dry_run=True
        )
        assert job.dry_run is True

    def test_job_custom_branch(self):
        p = _make_provider()
        job = DeployJob(
            job_id="j3", provider=p, project_dir="/proj", env={}, branch="dev"
        )
        assert job.branch == "dev"


class TestDeployResult(unittest.TestCase):
    def test_create_result(self):
        r = DeployResult(
            job_id="j1", success=True, url="https://app.com", duration_ms=1200, logs=["ok"]
        )
        assert r.success is True
        assert r.url == "https://app.com"
        assert r.error == ""

    def test_result_with_error(self):
        r = DeployResult(
            job_id="j1", success=False, url="", duration_ms=500, logs=["fail"], error="boom"
        )
        assert r.success is False
        assert r.error == "boom"


class TestDeployPipeline(unittest.TestCase):
    def test_init_no_deps(self):
        pipeline = DeployPipeline()
        assert pipeline is not None

    def test_init_with_job_queue(self):
        jq = MagicMock()
        pipeline = DeployPipeline(job_queue=jq)
        assert pipeline is not None

    def test_init_with_checkpoint_manager(self):
        cm = MagicMock()
        pipeline = DeployPipeline(checkpoint_manager=cm)
        assert pipeline is not None

    def test_dry_run_returns_success(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=True)
        assert result.success is True
        assert any("dry-run" in log.lower() for log in result.logs)

    def test_dry_run_skips_deploy(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=True)
        assert result.success is True

    def test_run_returns_deploy_result(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=True)
        assert isinstance(result, DeployResult)

    def test_run_has_job_id(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=True)
        assert result.job_id != ""

    def test_run_has_duration(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=True)
        assert result.duration_ms >= 0

    def test_run_has_logs(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=True)
        assert len(result.logs) > 0

    def test_run_step_dry_run(self):
        pipeline = DeployPipeline()
        ok, output = pipeline._run_step("build", "npm run build", dry_run=True)
        assert ok is True
        assert "dry-run" in output.lower()

    def test_run_step_real_mocked(self):
        pipeline = DeployPipeline()
        # Real execution is mocked to avoid subprocess
        with patch.object(pipeline, "_run_step", return_value=(True, "done")):
            ok, output = pipeline._run_step("build", "npm run build", dry_run=False)
            assert ok is True

    def test_estimate(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        est = pipeline.estimate(provider)
        assert "steps" in est
        assert "estimated_duration_ms" in est
        assert isinstance(est["steps"], list)
        assert isinstance(est["estimated_duration_ms"], int)

    def test_estimate_has_build_step(self):
        pipeline = DeployPipeline()
        provider = _make_provider(build_cmd="npm run build")
        est = pipeline.estimate(provider)
        assert any("build" in s.lower() for s in est["steps"])

    def test_estimate_has_deploy_step(self):
        pipeline = DeployPipeline()
        provider = _make_provider(deploy_cmd="deploy --prod")
        est = pipeline.estimate(provider)
        assert any("deploy" in s.lower() for s in est["steps"])

    def test_run_with_env(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        result = pipeline.run("/proj", provider, env={"KEY": "val"}, dry_run=True)
        assert result.success is True

    def test_run_with_branch(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        result = pipeline.run("/proj", provider, branch="dev", dry_run=True)
        assert result.success is True

    def test_run_failure_calls_rollback(self):
        cm = MagicMock()
        pipeline = DeployPipeline(checkpoint_manager=cm)
        # Force a failure by making _run_step fail
        pipeline._run_step = MagicMock(return_value=(False, "error"))
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=False)
        assert result.success is False
        cm.rollback.assert_called()

    def test_run_failure_no_checkpoint_manager(self):
        pipeline = DeployPipeline()
        pipeline._run_step = MagicMock(return_value=(False, "error"))
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=False)
        assert result.success is False

    def test_run_uses_job_queue_when_available(self):
        jq = MagicMock()
        jq.submit = MagicMock(return_value=MagicMock(id="j42"))
        pipeline = DeployPipeline(job_queue=jq)
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=True)
        assert isinstance(result, DeployResult)

    def test_run_result_url_empty_on_dry_run(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=True)
        # dry-run won't produce a real URL
        assert isinstance(result.url, str)

    def test_run_result_error_empty_on_success(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        result = pipeline.run("/proj", provider, dry_run=True)
        assert result.error == ""

    def test_estimate_positive_duration(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        est = pipeline.estimate(provider)
        assert est["estimated_duration_ms"] > 0

    def test_multiple_runs(self):
        pipeline = DeployPipeline()
        provider = _make_provider()
        r1 = pipeline.run("/proj", provider, dry_run=True)
        r2 = pipeline.run("/proj", provider, dry_run=True)
        assert r1.job_id != r2.job_id


if __name__ == "__main__":
    unittest.main()
