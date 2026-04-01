"""Inline code review with comment threads and suggestion application."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import hashlib
import time


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    MERGED = "merged"


@dataclass(frozen=True)
class CommentThread:
    id: str
    file_path: str
    line: int
    author: str
    body: str
    created_at: float = field(default_factory=time.time)
    resolved: bool = False
    replies: tuple = ()


@dataclass(frozen=True)
class ReviewSuggestion:
    id: str
    file_path: str
    line: int
    original: str
    replacement: str
    author: str
    applied: bool = False


_counter = 0


def _next_id(prefix: str) -> str:
    global _counter
    _counter += 1
    return f"{prefix}_{_counter}"


class ReviewIntegration:
    """Inline code review with comment threads and suggestions."""

    def __init__(self) -> None:
        self._threads: list[CommentThread] = []
        self._suggestions: list[ReviewSuggestion] = []
        self._status: ReviewStatus = ReviewStatus.PENDING

    def add_comment(
        self, file_path: str, line: int, author: str, body: str
    ) -> CommentThread:
        thread = CommentThread(
            id=_next_id("thread"),
            file_path=file_path,
            line=line,
            author=author,
            body=body,
        )
        self._threads = [*self._threads, thread]
        return thread

    def reply_to(self, thread_id: str, author: str, body: str) -> CommentThread | None:
        for i, t in enumerate(self._threads):
            if t.id == thread_id:
                reply = CommentThread(
                    id=_next_id("reply"),
                    file_path=t.file_path,
                    line=t.line,
                    author=author,
                    body=body,
                )
                updated = CommentThread(
                    id=t.id,
                    file_path=t.file_path,
                    line=t.line,
                    author=t.author,
                    body=t.body,
                    created_at=t.created_at,
                    resolved=t.resolved,
                    replies=(*t.replies, reply),
                )
                self._threads = [
                    *self._threads[:i], updated, *self._threads[i + 1:]
                ]
                return updated
        return None

    def resolve_thread(self, thread_id: str) -> bool:
        for i, t in enumerate(self._threads):
            if t.id == thread_id:
                updated = CommentThread(
                    id=t.id,
                    file_path=t.file_path,
                    line=t.line,
                    author=t.author,
                    body=t.body,
                    created_at=t.created_at,
                    resolved=True,
                    replies=t.replies,
                )
                self._threads = [
                    *self._threads[:i], updated, *self._threads[i + 1:]
                ]
                return True
        return False

    def add_suggestion(
        self,
        file_path: str,
        line: int,
        original: str,
        replacement: str,
        author: str,
    ) -> ReviewSuggestion:
        suggestion = ReviewSuggestion(
            id=_next_id("sugg"),
            file_path=file_path,
            line=line,
            original=original,
            replacement=replacement,
            author=author,
        )
        self._suggestions = [*self._suggestions, suggestion]
        return suggestion

    def apply_suggestion(self, suggestion_id: str) -> bool:
        for i, s in enumerate(self._suggestions):
            if s.id == suggestion_id:
                updated = ReviewSuggestion(
                    id=s.id,
                    file_path=s.file_path,
                    line=s.line,
                    original=s.original,
                    replacement=s.replacement,
                    author=s.author,
                    applied=True,
                )
                self._suggestions = [
                    *self._suggestions[:i], updated, *self._suggestions[i + 1:]
                ]
                return True
        return False

    def approve(self) -> None:
        self._status = ReviewStatus.APPROVED

    def request_changes(self) -> None:
        self._status = ReviewStatus.CHANGES_REQUESTED

    def get_threads(self, file_path: str | None = None) -> list[CommentThread]:
        if file_path is None:
            return list(self._threads)
        return [t for t in self._threads if t.file_path == file_path]

    def get_suggestions(self, applied: bool | None = None) -> list[ReviewSuggestion]:
        if applied is None:
            return list(self._suggestions)
        return [s for s in self._suggestions if s.applied == applied]

    def summary(self) -> str:
        resolved = sum(1 for t in self._threads if t.resolved)
        applied = sum(1 for s in self._suggestions if s.applied)
        lines = [
            f"Review status: {self._status.value}",
            f"Threads: {len(self._threads)} ({resolved} resolved)",
            f"Suggestions: {len(self._suggestions)} ({applied} applied)",
        ]
        return "\n".join(lines)
