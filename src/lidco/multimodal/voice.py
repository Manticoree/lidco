"""Voice input — speech-to-text via sounddevice/whisper or WAV file fallback."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

# Optional deps
try:
    import sounddevice as sd  # type: ignore[import]
    import numpy as np  # type: ignore[import]
    _HAS_SOUNDDEVICE = True
except ImportError:
    _HAS_SOUNDDEVICE = False

try:
    import whisper as _whisper  # type: ignore[import]
    _HAS_WHISPER = True
except ImportError:
    _HAS_WHISPER = False

_SAMPLE_RATE = 16_000  # Hz expected by Whisper


class VoiceRecorder:
    """Records audio from microphone or accepts a WAV file path."""

    def __init__(self, sample_rate: int = _SAMPLE_RATE) -> None:
        self._sample_rate = sample_rate

    def record(self, duration_s: int = 10) -> bytes:
        """Record *duration_s* seconds of audio, return raw PCM bytes.

        Raises RuntimeError if sounddevice is not installed.
        """
        if not _HAS_SOUNDDEVICE:
            raise RuntimeError(
                "sounddevice is not installed. "
                "Install it with: pip install sounddevice numpy\n"
                "Or use VoiceRecorder.from_wav(path) to transcribe a WAV file."
            )
        audio: Any = sd.rec(
            int(duration_s * self._sample_rate),
            samplerate=self._sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()
        return audio.tobytes()

    @staticmethod
    def from_wav(path: str | Path) -> bytes:
        """Read audio bytes from a WAV file."""
        return Path(path).read_bytes()


class WhisperTranscriber:
    """Transcribes audio using local openai-whisper or the OpenAI Whisper API."""

    def __init__(self, model: str = "base", api_key: str | None = None) -> None:
        self._model_name = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._local_model: Any = None

    def _load_local(self) -> Any:
        if not _HAS_WHISPER:
            raise RuntimeError(
                "openai-whisper is not installed. "
                "Install it with: pip install openai-whisper\n"
                "Alternatively set OPENAI_API_KEY to use the Whisper API."
            )
        if self._local_model is None:
            self._local_model = _whisper.load_model(self._model_name)
        return self._local_model

    def transcribe_bytes(self, audio_bytes: bytes) -> str:
        """Transcribe raw PCM audio bytes, returning the text."""
        if _HAS_WHISPER:
            import tempfile
            import wave

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                with wave.open(tmp_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # int16
                    wf.setframerate(_SAMPLE_RATE)
                    wf.writeframes(audio_bytes)
                model = self._load_local()
                result: dict = model.transcribe(tmp_path)
                return result.get("text", "").strip()
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        # Fallback: OpenAI Whisper API
        if not self._api_key:
            raise RuntimeError(
                "No transcription backend available. "
                "Install openai-whisper (pip install openai-whisper) "
                "or set OPENAI_API_KEY for the remote API."
            )
        try:
            import openai  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Run: pip install openai"
            ) from exc

        client = openai.OpenAI(api_key=self._api_key)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"
        response = client.audio.transcriptions.create(
            model="whisper-1", file=audio_file
        )
        return response.text.strip()

    def transcribe_file(self, path: str | Path) -> str:
        """Transcribe a WAV file by path."""
        return self.transcribe_bytes(VoiceRecorder.from_wav(path))


class VoiceInput:
    """High-level voice capture + transcription pipeline."""

    def __init__(
        self,
        model: str = "base",
        api_key: str | None = None,
    ) -> None:
        self._recorder = VoiceRecorder()
        self._transcriber = WhisperTranscriber(model=model, api_key=api_key)

    def capture_and_transcribe(self, timeout_s: int = 10) -> str:
        """Record *timeout_s* seconds and return transcribed text.

        If sounddevice is unavailable, raises RuntimeError with install guidance.
        """
        audio = self._recorder.record(duration_s=timeout_s)
        return self._transcriber.transcribe_bytes(audio)

    def transcribe_file(self, path: str | Path) -> str:
        """Transcribe an existing audio file."""
        return self._transcriber.transcribe_file(path)
