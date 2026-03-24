"""Tests for Task 470: WikiExporter."""
import json
import pytest
from pathlib import Path
from lidco.wiki.exporter import WikiExporter
from lidco.wiki.generator import WikiPage


def _setup_wiki(project_dir: Path, count: int = 2) -> None:
    wiki_dir = project_dir / ".lidco" / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        page = WikiPage(
            module_path=f"src/mod{i}.py",
            summary=f"Module {i} summary.",
            generated_at="2025-01-01",
        )
        (wiki_dir / f"src_mod{i}.md").write_text(page.to_markdown(), encoding="utf-8")


class TestWikiExporter:
    def test_export_returns_count(self, tmp_path):
        _setup_wiki(tmp_path, count=3)
        exporter = WikiExporter()
        count = exporter.export(tmp_path, tmp_path / "out")
        assert count == 3

    def test_export_creates_files(self, tmp_path):
        _setup_wiki(tmp_path, count=2)
        exporter = WikiExporter()
        out = tmp_path / "out"
        exporter.export(tmp_path, out)
        assert len(list(out.glob("*.md"))) >= 2

    def test_export_creates_readme_index(self, tmp_path):
        _setup_wiki(tmp_path, count=2)
        exporter = WikiExporter()
        out = tmp_path / "out"
        exporter.export(tmp_path, out)
        assert (out / "README.md").exists()

    def test_readme_contains_links(self, tmp_path):
        _setup_wiki(tmp_path, count=2)
        exporter = WikiExporter()
        out = tmp_path / "out"
        exporter.export(tmp_path, out)
        readme = (out / "README.md").read_text()
        assert ".md" in readme

    def test_export_creates_output_dir(self, tmp_path):
        _setup_wiki(tmp_path, count=1)
        exporter = WikiExporter()
        out = tmp_path / "nested" / "out"
        exporter.export(tmp_path, out)
        assert out.exists()

    def test_export_no_wiki_returns_zero(self, tmp_path):
        exporter = WikiExporter()
        count = exporter.export(tmp_path, tmp_path / "out")
        assert count == 0

    def test_export_json(self, tmp_path):
        _setup_wiki(tmp_path, count=2)
        exporter = WikiExporter()
        out_path = tmp_path / "wiki.json"
        count = exporter.export_json(tmp_path, out_path)
        assert count == 2
        data = json.loads(out_path.read_text())
        assert len(data["pages"]) == 2
        assert "content" in data["pages"][0]
