"""Tests for exit code constants — Task 263."""

from __future__ import annotations

from lidco.cli.exit_codes import (
    SUCCESS,
    TASK_FAILED,
    CONFIG_ERROR,
    PERMISSION_DENIED,
    TIMEOUT,
    INPUT_ERROR,
)


class TestExitCodes:
    def test_success_is_zero(self):
        assert SUCCESS == 0

    def test_task_failed_is_one(self):
        assert TASK_FAILED == 1

    def test_config_error_is_two(self):
        assert CONFIG_ERROR == 2

    def test_permission_denied_is_three(self):
        assert PERMISSION_DENIED == 3

    def test_timeout_is_four(self):
        assert TIMEOUT == 4

    def test_input_error_is_five(self):
        assert INPUT_ERROR == 5

    def test_all_unique(self):
        codes = [SUCCESS, TASK_FAILED, CONFIG_ERROR, PERMISSION_DENIED, TIMEOUT, INPUT_ERROR]
        assert len(set(codes)) == len(codes)

    def test_all_non_negative(self):
        codes = [SUCCESS, TASK_FAILED, CONFIG_ERROR, PERMISSION_DENIED, TIMEOUT, INPUT_ERROR]
        assert all(c >= 0 for c in codes)
