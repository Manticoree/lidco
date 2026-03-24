"""WikiExporter — exports all wiki pages to a directory with an index."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class WikiExporter:
    """Exports `.lidco/wiki/` pages to an output directory."""

    def __init__(self) -> None:
        pass

    def export(self, project_dir: Path, output_dir: Path) -> int:
        """Copy all wiki pages to *output_dir*, generate README index.

        Returns the number of pages exported.
        """
        wiki_src = project_dir / ".lidco" / "wiki"
        if not wiki_src.exists():
            return 0

        output_dir.mkdir(parents=True, exist_ok=True)
        pages = list(wiki_src.glob("*.md"))
        exported = 0
        index_entries: list[tuple[str, str]] = []

        for page_path in sorted(pages):
            dest = output_dir / page_path.name
            content = page_path.read_text(encoding="utf-8")
            dest.write_text(content, encoding="utf-8")
            exported += 1
            # Extract title (first H1)
            title = page_path.stem
            for line in content.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            index_entries.append((page_path.name, title))

        if index_entries:
            self._write_index(output_dir, index_entries)

        logger.info("Exported %d wiki pages to %s", exported, output_dir)
        return exported

    def export_json(self, project_dir: Path, output_path: Path) -> int:
        """Export wiki pages as a JSON file for external tools.

        Returns the number of pages included.
        """
        wiki_src = project_dir / ".lidco" / "wiki"
        if not wiki_src.exists():
            return 0

        pages = []
        for p in sorted(wiki_src.glob("*.md")):
            content = p.read_text(encoding="utf-8")
            title = p.stem
            for line in content.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            pages.append({"file": p.name, "title": title, "content": content})

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({"pages": pages}, indent=2), encoding="utf-8")
        return len(pages)

    # ------------------------------------------------------------------

    def _write_index(self, output_dir: Path, entries: list[tuple[str, str]]) -> None:
        lines = [
            "# Wiki Index",
            "",
            "Auto-generated documentation.",
            "",
        ]
        for filename, title in sorted(entries):
            lines.append(f"- [{title}]({filename})")
        lines.append("")
        (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
