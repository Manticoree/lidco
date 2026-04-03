"""SecretRotator — automated rotation with provider handlers and scheduling."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RotationResult:
    """Result of a single rotation attempt."""

    secret_name: str
    provider: str
    old_prefix: str
    new_prefix: str
    rotated_at: float
    success: bool
    error: str | None = None


@runtime_checkable
class RotationHandler(Protocol):
    """Provider-specific rotation logic."""

    def rotate(self, secret_name: str, current_value: str) -> tuple[str, str | None]:
        """Return (new_value, error_or_none)."""
        ...


class SecretRotator:
    """Manage secret rotation via pluggable handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, RotationHandler] = {}
        self._history: list[RotationResult] = []
        self._schedules: dict[str, dict] = {}  # name -> schedule info

    def register_handler(self, provider: str, handler: RotationHandler) -> None:
        """Register a rotation handler for *provider*."""
        self._handlers[provider] = handler

    def rotate(self, secret_name: str, provider: str, current_value: str) -> RotationResult:
        """Rotate a secret using the registered handler for *provider*."""
        handler = self._handlers.get(provider)
        if handler is None:
            result = RotationResult(
                secret_name=secret_name,
                provider=provider,
                old_prefix=current_value[:8] if len(current_value) >= 8 else current_value,
                new_prefix="",
                rotated_at=time.time(),
                success=False,
                error=f"No handler registered for provider '{provider}'",
            )
            self._history.append(result)
            return result

        try:
            new_value, error = handler.rotate(secret_name, current_value)
        except Exception as exc:
            result = RotationResult(
                secret_name=secret_name,
                provider=provider,
                old_prefix=current_value[:8] if len(current_value) >= 8 else current_value,
                new_prefix="",
                rotated_at=time.time(),
                success=False,
                error=str(exc),
            )
            self._history.append(result)
            return result

        if error is not None:
            result = RotationResult(
                secret_name=secret_name,
                provider=provider,
                old_prefix=current_value[:8] if len(current_value) >= 8 else current_value,
                new_prefix="",
                rotated_at=time.time(),
                success=False,
                error=error,
            )
        else:
            result = RotationResult(
                secret_name=secret_name,
                provider=provider,
                old_prefix=current_value[:8] if len(current_value) >= 8 else current_value,
                new_prefix=new_value[:8] if len(new_value) >= 8 else new_value,
                rotated_at=time.time(),
                success=True,
            )
        self._history.append(result)
        return result

    def schedule_rotation(self, secret_name: str, provider: str, interval_days: int) -> dict:
        """Schedule a recurring rotation for *secret_name*."""
        entry = {
            "id": uuid.uuid4().hex[:12],
            "secret_name": secret_name,
            "provider": provider,
            "interval_days": interval_days,
            "created_at": time.time(),
            "next_rotation": time.time() + interval_days * 86400,
        }
        self._schedules[secret_name] = entry
        return entry

    def pending_rotations(self) -> list[dict]:
        """Return schedules whose next_rotation is in the past."""
        now = time.time()
        return [s for s in self._schedules.values() if s["next_rotation"] <= now]

    def history(self, secret_name: str | None = None) -> list[RotationResult]:
        """Return rotation history, optionally filtered by *secret_name*."""
        if secret_name is None:
            return list(self._history)
        return [r for r in self._history if r.secret_name == secret_name]

    def providers(self) -> list[str]:
        """Return registered provider names."""
        return sorted(self._handlers.keys())

    def summary(self) -> dict:
        """Return rotator statistics."""
        successful = sum(1 for r in self._history if r.success)
        failed = len(self._history) - successful
        return {
            "providers": len(self._handlers),
            "schedules": len(self._schedules),
            "total_rotations": len(self._history),
            "successful": successful,
            "failed": failed,
        }
