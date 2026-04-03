"""Flow controller that coordinates producers and consumers.

Bridges a :class:`BackpressureController` with a :class:`StreamBuffer` so
that producers receive backpressure signals and consumers can drain at a
sustainable pace.
"""
from __future__ import annotations

from lidco.streaming.backpressure import BackpressureController, BackpressureState
from lidco.streaming.stream_buffer import StreamBuffer


class FlowController:
    """Coordinate a producer–consumer pipeline with backpressure.

    Parameters
    ----------
    backpressure:
        An existing :class:`BackpressureController`, or ``None`` to create a
        default instance.
    buffer:
        An existing :class:`StreamBuffer`, or ``None`` to create a default
        instance.
    """

    def __init__(
        self,
        *,
        backpressure: BackpressureController | None = None,
        buffer: StreamBuffer | None = None,
    ) -> None:
        self._backpressure = backpressure or BackpressureController()
        self._buffer = buffer or StreamBuffer()
        self._produce_count = 0
        self._consume_count = 0
        self._rejected_count = 0

    # ------------------------------------------------------------------
    # Producer side
    # ------------------------------------------------------------------

    def produce(self, token: str) -> bool:
        """Write *token* to the buffer and check backpressure.

        Returns ``True`` if the token was accepted, ``False`` when
        backpressure is active and the buffer refused the write.
        """
        if self._backpressure.is_paused:
            self._rejected_count += 1
            return False

        ok = self._buffer.write(token)
        if not ok:
            self._rejected_count += 1
            return False

        self._produce_count += 1

        # Evaluate backpressure after the write
        self._backpressure.check(self._buffer.size)
        return True

    # ------------------------------------------------------------------
    # Consumer side
    # ------------------------------------------------------------------

    def consume(self, count: int = 1) -> list[str]:
        """Read up to *count* tokens from the buffer.

        After reading, backpressure is re-evaluated so a paused producer
        can be resumed.
        """
        tokens = self._buffer.read(count)
        self._consume_count += len(tokens)

        # Re-evaluate after consuming — may trigger resume
        self._backpressure.check(self._buffer.size)
        return tokens

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def is_congested(self) -> bool:
        """``True`` when the backpressure controller is paused."""
        return self._backpressure.is_paused

    def adaptive_rate(self) -> float:
        """Suggest a producer rate based on current buffer fill.

        Returns a multiplier in the range ``[0.1, 1.0]`` where ``1.0`` means
        the buffer is nearly empty (produce at full speed) and ``0.1`` means
        the buffer is nearly full (slow down significantly).
        """
        bp_stats = self._backpressure.stats()
        buf_stats = self._buffer.stats()
        capacity = buf_stats["capacity"]
        used = buf_stats["used"]

        if capacity == 0:
            return 1.0

        fill = used / capacity
        # Linear mapping: fill 0 -> rate 1.0, fill 1 -> rate 0.1
        rate = max(0.1, 1.0 - 0.9 * fill)
        return round(rate, 4)

    def stats(self) -> dict:
        """Return combined backpressure and buffer statistics."""
        return {
            "backpressure": self._backpressure.stats(),
            "buffer": self._buffer.stats(),
            "produce_count": self._produce_count,
            "consume_count": self._consume_count,
            "rejected_count": self._rejected_count,
            "is_congested": self.is_congested,
            "adaptive_rate": self.adaptive_rate(),
        }
