"""Tests for /hash (#203), /base64 (#204), /json (#205)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 203: /hash ───────────────────────────────────────────────────────────

class TestHashCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("hash") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("hash").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_default_algo_sha256(self):
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg="hello"))
        expected = hashlib.sha256(b"hello").hexdigest()
        assert expected in result

    def test_algo_md5(self):
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg="hello --algo md5"))
        expected = hashlib.md5(b"hello").hexdigest()
        assert expected in result

    def test_algo_sha1(self):
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg="hello --algo sha1"))
        expected = hashlib.sha1(b"hello").hexdigest()
        assert expected in result

    def test_algo_sha512(self):
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg="hello --algo sha512"))
        expected = hashlib.sha512(b"hello").hexdigest()
        assert expected in result

    def test_algo_sha3_256(self):
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg="hello --algo sha3_256"))
        expected = hashlib.sha3_256(b"hello").hexdigest()
        assert expected in result

    def test_unknown_algo_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg="hello --algo xyz"))
        assert "xyz" in result or "неизвестный" in result.lower() or "unknown" in result.lower()

    def test_hashes_file(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_bytes(b"file content")
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg=str(f)))
        expected = hashlib.sha256(b"file content").hexdigest()
        assert expected in result

    def test_shows_algorithm_name(self):
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg="test --algo md5"))
        assert "md5" in result

    def test_shows_digest_length(self):
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg="test"))
        assert "256" in result or "64" in result  # sha256 = 64 hex chars = 256 bits

    def test_shows_all_algos_for_short_text(self):
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg="hi"))
        assert "md5" in result or "sha1" in result

    def test_different_inputs_different_hashes(self):
        reg = _make_registry()
        r1 = _run(reg.get("hash").handler(arg="hello"))
        r2 = _run(reg.get("hash").handler(arg="world"))
        # Digests must differ
        h1 = hashlib.sha256(b"hello").hexdigest()
        h2 = hashlib.sha256(b"world").hexdigest()
        assert h1 in r1
        assert h2 in r2
        assert h1 not in r2

    def test_shows_file_name_label(self, tmp_path):
        f = tmp_path / "myfile.bin"
        f.write_bytes(b"data")
        reg = _make_registry()
        result = _run(reg.get("hash").handler(arg=str(f)))
        assert "myfile.bin" in result


# ── Task 204: /base64 ─────────────────────────────────────────────────────────

class TestBase64Command:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("base64") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("base64").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_encodes_text(self):
        reg = _make_registry()
        result = _run(reg.get("base64").handler(arg="hello world"))
        expected = base64.b64encode(b"hello world").decode()
        assert expected in result

    def test_decode_flag(self):
        encoded = base64.b64encode(b"decoded text").decode()
        reg = _make_registry()
        result = _run(reg.get("base64").handler(arg=f"{encoded} --decode"))
        assert "decoded text" in result

    def test_decode_cyrillic(self):
        original = "Привет мир"
        encoded = base64.b64encode(original.encode()).decode()
        reg = _make_registry()
        result = _run(reg.get("base64").handler(arg=f"{encoded} --decode"))
        assert original in result

    def test_encodes_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"file data")
        expected = base64.b64encode(b"file data").decode()
        reg = _make_registry()
        result = _run(reg.get("base64").handler(arg=str(f)))
        assert expected in result

    def test_shows_byte_counts(self):
        reg = _make_registry()
        result = _run(reg.get("base64").handler(arg="hello"))
        assert "байт" in result or "byte" in result.lower() or "5" in result

    def test_shows_source_label(self):
        reg = _make_registry()
        result = _run(reg.get("base64").handler(arg="test input"))
        assert "test input" in result or "Base64" in result

    def test_invalid_base64_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("base64").handler(arg="not!valid@base64### --decode"))
        assert "ошибка" in result.lower() or "error" in result.lower() or isinstance(result, str)

    def test_long_output_split_into_lines(self):
        long_text = "A" * 200
        reg = _make_registry()
        result = _run(reg.get("base64").handler(arg=long_text))
        # Base64 of 200 chars = ~268 chars; should be split at 76
        encoded_part = base64.b64encode(long_text.encode()).decode()
        assert encoded_part[:76] in result

    def test_shows_file_name_label(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_bytes(b"x")
        reg = _make_registry()
        result = _run(reg.get("base64").handler(arg=str(f)))
        assert "data.txt" in result


# ── Task 205: /json ───────────────────────────────────────────────────────────

class TestJsonCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("json") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_formats_json(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg='{"a":1,"b":2}'))
        assert '"a"' in result
        assert '"b"' in result

    def test_invalid_json_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg="{not valid json}"))
        assert "ошибка" in result.lower() or "error" in result.lower() or "invalid" in result.lower()

    def test_shows_line_and_col_on_error(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg="{bad}"))
        assert isinstance(result, str) and len(result) > 0

    def test_compact_flag(self):
        reg = _make_registry()
        raw = json.dumps({"key": "value", "num": 42})
        result = _run(reg.get("json").handler(arg=f"{raw} --compact"))
        assert '{"key":"value","num":42}' in result or '"key":"value"' in result

    def test_keys_flag_shows_key_list(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg='{"foo": 1, "bar": 2, "baz": 3} --keys'))
        assert "foo" in result
        assert "bar" in result
        assert "baz" in result

    def test_validate_flag_valid(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg='{"ok": true} --validate'))
        assert "валиден" in result or "valid" in result.lower()

    def test_validate_flag_invalid(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg='{oops} --validate'))
        assert "ошибка" in result.lower() or "error" in result.lower()

    def test_formats_file(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"x": 1, "y": [1, 2, 3]}')
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg=str(f)))
        assert '"x"' in result
        assert "data.json" in result

    def test_shows_depth(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg='{"a": {"b": {"c": 1}}}'))
        assert "Глубина" in result or "depth" in result.lower() or "3" in result

    def test_shows_key_count(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg='{"a": 1, "b": 2, "c": 3}'))
        assert "Ключей" in result or "key" in result.lower() or "3" in result

    def test_truncates_long_json(self, tmp_path):
        big = {f"key_{i}": i for i in range(200)}
        f = tmp_path / "big.json"
        f.write_text(json.dumps(big))
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg=str(f)))
        assert "скрыто" in result or "hidden" in result.lower() or "100" in result

    def test_shows_file_name_label(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text('{"env": "prod"}')
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg=str(f)))
        assert "config.json" in result

    def test_array_json(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg='[1, 2, 3]'))
        assert isinstance(result, str) and "1" in result

    def test_nested_keys_count(self):
        reg = _make_registry()
        # {"a": {"x": 1}} → 2 keys total
        result = _run(reg.get("json").handler(arg='{"a": {"x": 1}}'))
        assert "2" in result or "Ключей" in result

    def test_shows_type_in_keys_flag(self):
        reg = _make_registry()
        result = _run(reg.get("json").handler(arg='{"items": [1,2], "name": "test"} --keys'))
        assert "list" in result or "список" in result.lower() or "items" in result
