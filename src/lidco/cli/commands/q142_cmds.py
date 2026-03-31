"""Q142 CLI commands: /stream."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q142 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def stream_handler(args: str) -> str:
        from lidco.streaming.line_buffer import LineBuffer
        from lidco.streaming.log_tailer import LogTailer
        from lidco.streaming.multiplexer import StreamMultiplexer
        from lidco.streaming.paginator import OutputPaginator

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        # ---- buffer ----
        if sub == "buffer":
            buf: LineBuffer = _state.get("buffer")  # type: ignore[assignment]
            if buf is None:
                buf = LineBuffer()
                _state["buffer"] = buf

            sub2_parts = rest.strip().split(maxsplit=1)
            action = sub2_parts[0].lower() if sub2_parts and sub2_parts[0] else "status"
            action_rest = sub2_parts[1] if len(sub2_parts) > 1 else ""

            if action == "write":
                if not action_rest:
                    return "Usage: /stream buffer write <text>"
                buf.write(action_rest)
                return f"Buffered ({buf.line_count} lines total)"

            if action == "read":
                n = int(action_rest) if action_rest else None
                lines = buf.read_lines(n)
                if not lines:
                    return "Buffer is empty."
                return "\n".join(bl.text for bl in lines)

            if action == "new":
                lines = buf.read_new()
                if not lines:
                    return "No new lines."
                return "\n".join(bl.text for bl in lines)

            if action == "flush":
                lines = buf.flush()
                return f"Flushed {len(lines)} lines."

            if action == "search":
                if not action_rest:
                    return "Usage: /stream buffer search <pattern>"
                matches = buf.search(action_rest)
                if not matches:
                    return "No matches."
                return "\n".join(bl.text for bl in matches)

            if action == "clear":
                buf.clear()
                return "Buffer cleared."

            if action == "status":
                return f"Lines: {buf.line_count}, empty: {buf.is_empty}"

            return (
                "Usage: /stream buffer <action>\n"
                "  write <text>     -- buffer text\n"
                "  read [n]         -- read last n lines\n"
                "  new              -- read new lines\n"
                "  flush            -- flush all\n"
                "  search <pat>     -- regex search\n"
                "  clear            -- clear buffer\n"
                "  status           -- show stats"
            )

        # ---- tail ----
        if sub == "tail":
            tailer: LogTailer = _state.get("tailer")  # type: ignore[assignment]
            if tailer is None:
                tailer = LogTailer()
                _state["tailer"] = tailer

            sub2_parts = rest.strip().split(maxsplit=1)
            action = sub2_parts[0].lower() if sub2_parts and sub2_parts[0] else "show"
            action_rest = sub2_parts[1] if len(sub2_parts) > 1 else ""

            if action == "add":
                if not action_rest:
                    return "Usage: /stream tail add <text>"
                tailer.add_line(action_rest)
                return "Line added."

            if action == "show":
                n = int(action_rest) if action_rest else 10
                entries = tailer.tail(n)
                if not entries:
                    return "No lines."
                return "\n".join(e.line for e in entries)

            if action == "grep":
                if not action_rest:
                    return "Usage: /stream tail grep <pattern>"
                matches = tailer.grep(action_rest)
                if not matches:
                    return "No matches."
                return "\n".join(e.line for e in matches)

            if action == "followers":
                return f"Followers: {tailer.follower_count}"

            return (
                "Usage: /stream tail <action>\n"
                "  add <text>       -- add a line\n"
                "  show [n]         -- show last n lines\n"
                "  grep <pattern>   -- regex filter\n"
                "  followers        -- follower count"
            )

        # ---- mux ----
        if sub == "mux":
            mux: StreamMultiplexer = _state.get("mux")  # type: ignore[assignment]
            if mux is None:
                mux = StreamMultiplexer()
                _state["mux"] = mux

            sub2_parts = rest.strip().split(maxsplit=1)
            action = sub2_parts[0].lower() if sub2_parts and sub2_parts[0] else "status"
            action_rest = sub2_parts[1] if len(sub2_parts) > 1 else ""

            if action == "add":
                if not action_rest:
                    return "Usage: /stream mux add <name>"
                mux.add_stream(action_rest.strip())
                return f"Stream '{action_rest.strip()}' added."

            if action == "remove":
                if not action_rest:
                    return "Usage: /stream mux remove <name>"
                mux.remove_stream(action_rest.strip())
                return f"Stream '{action_rest.strip()}' removed."

            if action == "write":
                w_parts = action_rest.split(maxsplit=1)
                if len(w_parts) < 2:
                    return "Usage: /stream mux write <name> <content>"
                try:
                    mux.write(w_parts[0], w_parts[1])
                except KeyError as exc:
                    return str(exc)
                return f"Written to '{w_parts[0]}'."

            if action == "read":
                name = action_rest.strip()
                if name:
                    entries = mux.read_stream(name)
                else:
                    entries = mux.read_all()
                if not entries:
                    return "No entries."
                return "\n".join(
                    f"[{e.stream_name}] {e.content}" for e in entries
                )

            if action == "status":
                return (
                    f"Streams: {', '.join(mux.stream_names) or 'none'}\n"
                    f"Total entries: {mux.total_entries}"
                )

            return (
                "Usage: /stream mux <action>\n"
                "  add <name>               -- add stream\n"
                "  remove <name>            -- remove stream\n"
                "  write <name> <content>   -- write to stream\n"
                "  read [name]              -- read entries\n"
                "  status                   -- show stats"
            )

        # ---- page ----
        if sub == "page":
            sub2_parts = rest.strip().split(maxsplit=1)
            action = sub2_parts[0].lower() if sub2_parts and sub2_parts[0] else "status"
            action_rest = sub2_parts[1] if len(sub2_parts) > 1 else ""

            if action == "load":
                if not action_rest:
                    return "Usage: /stream page load <text>"
                lines = action_rest.split("\n")
                pag = OutputPaginator(lines, page_size=20)
                _state["paginator"] = pag
                return f"Loaded {len(lines)} lines, {pag.total_pages} pages."

            pag: OutputPaginator = _state.get("paginator")  # type: ignore[assignment]
            if pag is None:
                return "No content loaded. Use: /stream page load <text>"

            if action == "show":
                n = int(action_rest) if action_rest else pag.current_page_number
                pg = pag.page(n)
                header = f"[Page {pg.page_number}/{pg.total_pages}]"
                return header + "\n" + "\n".join(pg.content)

            if action == "next":
                pg = pag.next_page()
                header = f"[Page {pg.page_number}/{pg.total_pages}]"
                return header + "\n" + "\n".join(pg.content)

            if action == "prev":
                pg = pag.prev_page()
                header = f"[Page {pg.page_number}/{pg.total_pages}]"
                return header + "\n" + "\n".join(pg.content)

            if action == "first":
                pg = pag.first_page()
                header = f"[Page {pg.page_number}/{pg.total_pages}]"
                return header + "\n" + "\n".join(pg.content)

            if action == "last":
                pg = pag.last_page()
                header = f"[Page {pg.page_number}/{pg.total_pages}]"
                return header + "\n" + "\n".join(pg.content)

            if action == "search":
                if not action_rest:
                    return "Usage: /stream page search <pattern>"
                pages = pag.search_pages(action_rest)
                if not pages:
                    return "No matching pages."
                return f"Matches on pages: {', '.join(str(p) for p in pages)}"

            if action == "status":
                return f"Page {pag.current_page_number}/{pag.total_pages}"

            return (
                "Usage: /stream page <action>\n"
                "  load <text>      -- load content\n"
                "  show [n]         -- show page n\n"
                "  next / prev      -- navigate\n"
                "  first / last     -- jump to start/end\n"
                "  search <pat>     -- find pages with matches\n"
                "  status           -- current position"
            )

        return (
            "Usage: /stream <sub>\n"
            "  buffer <action>  -- line buffering\n"
            "  tail <action>    -- log tailing\n"
            "  mux <action>     -- stream multiplexing\n"
            "  page <action>    -- output pagination"
        )

    registry.register(
        SlashCommand("stream", "Output streaming & live display (Q142)", stream_handler)
    )
