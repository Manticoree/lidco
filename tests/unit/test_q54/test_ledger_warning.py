"""Q54/367 — ErrorLedger failure counter with user warning."""
from __future__ import annotations

import logging
import pytest
from unittest.mock import MagicMock, patch


def _make_session_with_failing_ledger(fail_count: int):
    """Return a Session-like object where _error_ledger raises after N calls."""
    from lidco.core.session import Session

    session = object.__new__(Session)
    session._error_history = MagicMock()
    session._ledger_failure_count = 0

    call_count = [0]

    def failing_record(**kwargs):
        call_count[0] += 1
        raise RuntimeError("DB locked")

    session._error_ledger = MagicMock()
    session._error_ledger.record.side_effect = failing_record
    return session


class TestLedgerWarning:
    def test_no_warning_on_first_failure(self, caplog):
        session = _make_session_with_failing_ledger(1)
        record = MagicMock()
        record.error_type = "SyntaxError"
        record.file_hint = "foo.py"
        record.message = "msg"

        with caplog.at_level(logging.WARNING, logger="lidco.core.session"):
            session._on_error_record(record)

        assert "недоступен" not in caplog.text

    def test_warning_on_third_failure(self, caplog):
        session = _make_session_with_failing_ledger(3)
        record = MagicMock()
        record.error_type = "TypeError"
        record.file_hint = "bar.py"
        record.message = "msg"

        with caplog.at_level(logging.WARNING, logger="lidco.core.session"):
            for _ in range(3):
                session._on_error_record(record)

        assert "недоступен" in caplog.text

    def test_no_duplicate_warning_after_third(self, caplog):
        session = _make_session_with_failing_ledger(10)
        record = MagicMock()
        record.error_type = "TypeError"
        record.file_hint = "bar.py"
        record.message = "msg"

        with caplog.at_level(logging.WARNING, logger="lidco.core.session"):
            for _ in range(6):
                session._on_error_record(record)

        # Warning should appear exactly once (at the 3rd failure)
        count = caplog.text.count("недоступен")
        assert count == 1

    def test_counter_resets_on_success(self):
        session = object.__new__(__import__("lidco.core.session", fromlist=["Session"]).Session)
        session._error_history = MagicMock()
        session._ledger_failure_count = 2  # was at 2 failures

        # Make ledger succeed now
        session._error_ledger = MagicMock()
        session._error_ledger.record.return_value = None

        record = MagicMock()
        record.error_type = "E"
        record.file_hint = "f"
        record.message = "m"

        session._on_error_record(record)
        assert session._ledger_failure_count == 0
