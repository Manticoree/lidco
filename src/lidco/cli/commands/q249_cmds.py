"""Q249 CLI commands: /code-graph, /graph-query, /impact, /graph-viz."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q249 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /code-graph
    # ------------------------------------------------------------------

    async def code_graph_handler(args: str) -> str:
        from lidco.codegraph.builder import CodeGraphBuilder

        builder = CodeGraphBuilder()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            if not rest:
                return "Usage: /code-graph add <name> <kind> <file>"
            tokens = rest.split()
            if len(tokens) < 3:
                return "Usage: /code-graph add <name> <kind> <file>"
            from lidco.codegraph.builder import GraphNode

            node = GraphNode(name=tokens[0], kind=tokens[1], file=tokens[2])
            builder.add_node(node)
            return f"Added node {tokens[0]} ({tokens[1]}) in {tokens[2]}."

        if sub == "show":
            d = builder.to_dict()
            return f"{len(d['nodes'])} nodes, {len(d['edges'])} edges."

        return (
            "Usage: /code-graph <subcommand>\n"
            "  add <name> <kind> <file> — add a node\n"
            "  show                     — show graph stats"
        )

    # ------------------------------------------------------------------
    # /graph-query
    # ------------------------------------------------------------------

    async def graph_query_handler(args: str) -> str:
        from lidco.codegraph.builder import CodeGraphBuilder, GraphNode
        from lidco.codegraph.query import GraphQueryEngine

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "callers":
            if not rest:
                return "Usage: /graph-query callers <name>"
            builder = CodeGraphBuilder()
            engine = GraphQueryEngine(builder)
            callers = engine.callers_of(rest)
            if not callers:
                return f"No callers of {rest}."
            return "Callers: " + ", ".join(callers)

        if sub == "search":
            if not rest:
                return "Usage: /graph-query search <pattern>"
            builder = CodeGraphBuilder()
            engine = GraphQueryEngine(builder)
            results = engine.search(rest)
            if not results:
                return "No matches."
            return "Matches: " + ", ".join(n.name for n in results)

        return (
            "Usage: /graph-query <subcommand>\n"
            "  callers <name>    — find callers of a symbol\n"
            "  search <pattern>  — regex search node names"
        )

    # ------------------------------------------------------------------
    # /impact
    # ------------------------------------------------------------------

    async def impact_handler(args: str) -> str:
        from lidco.codegraph.builder import CodeGraphBuilder
        from lidco.codegraph.impact import ImpactAnalyzer

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "analyze":
            if not rest:
                return "Usage: /impact analyze <name1> [name2 ...]"
            names = rest.split()
            builder = CodeGraphBuilder()
            analyzer = ImpactAnalyzer(builder)
            result = analyzer.analyze(names)
            return (
                f"Affected: {len(result.affected)}, "
                f"confidence: {result.confidence}, "
                f"transitive: {result.transitive_count}"
            )

        if sub == "files":
            if not rest:
                return "Usage: /impact files <name1> [name2 ...]"
            names = rest.split()
            builder = CodeGraphBuilder()
            analyzer = ImpactAnalyzer(builder)
            files = analyzer.affected_files(names)
            if not files:
                return "No affected files."
            return "Affected files: " + ", ".join(sorted(files))

        return (
            "Usage: /impact <subcommand>\n"
            "  analyze <names...> — analyze impact of changes\n"
            "  files <names...>   — list affected files"
        )

    # ------------------------------------------------------------------
    # /graph-viz
    # ------------------------------------------------------------------

    async def graph_viz_handler(args: str) -> str:
        from lidco.codegraph.builder import CodeGraphBuilder
        from lidco.codegraph.visualizer import GraphVisualizer

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "dot":
            builder = CodeGraphBuilder()
            viz = GraphVisualizer(builder)
            return viz.to_dot()

        if sub == "mermaid":
            builder = CodeGraphBuilder()
            viz = GraphVisualizer(builder)
            return viz.to_mermaid()

        if sub == "filter":
            if not rest:
                return "Usage: /graph-viz filter <file>"
            builder = CodeGraphBuilder()
            viz = GraphVisualizer(builder)
            return viz.filter_by_file(rest)

        return (
            "Usage: /graph-viz <subcommand>\n"
            "  dot              — render DOT format\n"
            "  mermaid          — render Mermaid format\n"
            "  filter <file>    — DOT filtered to file"
        )

    registry.register(SlashCommand("code-graph", "Semantic code graph builder", code_graph_handler))
    registry.register(SlashCommand("graph-query", "Query the code graph", graph_query_handler))
    registry.register(SlashCommand("impact", "Impact analysis for code changes", impact_handler))
    registry.register(SlashCommand("graph-viz", "Visualize code graph", graph_viz_handler))
