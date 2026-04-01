"""Tests for lidco.cli.commands.q218_cmds."""

import asyncio

from lidco.cli.commands.registry import CommandRegistry


def _make_registry():
    from lidco.cli.commands.q218_cmds import register

    reg = CommandRegistry()
    register(reg)
    return reg


class TestCommandRegistration:
    def test_gen_actions_registered(self):
        reg = _make_registry()
        assert "gen-actions" in reg._commands

    def test_pipeline_registered(self):
        reg = _make_registry()
        assert "pipeline" in reg._commands

    def test_deploy_registered(self):
        reg = _make_registry()
        assert "deploy" in reg._commands

    def test_cloud_registered(self):
        reg = _make_registry()
        assert "cloud" in reg._commands


class TestGenActionsCommand:
    def test_default_python(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["gen-actions"].handler(""))
        assert "name: CI" in result
        assert "pytest" in result

    def test_node_project(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["gen-actions"].handler("node"))
        assert "npm test" in result

    def test_rust_project(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["gen-actions"].handler("rust"))
        assert "cargo test" in result


class TestPipelineCommand:
    def test_no_args(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pipeline"].handler(""))
        assert "Usage" in result

    def test_trigger(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pipeline"].handler("trigger github_actions"))
        assert "Triggered" in result
        assert "github_actions" in result

    def test_trigger_default_provider(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pipeline"].handler("trigger"))
        assert "Triggered" in result

    def test_trigger_unknown_provider(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pipeline"].handler("trigger bogus"))
        assert "Unknown provider" in result

    def test_status_no_run_id(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pipeline"].handler("status"))
        assert "Usage" in result

    def test_status_not_found(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pipeline"].handler("status run_999999"))
        assert "not found" in result

    def test_list(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pipeline"].handler("list"))
        assert "No pipeline runs" in result

    def test_unknown_subcommand(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pipeline"].handler("foo"))
        assert "Unknown subcommand" in result


class TestDeployCommand:
    def test_no_args(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["deploy"].handler(""))
        assert "Usage" in result

    def test_deploy_env(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["deploy"].handler("production"))
        assert "Deployed" in result
        assert "production" in result
        assert "HEAD" in result

    def test_deploy_with_commit(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["deploy"].handler("staging abc123"))
        assert "abc123" in result


class TestCloudCommand:
    def test_no_args(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["cloud"].handler(""))
        assert "Usage" in result

    def test_list_empty(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["cloud"].handler("list"))
        assert "No cloud resources" in result

    def test_logs_empty(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["cloud"].handler("logs"))
        assert "No logs" in result

    def test_invoke_no_resource(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["cloud"].handler("invoke"))
        assert "Usage" in result

    def test_invoke_resource(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["cloud"].handler("invoke res_42"))
        assert "Invoked" in result
        assert "res_42" in result

    def test_unknown_subcommand(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["cloud"].handler("foo"))
        assert "Unknown subcommand" in result
