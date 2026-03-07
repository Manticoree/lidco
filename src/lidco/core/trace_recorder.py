"""Execution Trace Recorder — LDB-style hybrid trace for failing tests.

Builds a :class:`TraceSession` from pytest ``--tb=long --showlocals`` output,
combining :class:`~lidco.core.traceback_parser.TracebackParser` frame extraction
with local variable capture.  Detects anomalies by comparing against a saved
baseline from a passing run.

Approach:
    This implementation uses the **hybrid** strategy (Q26 first version):
    - Parses ``pytest --tb=long --showlocals`` output for frames + locals
    - Builds ``TraceEvent`` objects from traceback frame lines
    - Detects anomalies by diffing failing locals against baseline
    - Avoids ``sys.settrace`` in the main process (which breaks coverage)

Reference: LDB Trace Recorder (ACL 2024) — +9.8% fix rate on HumanEval.

Usage::

    from lidco.core.trace_recorder import record_trace, save_baseline, load_baseline

    session = await record_trace("tests/unit/test_foo.py::test_bar",
                                 "src/lidco/core/foo.py", project_dir=Path.cwd())
    if session:
        anomalies = detect_anomalies(session, load_baseline(project_dir))
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Maximum events stored per session (prevents memory bloat)
_MAX_EVENTS = 200


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TraceEvent:
    """A single captured execution event from a test run.

    Attributes:
        file:             Source file path (normalised to forward slashes).
        line:             1-based line number.
        event:            Event type: ``"call"`` | ``"line"`` | ``"return"`` |
                          ``"exception"``.
        locals_snapshot:  ``{name: repr[:80]}`` — up to 5 local variables.
        elapsed_ns:       Nanoseconds since trace start (0 for parsed events).
    """

    file: str
    line: int
    event: str
    locals_snapshot: dict[str, str]
    elapsed_ns: int


@dataclass(frozen=True)
class TraceAnomaly:
    """A detected deviation between a failing and a baseline (passing) run.

    Attributes:
        line:           Line where the anomaly was observed.
        variable:       Variable name that differs.
        failing_value:  ``repr`` of the variable in the failing run.
        baseline_value: Most common ``repr`` from passing runs.
        anomaly_type:   Classification: ``"unexpected_none"`` |
                        ``"type_drift"`` | ``"missing_key"`` |
                        ``"value_change"``.
    """

    line: int
    variable: str
    failing_value: str
    baseline_value: str
    anomaly_type: str


@dataclass
class TraceSession:
    """Captured execution trace for a single test run.

    Attributes:
        events:          Ordered list of captured :class:`TraceEvent` objects.
        target_file:     Source file the trace focuses on.
        target_function: Entry-point function (from traceback parsing).
        total_events:    Total events seen (may exceed ``len(events)`` if
                         truncated).
        truncated:       True when ``total_events > _MAX_EVENTS``.
    """

    events: list[TraceEvent]
    target_file: str
    target_function: str
    total_events: int
    truncated: bool


# ---------------------------------------------------------------------------
# Baseline persistence
# ---------------------------------------------------------------------------

_BASELINE_FILENAME = "trace_baseline.json"


def save_baseline(session: TraceSession, project_dir: Path) -> None:
    """Persist a passing-run trace as the baseline for future anomaly detection.

    Writes ``{line: {var: value, ...}}`` for each event to
    ``.lidco/trace_baseline.json``.
    """
    baseline_path = project_dir / ".lidco" / _BASELINE_FILENAME
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, dict[str, str]] = {}
    for ev in session.events:
        key = f"{ev.file}:{ev.line}"
        if key not in data:
            data[key] = {}
        data[key].update(ev.locals_snapshot)
    try:
        baseline_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.debug("save_baseline failed: %s", exc)


def load_baseline(project_dir: Path) -> dict[str, dict[str, str]]:
    """Load the saved baseline from ``.lidco/trace_baseline.json``.

    Returns ``{}`` when the file does not exist or cannot be parsed.
    """
    baseline_path = project_dir / ".lidco" / _BASELINE_FILENAME
    if not baseline_path.exists():
        return {}
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.debug("load_baseline failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------


def detect_anomalies(
    session: TraceSession,
    baseline: dict[str, dict[str, str]],
) -> list[TraceAnomaly]:
    """Detect anomalies by diffing failing-run locals against *baseline*.

    Compares each ``TraceEvent`` in *session* against the corresponding entry
    in *baseline* (keyed by ``"file:line"``).

    Anomaly types detected:
    - ``"unexpected_none"``: variable was not None in baseline but is ``"None"`` now
    - ``"type_drift"``: variable repr starts differently (different type)
    - ``"value_change"``: any other value change

    Args:
        session:  :class:`TraceSession` from the failing run.
        baseline: Dict loaded via :func:`load_baseline`.

    Returns:
        List of :class:`TraceAnomaly` objects (may be empty).
    """
    anomalies: list[TraceAnomaly] = []
    if not baseline:
        return anomalies

    for ev in session.events:
        key = f"{ev.file}:{ev.line}"
        baseline_locals = baseline.get(key, {})
        if not baseline_locals:
            continue

        for var, failing_val in ev.locals_snapshot.items():
            if var not in baseline_locals:
                continue
            baseline_val = baseline_locals[var]
            if failing_val == baseline_val:
                continue

            # Classify the anomaly
            if failing_val == "None" and baseline_val != "None":
                anomaly_type = "unexpected_none"
            elif _type_prefix(failing_val) != _type_prefix(baseline_val):
                anomaly_type = "type_drift"
            else:
                anomaly_type = "value_change"

            anomalies.append(TraceAnomaly(
                line=ev.line,
                variable=var,
                failing_value=failing_val,
                baseline_value=baseline_val,
                anomaly_type=anomaly_type,
            ))

    return anomalies


def _type_prefix(repr_str: str) -> str:
    """Extract the type prefix from a repr string for type_drift detection.

    Returns a normalised type indicator:
    - Numeric literals (int/float) → ``"<numeric>"``
    - String literals (quoted)     → ``"<str>"``
    - List / tuple                 → ``"<list>"``
    - Dict / set                   → ``"<dict>"``
    - ``None``                     → ``"<none>"``
    - Object repr ``ClassName(…)`` → ``"ClassName"``
    """
    s = repr_str.strip()
    if not s:
        return ""
    if s == "None":
        return "<none>"
    if s[0] in ("'", '"'):
        return "<str>"
    if s[0] == "[":
        return "<list>"
    if s[0] == "(":
        return "<tuple>"
    if s[0] in ("{",):
        return "<dict>"
    # Numeric: starts with digit or sign followed by digit
    if s[0].isdigit() or (s[0] in "+-" and len(s) > 1 and s[1].isdigit()):
        return "<numeric>"
    # Object repr: ClassName(…)
    return s.split("(")[0].strip()


# ---------------------------------------------------------------------------
# Trace recording (hybrid: parse pytest --tb=long --showlocals)
# ---------------------------------------------------------------------------


_FRAME_RE = re.compile(
    r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(\w+)'
)
_LOCALS_RE = re.compile(r'^\s{4}(\w+)\s+=\s+(.+)$')


def _parse_trace_output(
    output: str,
    target_file: str,
    max_events: int = _MAX_EVENTS,
) -> tuple[list[TraceEvent], int, bool]:
    """Parse pytest ``--tb=long --showlocals`` output into :class:`TraceEvent` objects.

    Parses traceback frames for the target file and extracts local variable
    snapshots from the indented ``var = repr`` lines that follow each frame.

    Returns:
        ``(events, total_seen, truncated)``
    """
    norm_target = target_file.replace("\\", "/")
    events: list[TraceEvent] = []
    total_seen = 0

    lines = output.splitlines()
    i = 0
    while i < len(lines):
        frame_match = _FRAME_RE.search(lines[i])
        if frame_match:
            file_path = frame_match.group(1).replace("\\", "/")
            lineno = int(frame_match.group(2))
            func_name = frame_match.group(3)

            # Check if this frame belongs to the target file
            if norm_target in file_path or file_path.endswith(norm_target):
                # Collect local variables from subsequent indented lines
                locals_snap: dict[str, str] = {}
                j = i + 1
                while j < len(lines) and len(locals_snap) < 5:
                    local_match = _LOCALS_RE.match(lines[j])
                    if local_match:
                        var_name = local_match.group(1)
                        var_repr = local_match.group(2).strip()[:80]
                        locals_snap[var_name] = var_repr
                        j += 1
                    elif lines[j].strip() == "" or _FRAME_RE.search(lines[j]):
                        break
                    else:
                        j += 1

                total_seen += 1
                if total_seen <= max_events:
                    # Determine event type from context
                    event_type = "exception" if "Error" in output[max(0, output.find(lines[i])-100):output.find(lines[i])+100] else "line"
                    events.append(TraceEvent(
                        file=file_path,
                        line=lineno,
                        event=event_type,
                        locals_snapshot=locals_snap,
                        elapsed_ns=0,
                    ))
        i += 1

    truncated = total_seen > max_events
    return events, total_seen, truncated


async def record_trace(
    test_command: str,
    target_file: str,
    project_dir: Path,
    max_events: int = _MAX_EVENTS,
    timeout_s: float = 30.0,
) -> TraceSession | None:
    """Record an execution trace by running pytest with ``--tb=long --showlocals``.

    Captures traceback frames and local variables for *target_file* from the
    pytest output.  Does **not** use ``sys.settrace`` (which would break coverage).

    Args:
        test_command: Pytest node ID or path (e.g., ``"tests/unit/test_foo.py::test_bar"``).
        target_file:  Source file to focus on (e.g., ``"src/lidco/core/session.py"``).
        project_dir:  Project root directory.
        max_events:   Cap on stored events (default 200).
        timeout_s:    Subprocess timeout in seconds (default 30).

    Returns:
        A :class:`TraceSession`, or ``None`` on failure / timeout.
    """
    cmd = [
        "python", "-m", "pytest",
        test_command,
        "-x",
        "--tb=long",
        "--showlocals",
        "-q",
        "--no-header",
    ]

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            ),
            timeout=5.0,
        )
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_s,
        )
        output = (stdout_bytes or b"").decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        logger.debug("record_trace timed out for %s", test_command)
        return None
    except Exception as exc:
        logger.debug("record_trace subprocess failed: %s", exc)
        return None

    events, total_seen, truncated = _parse_trace_output(output, target_file, max_events)

    # Extract target function from the last frame in target file
    target_function = ""
    for ev in reversed(events):
        if ev.event in ("exception", "line") and ev.file:
            # Try to parse function from the raw output
            for frame_match in _FRAME_RE.finditer(output):
                if frame_match.group(1).replace("\\", "/").endswith(
                    target_file.replace("\\", "/")
                ):
                    target_function = frame_match.group(3)
                    break
            break

    return TraceSession(
        events=events,
        target_file=target_file,
        target_function=target_function,
        total_events=total_seen,
        truncated=truncated,
    )


def format_trace_session(session: TraceSession, max_events: int = 10) -> str:
    """Format *session* as a Markdown summary for agent context injection.

    Returns ``""`` when the session has no events.

    Example output::

        ## Execution Trace
        File: src/lidco/core/session.py | Function: run

        | Line | Event | Locals |
        |------|-------|--------|
        | 42   | line  | self=<Session...>, x=None |
    """
    if not session.events:
        return ""

    lines: list[str] = [
        "## Execution Trace\n",
        f"File: `{session.target_file}`"
        + (f" | Function: `{session.target_function}`" if session.target_function else ""),
        "",
        "| Line | Event | Locals |",
        "|------|-------|--------|",
    ]
    for ev in session.events[:max_events]:
        locals_str = ", ".join(f"{k}={v}" for k, v in ev.locals_snapshot.items())
        lines.append(f"| {ev.line} | {ev.event} | {locals_str[:120]} |")

    if session.truncated:
        lines.append(
            f"\n*({session.total_events} total events — truncated to {max_events})*"
        )
    return "\n".join(lines)
