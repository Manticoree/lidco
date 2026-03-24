"""Tests for Task 463: SpecContextProvider."""
from pathlib import Path
from lidco.spec.context import SpecContextProvider
from lidco.spec.writer import SpecDocument, SpecWriter
from lidco.spec.task_decomposer import SpecTask, TaskDecomposer
from lidco.spec.design_doc import DesignDocument


def _write_requirements(project_dir: Path, title: str = "Feature X") -> None:
    spec_dir = project_dir / ".lidco" / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    doc = SpecDocument(
        title=title,
        overview="A great feature.",
        user_stories=["As a user I want X so that Y"],
        acceptance_criteria=["The system shall do X when triggered"],
        out_of_scope=["Out"],
    )
    (spec_dir / "requirements.md").write_text(doc.to_markdown(), encoding="utf-8")


def _write_tasks(project_dir: Path, open_count: int = 2, done_count: int = 1) -> None:
    spec_dir = project_dir / ".lidco" / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Tasks\n"]
    for i in range(1, open_count + 1):
        lines.append(f"- [ ] T{i}: Open task {i}")
        lines.append(f"  Description {i}")
        lines.append("")
    for i in range(open_count + 1, open_count + done_count + 1):
        lines.append(f"- [x] T{i}: Done task {i}")
        lines.append(f"  Description {i}")
        lines.append("")
    (spec_dir / "tasks.md").write_text("\n".join(lines), encoding="utf-8")


class TestSpecContextProvider:
    def test_returns_none_when_no_spec(self, tmp_path):
        provider = SpecContextProvider(tmp_path)
        assert provider.load() is None

    def test_returns_block_when_spec_exists(self, tmp_path):
        _write_requirements(tmp_path)
        provider = SpecContextProvider(tmp_path)
        result = provider.load()
        assert result is not None
        assert "## Project Specification" in result

    def test_block_contains_requirements_content(self, tmp_path):
        _write_requirements(tmp_path, "Auth Module")
        provider = SpecContextProvider(tmp_path)
        result = provider.load()
        assert "Auth Module" in result

    def test_open_tasks_included(self, tmp_path):
        _write_requirements(tmp_path)
        _write_tasks(tmp_path, open_count=2, done_count=1)
        provider = SpecContextProvider(tmp_path)
        result = provider.load()
        assert "Open task" in result

    def test_done_tasks_excluded(self, tmp_path):
        _write_requirements(tmp_path)
        _write_tasks(tmp_path, open_count=0, done_count=2)
        provider = SpecContextProvider(tmp_path)
        result = provider.load()
        # No open tasks → Open Tasks section should be empty or absent
        assert "Done task" not in (result or "")

    def test_truncation_at_max_chars(self, tmp_path):
        spec_dir = tmp_path / ".lidco" / "spec"
        spec_dir.mkdir(parents=True, exist_ok=True)
        big_content = "x" * 10000
        (spec_dir / "requirements.md").write_text(big_content, encoding="utf-8")
        provider = SpecContextProvider(tmp_path)
        result = provider.load()
        assert result is not None
        assert len(result) <= 8200  # slight buffer

    def test_spec_exists_true_when_file_present(self, tmp_path):
        _write_requirements(tmp_path)
        provider = SpecContextProvider(tmp_path)
        assert provider.spec_exists() is True

    def test_spec_exists_false_when_absent(self, tmp_path):
        provider = SpecContextProvider(tmp_path)
        assert provider.spec_exists() is False

    def test_load_with_explicit_project_dir(self, tmp_path):
        _write_requirements(tmp_path)
        provider = SpecContextProvider()
        result = provider.load(project_dir=tmp_path)
        assert result is not None
