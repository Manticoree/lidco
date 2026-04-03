#!/usr/bin/env python3
"""Run tests only for the most recent N quarters (default: 20).

Usage:
    python scripts/test_recent.py          # last 20 quarters
    python scripts/test_recent.py 10       # last 10 quarters
    python scripts/test_recent.py 5 -v     # last 5, verbose

This avoids running 12000+ tests at once and consuming all RAM.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent.parent / "tests" / "unit"


def get_quarter_dirs() -> list[Path]:
    """Return test_qNN dirs sorted by quarter number descending."""
    pattern = re.compile(r"^test_q(\d+)$")
    dirs = []
    for d in TESTS_DIR.iterdir():
        if d.is_dir():
            m = pattern.match(d.name)
            if m:
                dirs.append((int(m.group(1)), d))
    dirs.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in dirs]


def main() -> None:
    args = sys.argv[1:]

    # Extract count (first numeric arg) or default to 20
    count = 20
    extra_args: list[str] = []
    for arg in args:
        if arg.isdigit():
            count = int(arg)
        else:
            extra_args.append(arg)

    recent = get_quarter_dirs()[:count]
    if not recent:
        print("No test_qNN directories found.")
        sys.exit(1)

    dirs = [str(d) for d in reversed(recent)]  # run oldest first
    print(f"Running tests for {count} most recent quarters ({recent[-1].name} .. {recent[0].name})")
    print(f"Directories: {len(dirs)}")

    cmd = [
        sys.executable, "-m", "pytest",
        *dirs,
        "-x",   # stop on first failure
        "-q",   # quiet output
        *extra_args,
    ]

    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
