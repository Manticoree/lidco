"""Conversation pruning to keep token usage under control.

Replaces old tool results with compact summaries and trims old assistant
messages so the conversation stays within a target character budget.
"""

from __future__ import annotations

from lidco.llm.base import Message


def prune_conversation(
    messages: list[Message],
    max_chars: int = 80_000,
    keep_recent_exchanges: int = 3,
) -> list[Message]:
    """Return a pruned copy of *messages* that fits within *max_chars*.

    Strategy:
    1. The system prompt (messages[0]) is always kept in full.
    2. The last *keep_recent_exchanges* assistant+tool exchange groups
       are kept in full.
    3. Older tool results are replaced with a one-line summary.
    4. Older assistant messages are trimmed to the first 200 chars.

    Returns a new list — the original is never mutated.
    """
    if not messages:
        return []

    total_chars = sum(len(m.content) for m in messages)
    if total_chars <= max_chars:
        return list(messages)

    # Identify the boundary: keep system (index 0) + user (index 1)
    # and the last N exchange cycles untouched.
    # An "exchange" = one assistant message + its following tool messages.
    boundary = _find_keep_boundary(messages, keep_recent_exchanges)

    pruned: list[Message] = []
    for i, msg in enumerate(messages):
        if i == 0:
            # System prompt — always keep
            pruned.append(msg)
        elif i >= boundary:
            # Recent messages — keep in full
            pruned.append(msg)
        elif msg.role == "tool":
            pruned.append(_summarize_tool_message(msg))
        elif msg.role == "assistant":
            pruned.append(_trim_assistant_message(msg))
        else:
            # user messages in middle — keep (usually just one)
            pruned.append(msg)

    return pruned


def _find_keep_boundary(
    messages: list[Message],
    keep_recent_exchanges: int,
) -> int:
    """Find the index from which to keep messages in full.

    Walks backwards counting assistant messages to identify the start
    of the last *keep_recent_exchanges* exchange cycles.
    """
    assistant_count = 0
    for i in range(len(messages) - 1, 0, -1):
        if messages[i].role == "assistant":
            assistant_count += 1
            if assistant_count >= keep_recent_exchanges:
                return i
    # Not enough exchanges to prune — keep everything
    return 1


def _summarize_tool_message(msg: Message) -> Message:
    """Replace a tool result with a compact summary line."""
    tool_name = msg.name or "tool"
    content = msg.content
    line_count = content.count("\n") + 1

    # Extract a brief hint from the first line
    first_line = content.split("\n", 1)[0][:80]

    summary = f"[{tool_name}: {line_count} lines | {first_line}...]"

    return Message(
        role=msg.role,
        content=summary,
        tool_call_id=msg.tool_call_id,
        name=msg.name,
    )


def _trim_assistant_message(msg: Message, max_chars: int = 200) -> Message:
    """Trim an assistant message to the first *max_chars* characters."""
    content = msg.content
    if len(content) <= max_chars:
        return msg

    trimmed = content[:max_chars] + "... (trimmed)"

    return Message(
        role=msg.role,
        content=trimmed,
        tool_calls=msg.tool_calls,
        tool_call_id=msg.tool_call_id,
        name=msg.name,
    )
