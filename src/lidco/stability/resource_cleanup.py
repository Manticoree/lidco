"""
Resource Cleanup Validator — Q343.

Validates that file handles, connections, and temp directories are properly
cleaned up, and audits __del__ methods for correctness.
"""
from __future__ import annotations

import re


class ResourceCleanupValidator:
    """Validate resource cleanup patterns in Python source code."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_file_handles(self, source_code: str) -> list[dict]:
        """Verify open() calls use context managers.

        Returns dicts with "line", "pattern", "uses_context_manager" (bool),
        "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Match open() call — but only flag non-context-manager usage.
            if re.search(r'\bopen\s*\(', stripped):
                # Context manager: 'with open(...)' on the same line.
                uses_cm = bool(
                    re.search(r'\bwith\s+(?:\w+\s*=\s*)?open\s*\(', stripped)
                    or re.search(r'\bwith\s+.*open\s*\(', stripped)
                )

                # Assignment without context manager: f = open(...)
                is_assignment = bool(
                    re.search(r'\w+\s*=\s*open\s*\(', stripped)
                    and not uses_cm
                )

                if is_assignment:
                    results.append(
                        {
                            "line": lineno,
                            "pattern": stripped,
                            "uses_context_manager": False,
                            "suggestion": (
                                "Replace 'f = open(...)' with "
                                "'with open(...) as f:' to guarantee the file "
                                "is closed even if an exception occurs."
                            ),
                        }
                    )
                elif uses_cm:
                    results.append(
                        {
                            "line": lineno,
                            "pattern": stripped,
                            "uses_context_manager": True,
                            "suggestion": "Good: file opened with context manager.",
                        }
                    )

        return results

    def check_connections(self, source_code: str) -> list[dict]:
        """Verify network/db connections are properly closed.

        Returns dicts with "line", "connection_type", "has_cleanup" (bool),
        "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        connection_patterns = [
            (r'sqlite3\.connect\s*\(', "sqlite3"),
            (r'psycopg2\.connect\s*\(', "psycopg2"),
            (r'pymysql\.connect\s*\(', "pymysql"),
            (r'mysql\.connector\.connect\s*\(', "mysql-connector"),
            (r'socket\.socket\s*\(', "socket"),
            (r'http\.client\.\w+Connection\s*\(', "http.client"),
            (r'smtplib\.SMTP\s*\(', "smtplib.SMTP"),
            (r'ftplib\.FTP\s*\(', "ftplib.FTP"),
            (r'paramiko\.SSHClient\s*\(', "paramiko"),
            (r'aiohttp\.ClientSession\s*\(', "aiohttp"),
        ]

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            for pat, conn_type in connection_patterns:
                if re.search(pat, stripped):
                    # Context manager on the same line.
                    uses_cm = bool(re.search(r'\bwith\b', stripped))

                    # Check ±30 lines for .close() call.
                    window = lines[max(0, lineno - 5) : min(len(lines), lineno + 30)]
                    has_close = any(
                        re.search(r'\.\s*close\s*\(\)', l) for l in window
                    )
                    has_cleanup = uses_cm or has_close

                    results.append(
                        {
                            "line": lineno,
                            "connection_type": conn_type,
                            "has_cleanup": has_cleanup,
                            "suggestion": (
                                "Good: connection is cleaned up."
                                if has_cleanup
                                else (
                                    f"'{conn_type}' connection opened without context manager or .close(). "
                                    "Use 'with connection:' or call .close() in a finally block."
                                )
                            ),
                        }
                    )
                    break  # one finding per line

        return results

    def check_temp_dirs(self, source_code: str) -> list[dict]:
        """Verify temp directories are cleaned up.

        Returns dicts with "line", "pattern", "has_cleanup" (bool),
        "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        temp_patterns = [
            r'tempfile\.mkdtemp\s*\(',
            r'tempfile\.TemporaryDirectory\s*\(',
            r'tempfile\.mkstemp\s*\(',
            r'tempfile\.NamedTemporaryFile\s*\(',
        ]

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            for pat in temp_patterns:
                if re.search(pat, stripped):
                    uses_cm = bool(re.search(r'\bwith\b', stripped))

                    # Look forward for shutil.rmtree / os.rmdir / .cleanup() / .close().
                    window = lines[lineno : min(len(lines), lineno + 50)]
                    has_cleanup = uses_cm or any(
                        re.search(
                            r'shutil\.rmtree\s*\(|os\.rmdir\s*\(|\.cleanup\s*\(\)|\.close\s*\(\)',
                            l,
                        )
                        for l in window
                    )

                    results.append(
                        {
                            "line": lineno,
                            "pattern": stripped,
                            "has_cleanup": has_cleanup,
                            "suggestion": (
                                "Good: temp directory/file is cleaned up."
                                if has_cleanup
                                else (
                                    "Temp resource created without cleanup. "
                                    "Use 'with tempfile.TemporaryDirectory() as d:' or "
                                    "call shutil.rmtree(d) in a finally block."
                                )
                            ),
                        }
                    )
                    break  # one finding per line

        return results

    def audit_del_methods(self, source_code: str) -> list[dict]:
        """Audit __del__ methods for correctness.

        Checks for:
        - __del__ that calls other methods (may fail during interpreter shutdown).
        - __del__ without None-checks on attributes.
        - __del__ that raises exceptions (silently swallowed by the interpreter).

        Returns dicts with "line", "class_name", "issues" (list), "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        # Find class names.
        current_class: str = ""
        class_indent = 0

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            m_class = re.match(r'class\s+(\w+)', stripped)
            if m_class:
                current_class = m_class.group(1)
                class_indent = indent
                i += 1
                continue

            # Detect __del__ method.
            m_del = re.match(r'def\s+__del__\s*\(', stripped)
            if m_del and current_class:
                del_lineno = i + 1
                del_indent = indent
                body_lines: list[str] = []
                j = i + 1
                while j < len(lines):
                    bl = lines[j]
                    bl_indent = len(bl) - len(bl.lstrip()) if bl.strip() else del_indent + 1
                    if bl.strip() and bl_indent <= del_indent:
                        break
                    body_lines.append(bl)
                    j += 1

                body = "\n".join(body_lines)
                issues: list[str] = []

                # Issue: calling self.method() that may fail during shutdown.
                if re.search(r'self\.\w+\s*\(', body):
                    if not re.search(r'if\s+self\.\w+\s+is\s+not\s+None', body):
                        issues.append(
                            "Calls self.method() without None-check — "
                            "attributes may be None during interpreter shutdown."
                        )

                # Issue: raise in __del__ is silently swallowed.
                if re.search(r'\braise\b', body):
                    issues.append(
                        "Raises an exception in __del__ — exceptions from __del__ are ignored "
                        "by the interpreter and printed to stderr instead."
                    )

                # Issue: accessing global modules that may already be None at shutdown.
                if re.search(r'\b(?:os|sys|logging|print)\s*\.', body):
                    issues.append(
                        "References module-level names (os, sys, logging, print) in __del__ — "
                        "these may have been set to None during interpreter shutdown."
                    )

                # Issue: missing try/except around cleanup.
                if body.strip() and "try:" not in body and issues:
                    issues.append(
                        "No try/except in __del__ — wrap cleanup in try/except Exception to prevent "
                        "error messages during shutdown."
                    )

                suggestion = (
                    "Provide an explicit close()/cleanup() method and call it via context manager; "
                    "keep __del__ minimal with None-checks and try/except."
                    if issues
                    else "__del__ looks acceptable."
                )

                results.append(
                    {
                        "line": del_lineno,
                        "class_name": current_class,
                        "issues": issues,
                        "suggestion": suggestion,
                    }
                )

            i += 1

        return results
