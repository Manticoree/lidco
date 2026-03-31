"""Q139 CLI commands: /ui progress/table/status/report."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q139 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def ui_handler(args: str) -> str:
        from lidco.ui.progress_bar import ProgressBar
        from lidco.ui.table_formatter import TableFormatter
        from lidco.ui.status_formatter import StatusFormatter
        from lidco.ui.report_renderer import ReportRenderer

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "progress":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else "demo"
            if action == "demo":
                bar = ProgressBar(total=20, label="Demo")
                bar.update(13)
                return bar.render()
            if action == "create":
                # /ui progress create <total> [label]
                create_parts = (sub_parts[1] if len(sub_parts) > 1 else "").split(maxsplit=1)
                try:
                    total = int(create_parts[0])
                except (ValueError, IndexError):
                    return "Usage: /ui progress create <total> [label]"
                label = create_parts[1] if len(create_parts) > 1 else ""
                bar = ProgressBar(total=total, label=label)
                _state["progress"] = bar
                return f"Progress bar created: total={total}, label={label!r}"
            if action == "advance":
                bar = _state.get("progress")
                if bar is None:
                    return "No active progress bar. Use /ui progress create <total> first."
                n = 1
                if len(sub_parts) > 1:
                    try:
                        n = int(sub_parts[1])
                    except ValueError:
                        pass
                bar.advance(n)  # type: ignore[union-attr]
                return bar.render()  # type: ignore[union-attr]
            if action == "finish":
                bar = _state.get("progress")
                if bar is None:
                    return "No active progress bar."
                bar.finish()  # type: ignore[union-attr]
                return bar.render()  # type: ignore[union-attr]
            if action == "show":
                bar = _state.get("progress")
                if bar is None:
                    return "No active progress bar."
                return bar.render()  # type: ignore[union-attr]
            return "Usage: /ui progress demo|create|advance|finish|show"

        if sub == "table":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else "demo"
            if action == "demo":
                tf = TableFormatter(["Name", "Value", "Status"])
                tf.add_row("alpha", "100", "OK")
                tf.add_row("beta", "200", "WARN")
                tf.add_separator()
                tf.add_row("gamma", "300", "ERR")
                return tf.render()
            if action == "markdown":
                tf = TableFormatter(["Name", "Value", "Status"])
                tf.add_row("alpha", "100", "OK")
                tf.add_row("beta", "200", "WARN")
                return tf.render_markdown()
            if action == "compact":
                tf = TableFormatter(["Name", "Value", "Status"])
                tf.add_row("alpha", "100", "OK")
                tf.add_row("beta", "200", "WARN")
                return tf.render_compact()
            return "Usage: /ui table demo|markdown|compact"

        if sub == "status":
            sf = StatusFormatter()
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else "demo"
            detail = sub_parts[1] if len(sub_parts) > 1 else None
            if action == "demo":
                lines = [
                    sf.success("Build", "completed in 2.3s"),
                    sf.warning("Lint", "3 warnings"),
                    sf.error("Tests", "2 failures"),
                    sf.info("Coverage", "87%"),
                ]
                return "\n".join(lines)
            if action == "duration":
                try:
                    secs = float(detail) if detail else 0.0
                except ValueError:
                    secs = 0.0
                return sf.format_duration(secs)
            if action == "bytes":
                try:
                    n = int(detail) if detail else 0
                except ValueError:
                    n = 0
                return sf.format_bytes(n)
            return "Usage: /ui status demo|duration <s>|bytes <n>"

        if sub == "report":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else "demo"
            if action == "demo":
                rr = ReportRenderer("Demo Report")
                rr.add_section("Overview", "This is a demo report.")
                rr.add_key_value("Version", "1.0.0")
                rr.add_list(["Item A", "Item B", "Item C"])
                rr.add_divider()
                rr.add_section("Details", "Additional information here.", level=2)
                return rr.render()
            if action == "markdown":
                rr = ReportRenderer("Demo Report")
                rr.add_section("Overview", "This is a demo report.")
                rr.add_key_value("Version", "1.0.0")
                rr.add_list(["Item A", "Item B"])
                return rr.render_markdown()
            if action == "summary":
                rr = ReportRenderer("Quick Report")
                rr.add_section("S1", "content")
                rr.add_section("S2", "content")
                return rr.summary()
            return "Usage: /ui report demo|markdown|summary"

        return (
            "Usage: /ui <sub>\n"
            "  progress demo|create|advance|finish|show\n"
            "  table demo|markdown|compact\n"
            "  status demo|duration <s>|bytes <n>\n"
            "  report demo|markdown|summary"
        )

    registry.register(SlashCommand("ui", "Rich output formatting & progress display (Q139)", ui_handler))
