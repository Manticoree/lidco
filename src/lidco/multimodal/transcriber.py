"""Audio transcription module — simulated voice transcription.

AudioTranscriber provides simulated speech-to-text, action-item extraction,
and speaker diarisation capabilities.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TranscriptSegment:
    """A single segment within a transcript."""

    speaker: str
    text: str
    start_time: float
    end_time: float


@dataclass
class Transcript:
    """Full transcription result."""

    path: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    duration: float = 0.0
    language: str = "en"

    @property
    def full_text(self) -> str:
        return " ".join(seg.text for seg in self.segments)


@dataclass(frozen=True)
class ActionItem:
    """Action item extracted from a transcript."""

    text: str
    assignee: str = ""
    priority: str = "medium"
    source_segment: int = 0


@dataclass(frozen=True)
class SpeakerInfo:
    """Detected speaker information."""

    speaker_id: str
    label: str
    segment_count: int
    total_duration: float


class AudioTranscriber:
    """Simulated audio transcription engine."""

    def __init__(self, *, language: str = "en") -> None:
        self._language = language

    def transcribe(self, path: str) -> Transcript:
        """Transcribe an audio file (simulated)."""
        if not path:
            raise ValueError("path must not be empty")
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".wav", ".mp3", ".ogg", ".m4a", ".flac", ".webm"):
            raise ValueError(f"unsupported audio format: {ext or 'none'}")

        # Simulate transcription based on file name
        base = os.path.splitext(os.path.basename(path))[0]
        segments = self._simulate_segments(base)
        duration = segments[-1].end_time if segments else 0.0
        return Transcript(
            path=path,
            segments=segments,
            duration=duration,
            language=self._language,
        )

    def extract_action_items(self, transcript: Transcript) -> list[ActionItem]:
        """Extract action items from a transcript."""
        items: list[ActionItem] = []
        action_patterns = [
            re.compile(r"(?:need to|should|must|will|please)\s+(.+)", re.IGNORECASE),
            re.compile(r"(?:action item|todo|task):\s*(.+)", re.IGNORECASE),
        ]
        for idx, seg in enumerate(transcript.segments):
            for pattern in action_patterns:
                match = pattern.search(seg.text)
                if match:
                    items.append(ActionItem(
                        text=match.group(1).strip().rstrip("."),
                        assignee=seg.speaker,
                        priority="high" if "must" in seg.text.lower() else "medium",
                        source_segment=idx,
                    ))
                    break
        return items

    def detect_speakers(self, transcript: Transcript) -> list[SpeakerInfo]:
        """Detect unique speakers in a transcript."""
        speaker_map: dict[str, dict[str, Any]] = {}
        for seg in transcript.segments:
            if seg.speaker not in speaker_map:
                speaker_map[seg.speaker] = {"count": 0, "duration": 0.0}
            speaker_map[seg.speaker]["count"] += 1
            speaker_map[seg.speaker]["duration"] += seg.end_time - seg.start_time
        return [
            SpeakerInfo(
                speaker_id=spk,
                label=spk,
                segment_count=info["count"],
                total_duration=round(info["duration"], 2),
            )
            for spk, info in speaker_map.items()
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _simulate_segments(name: str) -> list[TranscriptSegment]:
        """Generate simulated transcript segments."""
        sentences = [
            "Hello, let's discuss the project status.",
            "We need to complete the API integration by Friday.",
            "Action item: review the security audit report.",
            "I will update the documentation tomorrow.",
            "Let's schedule a follow-up meeting next week.",
        ]
        speakers = ["Speaker A", "Speaker B"]
        segments: list[TranscriptSegment] = []
        t = 0.0
        for i, text in enumerate(sentences):
            duration = 2.0 + len(text) * 0.05
            segments.append(TranscriptSegment(
                speaker=speakers[i % len(speakers)],
                text=text,
                start_time=round(t, 2),
                end_time=round(t + duration, 2),
            ))
            t += duration + 0.5
        return segments
