"""Tests for lidco.multimodal.transcriber."""
from __future__ import annotations

import unittest

from lidco.multimodal.transcriber import (
    ActionItem,
    AudioTranscriber,
    SpeakerInfo,
    Transcript,
    TranscriptSegment,
)


class TestAudioTranscriber(unittest.TestCase):
    def setUp(self):
        self.transcriber = AudioTranscriber()

    # -- transcribe -------------------------------------------------------

    def test_transcribe_wav(self):
        t = self.transcriber.transcribe("meeting.wav")
        self.assertIsInstance(t, Transcript)
        self.assertEqual(t.path, "meeting.wav")
        self.assertGreater(len(t.segments), 0)
        self.assertGreater(t.duration, 0)

    def test_transcribe_mp3(self):
        t = self.transcriber.transcribe("audio.mp3")
        self.assertIsInstance(t, Transcript)
        self.assertEqual(t.language, "en")

    def test_transcribe_empty_path_raises(self):
        with self.assertRaises(ValueError):
            self.transcriber.transcribe("")

    def test_transcribe_unsupported_format(self):
        with self.assertRaises(ValueError):
            self.transcriber.transcribe("file.txt")

    def test_transcribe_full_text(self):
        t = self.transcriber.transcribe("call.wav")
        self.assertIsInstance(t.full_text, str)
        self.assertGreater(len(t.full_text), 0)

    def test_transcribe_segments_ordered(self):
        t = self.transcriber.transcribe("x.ogg")
        for i in range(1, len(t.segments)):
            self.assertGreaterEqual(t.segments[i].start_time, t.segments[i - 1].start_time)

    def test_transcribe_custom_language(self):
        tr = AudioTranscriber(language="fr")
        t = tr.transcribe("french.mp3")
        self.assertEqual(t.language, "fr")

    def test_transcribe_supported_formats(self):
        for ext in (".wav", ".mp3", ".ogg", ".m4a", ".flac", ".webm"):
            t = self.transcriber.transcribe(f"file{ext}")
            self.assertIsInstance(t, Transcript)

    # -- extract_action_items ---------------------------------------------

    def test_extract_action_items(self):
        t = self.transcriber.transcribe("meeting.wav")
        items = self.transcriber.extract_action_items(t)
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        self.assertIsInstance(items[0], ActionItem)

    def test_action_items_have_assignee(self):
        t = self.transcriber.transcribe("standup.mp3")
        items = self.transcriber.extract_action_items(t)
        for item in items:
            self.assertTrue(item.assignee)

    def test_action_item_priority(self):
        seg = TranscriptSegment(speaker="Alice", text="We must fix the critical bug.", start_time=0, end_time=3)
        t = Transcript(path="x.wav", segments=[seg])
        items = self.transcriber.extract_action_items(t)
        self.assertTrue(any(i.priority == "high" for i in items))

    # -- detect_speakers --------------------------------------------------

    def test_detect_speakers(self):
        t = self.transcriber.transcribe("call.wav")
        speakers = self.transcriber.detect_speakers(t)
        self.assertIsInstance(speakers, list)
        self.assertGreater(len(speakers), 0)
        self.assertIsInstance(speakers[0], SpeakerInfo)

    def test_detect_speakers_unique(self):
        t = self.transcriber.transcribe("panel.flac")
        speakers = self.transcriber.detect_speakers(t)
        ids = [s.speaker_id for s in speakers]
        self.assertEqual(len(ids), len(set(ids)))

    def test_detect_speakers_duration(self):
        t = self.transcriber.transcribe("talk.m4a")
        speakers = self.transcriber.detect_speakers(t)
        for spk in speakers:
            self.assertGreater(spk.total_duration, 0)


if __name__ == "__main__":
    unittest.main()
