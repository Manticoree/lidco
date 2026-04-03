"""Ring buffer for string tokens with configurable overflow policy."""
from __future__ import annotations

import enum


class OverflowPolicy(enum.Enum):
    """What to do when the buffer is full."""

    DROP_OLDEST = "drop_oldest"
    BLOCK = "block"
    ERROR = "error"


class BufferOverflowError(Exception):
    """Raised when the buffer is full and overflow policy is ERROR."""


class StreamBuffer:
    """Fixed-capacity ring buffer for streaming string tokens.

    Parameters
    ----------
    capacity:
        Maximum number of tokens the buffer can hold.
    overflow_policy:
        Behaviour when a write is attempted on a full buffer.
    """

    def __init__(
        self,
        *,
        capacity: int = 10000,
        overflow_policy: OverflowPolicy | str = OverflowPolicy.DROP_OLDEST,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")

        if isinstance(overflow_policy, str):
            overflow_policy = OverflowPolicy(overflow_policy)

        self._capacity = capacity
        self._overflow_policy = overflow_policy

        # Ring buffer internals
        self._buf: list[str | None] = [None] * capacity
        self._head = 0  # next write position
        self._tail = 0  # next read position
        self._count = 0

        # Stats
        self._overflow_count = 0
        self._total_written = 0
        self._total_read = 0

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(self, token: str) -> bool:
        """Append *token* to the buffer.

        Returns
        -------
        bool
            ``True`` on success, ``False`` when the policy is BLOCK and the
            buffer is full.

        Raises
        ------
        BufferOverflowError
            When the buffer is full and the policy is ERROR.
        """
        if self._count >= self._capacity:
            if self._overflow_policy is OverflowPolicy.DROP_OLDEST:
                # Advance tail (discard oldest)
                self._tail = (self._tail + 1) % self._capacity
                self._count -= 1
                self._overflow_count += 1
            elif self._overflow_policy is OverflowPolicy.BLOCK:
                return False
            else:  # ERROR
                self._overflow_count += 1
                raise BufferOverflowError("Stream buffer is full")

        self._buf[self._head] = token
        self._head = (self._head + 1) % self._capacity
        self._count += 1
        self._total_written += 1
        return True

    # ------------------------------------------------------------------
    # Read / Peek / Drain
    # ------------------------------------------------------------------

    def read(self, count: int = 1) -> list[str]:
        """Consume and return up to *count* tokens from the buffer."""
        actual = min(count, self._count)
        result: list[str] = []
        for _ in range(actual):
            token = self._buf[self._tail]
            self._buf[self._tail] = None
            self._tail = (self._tail + 1) % self._capacity
            self._count -= 1
            self._total_read += 1
            if token is not None:
                result.append(token)
        return result

    def drain(self) -> list[str]:
        """Read and return all tokens currently in the buffer."""
        return self.read(self._count)

    def peek(self, count: int = 1) -> list[str]:
        """Return up to *count* tokens without consuming them."""
        actual = min(count, self._count)
        result: list[str] = []
        idx = self._tail
        for _ in range(actual):
            token = self._buf[idx]
            if token is not None:
                result.append(token)
            idx = (idx + 1) % self._capacity
        return result

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """Number of tokens currently in the buffer."""
        return self._count

    @property
    def is_full(self) -> bool:
        """``True`` when the buffer has reached capacity."""
        return self._count >= self._capacity

    @property
    def is_empty(self) -> bool:
        """``True`` when the buffer contains no tokens."""
        return self._count == 0

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return buffer statistics."""
        return {
            "capacity": self._capacity,
            "used": self._count,
            "overflow_count": self._overflow_count,
            "total_written": self._total_written,
            "total_read": self._total_read,
            "overflow_policy": self._overflow_policy.value,
        }
