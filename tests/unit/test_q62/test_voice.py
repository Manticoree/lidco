"""Tests for VoiceInput — Q62 Task 417."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


class TestVoiceRecorderGracefulDegradation:
    def test_record_raises_without_sounddevice(self):
        """VoiceRecorder.record() raises RuntimeError when sounddevice is missing."""
        with patch("lidco.multimodal.voice._HAS_SOUNDDEVICE", False):
            from lidco.multimodal.voice import VoiceRecorder
            recorder = VoiceRecorder()
            with pytest.raises(RuntimeError, match="sounddevice"):
                recorder.record(duration_s=1)

    def test_from_wav_reads_bytes(self, tmp_path):
        """VoiceRecorder.from_wav() reads bytes from a WAV file."""
        from lidco.multimodal.voice import VoiceRecorder
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFFWAVE")
        data = VoiceRecorder.from_wav(wav)
        assert data == b"RIFFWAVE"


class TestWhisperTranscriberGracefulDegradation:
    def test_transcribe_without_whisper_or_key_raises(self):
        """Raises RuntimeError when neither whisper nor API key is available."""
        with patch("lidco.multimodal.voice._HAS_WHISPER", False):
            from lidco.multimodal.voice import WhisperTranscriber
            transcriber = WhisperTranscriber(model="base", api_key=None)
            # Patching env to ensure no key
            with patch.dict("os.environ", {}, clear=False):
                import os
                old = os.environ.pop("OPENAI_API_KEY", None)
                try:
                    with pytest.raises(RuntimeError):
                        transcriber.transcribe_bytes(b"\x00" * 100)
                finally:
                    if old is not None:
                        os.environ["OPENAI_API_KEY"] = old

    def test_transcriber_init_uses_env_key(self, monkeypatch):
        """WhisperTranscriber picks up OPENAI_API_KEY from env."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
        with patch("lidco.multimodal.voice._HAS_WHISPER", False):
            from lidco.multimodal.voice import WhisperTranscriber
            t = WhisperTranscriber()
            assert t._api_key == "test-key-123"


class TestVoiceInputInterface:
    def test_voice_input_has_capture_and_transcribe(self):
        """VoiceInput exposes capture_and_transcribe and transcribe_file."""
        from lidco.multimodal.voice import VoiceInput
        vi = VoiceInput()
        assert hasattr(vi, "capture_and_transcribe")
        assert hasattr(vi, "transcribe_file")

    def test_voice_input_capture_raises_without_sounddevice(self):
        """capture_and_transcribe raises RuntimeError if sounddevice absent."""
        with patch("lidco.multimodal.voice._HAS_SOUNDDEVICE", False):
            from lidco.multimodal.voice import VoiceInput
            vi = VoiceInput()
            with pytest.raises(RuntimeError):
                vi.capture_and_transcribe(timeout_s=1)

    def test_voice_input_transcribe_file(self, tmp_path):
        """transcribe_file delegates to WhisperTranscriber."""
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"RIFF" + b"\x00" * 100)
        from lidco.multimodal.voice import VoiceInput
        vi = VoiceInput()
        with patch.object(vi._transcriber, "transcribe_bytes", return_value="hello"):
            result = vi.transcribe_file(wav)
        assert result == "hello"

    def test_has_sounddevice_flag(self):
        """Module exposes _HAS_SOUNDDEVICE flag."""
        import lidco.multimodal.voice as m
        assert hasattr(m, "_HAS_SOUNDDEVICE")

    def test_has_whisper_flag(self):
        """Module exposes _HAS_WHISPER flag."""
        import lidco.multimodal.voice as m
        assert hasattr(m, "_HAS_WHISPER")

    def test_voice_recorder_sample_rate_default(self):
        """VoiceRecorder uses 16000 Hz by default."""
        from lidco.multimodal.voice import VoiceRecorder, _SAMPLE_RATE
        recorder = VoiceRecorder()
        assert recorder._sample_rate == _SAMPLE_RATE
        assert _SAMPLE_RATE == 16_000

    def test_voice_input_model_passed_to_transcriber(self):
        """VoiceInput passes model to WhisperTranscriber."""
        from lidco.multimodal.voice import VoiceInput
        vi = VoiceInput(model="small")
        assert vi._transcriber._model_name == "small"
