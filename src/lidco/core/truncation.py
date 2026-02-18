"""Tool result truncation to reduce token usage in conversations."""

from __future__ import annotations


def truncate_tool_result(
    tool_name: str,
    output: str,
    max_chars: int = 12000,
) -> str:
    """Truncate a tool result to fit within token budget.

    Applies tool-specific truncation strategies:
    - file_read: keep first 80 + last 20 lines
    - grep/glob: keep first 30 matches
    - bash: keep first 100 + last 20 lines
    - others: hard truncate to max_chars
    """
    if len(output) <= max_chars:
        return output

    if tool_name == "file_read":
        return _truncate_file_read(output, head_lines=80, tail_lines=20)

    if tool_name in ("grep", "glob"):
        return _truncate_search_results(output, max_results=30)

    if tool_name == "bash":
        return _truncate_file_read(output, head_lines=100, tail_lines=20)

    if tool_name == "git":
        return _truncate_file_read(output, head_lines=100, tail_lines=20)

    return _truncate_plain(output, max_chars)


def _truncate_file_read(
    output: str,
    head_lines: int,
    tail_lines: int,
) -> str:
    """Truncate by keeping head and tail lines."""
    lines = output.splitlines()
    total = len(lines)

    if total <= head_lines + tail_lines:
        return output

    omitted = total - head_lines - tail_lines
    head = lines[:head_lines]
    tail = lines[-tail_lines:]

    return (
        "\n".join(head)
        + f"\n\n... ({omitted} lines omitted) ...\n\n"
        + "\n".join(tail)
    )


def _truncate_search_results(output: str, max_results: int) -> str:
    """Truncate search output by limiting result count."""
    lines = output.splitlines()
    total = len(lines)

    if total <= max_results:
        return output

    omitted = total - max_results
    kept = lines[:max_results]

    return "\n".join(kept) + f"\n\n... ({omitted} more matches) ..."


def _truncate_plain(output: str, max_chars: int) -> str:
    """Hard truncate with a marker at the cut point."""
    return output[:max_chars] + f"\n\n... (truncated, {len(output) - max_chars} chars omitted) ..."
