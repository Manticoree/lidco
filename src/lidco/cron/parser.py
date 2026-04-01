"""Cron expression parser."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta


class CronParseError(Exception):
    """Raised when a cron expression cannot be parsed."""


@dataclass(frozen=True)
class CronField:
    """A single field in a cron expression."""

    values: frozenset[int]
    min_val: int
    max_val: int
    name: str


@dataclass(frozen=True)
class CronExpression:
    """A parsed cron expression."""

    minute: CronField
    hour: CronField
    day_of_month: CronField
    month: CronField
    day_of_week: CronField
    raw: str = ""

    def matches(self, dt: datetime) -> bool:
        """Check if *dt* matches this expression."""
        if dt.minute not in self.minute.values:
            return False
        if dt.hour not in self.hour.values:
            return False
        if dt.day not in self.day_of_month.values:
            return False
        if dt.month not in self.month.values:
            return False
        if dt.weekday() not in self._sunday_based_to_python():
            return False
        return True

    def next_run(self, from_time: datetime | None = None) -> datetime:
        """Calculate the next execution time after *from_time*."""
        if from_time is None:
            from_time = datetime.now()
        # Start from the next minute
        candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
        # Search up to ~2 years
        limit = 366 * 24 * 60
        for _ in range(limit):
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        raise CronParseError(f"No matching time found within search range for '{self.raw}'")

    def describe(self) -> str:
        """Return a human-readable description."""
        parts: list[str] = []
        parts.append(self._describe_field(self.minute, "minute"))
        parts.append(self._describe_field(self.hour, "hour"))
        parts.append(self._describe_field(self.day_of_month, "day"))
        parts.append(self._describe_field(self.month, "month"))
        parts.append(self._describe_field(self.day_of_week, "weekday"))
        return ", ".join(parts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sunday_based_to_python(self) -> set[int]:
        """Convert cron day-of-week values (0=Sun) to Python weekday (0=Mon)."""
        result: set[int] = set()
        for v in self.day_of_week.values:
            result.add((v - 1) % 7)  # cron 0/7=Sun->6, 1=Mon->0, ...
        return result

    @staticmethod
    def _describe_field(f: CronField, label: str) -> str:
        all_vals = frozenset(range(f.min_val, f.max_val + 1))
        if f.values == all_vals:
            return f"every {label}"
        vals = sorted(f.values)
        if len(vals) == 1:
            return f"{label}={vals[0]}"
        return f"{label}={','.join(str(v) for v in vals)}"


class CronParser:
    """Parse and validate cron expressions."""

    FIELD_DEFS = [
        ("minute", 0, 59),
        ("hour", 0, 23),
        ("day_of_month", 1, 31),
        ("month", 1, 12),
        ("day_of_week", 0, 7),
    ]

    def parse(self, expression: str) -> CronExpression:
        """Parse a cron expression like ``*/5 * * * *``."""
        parts = expression.strip().split()
        if len(parts) != 5:
            raise CronParseError(
                f"Expected 5 fields, got {len(parts)}: '{expression}'"
            )
        fields: list[CronField] = []
        for token, (name, lo, hi) in zip(parts, self.FIELD_DEFS):
            fields.append(self.parse_field(token, lo, hi, name))
        return CronExpression(
            minute=fields[0],
            hour=fields[1],
            day_of_month=fields[2],
            month=fields[3],
            day_of_week=fields[4],
            raw=expression.strip(),
        )

    def parse_field(
        self, field_str: str, min_val: int, max_val: int, name: str = ""
    ) -> CronField:
        """Parse a single cron field token."""
        values: set[int] = set()
        for part in field_str.split(","):
            values.update(self._parse_part(part.strip(), min_val, max_val))
        return CronField(
            values=frozenset(values),
            min_val=min_val,
            max_val=max_val,
            name=name,
        )

    def validate(self, expression: str) -> list[str]:
        """Return a list of validation errors (empty if valid)."""
        errors: list[str] = []
        parts = expression.strip().split()
        if len(parts) != 5:
            errors.append(f"Expected 5 fields, got {len(parts)}")
            return errors
        for token, (name, lo, hi) in zip(parts, self.FIELD_DEFS):
            try:
                self.parse_field(token, lo, hi, name)
            except CronParseError as exc:
                errors.append(str(exc))
        return errors

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_part(part: str, min_val: int, max_val: int) -> set[int]:
        """Parse a single comma-separated segment (e.g. ``*/5``, ``1-3``)."""
        # Handle step: */N or N-M/S
        step = 1
        if "/" in part:
            base, step_str = part.split("/", 1)
            if not step_str.isdigit() or int(step_str) == 0:
                raise CronParseError(f"Invalid step value: '{step_str}'")
            step = int(step_str)
            part = base

        if part == "*":
            return set(range(min_val, max_val + 1, step))

        if "-" in part:
            lo_str, hi_str = part.split("-", 1)
            if not lo_str.isdigit() or not hi_str.isdigit():
                raise CronParseError(f"Invalid range: '{part}'")
            lo, hi = int(lo_str), int(hi_str)
            if lo < min_val or hi > max_val or lo > hi:
                raise CronParseError(
                    f"Range {lo}-{hi} out of bounds [{min_val}-{max_val}]"
                )
            return set(range(lo, hi + 1, step))

        if part.isdigit():
            val = int(part)
            if val < min_val or val > max_val:
                raise CronParseError(
                    f"Value {val} out of bounds [{min_val}-{max_val}]"
                )
            return {val}

        raise CronParseError(f"Invalid cron token: '{part}'")
