"""Q329 CLI commands — /knowledge, /knowledge-search, /knowledge-graph, /knowledge-update

Registered via register_q329_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q329_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q329 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /knowledge — Extract knowledge concepts from code
    # ------------------------------------------------------------------
    async def knowledge_handler(args: str) -> str:
        """
        Usage: /knowledge extract <file>
               /knowledge extract-source <python-code>
               /knowledge types
        """
        from lidco.knowledge.extractor import ConceptType, KnowledgeExtractor

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /knowledge <subcommand>\n"
                "  extract <file>           extract concepts from a file\n"
                "  extract-source <code>    extract concepts from source string\n"
                "  types                    list concept types"
            )

        subcmd = parts[0].lower()

        if subcmd == "types":
            lines = ["Concept types:"]
            for ct in ConceptType:
                lines.append(f"  {ct.value}")
            return "\n".join(lines)

        if subcmd == "extract":
            if len(parts) < 2:
                return "Usage: /knowledge extract <file>"
            file_path = parts[1]
            extractor = KnowledgeExtractor()
            result = extractor.extract_from_file(file_path)
            if result.errors:
                return f"Errors: {'; '.join(result.errors)}"
            lines = [f"Extracted {result.concept_count} concepts from {file_path}:"]
            for concept in result.concepts[:20]:
                lines.append(
                    f"  [{concept.concept_type.value}] {concept.name} "
                    f"(line {concept.line_number}, confidence={concept.confidence:.2f})"
                )
            if result.concept_count > 20:
                lines.append(f"  ... and {result.concept_count - 20} more")
            return "\n".join(lines)

        if subcmd == "extract-source":
            raw = args.strip()[len("extract-source"):].strip()
            if not raw:
                return "Usage: /knowledge extract-source <python-code>"
            extractor = KnowledgeExtractor()
            result = extractor.extract_from_source(raw)
            lines = [f"Extracted {result.concept_count} concepts:"]
            for concept in result.concepts[:20]:
                lines.append(
                    f"  [{concept.concept_type.value}] {concept.name}"
                )
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use extract/extract-source/types."

    registry.register_async("knowledge", "Extract knowledge concepts from code", knowledge_handler)

    # ------------------------------------------------------------------
    # /knowledge-search — Search the knowledge graph
    # ------------------------------------------------------------------
    async def knowledge_search_handler(args: str) -> str:
        """
        Usage: /knowledge-search <query>
               /knowledge-search concept <concept-name>
               /knowledge-search answer <question>
        """
        from lidco.knowledge.graph import KnowledgeGraph
        from lidco.knowledge.search import KnowledgeSearch

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /knowledge-search <subcommand>\n"
                "  <query>                search the knowledge graph\n"
                "  concept <name>         search for a specific concept\n"
                "  answer <question>      get an answer to a question"
            )

        subcmd = parts[0].lower()
        graph = KnowledgeGraph()
        search = KnowledgeSearch(graph)

        if subcmd == "concept":
            query = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not query:
                return "Usage: /knowledge-search concept <name>"
            result = search.find_by_concept(query)
            return result.summary()

        if subcmd == "answer":
            question = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not question:
                return "Usage: /knowledge-search answer <question>"
            return search.answer(question)

        # Default: free-text search
        query = args.strip()
        result = search.search(query)
        return result.summary()

    registry.register_async("knowledge-search", "Search the knowledge graph", knowledge_search_handler)

    # ------------------------------------------------------------------
    # /knowledge-graph — Manage and inspect the knowledge graph
    # ------------------------------------------------------------------
    async def knowledge_graph_handler(args: str) -> str:
        """
        Usage: /knowledge-graph stats
               /knowledge-graph entity <id>
               /knowledge-graph neighbors <id>
               /knowledge-graph path <from-id> <to-id>
               /knowledge-graph types
        """
        from lidco.knowledge.graph import EntityType, KnowledgeGraph

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /knowledge-graph <subcommand>\n"
                "  stats               show graph statistics\n"
                "  entity <id>         show entity details\n"
                "  neighbors <id>      show neighbors of entity\n"
                "  path <from> <to>    find shortest path\n"
                "  types               list entity types"
            )

        subcmd = parts[0].lower()
        graph = KnowledgeGraph()

        if subcmd == "stats":
            s = graph.stats()
            return (
                f"Entities: {s['entities']}\n"
                f"Relationships: {s['relationships']}\n"
                f"Entity types: {s['entity_types']}\n"
                f"Relationship types: {s['relationship_types']}"
            )

        if subcmd == "entity":
            if len(parts) < 2:
                return "Usage: /knowledge-graph entity <id>"
            entity = graph.get_entity(parts[1])
            if entity is None:
                return f"Entity '{parts[1]}' not found."
            return (
                f"ID: {entity.id}\n"
                f"Name: {entity.name}\n"
                f"Type: {entity.entity_type.value}\n"
                f"Description: {entity.description}\n"
                f"Source: {entity.source_file}:{entity.line_number}\n"
                f"Tags: {', '.join(entity.tags) or '(none)'}"
            )

        if subcmd == "neighbors":
            if len(parts) < 2:
                return "Usage: /knowledge-graph neighbors <id>"
            neighbors = graph.neighbors(parts[1])
            if not neighbors:
                return f"No neighbors for '{parts[1]}'."
            lines = [f"Neighbors of '{parts[1]}' ({len(neighbors)}):"]
            for n in neighbors:
                lines.append(f"  {n.id}: {n.name} ({n.entity_type.value})")
            return "\n".join(lines)

        if subcmd == "path":
            if len(parts) < 3:
                return "Usage: /knowledge-graph path <from-id> <to-id>"
            path = graph.shortest_path(parts[1], parts[2])
            if not path:
                return f"No path from '{parts[1]}' to '{parts[2]}'."
            return f"Path ({len(path)} steps): {' -> '.join(path)}"

        if subcmd == "types":
            lines = ["Entity types:"]
            for et in EntityType:
                lines.append(f"  {et.value}")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use stats/entity/neighbors/path/types."

    registry.register_async("knowledge-graph", "Inspect the knowledge graph", knowledge_graph_handler)

    # ------------------------------------------------------------------
    # /knowledge-update — Update the knowledge graph from code changes
    # ------------------------------------------------------------------
    async def knowledge_update_handler(args: str) -> str:
        """
        Usage: /knowledge-update <file> [file2 ...]
               /knowledge-update dir <project-dir>
               /knowledge-update status
        """
        from lidco.knowledge.graph import KnowledgeGraph
        from lidco.knowledge.updater import KnowledgeUpdater

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /knowledge-update <subcommand>\n"
                "  <file> [file2 ...]   update graph for specific files\n"
                "  dir <project-dir>    full update from project directory\n"
                "  status               show tracked file count"
            )

        subcmd = parts[0].lower()
        graph = KnowledgeGraph()
        updater = KnowledgeUpdater(graph)

        if subcmd == "dir":
            if len(parts) < 2:
                return "Usage: /knowledge-update dir <project-dir>"
            result = updater.full_update(parts[1])
            lines = [
                f"Scanned {result.files_scanned} files, {result.files_changed} changed.",
                f"Added: {result.entities_added}, Removed: {result.entities_removed}",
            ]
            if result.conflicts:
                lines.append(f"Conflicts: {len(result.conflicts)}")
            if result.errors:
                lines.append(f"Errors: {len(result.errors)}")
            return "\n".join(lines)

        if subcmd == "status":
            tracked = updater.tracked_files
            return f"Tracked files: {len(tracked)}"

        # Default: treat all args as file paths
        result = updater.update_files(parts)
        lines = [
            f"Updated {result.files_changed}/{result.files_scanned} files.",
            f"Entities added: {result.entities_added}, removed: {result.entities_removed}",
        ]
        if result.conflicts:
            lines.append(f"Conflicts ({len(result.conflicts)}):")
            for c in result.conflicts[:5]:
                lines.append(f"  {c}")
        if result.errors:
            lines.append(f"Errors ({len(result.errors)}):")
            for e in result.errors[:5]:
                lines.append(f"  {e}")
        return "\n".join(lines)

    registry.register_async("knowledge-update", "Update the knowledge graph", knowledge_update_handler)
