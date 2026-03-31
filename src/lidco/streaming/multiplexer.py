"""Stream multiplexer — merge multiple named streams into one timeline."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class StreamEntry:
    """A single entry written to a multiplexed stream."""

    content: str
    stream_name: str
    timestamp: float
    sequence: int


class StreamMultiplexer:
    """Multiplex writes from several named streams into a unified timeline."""

    def __init__(self) -> None:
        self._streams: dict[str, list[StreamEntry]] = {}
        self._all: list[StreamEntry] = []
        self._seq: int = 0

    # ------------------------------------------------------------------
    # Stream management
    # ------------------------------------------------------------------

    def add_stream(self, name: str) -> None:
        """Register a named stream."""
        if name not in self._streams:
            self._streams[name] = []

    def remove_stream(self, name: str) -> None:
        """Remove a named stream (entries already written are kept)."""
        self._streams.pop(name, None)

    @property
    def stream_names(self) -> list[str]:
        """Names of currently registered streams."""
        return list(self._streams.keys())

    # ------------------------------------------------------------------
    # Write / read
    # ------------------------------------------------------------------

    def write(self, stream_name: str, content: str) -> None:
        """Write *content* to the stream *stream_name*.

        Raises :class:`KeyError` if the stream has not been added.
        """
        if stream_name not in self._streams:
            raise KeyError(f"Unknown stream: {stream_name!r}")
        self._seq += 1
        entry = StreamEntry(
            content=content,
            stream_name=stream_name,
            timestamp=time.time(),
            sequence=self._seq,
        )
        self._streams[stream_name].append(entry)
        self._all.append(entry)

    def read_all(self, since_sequence: int = 0) -> list[StreamEntry]:
        """Return entries across all streams with ``sequence > since_sequence``."""
        return [e for e in self._all if e.sequence > since_sequence]

    def read_stream(self, name: str) -> list[StreamEntry]:
        """Return all entries for a single stream."""
        return list(self._streams.get(name, []))

    @property
    def total_entries(self) -> int:
        """Total number of entries across all streams."""
        return len(self._all)
