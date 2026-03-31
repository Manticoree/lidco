"""Q130 CLI commands: /graph."""
from __future__ import annotations

import json

_state: dict = {}


def register(registry) -> None:
    """Register Q130 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def graph_handler(args: str) -> str:
        from lidco.memory.memory_graph import MemoryGraph
        from lidco.memory.memory_node import MemoryEdge, MemoryNode
        from lidco.memory.graph_query import GraphQuery
        from lidco.memory.graph_serializer import GraphSerializer

        if "graph" not in _state:
            _state["graph"] = MemoryGraph()
        graph: MemoryGraph = _state["graph"]

        parts = args.strip().split(maxsplit=4)
        sub = parts[0].lower() if parts else ""

        if sub == "add":
            # /graph add <id> <type> <content>
            if len(parts) < 4:
                return "Usage: /graph add <id> <type> <content>"
            nid = parts[1]
            ntype = parts[2]
            content = " ".join(parts[3:])
            node = MemoryNode(id=nid, content=content, node_type=ntype)
            graph.add_node(node)
            return f"Added node '{nid}' [{ntype}]."

        if sub == "connect":
            # /graph connect <from_id> <to_id> <relation>
            if len(parts) < 4:
                return "Usage: /graph connect <from> <to> <relation>"
            edge = MemoryEdge(source_id=parts[1], target_id=parts[2], relation=parts[3])
            graph.add_edge(edge)
            return f"Connected '{parts[1]}' -> '{parts[2]}' [{parts[3]}]."

        if sub == "find":
            if len(parts) < 2:
                return "Usage: /graph find <query>"
            query = " ".join(parts[1:])
            results = graph.search(query)
            if not results:
                return f"No nodes found for '{query}'."
            lines = [f"Found {len(results)} node(s):"]
            for n in results:
                lines.append(f"  {n.id} [{n.node_type}]: {n.content[:60]}")
            return "\n".join(lines)

        if sub == "path":
            if len(parts) < 3:
                return "Usage: /graph path <from_id> <to_id>"
            q = GraphQuery(graph)
            path = q.path(parts[1], parts[2])
            if not path:
                return f"No path from '{parts[1]}' to '{parts[2]}'."
            return " -> ".join(path)

        if sub == "stats":
            s = graph.stats()
            lines = [
                f"Nodes: {s['nodes']}  Edges: {s['edges']}",
                "Types: " + ", ".join(f"{k}={v}" for k, v in s["types"].items()),
            ]
            return "\n".join(lines)

        if sub == "export":
            ser = GraphSerializer()
            return ser.to_json(graph)

        if sub == "import":
            if len(parts) < 2:
                return "Usage: /graph import <json>"
            raw = " ".join(parts[1:])
            try:
                ser = GraphSerializer()
                imported = ser.from_json(raw)
                for node in imported.all_nodes():
                    graph.add_node(node)
                for edge in imported.all_edges():
                    graph.add_edge(edge)
                return f"Imported {len(imported.all_nodes())} nodes, {len(imported.all_edges())} edges."
            except Exception as exc:
                return f"Import failed: {exc}"

        return (
            "Usage: /graph <sub>\n"
            "  add <id> <type> <content>      -- add a memory node\n"
            "  connect <from> <to> <relation> -- add an edge\n"
            "  find <query>                   -- search nodes\n"
            "  path <from> <to>               -- shortest path\n"
            "  stats                          -- graph statistics\n"
            "  export                         -- export as JSON\n"
            "  import <json>                  -- import from JSON"
        )

    registry.register(SlashCommand("graph", "Agent memory graph", graph_handler))
