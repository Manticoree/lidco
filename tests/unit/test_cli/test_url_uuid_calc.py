"""Tests for /url (#206), /uuid (#207), /calc (#208)."""

from __future__ import annotations

import asyncio
import math
import re
import uuid

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 206: /url ────────────────────────────────────────────────────────────

class TestUrlCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("url") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_parses_url_scheme(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler(arg="https://example.com/path?q=1"))
        assert "https" in result

    def test_parses_url_host(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler(arg="https://example.com/path"))
        assert "example.com" in result

    def test_parses_url_path(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler(arg="https://example.com/some/path"))
        assert "/some/path" in result

    def test_parses_query_params(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler(arg="https://example.com/?foo=bar&baz=42"))
        assert "foo" in result
        assert "bar" in result

    def test_parses_fragment(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler(arg="https://example.com/page#section1"))
        assert "section1" in result

    def test_encode_flag(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler(arg="hello world --encode"))
        assert "hello%20world" in result or "%20" in result

    def test_decode_flag(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler(arg="hello%20world --decode"))
        assert "hello world" in result

    def test_encode_special_chars(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler(arg="a&b=c --encode"))
        assert "%" in result

    def test_parses_port(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler(arg="http://localhost:8080/api"))
        assert "8080" in result

    def test_shows_multiple_query_params(self):
        reg = _make_registry()
        result = _run(reg.get("url").handler(arg="https://api.example.com/?a=1&b=2&c=3"))
        assert "a" in result and "b" in result and "c" in result


# ── Task 207: /uuid ───────────────────────────────────────────────────────────

class TestUuidCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("uuid") is not None

    def test_generates_one_uuid_by_default(self):
        reg = _make_registry()
        result = _run(reg.get("uuid").handler())
        # Should contain a valid UUID pattern
        pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        assert re.search(pattern, result)

    def test_generates_multiple_uuids(self):
        reg = _make_registry()
        result = _run(reg.get("uuid").handler(arg="3"))
        pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        matches = re.findall(pattern, result)
        assert len(matches) == 3

    def test_caps_at_20(self):
        reg = _make_registry()
        result = _run(reg.get("uuid").handler(arg="100"))
        pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        matches = re.findall(pattern, result)
        assert len(matches) == 20

    def test_generated_uuid_is_valid(self):
        reg = _make_registry()
        result = _run(reg.get("uuid").handler())
        pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        m = re.search(pattern, result)
        assert m
        # Should not raise
        uuid.UUID(m.group())

    def test_validate_valid_uuid(self):
        reg = _make_registry()
        valid = str(uuid.uuid4())
        result = _run(reg.get("uuid").handler(arg=f"validate {valid}"))
        assert "валиден" in result or "valid" in result.lower()

    def test_validate_invalid_uuid(self):
        reg = _make_registry()
        result = _run(reg.get("uuid").handler(arg="validate not-a-uuid"))
        assert "неверный" in result.lower() or "invalid" in result.lower() or "не" in result.lower()

    def test_shows_version(self):
        reg = _make_registry()
        result = _run(reg.get("uuid").handler())
        assert "v4" in result or "4" in result

    def test_shows_validate_hint(self):
        reg = _make_registry()
        result = _run(reg.get("uuid").handler())
        assert "validate" in result

    def test_validate_shows_version_info(self):
        reg = _make_registry()
        valid = str(uuid.uuid4())
        result = _run(reg.get("uuid").handler(arg=f"validate {valid}"))
        assert "4" in result or "Версия" in result

    def test_uuids_are_unique(self):
        reg = _make_registry()
        result = _run(reg.get("uuid").handler(arg="5"))
        pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        matches = re.findall(pattern, result)
        assert len(set(matches)) == 5  # all unique


# ── Task 208: /calc ───────────────────────────────────────────────────────────

class TestCalcCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("calc") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_simple_addition(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="2 + 2"))
        assert "4" in result

    def test_subtraction(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="10 - 3"))
        assert "7" in result

    def test_multiplication(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="6 * 7"))
        assert "42" in result

    def test_division(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="15 / 3"))
        assert "5" in result

    def test_power(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="2**10"))
        assert "1024" in result

    def test_sqrt(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="sqrt(144)"))
        assert "12" in result

    def test_pi_constant(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="pi"))
        assert "3.14" in result

    def test_floor_division(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="17 // 5"))
        assert "3" in result

    def test_modulo(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="17 % 5"))
        assert "2" in result

    def test_division_by_zero(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="1 / 0"))
        assert "ноль" in result or "zero" in result.lower() or "ошибка" in result.lower()

    def test_invalid_expression(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="2 + * 3"))
        assert "ошибка" in result.lower() or "syntax" in result.lower() or "синтаксическ" in result.lower()

    def test_blocked_import(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="__import__('os').getcwd()"))
        # Any blocking message is acceptable — import or attribute guard
        assert isinstance(result, str) and len(result) > 0
        # Should NOT successfully return a path
        import os
        assert os.getcwd() not in result

    def test_log_function(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="log(100, 10)"))
        assert "2" in result

    def test_sin_function(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="sin(0)"))
        assert "0" in result

    def test_abs_function(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="abs(-42)"))
        assert "42" in result

    def test_shows_expression_and_result(self):
        reg = _make_registry()
        result = _run(reg.get("calc").handler(arg="3 + 4"))
        assert "3 + 4" in result or "7" in result
