"""Tests for Task 459: SpecWriter — NL prompt → requirements.md."""
import json
import pytest
from pathlib import Path
from lidco.spec.writer import SpecDocument, SpecWriter


class TestSpecDocument:
    def test_to_markdown_contains_title(self):
        doc = SpecDocument(
            title="Auth System",
            overview="Handles user authentication.",
            user_stories=["As a user I want to login so that I can access my data"],
            acceptance_criteria=["The system shall verify credentials when login is attempted"],
            out_of_scope=["OAuth integration"],
        )
        md = doc.to_markdown()
        assert "# Auth System" in md
        assert "The system shall verify credentials" in md
        assert "OAuth integration" in md

    def test_to_markdown_user_stories(self):
        doc = SpecDocument(
            title="T",
            overview="O",
            user_stories=["As a dev I want X so that Y"],
        )
        md = doc.to_markdown()
        assert "As a dev I want X" in md

    def test_roundtrip_markdown(self):
        doc = SpecDocument(
            title="Feature X",
            overview="Does X.",
            user_stories=["As a user I want X so that Z"],
            acceptance_criteria=["The system shall do X when triggered"],
            out_of_scope=["Feature Y"],
        )
        md = doc.to_markdown()
        restored = SpecDocument.from_markdown(md)
        assert restored.title == "Feature X"
        assert len(restored.acceptance_criteria) == 1
        assert "The system shall do X" in restored.acceptance_criteria[0]

    def test_from_markdown_preserves_stories(self):
        doc = SpecDocument(
            title="T",
            overview="O",
            user_stories=["As a admin I want Y so that Z"],
            acceptance_criteria=[],
            out_of_scope=[],
        )
        restored = SpecDocument.from_markdown(doc.to_markdown())
        assert "As a admin I want Y so that Z" in restored.user_stories

    def test_empty_lists(self):
        doc = SpecDocument(title="Empty", overview="Nothing")
        md = doc.to_markdown()
        assert "# Empty" in md


class TestSpecWriterOffline:
    def test_generate_offline_returns_spec_document(self, tmp_path):
        writer = SpecWriter()
        doc = writer.generate("Build a file watcher system", tmp_path)
        assert isinstance(doc, SpecDocument)
        assert doc.title
        assert doc.overview

    def test_generate_saves_requirements_md(self, tmp_path):
        writer = SpecWriter()
        writer.generate("Build a cache layer", tmp_path)
        p = tmp_path / ".lidco" / "spec" / "requirements.md"
        assert p.exists()

    def test_generate_creates_parent_dirs(self, tmp_path):
        writer = SpecWriter()
        writer.generate("Feature", tmp_path)
        assert (tmp_path / ".lidco" / "spec").is_dir()

    def test_load_returns_none_when_missing(self, tmp_path):
        writer = SpecWriter()
        assert writer.load(tmp_path) is None

    def test_load_returns_spec_after_generate(self, tmp_path):
        writer = SpecWriter()
        writer.generate("Notification system", tmp_path)
        loaded = writer.load(tmp_path)
        assert loaded is not None
        assert isinstance(loaded, SpecDocument)

    def test_generate_with_llm_client(self, tmp_path):
        payload = json.dumps({
            "title": "LLM Feature",
            "overview": "Described by LLM.",
            "user_stories": ["As a user I want LLM so that magic"],
            "acceptance_criteria": ["The system shall call LLM when needed"],
            "out_of_scope": ["None"],
        })

        def fake_llm(messages):
            return payload

        writer = SpecWriter(llm_client=fake_llm)
        doc = writer.generate("Any description", tmp_path)
        assert doc.title == "LLM Feature"
        assert "LLM" in doc.acceptance_criteria[0]

    def test_generate_with_llm_json_in_codeblock(self, tmp_path):
        payload = json.dumps({
            "title": "CB",
            "overview": "O",
            "user_stories": [],
            "acceptance_criteria": ["The system shall work"],
            "out_of_scope": [],
        })

        def fake_llm(messages):
            return f"```json\n{payload}\n```"

        writer = SpecWriter(llm_client=fake_llm)
        doc = writer.generate("Anything", tmp_path)
        assert doc.title == "CB"

    def test_existing_requirements_loaded_as_context(self, tmp_path):
        """Second generate call should see existing requirements in context."""
        writer = SpecWriter()
        writer.generate("First feature", tmp_path)
        calls = []

        def recording_llm(messages):
            calls.append(messages)
            return json.dumps({
                "title": "T",
                "overview": "O",
                "user_stories": [],
                "acceptance_criteria": ["The system shall exist"],
                "out_of_scope": [],
            })

        writer2 = SpecWriter(llm_client=recording_llm)
        writer2.generate("Second feature", tmp_path)
        assert calls
        user_content = calls[0][1]["content"]
        assert "Existing requirements" in user_content
