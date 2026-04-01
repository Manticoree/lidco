"""Tests for lidco.ecosystem.pipeline_manager."""

from lidco.ecosystem.pipeline_manager import (
    PipelineManager,
    PipelineProvider,
    PipelineRun,
    PipelineStatus,
)


class TestPipelineEnums:
    def test_provider_values(self):
        assert PipelineProvider.GITHUB_ACTIONS.value == "github_actions"
        assert PipelineProvider.GITLAB_CI.value == "gitlab_ci"
        assert PipelineProvider.CIRCLECI.value == "circleci"

    def test_status_values(self):
        assert PipelineStatus.PENDING.value == "pending"
        assert PipelineStatus.RUNNING.value == "running"
        assert PipelineStatus.SUCCESS.value == "success"
        assert PipelineStatus.FAILURE.value == "failure"
        assert PipelineStatus.CANCELLED.value == "cancelled"


class TestPipelineRun:
    def test_frozen(self):
        run = PipelineRun(id="r1", provider=PipelineProvider.GITHUB_ACTIONS, status=PipelineStatus.PENDING)
        assert run.id == "r1"
        assert run.branch == "main"
        assert run.url == ""


class TestPipelineManager:
    def test_register_provider(self):
        mgr = PipelineManager()
        mgr.register_provider("gh", PipelineProvider.GITHUB_ACTIONS)
        assert mgr._providers["gh"] == PipelineProvider.GITHUB_ACTIONS

    def test_register_provider_immutable(self):
        mgr = PipelineManager()
        old = mgr._providers
        mgr.register_provider("gh", PipelineProvider.GITHUB_ACTIONS)
        assert mgr._providers is not old

    def test_trigger_build(self):
        mgr = PipelineManager()
        run = mgr.trigger_build(PipelineProvider.GITHUB_ACTIONS)
        assert run.provider == PipelineProvider.GITHUB_ACTIONS
        assert run.status == PipelineStatus.PENDING
        assert run.branch == "main"
        assert run.id.startswith("run_")

    def test_trigger_build_custom_branch(self):
        mgr = PipelineManager()
        run = mgr.trigger_build(PipelineProvider.GITLAB_CI, branch="develop")
        assert run.branch == "develop"

    def test_get_status_found(self):
        mgr = PipelineManager()
        run = mgr.trigger_build(PipelineProvider.GITHUB_ACTIONS)
        found = mgr.get_status(run.id)
        assert found is not None
        assert found.id == run.id

    def test_get_status_not_found(self):
        mgr = PipelineManager()
        assert mgr.get_status("nonexistent") is None

    def test_list_runs_all(self):
        mgr = PipelineManager()
        mgr.trigger_build(PipelineProvider.GITHUB_ACTIONS)
        mgr.trigger_build(PipelineProvider.GITLAB_CI)
        runs = mgr.list_runs()
        assert len(runs) == 2

    def test_list_runs_filtered(self):
        mgr = PipelineManager()
        mgr.trigger_build(PipelineProvider.GITHUB_ACTIONS)
        mgr.trigger_build(PipelineProvider.GITLAB_CI)
        runs = mgr.list_runs(provider=PipelineProvider.GITHUB_ACTIONS)
        assert len(runs) == 1
        assert runs[0].provider == PipelineProvider.GITHUB_ACTIONS

    def test_list_runs_limit(self):
        mgr = PipelineManager()
        for _ in range(5):
            mgr.trigger_build(PipelineProvider.GITHUB_ACTIONS)
        runs = mgr.list_runs(limit=3)
        assert len(runs) == 3

    def test_cancel_run_success(self):
        mgr = PipelineManager()
        run = mgr.trigger_build(PipelineProvider.GITHUB_ACTIONS)
        assert mgr.cancel_run(run.id) is True
        cancelled = mgr.get_status(run.id)
        assert cancelled is not None
        assert cancelled.status == PipelineStatus.CANCELLED

    def test_cancel_run_not_found(self):
        mgr = PipelineManager()
        assert mgr.cancel_run("nonexistent") is False

    def test_get_latest(self):
        mgr = PipelineManager()
        mgr.trigger_build(PipelineProvider.GITHUB_ACTIONS)
        run2 = mgr.trigger_build(PipelineProvider.GITHUB_ACTIONS)
        latest = mgr.get_latest()
        assert latest is not None
        assert latest.id == run2.id

    def test_get_latest_empty(self):
        mgr = PipelineManager()
        assert mgr.get_latest() is None

    def test_get_latest_filtered(self):
        mgr = PipelineManager()
        mgr.trigger_build(PipelineProvider.GITHUB_ACTIONS)
        gl_run = mgr.trigger_build(PipelineProvider.GITLAB_CI)
        latest = mgr.get_latest(provider=PipelineProvider.GITLAB_CI)
        assert latest is not None
        assert latest.id == gl_run.id

    def test_summary_empty(self):
        mgr = PipelineManager()
        assert mgr.summary() == "No pipeline runs."

    def test_summary_with_runs(self):
        mgr = PipelineManager()
        mgr.trigger_build(PipelineProvider.GITHUB_ACTIONS)
        s = mgr.summary()
        assert "Pipeline runs: 1" in s
        assert "github_actions" in s
