"""
Async Handler Validator.

Detects blocking calls in async functions, missing awaits on coroutines,
and async operations that lack timeout guards.
"""
from __future__ import annotations

import re


# Blocking calls and their async alternatives
_BLOCKING_CALLS: list[tuple[str, str]] = [
    (r"\btime\.sleep\s*\(", "asyncio.sleep()"),
    (r"\bopen\s*\(", "aiofiles.open() or asyncio.to_thread(open, ...)"),
    (r"\bsubprocess\.run\s*\(", "asyncio.create_subprocess_exec() or asyncio.create_subprocess_shell()"),
    (r"\bsubprocess\.call\s*\(", "asyncio.create_subprocess_exec()"),
    (r"\bsubprocess\.check_output\s*\(", "asyncio.create_subprocess_exec()"),
    (r"\bos\.system\s*\(", "asyncio.create_subprocess_shell()"),
    (r"\brequests\.get\s*\(", "aiohttp.ClientSession().get()"),
    (r"\brequests\.post\s*\(", "aiohttp.ClientSession().post()"),
    (r"\brequests\.request\s*\(", "aiohttp.ClientSession().request()"),
    (r"\bsocket\.recv\s*\(", "asyncio streams or asyncio.create_connection()"),
    (r"\binput\s*\(", "asyncio.get_event_loop().run_in_executor()"),
]

# Coroutines that must be awaited — detected by presence WITHOUT a preceding await.
# We match the call and then check manually whether "await" precedes it on the same line.
_AWAITABLE_CALLS: list[str] = [
    r"\basyncio\.sleep\s*\(",
    r"\basyncio\.gather\s*\(",
    r"\basyncio\.wait\s*\(",
    r"\basyncio\.create_subprocess",
]

# Operations that should have timeout guards
_TIMEOUT_OPS: list[tuple[str, str]] = [
    (r"\baiohttp\.\S*\s*\(", "Use timeout=aiohttp.ClientTimeout(total=N)"),
    (r"\basyncio\.open_connection\s*\(", "Wrap with asyncio.wait_for(..., timeout=N)"),
    (r"\basyncio\.create_subprocess", "Wrap with asyncio.wait_for(..., timeout=N)"),
    (r"\bwebsockets\.connect\s*\(", "Use open_timeout= parameter or asyncio.wait_for()"),
]

_ASYNC_WAIT_FOR_RE = re.compile(r"\basyncio\.wait_for\s*\(")
_TIMEOUT_PARAM_RE = re.compile(r"\btimeout\s*=")


class AsyncHandlerValidator:
    """Validates async command handlers for common async anti-patterns."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_blocking_calls(self, source_code: str) -> list[dict]:
        """Find blocking calls inside async functions.

        Args:
            source_code: Python source code.

        Returns:
            List of dicts with "line", "call", "async_alternative".
        """
        findings: list[dict] = []
        lines = source_code.splitlines()

        for lineno, text in enumerate(lines, start=1):
            # Skip comment lines
            stripped = text.strip()
            if stripped.startswith("#"):
                continue
            for pattern, alternative in _BLOCKING_CALLS:
                if re.search(pattern, text):
                    # Extract actual call text
                    m = re.search(pattern, text)
                    call_text = m.group(0).rstrip("(").strip() if m else pattern
                    findings.append(
                        {
                            "line": lineno,
                            "call": call_text,
                            "async_alternative": alternative,
                        }
                    )
                    break  # one finding per line

        return findings

    def check_await_chains(self, source_code: str) -> list[dict]:
        """Find missing awaits on coroutines.

        Args:
            source_code: Python source code.

        Returns:
            List of dicts with "line", "expression", "issue".
        """
        findings: list[dict] = []
        lines = source_code.splitlines()
        _await_re = re.compile(r"\bawait\s+")

        for lineno, text in enumerate(lines, start=1):
            stripped = text.strip()
            if stripped.startswith("#"):
                continue
            for pattern in _AWAITABLE_CALLS:
                m = re.search(pattern, text)
                if m:
                    # Only flag if "await" does NOT appear before this call on the line
                    before = text[: m.start()]
                    if not _await_re.search(before):
                        call_m = re.search(r"(asyncio\.\w+)\s*\(", text)
                        expr = call_m.group(1) if call_m else text.strip()
                        findings.append(
                            {
                                "line": lineno,
                                "expression": expr,
                                "issue": f"'{expr}' is a coroutine — missing 'await' before call",
                            }
                        )
                    break

        return findings

    def check_timeout_guards(self, source_code: str) -> list[dict]:
        """Verify async operations have timeout guards.

        Args:
            source_code: Python source code.

        Returns:
            List of dicts with "line", "operation", "has_timeout" (bool),
            "suggestion".
        """
        findings: list[dict] = []
        lines = source_code.splitlines()

        for lineno, text in enumerate(lines, start=1):
            stripped = text.strip()
            if stripped.startswith("#"):
                continue
            for pattern, suggestion in _TIMEOUT_OPS:
                if re.search(pattern, text):
                    # Check if there is a timeout guard on this line or nearby
                    has_timeout = bool(
                        _ASYNC_WAIT_FOR_RE.search(text)
                        or _TIMEOUT_PARAM_RE.search(text)
                    )
                    m = re.search(r"(\w[\w.]*)\s*\(", text)
                    operation = m.group(1) if m else text.strip()
                    findings.append(
                        {
                            "line": lineno,
                            "operation": operation,
                            "has_timeout": has_timeout,
                            "suggestion": suggestion if not has_timeout else "",
                        }
                    )
                    break

        return findings

    def validate_handlers(self, handlers: list[dict]) -> list[dict]:
        """Validate a list of handler dicts.

        Args:
            handlers: List of dicts with "name" and "source" keys.

        Returns:
            Combined list of finding dicts, each augmented with "handler_name".
        """
        all_findings: list[dict] = []

        for handler in handlers:
            name = handler.get("name", "<unknown>")
            source = handler.get("source", "")

            for finding in self.find_blocking_calls(source):
                all_findings.append({**finding, "handler_name": name, "check": "blocking_call"})

            for finding in self.check_await_chains(source):
                all_findings.append({**finding, "handler_name": name, "check": "missing_await"})

            for finding in self.check_timeout_guards(source):
                if not finding.get("has_timeout", True):
                    all_findings.append({**finding, "handler_name": name, "check": "missing_timeout"})

        return all_findings
