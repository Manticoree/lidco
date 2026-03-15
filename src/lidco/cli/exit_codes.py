"""Exit codes for lidco exec mode — Task 263.

Codes:
  0  SUCCESS          — task completed, no errors
  1  TASK_FAILED      — agent encountered an error or task could not be completed
  2  CONFIG_ERROR     — invalid config, missing API key, bad flags
  3  PERMISSION_DENIED — tool call blocked by permission policy
  4  TIMEOUT          — agent hit max-turns or wall-clock timeout
  5  INPUT_ERROR      — no task provided (empty stdin, no argument)
"""

from __future__ import annotations

SUCCESS = 0
TASK_FAILED = 1
CONFIG_ERROR = 2
PERMISSION_DENIED = 3
TIMEOUT = 4
INPUT_ERROR = 5
