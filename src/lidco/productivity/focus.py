"""Focus Mode — focus sessions, notification blocking, Pomodoro timer, break reminders."""

from __future__ import annotations

import datetime
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class FocusState(Enum):
    """Focus mode state."""

    IDLE = "idle"
    FOCUSED = "focused"
    BREAK = "break"
    PAUSED = "paused"


class PomodoroPhase(Enum):
    """Pomodoro cycle phase."""

    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


@dataclass(frozen=True)
class FocusConfig:
    """Configuration for a focus session."""

    work_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    cycles_before_long_break: int = 4
    block_notifications: bool = True
    block_distractions: bool = True
    auto_break_reminders: bool = True


@dataclass(frozen=True)
class FocusSession:
    """A focus session record."""

    session_id: str
    started_at: datetime.datetime
    ended_at: Optional[datetime.datetime] = None
    config: FocusConfig = field(default_factory=FocusConfig)
    completed_cycles: int = 0
    total_focus_seconds: float = 0.0

    def with_end(
        self,
        ended_at: datetime.datetime,
        completed_cycles: int,
        total_focus_seconds: float,
    ) -> FocusSession:
        """Return a new session with end data."""
        return FocusSession(
            session_id=self.session_id,
            started_at=self.started_at,
            ended_at=ended_at,
            config=self.config,
            completed_cycles=completed_cycles,
            total_focus_seconds=total_focus_seconds,
        )


@dataclass
class FocusStats:
    """Focus mode statistics."""

    total_sessions: int
    total_focus_seconds: float
    total_cycles: int
    avg_session_minutes: float


class FocusMode:
    """Manage focus sessions with Pomodoro support."""

    def __init__(self, config: Optional[FocusConfig] = None) -> None:
        self._config = config or FocusConfig()
        self._state = FocusState.IDLE
        self._current_session: Optional[FocusSession] = None
        self._history: List[FocusSession] = []
        self._cycle_count = 0
        self._phase = PomodoroPhase.WORK
        self._phase_start: Optional[datetime.datetime] = None
        self._total_focus: float = 0.0
        self._session_counter = 0
        self._blocked_notifications: List[str] = []
        self._on_break_reminder: Optional[Callable[[str], None]] = None
        self._on_phase_change: Optional[Callable[[PomodoroPhase], None]] = None

    @property
    def state(self) -> FocusState:
        """Return current focus state."""
        return self._state

    @property
    def phase(self) -> PomodoroPhase:
        """Return current Pomodoro phase."""
        return self._phase

    @property
    def current_session(self) -> Optional[FocusSession]:
        """Return current session."""
        return self._current_session

    @property
    def history(self) -> List[FocusSession]:
        """Return completed sessions."""
        return list(self._history)

    def set_break_reminder_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for break reminders."""
        self._on_break_reminder = callback

    def set_phase_change_callback(self, callback: Callable[[PomodoroPhase], None]) -> None:
        """Set callback for phase changes."""
        self._on_phase_change = callback

    def start(self, config: Optional[FocusConfig] = None) -> FocusSession:
        """Start a new focus session."""
        if self._state == FocusState.FOCUSED:
            raise ValueError("Already in focus mode. Stop current session first.")

        cfg = config or self._config
        self._config = cfg
        self._session_counter += 1
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        session = FocusSession(
            session_id=f"focus-{self._session_counter}",
            started_at=now,
            config=cfg,
        )
        self._current_session = session
        self._state = FocusState.FOCUSED
        self._phase = PomodoroPhase.WORK
        self._phase_start = now
        self._cycle_count = 0
        self._total_focus = 0.0

        if cfg.block_notifications:
            self._blocked_notifications.clear()

        return session

    def stop(self) -> Optional[FocusSession]:
        """Stop the current focus session."""
        if self._current_session is None:
            return None

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        if self._phase == PomodoroPhase.WORK and self._phase_start:
            self._total_focus += (now - self._phase_start).total_seconds()

        completed = self._current_session.with_end(
            ended_at=now,
            completed_cycles=self._cycle_count,
            total_focus_seconds=self._total_focus,
        )
        self._history.append(completed)
        self._current_session = None
        self._state = FocusState.IDLE
        self._phase_start = None
        return completed

    def pause(self) -> bool:
        """Pause the current session."""
        if self._state != FocusState.FOCUSED:
            return False
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        if self._phase == PomodoroPhase.WORK and self._phase_start:
            self._total_focus += (now - self._phase_start).total_seconds()
        self._state = FocusState.PAUSED
        self._phase_start = None
        return True

    def resume(self) -> bool:
        """Resume a paused session."""
        if self._state != FocusState.PAUSED:
            return False
        self._state = FocusState.FOCUSED
        self._phase_start = datetime.datetime.now(tz=datetime.timezone.utc)
        return True

    def complete_cycle(self) -> PomodoroPhase:
        """Complete current Pomodoro cycle and move to next phase."""
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        if self._phase == PomodoroPhase.WORK:
            if self._phase_start:
                self._total_focus += (now - self._phase_start).total_seconds()
            self._cycle_count += 1

            if self._cycle_count % self._config.cycles_before_long_break == 0:
                self._phase = PomodoroPhase.LONG_BREAK
            else:
                self._phase = PomodoroPhase.SHORT_BREAK

            self._state = FocusState.BREAK
            if self._on_break_reminder:
                msg = f"Time for a break! Completed cycle {self._cycle_count}."
                self._on_break_reminder(msg)
        else:
            self._phase = PomodoroPhase.WORK
            self._state = FocusState.FOCUSED

        self._phase_start = now
        if self._on_phase_change:
            self._on_phase_change(self._phase)

        return self._phase

    def remaining_seconds(self) -> float:
        """Return remaining seconds in current phase."""
        if self._phase_start is None:
            return 0.0
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        elapsed = (now - self._phase_start).total_seconds()
        if self._phase == PomodoroPhase.WORK:
            total = self._config.work_minutes * 60
        elif self._phase == PomodoroPhase.SHORT_BREAK:
            total = self._config.short_break_minutes * 60
        else:
            total = self._config.long_break_minutes * 60
        return max(0.0, total - elapsed)

    def block_notification(self, source: str) -> bool:
        """Block a notification during focus mode."""
        if self._state not in (FocusState.FOCUSED, FocusState.BREAK):
            return False
        if not self._config.block_notifications:
            return False
        self._blocked_notifications.append(source)
        return True

    @property
    def blocked_notifications(self) -> List[str]:
        """Return list of blocked notification sources."""
        return list(self._blocked_notifications)

    def stats(self) -> FocusStats:
        """Return focus statistics."""
        total_sessions = len(self._history)
        total_focus = sum(s.total_focus_seconds for s in self._history)
        total_cycles = sum(s.completed_cycles for s in self._history)
        avg = (total_focus / total_sessions / 60) if total_sessions > 0 else 0.0
        return FocusStats(
            total_sessions=total_sessions,
            total_focus_seconds=total_focus,
            total_cycles=total_cycles,
            avg_session_minutes=avg,
        )
