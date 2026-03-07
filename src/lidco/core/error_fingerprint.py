"""Semantic error fingerprinting — stable SHA-256 hashes that survive minor variations.

Normalises ephemeral values (memory addresses, UUIDs, numeric IDs, temp paths, line
numbers in frames) before hashing so that two occurrences of the same *logical* error
produce the same fingerprint even when the exact message text differs.

Based on Sentry semantic fingerprinting principles (−40% noise on deduplicated errors).

Usage::

    from lidco.core.error_fingerprint import fingerprint_error

    fp = fingerprint_error("AttributeError", "NoneType has no attribute 'foo'", traceback_str)
    # fp → "4a7b1c2d3e4f5a6b"  (stable 16-char hex)
"""

from __future__ import annotations

import hashlib
import re

# ---------------------------------------------------------------------------
# Normalisation patterns
# ---------------------------------------------------------------------------

# 1. Memory addresses: 0x followed by 6+ hex digits
_RE_ADDR = re.compile(r"0x[0-9a-fA-F]{6,}")

# 2. UUIDs (8-4-4-4-12 lowercase or uppercase hex)
_RE_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# 3. Long numeric IDs (6+ digit standalone numbers in error messages)
_RE_NUMERIC_ID = re.compile(r"\b\d{6,}\b")

# 4a. Unix temp paths: /tmp/<something>
_RE_TMP_UNIX = re.compile(r"/tmp/\S+")

# 4b. Windows temp paths: AppData\Local\Temp\<something>
_RE_TMP_WIN = re.compile(r"AppData[\\\/]Local[\\\/]Temp[\\\/]\S+", re.IGNORECASE)

# 5. Frame line numbers: only inside "File ..., line <N>" traceback lines
_RE_FRAME_LINE = re.compile(r'(File\s+"[^"]+",\s+line\s+)\d+')

# 6. Module path normalisation: separates path segments with dots
_RE_MODULE_PATH = re.compile(r'((?:src|tests|lib)[/\\][^:,\s"\']+\.py)')


def _normalise_module_path(raw_path: str) -> str:
    """Convert a source file path to a dotted module string.

    Handles absolute paths by finding the first ``src``, ``tests``, or ``lib``
    segment and stripping everything before it.

    Examples::

        "src/lidco/core/session.py"             → "lidco.core.session"
        "/abs/src/lidco/core/session.py"        → "lidco.core.session"
        "src\\lidco\\core\\session.py"          → "lidco.core.session"
        "tests/unit/test_foo.py"               → "unit.test_foo"
    """
    path = raw_path.replace("\\", "/")
    parts = path.split("/")
    # Find the first recognized root segment and strip everything before it
    _ROOT_SEGS = {"src", "tests", "lib"}
    for i, part in enumerate(parts):
        if part in _ROOT_SEGS:
            parts = parts[i + 1:]
            break
    # Strip .py suffix from last segment
    if parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(p for p in parts if p)


def _normalize_message(msg: str) -> str:
    """Apply normalisations 1–4 to an error message string.

    Replacements (in order):
    1. Memory addresses ``0x…`` → ``<addr>``
    2. UUIDs               → ``<uuid>``
    3. Long numeric IDs    → ``<id>``
    4. Temp paths          → ``<tmp>``
    """
    msg = _RE_ADDR.sub("<addr>", msg)
    msg = _RE_UUID.sub("<uuid>", msg)
    msg = _RE_NUMERIC_ID.sub("<id>", msg)
    msg = _RE_TMP_UNIX.sub("<tmp>", msg)
    msg = _RE_TMP_WIN.sub("<tmp>", msg)
    return msg


def _extract_normalized_frames(
    traceback_str: str,
    n: int = 3,
) -> list[tuple[str, str]]:
    """Extract and normalise the top-*n* traceback frame identifiers.

    Parses lines of the form::

        File "/abs/path/src/foo/bar.py", line 42, in some_function

    Returns a list of ``(normalised_module, function_name)`` tuples for the
    last *n* frames (innermost first).

    Args:
        traceback_str: Raw traceback text.
        n:             Maximum number of frames to return (default 3).
    """
    pattern = re.compile(
        r'File\s+"([^"]+)",\s+line\s+\d+,\s+in\s+(\w+)'
    )
    matches = pattern.findall(traceback_str)
    # matches is list of (path, function) — take last n (innermost)
    tail = matches[-n:] if len(matches) > n else matches
    result: list[tuple[str, str]] = []
    for path, func in tail:
        mod = _normalise_module_path(path)
        result.append((mod, func))
    return result


def fingerprint_error(
    error_type: str,
    message: str,
    traceback_str: str | None,
) -> str:
    """Compute a stable 16-char hex fingerprint for an error occurrence.

    When *traceback_str* is available the fingerprint is derived from:
    - error_type
    - normalised message
    - normalised top-3 frame ``(module, function)`` pairs

    When *traceback_str* is ``None`` (legacy / no traceback) the fingerprint
    falls back to ``error_type:normalised_message`` without frame info.

    Returns:
        16-character lowercase hex string (SHA-256[:16]).
    """
    norm_msg = _normalize_message(message)

    if traceback_str is not None:
        frames = _extract_normalized_frames(traceback_str, n=3)
        frames_str = "|".join(f"{mod}:{fn}" for mod, fn in frames)
        raw = f"{error_type}:{norm_msg}:{frames_str}"
    else:
        raw = f"{error_type}:{norm_msg}"

    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]
