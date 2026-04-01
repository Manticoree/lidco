"""Chunked transfer protocol with checksum verification."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib


@dataclass(frozen=True)
class Chunk:
    """One piece of a chunked transfer."""

    index: int
    data: str
    checksum: str = ""
    total_chunks: int = 0


@dataclass(frozen=True)
class TransferSession:
    """Tracks progress of an ongoing chunked transfer."""

    id: str
    total_chunks: int = 0
    received: int = 0
    complete: bool = False
    checksum: str = ""


def _chunk_checksum(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


class TransferProtocol:
    """Split, reassemble, and verify chunked transfers."""

    def __init__(self, chunk_size: int = 4096) -> None:
        self._chunk_size = max(chunk_size, 1)

    def split(self, data: str) -> list[Chunk]:
        """Split *data* into chunks with per-chunk checksums."""
        if not data:
            return []
        parts: list[str] = []
        for i in range(0, len(data), self._chunk_size):
            parts.append(data[i : i + self._chunk_size])
        total = len(parts)
        return [
            Chunk(
                index=idx,
                data=part,
                checksum=_chunk_checksum(part),
                total_chunks=total,
            )
            for idx, part in enumerate(parts)
        ]

    def reassemble(self, chunks: list[Chunk]) -> str | None:
        """Reassemble chunks into original string.

        Returns *None* if any chunk fails checksum verification or
        chunks are incomplete.
        """
        if not chunks:
            return None
        total = chunks[0].total_chunks
        if len(chunks) != total:
            return None
        sorted_chunks = sorted(chunks, key=lambda c: c.index)
        for ch in sorted_chunks:
            if not self.verify_chunk(ch):
                return None
        return "".join(ch.data for ch in sorted_chunks)

    def verify_chunk(self, chunk: Chunk) -> bool:
        """Return True if chunk checksum is valid."""
        if not chunk.checksum:
            return True
        return _chunk_checksum(chunk.data) == chunk.checksum

    def create_session(self, total_chunks: int) -> TransferSession:
        """Create a new transfer session descriptor."""
        sid = hashlib.sha256(str(total_chunks).encode()).hexdigest()[:16]
        return TransferSession(
            id=sid,
            total_chunks=total_chunks,
            received=0,
            complete=total_chunks == 0,
        )

    def progress(self, session: TransferSession) -> float:
        """Return completion progress from 0.0 to 1.0."""
        if session.total_chunks <= 0:
            return 1.0
        return min(session.received / session.total_chunks, 1.0)

    def summary(self) -> str:
        """Protocol configuration summary."""
        return f"TransferProtocol(chunk_size={self._chunk_size})"
