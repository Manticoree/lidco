"""Tests for traceback_parser — structured traceback extraction."""

from __future__ import annotations

import pytest

from lidco.core.traceback_parser import (
    ParsedTraceback,
    TracebackFrame,
    parse_traceback,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_simple_tb(frames: list[tuple[str, int, str, str]], exc: str) -> str:
    """Build a minimal Python traceback string from frame tuples + exception."""
    lines = ["Traceback (most recent call last):"]
    for file, lineno, func, src in frames:
        lines.append(f'  File "{file}", line {lineno}, in {func}')
        lines.append(f"    {src}")
    lines.append(exc)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Test 1: Simple 2-frame traceback with AttributeError
# ---------------------------------------------------------------------------


class TestSimpleTwoFrameAttributeError:
    def test_parse_two_frame_attribute_error(self):
        tb = _make_simple_tb(
            [
                ("src/foo.py", 10, "bar", "result = obj.missing"),
                ("src/baz.py", 42, "qux", "bar()"),
            ],
            "AttributeError: 'NoneType' object has no attribute 'missing'",
        )
        result = parse_traceback(tb)

        assert result.error_type == "AttributeError"
        assert "missing" in result.error_message
        assert len(result.frames) == 2
        assert result.frames[0].file == "src/foo.py"
        assert result.frames[0].line == 10
        assert result.frames[0].function == "bar"
        assert result.frames[1].file == "src/baz.py"
        assert result.frames[1].line == 42


# ---------------------------------------------------------------------------
# Test 2: 3-frame traceback with KeyError
# ---------------------------------------------------------------------------


class TestThreeFrameKeyError:
    def test_parse_three_frame_key_error(self):
        tb = _make_simple_tb(
            [
                ("a.py", 1, "alpha", "x = d['key']"),
                ("b.py", 2, "beta", "alpha()"),
                ("c.py", 3, "gamma", "beta()"),
            ],
            "KeyError: 'key'",
        )
        result = parse_traceback(tb)

        assert result.error_type == "KeyError"
        assert len(result.frames) == 3
        assert result.frames[2].function == "gamma"


# ---------------------------------------------------------------------------
# Test 3: Empty string → UnknownError, empty frames
# ---------------------------------------------------------------------------


class TestEmptyString:
    def test_empty_string_returns_unknown_error(self):
        result = parse_traceback("")
        assert result.error_type == "UnknownError"
        assert result.error_message == ""
        assert result.frames == ()
        assert result.failure_frame is None

    def test_whitespace_only_returns_unknown_error(self):
        result = parse_traceback("   \n\t  ")
        assert result.error_type == "UnknownError"
        assert result.frames == ()


# ---------------------------------------------------------------------------
# Test 4: Single frame only
# ---------------------------------------------------------------------------


class TestSingleFrame:
    def test_single_frame_parsed(self):
        tb = _make_simple_tb(
            [("module.py", 7, "run", "do_thing()")],
            "ValueError: invalid literal",
        )
        result = parse_traceback(tb)
        assert len(result.frames) == 1
        assert result.frames[0].file == "module.py"
        assert result.frames[0].line == 7
        assert result.frames[0].function == "run"


# ---------------------------------------------------------------------------
# Test 5: Frame with locals in --tb=long style
# ---------------------------------------------------------------------------


class TestLocalsInLongStyle:
    def test_locals_extracted_up_to_three(self):
        tb = (
            "Traceback (most recent call last):\n"
            '  File "app.py", line 20, in process\n'
            "    result = compute(x, y)\n"
            "    x = 42\n"
            "    y = None\n"
            "    extra = 'hello'\n"
            "    ignored = 999\n"
            "RuntimeError: failed\n"
        )
        result = parse_traceback(tb)
        assert len(result.frames) == 1
        hint = result.frames[0].locals_hint
        assert "x=42" in hint
        assert "y=None" in hint
        assert "extra='hello'" in hint
        # Only first 3 vars captured
        assert "ignored" not in hint

    def test_no_locals_gives_empty_hint(self):
        tb = _make_simple_tb(
            [("app.py", 5, "main", "foo()")],
            "RuntimeError: oops",
        )
        result = parse_traceback(tb)
        assert result.frames[0].locals_hint == ""


# ---------------------------------------------------------------------------
# Test 6: Built-in frame like File "<string>", line 1, in <module>
# ---------------------------------------------------------------------------


class TestBuiltinFrame:
    def test_builtin_string_frame_parsed(self):
        tb = (
            "Traceback (most recent call last):\n"
            '  File "<string>", line 1, in <module>\n'
            "    exec(code)\n"
            "NameError: name 'code' is not defined\n"
        )
        result = parse_traceback(tb)
        assert len(result.frames) == 1
        assert result.frames[0].file == "<string>"
        assert result.frames[0].function == "<module>"
        # source falls back to the line found in the traceback
        assert result.frames[0].source == "exec(code)"

    def test_frozen_frame_parsed(self):
        tb = (
            "Traceback (most recent call last):\n"
            '  File "<frozen importlib._bootstrap>", line 228, in _call_with_frames_removed\n'
            "    f(*args, **kwds)\n"
            "ImportError: bad import\n"
        )
        result = parse_traceback(tb)
        assert len(result.frames) == 1
        assert result.frames[0].file.startswith("<frozen")


# ---------------------------------------------------------------------------
# Test 7: failure_frame is the last frame
# ---------------------------------------------------------------------------


class TestFailureFrame:
    def test_failure_frame_is_last(self):
        tb = _make_simple_tb(
            [
                ("first.py", 1, "a", "b()"),
                ("second.py", 2, "b", "c()"),
                ("third.py", 3, "c", "raise RuntimeError"),
            ],
            "RuntimeError: boom",
        )
        result = parse_traceback(tb)
        assert result.failure_frame is not None
        assert result.failure_frame.file == "third.py"
        assert result.failure_frame.function == "c"


# ---------------------------------------------------------------------------
# Test 8: root_cause_hint for AttributeError
# ---------------------------------------------------------------------------


class TestRootCauseHintAttributeError:
    def test_attribute_error_hint(self):
        tb = _make_simple_tb(
            [("x.py", 1, "f", "x.foo")],
            "AttributeError: has no attribute",
        )
        result = parse_traceback(tb)
        assert result.root_cause_hint == "None object or missing attribute"


# ---------------------------------------------------------------------------
# Test 9: root_cause_hint for ImportError
# ---------------------------------------------------------------------------


class TestRootCauseHintImportError:
    def test_import_error_hint(self):
        tb = _make_simple_tb(
            [("x.py", 1, "f", "import missing_mod")],
            "ImportError: cannot import name 'foo'",
        )
        result = parse_traceback(tb)
        assert result.root_cause_hint == "missing module or circular import"


# ---------------------------------------------------------------------------
# Test 10: Unknown exception type → root_cause_hint = ""
# ---------------------------------------------------------------------------


class TestUnknownExceptionHint:
    def test_unknown_exception_type_empty_hint(self):
        tb = _make_simple_tb(
            [("x.py", 1, "f", "raise Boom")],
            "BoomError: something exploded",
        )
        result = parse_traceback(tb)
        assert result.root_cause_hint == ""


# ---------------------------------------------------------------------------
# Test 11: error_message extraction is correct
# ---------------------------------------------------------------------------


class TestErrorMessageExtraction:
    def test_error_message_extracted(self):
        tb = _make_simple_tb(
            [("x.py", 1, "f", "x")],
            "TypeError: unsupported operand type(s) for +: 'int' and 'str'",
        )
        result = parse_traceback(tb)
        assert result.error_type == "TypeError"
        assert "unsupported operand" in result.error_message

    def test_error_message_with_colon_in_value(self):
        tb = _make_simple_tb(
            [("x.py", 1, "f", "x")],
            "KeyError: 'a:b:c'",
        )
        result = parse_traceback(tb)
        assert result.error_type == "KeyError"
        assert "'a:b:c'" in result.error_message


# ---------------------------------------------------------------------------
# Test 12: source field populated from traceback text
# ---------------------------------------------------------------------------


class TestSourceField:
    def test_source_from_traceback_text(self):
        tb = (
            "Traceback (most recent call last):\n"
            '  File "/no/such/file.py", line 99, in mystery\n'
            "    some_source_line()\n"
            "RuntimeError: failed\n"
        )
        result = parse_traceback(tb)
        # linecache won't find this file, so fallback to text
        assert result.frames[0].source == "some_source_line()"


# ---------------------------------------------------------------------------
# Test 13: frames are immutable (frozen dataclass)
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_traceback_frame_is_frozen(self):
        frame = TracebackFrame(
            file="x.py",
            line=1,
            function="f",
            source="pass",
            locals_hint="",
        )
        with pytest.raises((AttributeError, TypeError)):
            frame.line = 999  # type: ignore[misc]

    def test_parsed_traceback_is_frozen(self):
        pt = ParsedTraceback(
            error_type="ValueError",
            error_message="bad",
            frames=(),
            failure_frame=None,
            root_cause_hint="",
        )
        with pytest.raises((AttributeError, TypeError)):
            pt.error_type = "Other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 14: ParsedTraceback.failure_frame is None when no frames
# ---------------------------------------------------------------------------


class TestFailureFrameNoneWhenNoFrames:
    def test_failure_frame_none_for_no_frames(self):
        result = parse_traceback("ValueError: isolated error line\n")
        assert result.failure_frame is None


# ---------------------------------------------------------------------------
# Test 15: Traceback with no exception line at end → error_type="UnknownError"
# ---------------------------------------------------------------------------


class TestNoExceptionLine:
    def test_no_exception_line_gives_unknown_error(self):
        tb = (
            "Traceback (most recent call last):\n"
            '  File "x.py", line 1, in f\n'
            "    do_thing()\n"
            # No trailing exception line
        )
        result = parse_traceback(tb)
        assert result.error_type == "UnknownError"
        assert result.error_message == ""
        # Frame still parsed
        assert len(result.frames) == 1
