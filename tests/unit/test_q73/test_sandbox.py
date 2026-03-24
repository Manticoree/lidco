"""Tests for ExecutionSandbox — T488."""
from __future__ import annotations
import pytest
from lidco.tools.sandbox import ExecutionSandbox, SandboxVerdict


class TestExecutionSandbox:
    def test_safe_command_allowed(self):
        sb = ExecutionSandbox()
        v = sb.check("ls -la")
        assert v.allowed

    def test_rm_rf_root_blocked(self):
        sb = ExecutionSandbox()
        v = sb.check("rm -rf /")
        assert not v.allowed

    def test_dd_if_blocked(self):
        sb = ExecutionSandbox()
        v = sb.check("dd if=/dev/zero of=/dev/sda")
        assert not v.allowed

    def test_fork_bomb_blocked(self):
        sb = ExecutionSandbox()
        v = sb.check(":(){ :|:& };:")
        assert not v.allowed

    def test_mkfs_blocked(self):
        sb = ExecutionSandbox()
        v = sb.check("mkfs.ext4 /dev/sdb")
        assert not v.allowed

    def test_custom_blocked_pattern(self):
        sb = ExecutionSandbox(blocked_patterns=[r"deploy"])
        v = sb.check("./deploy.sh production")
        assert not v.allowed

    def test_network_cmd_blocked_when_disabled(self):
        sb = ExecutionSandbox(network_disabled=True)
        v = sb.check("curl https://example.com")
        assert not v.allowed

    def test_network_cmd_allowed_when_not_disabled(self):
        sb = ExecutionSandbox(network_disabled=False)
        v = sb.check("curl https://example.com")
        assert v.allowed

    def test_allowed_dirs_restricts_cwd(self):
        sb = ExecutionSandbox(allowed_dirs=["/safe"])
        v = sb.check("ls", cwd="/unsafe/path")
        assert not v.allowed

    def test_allowed_dirs_permits_cwd(self, tmp_path):
        sb = ExecutionSandbox(allowed_dirs=[str(tmp_path)])
        v = sb.check("ls", cwd=str(tmp_path))
        assert v.allowed

    def test_verdict_reason_present(self):
        sb = ExecutionSandbox()
        v = sb.check("rm -rf /")
        assert v.reason

    def test_env_var_allowed_no_restriction(self):
        sb = ExecutionSandbox()
        assert sb.is_env_var_allowed("ANY_VAR")

    def test_env_var_restriction(self):
        sb = ExecutionSandbox(allowed_env_vars=["PATH", "HOME"])
        assert sb.is_env_var_allowed("PATH")
        assert not sb.is_env_var_allowed("SECRET_KEY")
