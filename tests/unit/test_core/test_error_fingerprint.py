"""Tests for src/lidco/core/error_fingerprint.py"""
from __future__ import annotations

import pytest

from lidco.core.error_fingerprint import (
    _extract_normalized_frames,
    _normalise_module_path,
    _normalize_message,
    fingerprint_error,
)


# ── _normalize_message ────────────────────────────────────────────────────────

class TestNormalizeMessage:
    def test_no_special_content_unchanged(self):
        msg = "AttributeError: 'NoneType' object has no attribute 'foo'"
        assert _normalize_message(msg) == msg

    def test_memory_address_replaced(self):
        msg = "object at 0x7f3a1b2c3d4e"
        assert "<addr>" in _normalize_message(msg)
        assert "0x7f3a1b2c3d4e" not in _normalize_message(msg)

    def test_uuid_replaced(self):
        msg = "task id 550e8400-e29b-41d4-a716-446655440000 failed"
        result = _normalize_message(msg)
        assert "<uuid>" in result
        assert "550e8400" not in result

    def test_long_numeric_id_replaced(self):
        msg = "record 123456789 not found"
        result = _normalize_message(msg)
        assert "<id>" in result
        assert "123456789" not in result

    def test_short_numbers_preserved(self):
        msg = "line 42 has error"
        assert _normalize_message(msg) == msg

    def test_unix_tmp_path_replaced(self):
        msg = "file /tmp/pytest-abc123/test.py not found"
        result = _normalize_message(msg)
        assert "<tmp>" in result
        assert "/tmp/" not in result

    def test_windows_tmp_path_replaced(self):
        msg = r"file AppData\Local\Temp\pytest_abc\test.py missing"
        result = _normalize_message(msg)
        assert "<tmp>" in result

    def test_multiple_replacements(self):
        msg = "addr 0xDEADBEEFCAFE, uuid 12345678-1234-1234-1234-123456789012, id 999999"
        result = _normalize_message(msg)
        assert "<addr>" in result
        assert "<uuid>" in result
        assert "<id>" in result


# ── _normalise_module_path ────────────────────────────────────────────────────

class TestNormaliseModulePath:
    def test_src_prefix_stripped(self):
        assert _normalise_module_path("src/lidco/core/session.py") == "lidco.core.session"

    def test_windows_backslash(self):
        assert _normalise_module_path("src\\lidco\\core\\errors.py") == "lidco.core.errors"

    def test_tests_prefix_stripped(self):
        result = _normalise_module_path("tests/unit/test_foo.py")
        assert result == "unit.test_foo"

    def test_no_prefix(self):
        result = _normalise_module_path("foo/bar.py")
        assert result == "foo.bar"

    def test_single_file(self):
        result = _normalise_module_path("src/app.py")
        assert result == "app"


# ── _extract_normalized_frames ────────────────────────────────────────────────

class TestExtractNormalizedFrames:
    _TB = (
        'Traceback (most recent call last):\n'
        '  File "/abs/src/lidco/core/session.py", line 42, in run\n'
        '    result = self._do_thing()\n'
        '  File "/abs/src/lidco/core/errors.py", line 17, in _do_thing\n'
        '    raise ValueError("boom")\n'
        'ValueError: boom'
    )

    def test_extracts_two_frames(self):
        frames = _extract_normalized_frames(self._TB)
        assert len(frames) == 2

    def test_module_normalised(self):
        frames = _extract_normalized_frames(self._TB)
        assert frames[0][0] == "lidco.core.session"
        assert frames[1][0] == "lidco.core.errors"

    def test_function_names_extracted(self):
        frames = _extract_normalized_frames(self._TB)
        assert frames[0][1] == "run"
        assert frames[1][1] == "_do_thing"

    def test_top_n_limiting(self):
        tb = "\n".join(
            f'  File "/abs/src/lidco/mod{i}.py", line {i+1}, in fn{i}'
            for i in range(5)
        )
        frames = _extract_normalized_frames(tb, n=2)
        assert len(frames) == 2
        # Should be the last 2 (innermost)
        assert "mod3" in frames[0][0]
        assert "mod4" in frames[1][0]

    def test_empty_traceback(self):
        frames = _extract_normalized_frames("")
        assert frames == []

    def test_no_file_lines(self):
        frames = _extract_normalized_frames("ValueError: something went wrong")
        assert frames == []


