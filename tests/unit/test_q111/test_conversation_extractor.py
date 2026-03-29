"""Tests for src/lidco/memory/conversation_extractor.py."""
from lidco.memory.conversation_extractor import (
    ConversationMemoryExtractor,
    ExtractedFact,
    _extract_tags,
    _split_sentences,
)


class TestExtractedFact:
    def test_to_dict(self):
        f = ExtractedFact(content="use python", confidence=0.7, tags=["python"], source_turn=0)
        d = f.to_dict()
        assert d["content"] == "use python"
        assert d["confidence"] == 0.7
        assert d["tags"] == ["python"]
        assert d["source_turn"] == 0

    def test_from_dict(self):
        d = {"content": "use python", "confidence": 0.8, "tags": ["python"], "source_turn": 1}
        f = ExtractedFact.from_dict(d)
        assert f.content == "use python"
        assert f.confidence == 0.8
        assert f.source_turn == 1

    def test_from_dict_minimal(self):
        d = {"content": "x", "confidence": 0.5}
        f = ExtractedFact.from_dict(d)
        assert f.tags == []
        assert f.source_turn == 0

    def test_default_fields(self):
        f = ExtractedFact(content="hello", confidence=0.5)
        assert f.tags == []
        assert f.source_turn == 0


class TestHelpers:
    def test_extract_tags_python(self):
        tags = _extract_tags("We use Python and Django for the backend")
        assert "python" in tags
        assert "django" in tags
        assert "backend" in tags

    def test_extract_tags_empty(self):
        assert _extract_tags("") == []

    def test_extract_tags_no_match(self):
        assert _extract_tags("hello world nothing here") == []

    def test_split_sentences_basic(self):
        result = _split_sentences("First sentence. Second sentence.")
        assert len(result) == 2

    def test_split_sentences_empty(self):
        assert _split_sentences("") == []


class TestConversationMemoryExtractor:
    def test_empty_transcript(self):
        ext = ConversationMemoryExtractor()
        assert ext.extract([]) == []

    def test_extract_prefer_pattern(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": "I prefer using Python for scripts."}]
        facts = ext.extract(transcript)
        assert len(facts) >= 1
        assert any("prefer" in f.content.lower() for f in facts)
        assert all(f.confidence == 0.7 for f in facts)

    def test_extract_always_use_pattern(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": "Always use TypeScript for frontend."}]
        facts = ext.extract(transcript)
        assert len(facts) >= 1

    def test_extract_never_use_pattern(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": "Never use eval in JavaScript code."}]
        facts = ext.extract(transcript)
        assert len(facts) >= 1

    def test_extract_project_uses_pattern(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": "Project uses React and Docker."}]
        facts = ext.extract(transcript)
        assert len(facts) >= 1
        assert any("react" in f.tags or "docker" in f.tags for f in facts)

    def test_extract_we_use_pattern(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": "We use Git for version control."}]
        facts = ext.extract(transcript)
        assert len(facts) >= 1

    def test_extract_identity_pattern(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": "I am a backend developer."}]
        facts = ext.extract(transcript)
        assert len(facts) >= 1
        assert facts[0].confidence == 0.6

    def test_extract_im_a_pattern(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": "I'm a Python developer who likes TDD."}]
        facts = ext.extract(transcript)
        assert len(facts) >= 1

    def test_no_facts_from_generic_text(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": "Hello, how are you?"}]
        facts = ext.extract(transcript)
        assert facts == []

    def test_deduplication(self):
        ext = ConversationMemoryExtractor()
        transcript = [
            {"role": "user", "content": "I prefer Python. I prefer Python."},
        ]
        facts = ext.extract(transcript)
        contents = [f.content for f in facts]
        assert len(contents) == len(set(c.lower() for c in contents))

    def test_ignores_system_role(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "system", "content": "I prefer Python."}]
        facts = ext.extract(transcript)
        assert facts == []

    def test_handles_empty_content(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": ""}]
        facts = ext.extract(transcript)
        assert facts == []

    def test_handles_non_string_content(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": 12345}]
        facts = ext.extract(transcript)
        assert facts == []

    def test_multi_turn_transcript(self):
        ext = ConversationMemoryExtractor()
        transcript = [
            {"role": "user", "content": "I prefer TypeScript."},
            {"role": "assistant", "content": "Got it."},
            {"role": "user", "content": "We use Docker for deployment."},
        ]
        facts = ext.extract(transcript)
        assert len(facts) >= 2

    def test_source_turn_tracked(self):
        ext = ConversationMemoryExtractor()
        transcript = [
            {"role": "user", "content": "Hello."},
            {"role": "user", "content": "I prefer Rust."},
        ]
        facts = ext.extract(transcript)
        assert len(facts) >= 1
        assert facts[0].source_turn == 1

    def test_with_llm_fn(self):
        ext = ConversationMemoryExtractor()

        def fake_llm(prompt):
            return "- Uses Python\n- Prefers TDD\n- Uses Docker"

        transcript = [{"role": "user", "content": "Anything"}]
        facts = ext.extract(transcript, llm_fn=fake_llm)
        assert len(facts) == 3
        assert all(f.confidence == 0.85 for f in facts)

    def test_llm_fn_deduplicates(self):
        ext = ConversationMemoryExtractor()

        def fake_llm(prompt):
            return "- Uses Python\n- Uses Python\n- Uses Docker"

        facts = ext.extract([{"role": "user", "content": "x"}], llm_fn=fake_llm)
        assert len(facts) == 2

    def test_llm_fn_fallback_on_error(self):
        ext = ConversationMemoryExtractor()

        def failing_llm(prompt):
            raise RuntimeError("API error")

        transcript = [{"role": "user", "content": "I prefer Python."}]
        facts = ext.extract(transcript, llm_fn=failing_llm)
        # Falls back to heuristics
        assert len(facts) >= 1

    def test_extract_high_confidence(self):
        ext = ConversationMemoryExtractor()

        def fake_llm(prompt):
            return "- Uses Python\n- Prefers TDD"

        facts = ext.extract_high_confidence(
            [{"role": "user", "content": "x"}],
            threshold=0.8,
            llm_fn=fake_llm,
        )
        assert len(facts) == 2  # 0.85 > 0.8

    def test_extract_high_confidence_heuristics(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": "I prefer Python."}]
        facts = ext.extract_high_confidence(transcript, threshold=0.8)
        # Heuristic confidence is 0.7, below 0.8
        assert facts == []

    def test_tags_extracted(self):
        ext = ConversationMemoryExtractor()
        transcript = [{"role": "user", "content": "We use Python and Docker for testing."}]
        facts = ext.extract(transcript)
        assert len(facts) >= 1
        tags = facts[0].tags
        assert "python" in tags or "docker" in tags or "testing" in tags
