"""Q114 CLI commands: /notebook /search."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q114 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /notebook                                                           #
    # ------------------------------------------------------------------ #

    async def notebook_handler(args: str) -> str:
        from lidco.notebook.parser import NotebookParser, NotebookParseError
        from lidco.notebook.editor import NotebookEditor, NotebookEditError
        from lidco.notebook.agent import NotebookAgent

        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "open":
            path = parts[1] if len(parts) > 1 else ""
            if not path:
                return "Usage: /notebook open <path>"
            parser = NotebookParser()
            read_fn = _state.get("read_fn")
            try:
                doc = parser.parse(path, read_fn=read_fn)
            except NotebookParseError as exc:
                return f"Error opening notebook: {exc}"
            _state["notebook_doc"] = doc
            _state["notebook_path"] = path
            return f"Opened notebook '{path}' with {len(doc.cells)} cell(s)."

        if sub == "add":
            if "notebook_doc" not in _state:
                return "No notebook open. Use /notebook open <path> first."
            if len(parts) < 3:
                return "Usage: /notebook add <code|markdown> <source>"
            cell_type = parts[1]
            source = parts[2]
            editor = NotebookEditor()
            doc = _state["notebook_doc"]
            new_doc = editor.append_cell(doc, cell_type, source)  # type: ignore[arg-type]
            _state["notebook_doc"] = new_doc
            return f"Added {cell_type} cell. Notebook now has {len(new_doc.cells)} cell(s)."

        if sub == "replace":
            if "notebook_doc" not in _state:
                return "No notebook open. Use /notebook open <path> first."
            if len(parts) < 3:
                return "Usage: /notebook replace <idx> <source>"
            try:
                idx = int(parts[1])
            except ValueError:
                return "Index must be an integer."
            source = parts[2]
            editor = NotebookEditor()
            doc = _state["notebook_doc"]
            try:
                new_doc = editor.replace_cell(doc, idx, source)  # type: ignore[arg-type]
            except NotebookEditError as exc:
                return f"Error: {exc}"
            _state["notebook_doc"] = new_doc
            return f"Replaced cell {idx}."

        if sub == "delete":
            if "notebook_doc" not in _state:
                return "No notebook open. Use /notebook open <path> first."
            if len(parts) < 2:
                return "Usage: /notebook delete <idx>"
            try:
                idx = int(parts[1])
            except ValueError:
                return "Index must be an integer."
            editor = NotebookEditor()
            doc = _state["notebook_doc"]
            try:
                new_doc = editor.delete_cell(doc, idx)  # type: ignore[arg-type]
            except NotebookEditError as exc:
                return f"Error: {exc}"
            _state["notebook_doc"] = new_doc
            return f"Deleted cell {idx}. Notebook now has {len(new_doc.cells)} cell(s)."

        if sub == "show":
            if "notebook_doc" not in _state:
                return "No notebook open. Use /notebook open <path> first."
            agent = NotebookAgent()
            analysis = agent.analyze(_state["notebook_doc"])  # type: ignore[arg-type]
            lines = [
                f"Cells: {analysis['total_cells']} (code={analysis['code_cells']}, markdown={analysis['markdown_cells']})",
                f"Has outputs: {analysis['has_outputs']}",
            ]
            for s in analysis["cell_summary"]:
                lines.append(f"  {s}")
            return "\n".join(lines)

        if sub == "ask":
            if "notebook_doc" not in _state:
                return "No notebook open. Use /notebook open <path> first."
            question = parts[1] if len(parts) > 1 else ""
            if not question:
                return "Usage: /notebook ask <question>"
            agent = NotebookAgent()
            analysis = agent.analyze(_state["notebook_doc"])  # type: ignore[arg-type]
            return (
                f"Analysis for '{question}':\n"
                f"  Total cells: {analysis['total_cells']}\n"
                f"  Code cells: {analysis['code_cells']}\n"
                f"  Markdown cells: {analysis['markdown_cells']}\n"
                f"  Has outputs: {analysis['has_outputs']}"
            )

        return (
            "Usage: /notebook <sub>\n"
            "  open <path>                  -- open a .ipynb file\n"
            "  add <code|markdown> <source> -- add a cell\n"
            "  replace <idx> <source>       -- replace cell source\n"
            "  delete <idx>                 -- delete a cell\n"
            "  show                         -- show cell summary\n"
            "  ask <question>               -- analyze notebook"
        )

    # ------------------------------------------------------------------ #
    # /search                                                             #
    # ------------------------------------------------------------------ #

    async def search_handler(args: str) -> str:
        from lidco.search.web_search import WebSearchGrounder

        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub != "web":
            return (
                "Usage: /search <sub>\n"
                "  web <query>              -- search the web\n"
                "  web --grounded <prompt>  -- search and ground a prompt"
            )

        rest = parts[1] if len(parts) > 1 else ""
        extra = parts[2] if len(parts) > 2 else ""

        search_fn = _state.get("search_fn")
        grounder = WebSearchGrounder(search_fn=search_fn)

        if rest == "--grounded":
            if not extra:
                return "Usage: /search web --grounded <prompt>"
            result = grounder.grounded_prompt(extra, extra)
            return result

        query = rest
        if extra:
            query = f"{rest} {extra}"
        if not query:
            return "Usage: /search web <query>"

        results = grounder.search(query)
        if not results:
            return "No results found."
        lines = [f"Found {len(results)} result(s):"]
        for r in results:
            lines.append(f"  [{r.title}] {r.url}")
            if r.snippet:
                lines.append(f"    {r.snippet}")
        return "\n".join(lines)

    registry.register(SlashCommand("notebook", "Jupyter notebook operations", notebook_handler))
    registry.register(SlashCommand("search", "Web search and grounding", search_handler))
