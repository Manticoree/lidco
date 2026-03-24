"""Tests for Task 460: DesignDocGenerator — requirements → design.md."""
import json
import pytest
from pathlib import Path
from lidco.spec.writer import SpecDocument
from lidco.spec.design_doc import Component, DesignDocument, DesignDocGenerator


class TestComponent:
    def test_component_fields(self):
        c = Component(name="Cache", responsibility="Stores data", file_path="src/cache.py")
        assert c.name == "Cache"
        assert c.file_path == "src/cache.py"

    def test_component_default_file_path(self):
        c = Component(name="X", responsibility="Does X")
        assert c.file_path == ""


class TestDesignDocument:
    def test_to_markdown_contains_components(self):
        doc = DesignDocument(
            components=[Component("Fetcher", "Fetches data", "src/fetcher.py")],
            data_models=["FetchResult: url: str, data: bytes"],
            api_contracts=["fetch(url: str) -> FetchResult"],
            implementation_notes="Use httpx for async requests.",
        )
        md = doc.to_markdown()
        assert "Fetcher" in md
        assert "FetchResult" in md
        assert "httpx" in md

    def test_to_markdown_api_contracts(self):
        doc = DesignDocument(api_contracts=["run() -> None"])
        md = doc.to_markdown()
        assert "run() -> None" in md

    def test_roundtrip_markdown(self):
        doc = DesignDocument(
            components=[Component("A", "Does A", "src/a.py")],
            data_models=["AResult: ok: bool"],
            api_contracts=["do_a() -> AResult"],
            implementation_notes="Simple.",
        )
        restored = DesignDocument.from_markdown(doc.to_markdown())
        assert len(restored.components) == 1
        assert restored.components[0].name == "A"

    def test_empty_design_document(self):
        doc = DesignDocument()
        md = doc.to_markdown()
        assert "Design Document" in md


class TestDesignDocGeneratorOffline:
    def _spec(self):
        return SpecDocument(
            title="Notification System",
            overview="Sends push notifications.",
            user_stories=[],
            acceptance_criteria=["The system shall send notification when event fires"],
            out_of_scope=[],
        )

    def test_generate_offline_returns_design(self, tmp_path):
        gen = DesignDocGenerator()
        doc = gen.generate(self._spec(), tmp_path)
        assert isinstance(doc, DesignDocument)
        assert doc.components

    def test_generate_saves_design_md(self, tmp_path):
        gen = DesignDocGenerator()
        gen.generate(self._spec(), tmp_path)
        assert (tmp_path / ".lidco" / "spec" / "design.md").exists()

    def test_generate_creates_parent_dirs(self, tmp_path):
        gen = DesignDocGenerator()
        gen.generate(self._spec(), tmp_path)
        assert (tmp_path / ".lidco" / "spec").is_dir()

    def test_load_returns_none_when_absent(self, tmp_path):
        gen = DesignDocGenerator()
        assert gen.load(tmp_path) is None

    def test_load_returns_design_after_generate(self, tmp_path):
        gen = DesignDocGenerator()
        gen.generate(self._spec(), tmp_path)
        loaded = gen.load(tmp_path)
        assert loaded is not None

    def test_generate_with_llm_client(self, tmp_path):
        payload = json.dumps({
            "components": [{"name": "Notifier", "responsibility": "Sends SMS", "file_path": "src/notifier.py"}],
            "data_models": ["Notification: id: str, message: str"],
            "api_contracts": ["send(msg: str) -> bool"],
            "implementation_notes": "Use Twilio SDK.",
        })

        def fake_llm(messages):
            return payload

        gen = DesignDocGenerator(llm_client=fake_llm)
        doc = gen.generate(self._spec(), tmp_path)
        assert doc.components[0].name == "Notifier"
        assert "Twilio" in doc.implementation_notes

    def test_generate_with_llm_codeblock(self, tmp_path):
        payload = json.dumps({
            "components": [],
            "data_models": [],
            "api_contracts": [],
            "implementation_notes": "Simple.",
        })

        def fake_llm(messages):
            return f"```\n{payload}\n```"

        gen = DesignDocGenerator(llm_client=fake_llm)
        doc = gen.generate(self._spec(), tmp_path)
        assert doc.implementation_notes == "Simple."

    def test_component_file_path_preserved(self, tmp_path):
        gen = DesignDocGenerator()
        doc = gen.generate(self._spec(), tmp_path)
        assert doc.components[0].file_path  # offline generates a path
