"""
Q312 Task 1672 — Load Profile

Define load profiles: ramp-up, steady, spike, soak.
Concurrent users, request patterns, duration.
Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProfileType(Enum):
    """Supported load profile shapes."""

    RAMP_UP = "ramp_up"
    STEADY = "steady"
    SPIKE = "spike"
    SOAK = "soak"


class RequestMethod(Enum):
    """HTTP-like request methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class RequestPattern:
    """A single request definition within a load profile."""

    url: str
    method: RequestMethod = RequestMethod.GET
    headers: dict[str, str] = field(default_factory=dict)
    body: str | None = None
    weight: float = 1.0  # relative probability of selection

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.url:
            errors.append("url must not be empty")
        if self.weight <= 0:
            errors.append("weight must be positive")
        return errors


@dataclass
class LoadProfile:
    """
    A complete load test profile describing how load is shaped over time.

    Attributes:
        name: Human-readable label.
        profile_type: Shape of the load curve.
        duration_seconds: Total test duration.
        max_users: Peak concurrent users.
        ramp_up_seconds: Time to ramp from 0 to *max_users* (RAMP_UP/SPIKE).
        ramp_down_seconds: Cool-down period (SPIKE).
        spike_users: Extra users injected during spike.
        requests: Weighted request patterns to rotate through.
        think_time_ms: Pause between consecutive requests per virtual user.
        tags: Arbitrary metadata.
    """

    name: str
    profile_type: ProfileType = ProfileType.STEADY
    duration_seconds: int = 60
    max_users: int = 10
    ramp_up_seconds: int = 0
    ramp_down_seconds: int = 0
    spike_users: int = 0
    requests: list[RequestPattern] = field(default_factory=list)
    think_time_ms: int = 0
    tags: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Return list of validation error strings (empty == valid)."""
        errors: list[str] = []
        if not self.name:
            errors.append("name must not be empty")
        if self.duration_seconds <= 0:
            errors.append("duration_seconds must be positive")
        if self.max_users <= 0:
            errors.append("max_users must be positive")
        if self.ramp_up_seconds < 0:
            errors.append("ramp_up_seconds must be non-negative")
        if self.ramp_down_seconds < 0:
            errors.append("ramp_down_seconds must be non-negative")
        if self.profile_type == ProfileType.SPIKE and self.spike_users <= 0:
            errors.append("spike_users must be positive for spike profiles")
        if not self.requests:
            errors.append("at least one request pattern is required")
        for i, r in enumerate(self.requests):
            for e in r.validate():
                errors.append(f"requests[{i}]: {e}")
        return errors

    # ------------------------------------------------------------------
    # Concurrency schedule — users at time *t*
    # ------------------------------------------------------------------

    def users_at(self, t: float) -> int:
        """Return the number of concurrent users at time *t* seconds."""
        if t < 0 or t > self.duration_seconds:
            return 0

        if self.profile_type == ProfileType.STEADY:
            return self.max_users

        if self.profile_type == ProfileType.RAMP_UP:
            if self.ramp_up_seconds <= 0:
                return self.max_users
            ratio = min(t / self.ramp_up_seconds, 1.0)
            return max(1, int(ratio * self.max_users))

        if self.profile_type == ProfileType.SPIKE:
            # ramp → steady → spike → ramp-down → steady → end
            ramp_end = self.ramp_up_seconds
            spike_start = self.duration_seconds / 2
            spike_end = spike_start + self.ramp_down_seconds
            if t < ramp_end:
                ratio = t / ramp_end if ramp_end > 0 else 1.0
                return max(1, int(ratio * self.max_users))
            if spike_start <= t < spike_end:
                return self.max_users + self.spike_users
            return self.max_users

        if self.profile_type == ProfileType.SOAK:
            # instant to max, hold for full duration
            return self.max_users

        return self.max_users  # fallback

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def total_weight(self) -> float:
        return sum(r.weight for r in self.requests)

    def summary(self) -> str:
        return (
            f"Profile '{self.name}' ({self.profile_type.value}): "
            f"{self.max_users} users, {self.duration_seconds}s, "
            f"{len(self.requests)} request pattern(s)"
        )


# ------------------------------------------------------------------
# Factory helpers
# ------------------------------------------------------------------


def create_steady_profile(
    name: str,
    url: str,
    users: int = 10,
    duration: int = 60,
    think_time_ms: int = 0,
) -> LoadProfile:
    """Convenience: create a simple steady-state profile."""
    return LoadProfile(
        name=name,
        profile_type=ProfileType.STEADY,
        duration_seconds=duration,
        max_users=users,
        requests=[RequestPattern(url=url)],
        think_time_ms=think_time_ms,
    )


def create_ramp_profile(
    name: str,
    url: str,
    users: int = 50,
    duration: int = 120,
    ramp_up: int = 30,
) -> LoadProfile:
    """Convenience: create a ramp-up profile."""
    return LoadProfile(
        name=name,
        profile_type=ProfileType.RAMP_UP,
        duration_seconds=duration,
        max_users=users,
        ramp_up_seconds=ramp_up,
        requests=[RequestPattern(url=url)],
    )


def create_spike_profile(
    name: str,
    url: str,
    users: int = 20,
    spike_users: int = 80,
    duration: int = 120,
    ramp_up: int = 10,
    ramp_down: int = 10,
) -> LoadProfile:
    """Convenience: create a spike profile."""
    return LoadProfile(
        name=name,
        profile_type=ProfileType.SPIKE,
        duration_seconds=duration,
        max_users=users,
        spike_users=spike_users,
        ramp_up_seconds=ramp_up,
        ramp_down_seconds=ramp_down,
        requests=[RequestPattern(url=url)],
    )


def create_soak_profile(
    name: str,
    url: str,
    users: int = 10,
    duration: int = 3600,
) -> LoadProfile:
    """Convenience: create a long-running soak profile."""
    return LoadProfile(
        name=name,
        profile_type=ProfileType.SOAK,
        duration_seconds=duration,
        max_users=users,
        requests=[RequestPattern(url=url)],
    )
