"""Q287 CLI commands — /analyze-image, /gen-diagram, /transcribe, /analyze-pdf

Registered via register_q287_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q287_commands(registry) -> None:
    """Register Q287 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /analyze-image <path> [detect | diff <path_b> | describe]
    # ------------------------------------------------------------------
    async def analyze_image_handler(args: str) -> str:
        from lidco.multimodal.image_analyzer import ImageAnalyzer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /analyze-image <path> [detect | diff <path_b> | describe]"

        path = parts[0]
        subcmd = parts[1] if len(parts) > 1 else "analyze"
        analyzer = ImageAnalyzer(use_pil=False)

        if subcmd == "detect":
            elements = analyzer.detect_elements(path)
            lines = [f"Detected {len(elements)} UI element(s):"]
            for el in elements:
                lines.append(f"  [{el.kind}] {el.label} at ({el.x},{el.y}) {el.width}x{el.height}")
            return "\n".join(lines)

        if subcmd == "diff":
            if len(parts) < 3:
                return "Usage: /analyze-image <path_a> diff <path_b>"
            path_b = parts[2]
            diff = analyzer.diff_screenshots(path, path_b)
            return (
                f"Similarity: {diff.similarity:.0%}\n"
                f"Changed regions: {len(diff.changed_regions)}\n"
                f"Pixel diff: {diff.pixel_diff_count}\n"
                f"{diff.summary}"
            )

        if subcmd == "describe":
            return analyzer.describe(path)

        # Default: full analysis
        result = analyzer.analyze(path)
        lines = [
            f"Image: {result.path}",
            f"Size: {result.width}x{result.height}",
            f"Format: {result.format}",
            f"Labels: {', '.join(result.labels) if result.labels else 'none'}",
            f"Confidence: {result.confidence:.0%}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /gen-diagram <class|sequence|arch> [args...]
    # ------------------------------------------------------------------
    async def gen_diagram_handler(args: str) -> str:
        from lidco.multimodal.diagram_gen2 import (
            CallInfo,
            ClassInfo,
            ComponentInfo,
            DiagramGenerator2,
        )

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /gen-diagram <class|sequence|arch>"

        subcmd = parts[0]
        gen = DiagramGenerator2()

        if subcmd == "class":
            classes = [
                ClassInfo(name="BaseService", methods=["start", "stop"], attributes=["name"]),
                ClassInfo(name="ApiService", methods=["handle"], parent="BaseService"),
            ]
            return gen.class_diagram(classes)

        if subcmd == "sequence":
            calls = [
                CallInfo(caller="Client", callee="Server", method="request", return_type="response"),
                CallInfo(caller="Server", callee="Database", method="query", return_type="rows"),
            ]
            return gen.sequence_diagram(calls)

        if subcmd == "arch":
            components = [
                ComponentInfo(name="Gateway", kind="gateway", description="API Gateway"),
                ComponentInfo(name="Auth", kind="service", depends_on=["Gateway"], description="Auth Service"),
                ComponentInfo(name="DB", kind="database", depends_on=["Auth"], description="PostgreSQL"),
            ]
            return gen.architecture_diagram(components)

        return "Usage: /gen-diagram <class|sequence|arch>"

    # ------------------------------------------------------------------
    # /transcribe <path> [actions | speakers]
    # ------------------------------------------------------------------
    async def transcribe_handler(args: str) -> str:
        from lidco.multimodal.transcriber import AudioTranscriber

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /transcribe <path> [actions | speakers]"

        path = parts[0]
        subcmd = parts[1] if len(parts) > 1 else "full"
        transcriber = AudioTranscriber()
        transcript = transcriber.transcribe(path)

        if subcmd == "actions":
            items = transcriber.extract_action_items(transcript)
            if not items:
                return "No action items found."
            lines = [f"Action items ({len(items)}):"]
            for item in items:
                lines.append(f"  [{item.priority}] {item.text} (assignee: {item.assignee})")
            return "\n".join(lines)

        if subcmd == "speakers":
            speakers = transcriber.detect_speakers(transcript)
            lines = [f"Speakers ({len(speakers)}):"]
            for spk in speakers:
                lines.append(f"  {spk.label}: {spk.segment_count} segments, {spk.total_duration:.1f}s")
            return "\n".join(lines)

        # Default: full transcript
        lines = [
            f"Transcript: {transcript.path}",
            f"Duration: {transcript.duration:.1f}s",
            f"Language: {transcript.language}",
            f"Segments: {len(transcript.segments)}",
            "",
        ]
        for seg in transcript.segments:
            lines.append(f"  [{seg.start_time:.1f}-{seg.end_time:.1f}] {seg.speaker}: {seg.text}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /analyze-pdf <path> [tables | spec | summary | pages <range>]
    # ------------------------------------------------------------------
    async def analyze_pdf_handler(args: str) -> str:
        from lidco.multimodal.pdf_analyzer import PdfAnalyzer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /analyze-pdf <path> [tables | spec | summary | pages <range>]"

        path = parts[0]
        subcmd = parts[1] if len(parts) > 1 else "text"
        analyzer = PdfAnalyzer()

        if subcmd == "tables":
            tables = analyzer.extract_tables(path)
            lines = [f"Found {len(tables)} table(s):"]
            for tbl in tables:
                lines.append(f"  Page {tbl.page}: {len(tbl.rows)} rows, columns: {', '.join(tbl.header)}")
            return "\n".join(lines)

        if subcmd == "spec":
            spec = analyzer.parse_spec(path)
            lines = [f"Spec: {spec['title']}", f"Pages: {spec['page_count']}"]
            for sec in spec["sections"]:
                indent = "  " * sec["level"]
                lines.append(f"{indent}{sec['title']} (p.{sec['page']})")
            return "\n".join(lines)

        if subcmd == "summary":
            return analyzer.summary(path)

        if subcmd == "pages":
            page_range = parts[2] if len(parts) > 2 else "1-3"
            return analyzer.extract_text(path, pages=page_range)

        # Default: extract all text
        return analyzer.extract_text(path)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("analyze-image", "Analyse screenshots and images", analyze_image_handler))
    registry.register(SlashCommand("gen-diagram", "Generate Mermaid diagrams", gen_diagram_handler))
    registry.register(SlashCommand("transcribe", "Transcribe audio files", transcribe_handler))
    registry.register(SlashCommand("analyze-pdf", "Analyse PDF documents", analyze_pdf_handler))