# ── fingerprint_error ─────────────────────────────────────────────────────────

class TestFingerprintError:
    _TB = (
        'Traceback (most recent call last):\n'
        '  File "/abs/src/lidco/core/session.py", line 99, in run\n'
        '    do_thing()\n'
        'AttributeError: NoneType has no attribute foo'
    )

    def test_returns_16_char_hex(self):
        fp = fingerprint_error("AttributeError", "msg", None)
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_same_inputs_same_fingerprint(self):
        fp1 = fingerprint_error("ValueError", "some error", self._TB)
        fp2 = fingerprint_error("ValueError", "some error", self._TB)
        assert fp1 == fp2

    def test_different_error_type_different_fp(self):
        fp1 = fingerprint_error("AttributeError", "msg", None)
        fp2 = fingerprint_error("ValueError", "msg", None)
        assert fp1 != fp2

    def test_no_traceback_fallback(self):
        # Should still return a valid fingerprint
        fp = fingerprint_error("TypeError", "NoneType has no foo", None)
        assert len(fp) == 16

    def test_address_normalisation_stable(self):
        """Two messages differing only in memory address should get the same fp."""
        tb1 = self._TB
        tb2 = self._TB  # same TB
        fp1 = fingerprint_error("AttributeError", "object at 0x7f000001", tb1)
        fp2 = fingerprint_error("AttributeError", "object at 0x7f000002", tb2)
        assert fp1 == fp2

    def test_with_traceback_different_from_without(self):
        fp_with = fingerprint_error("ValueError", "msg", self._TB)
        fp_without = fingerprint_error("ValueError", "msg", None)
        # Different because traceback adds frame info
        assert fp_with != fp_without

    def test_different_message_different_fp(self):
        fp1 = fingerprint_error("ValueError", "message A", None)
        fp2 = fingerprint_error("ValueError", "message B", None)
        assert fp1 != fp2

    def test_uuid_in_message_normalised(self):
        msg1 = "error in task 550e8400-e29b-41d4-a716-446655440000"
        msg2 = "error in task 12345678-1234-1234-1234-123456789012"
        fp1 = fingerprint_error("RuntimeError", msg1, None)
        fp2 = fingerprint_error("RuntimeError", msg2, None)
        # Both UUIDs normalise to <uuid> → same fingerprint
        assert fp1 == fp2


# ── ErrorLedger.record integration ───────────────────────────────────────────

class TestErrorLedgerRecordTraceback:
    """Smoke tests for the patched ErrorLedger.record() signature."""

    def _make_ledger(self, tmp_path):
        from lidco.core.error_ledger import ErrorLedger
        return ErrorLedger(tmp_path / "test_ledger.db")

    def test_record_without_traceback_still_works(self, tmp_path):
        ledger = self._make_ledger(tmp_path)
        ledger.record("ValueError", "foo.py", "bar", "msg", "sess1")
        entries = ledger.get_frequent(min_occurrences=1)
        assert len(entries) == 1

    def test_record_with_traceback_uses_fingerprint(self, tmp_path):
        tb = (
            'Traceback (most recent call last):\n'
            '  File "/abs/src/lidco/core/foo.py", line 10, in bar\n'
            '    raise ValueError("boom")\n'
            'ValueError: boom'
        )
        ledger = self._make_ledger(tmp_path)
        ledger.record("ValueError", "foo.py", "bar", "boom", "sess1",
                      traceback_str=tb)
        entries = ledger.get_frequent(min_occurrences=1)
        assert len(entries) == 1

    def test_same_traceback_deduplicates(self, tmp_path):
        tb = (
            'Traceback (most recent call last):\n'
            '  File "/abs/src/lidco/core/foo.py", line 10, in run\n'
            'ValueError: boom'
        )
        ledger = self._make_ledger(tmp_path)
        for _ in range(3):
            ledger.record("ValueError", None, None, "boom", "sess",
                          traceback_str=tb)
        entries = ledger.get_frequent(min_occurrences=1)
        assert len(entries) == 1
        assert entries[0]["total_occurrences"] == 3
