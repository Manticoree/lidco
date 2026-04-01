"""Shared pytest fixtures and configuration for LIDCO test suite."""
from __future__ import annotations

import asyncio
import gc
import sys
from typing import Any
from unittest.mock import MagicMock, AsyncMock

import pytest


# ---------------------------------------------------------------------------
# Memory limit: 15 GB hard cap to prevent system freeze
# ---------------------------------------------------------------------------

_MEMORY_LIMIT_BYTES = 15 * 1024 * 1024 * 1024  # 15 GB


def _apply_memory_limit() -> None:
    """Restrict the process memory to _MEMORY_LIMIT_BYTES.

    On Windows: uses Job Objects via ctypes.
    On POSIX: uses resource.setrlimit.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

            # CreateJobObjectW
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return

            # JOBOBJECT_EXTENDED_LIMIT_INFORMATION
            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_ulonglong),
                    ("WriteOperationCount", ctypes.c_ulonglong),
                    ("OtherOperationCount", ctypes.c_ulonglong),
                    ("ReadTransferCount", ctypes.c_ulonglong),
                    ("WriteTransferCount", ctypes.c_ulonglong),
                    ("OtherTransferCount", ctypes.c_ulonglong),
                ]

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
            JobObjectExtendedLimitInformation = 9

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY
            info.ProcessMemoryLimit = _MEMORY_LIMIT_BYTES

            kernel32.SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )

            # Assign current process to the job
            current_process = kernel32.GetCurrentProcess()
            kernel32.AssignProcessToJobObject(job, current_process)
        except Exception:
            pass  # Best effort — don't break tests if limit fails
    else:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (_MEMORY_LIMIT_BYTES, _MEMORY_LIMIT_BYTES))
        except Exception:
            pass


_apply_memory_limit()


# ---------------------------------------------------------------------------
# Event loop isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_event_loop_policy():
    """Ensure each test gets a fresh event loop, preventing cross-test contamination.

    Without this, tests that use asyncio.get_event_loop() fail when run after
    tests that close the event loop (e.g., test_cli fixtures).
    """
    yield
    # After each test, reset any closed loops
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if loop.is_closed():
            asyncio.get_event_loop_policy().set_event_loop(asyncio.new_event_loop())
    except RuntimeError:
        asyncio.get_event_loop_policy().set_event_loop(asyncio.new_event_loop())


# ---------------------------------------------------------------------------
# Common mock factories
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    """A minimal mock Session object for command handler tests."""
    session = MagicMock()
    session.config = MagicMock()
    session.config.agents = MagicMock()
    session.orchestrator = MagicMock()
    session.orchestrator.handle = AsyncMock(return_value=MagicMock(content="ok"))
    return session


@pytest.fixture
def mock_llm_response():
    """Factory for mock LLM responses."""
    def _make(content: str = "test response"):
        resp = MagicMock()
        resp.content = content
        resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        return resp
    return _make


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with basic structure."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")
    (tmp_path / "README.md").write_text("# Test Project\n")
    return tmp_path


# ---------------------------------------------------------------------------
# Async helper
# ---------------------------------------------------------------------------

def run_async(coro):
    """Run a coroutine synchronously. Prefer asyncio.run() in tests directly."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Periodic GC to reduce peak memory with 12000+ tests
# ---------------------------------------------------------------------------

_test_counter = 0


@pytest.fixture(autouse=True)
def _periodic_gc():
    """Force garbage collection every 200 tests to keep memory in check."""
    global _test_counter
    _test_counter += 1
    yield
    if _test_counter % 200 == 0:
        gc.collect()
