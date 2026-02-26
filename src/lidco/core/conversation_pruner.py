"""Conversation pruning to keep token usage under control.

Replaces old tool results with compact summaries and trims old assistant
messages so the conversation stays within a target character budget.

Also provides async conversation summarization: when a conversation grows
beyond a turn threshold, older turns are condensed into a compact paragraph
via an LLM call and replaced with a single summary system message.
"""

from __future__ import annotations

import logging

from lidco.llm.base import Message

logger = logging.getLogger(__name__)


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


# ── Tool Result Compression ──────────────────────────────────────────────────

_DEFAULT_MAX_TOOL_RESULT_CHARS = 2_000
_DEFAULT_KEEP_RECENT_TOOL_RESULTS = 3


def compress_tool_results(
    messages: list[Message],
    max_chars: int = _DEFAULT_MAX_TOOL_RESULT_CHARS,
    keep_recent: int = _DEFAULT_KEEP_RECENT_TOOL_RESULTS,
) -> list[Message]:
    """Reduce token cost of tool results before message-level pruning.

    Strategy:
    - The last *keep_recent* tool messages are kept, each truncated to
      *max_chars* if they exceed it.
    - Earlier tool messages are replaced with a compact one-line summary
      (identical to what ``prune_conversation`` does for old messages).

    Returns a new list — the original is never mutated.
    Only called when there is work to do (large results present).
    """
    if not messages:
        return []

    tool_indices = [i for i, m in enumerate(messages) if m.role == "tool"]
    if not tool_indices:
        return list(messages)

    # Check if any compression is needed — skip entirely when all results
    # are small and there are no old messages (nothing would change).
    old_indices = tool_indices[:-keep_recent] if len(tool_indices) > keep_recent else []
    any_large_recent = any(len(messages[i].content) > max_chars for i in tool_indices[-keep_recent:])
    any_large_old = any(len(messages[i].content) > 200 for i in old_indices)
    if not any_large_recent and not any_large_old:
        return list(messages)

    recent_set = set(tool_indices[-keep_recent:])

    result: list[Message] = []
    for i, msg in enumerate(messages):
        if msg.role != "tool":
            result.append(msg)
            continue

        content = msg.content
        if i in recent_set:
            if len(content) > max_chars:
                truncated = (
                    content[:max_chars]
                    + f"\n... [{len(content) - max_chars} chars truncated]"
                )
                result.append(
                    Message(
                        role=msg.role,
                        content=truncated,
                        tool_call_id=msg.tool_call_id,
                        name=msg.name,
                    )
                )
            else:
                result.append(msg)
        else:
            # Summarize old messages only when they're large enough to benefit.
            # Small old messages (≤200 chars) are cheaper to keep than replace.
            if len(content) > 200:
                result.append(_summarize_tool_message(msg))
            else:
                result.append(msg)

    return result


# ── Conversation Summarizer ──────────────────────────────────────────────────

_SUMMARIZE_SYSTEM = (
    "You are a concise conversation summarizer. "
    "Summarize the provided conversation turns in 3-5 sentences. "
    "Preserve: key decisions made, file names mentioned, errors found, "
    "solutions applied, and the overall task context. "
    "Be factual and brief."
)

_SUMMARIZE_TURNS_THRESHOLD = 20   # number of messages (not exchanges)
_SUMMARIZE_KEEP_RECENT = 6        # keep last N messages verbatim (keep even for assistant+tool pairs)
_SUMMARIZE_MIN_TURNS = 4          # minimum messages to summarize; below this the LLM call isn't worth it


def _needs_summarization(messages: list[Message], threshold: int) -> bool:
    """Return True when the conversation is long enough to warrant summarization."""
    return len(messages) > threshold


def _build_turns_text(messages: list[Message]) -> str:
    """Convert a list of messages to a readable text for the summarizer."""
    parts = []
    for msg in messages:
        role = msg.role.upper()
        # Truncate individual tool results to keep the prompt manageable
        content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
        parts.append(f"[{role}]: {content}")
    return "\n\n".join(parts)


def _has_existing_summary(messages: list[Message]) -> bool:
    """Return True if the conversation already contains a summary message.

    Prevents repeated summarization on every iteration once the threshold is
    crossed.  The check is intentionally shallow (first 5 messages only) since
    summaries are always injected near the start of the conversation.
    Checks both "system" and "assistant" roles since the summary may be stored
    as either depending on provider compatibility.
    """
    for msg in messages[:5]:
        if msg.role in ("system", "assistant") and "Earlier Conversation Summary" in msg.content:
            return True
    return False


async def summarize_conversation_if_needed(
    messages: list[Message],
    llm: object,
    *,
    model: str | None = None,
    threshold: int = _SUMMARIZE_TURNS_THRESHOLD,
    keep_recent: int = _SUMMARIZE_KEEP_RECENT,
    min_turns: int = _SUMMARIZE_MIN_TURNS,
) -> list[Message]:
    """Return a conversation with older turns replaced by an LLM summary.

    Only triggers when ``len(messages) > threshold`` AND no summary exists yet.
    Always keeps:
    - ``messages[0]``  — system prompt (index 0)
    - ``messages[1]``  — first user message (index 1)
    - ``messages[-keep_recent:]`` — most recent turns verbatim

    The turns in between are summarized into a single assistant message
    (avoids inserting a second system message which some providers reject).

    *llm* must implement ``BaseLLMProvider.complete()``.  If the summarization
    LLM call fails, the original messages are returned unchanged.
    """
    if not _needs_summarization(messages, threshold):
        return messages

    # Skip if already summarized — prevents a new LLM call every ~6 iterations
    if _has_existing_summary(messages):
        return messages

    # Boundaries: [0]=system, [1]=first-user, [2..-(keep_recent)]=to summarize,
    # [-(keep_recent)..]=keep verbatim
    head = messages[:2]  # system + first user
    to_summarize = messages[2:-keep_recent] if keep_recent else messages[2:]
    tail = messages[-keep_recent:] if keep_recent else []

    if not to_summarize or len(to_summarize) < min_turns:
        return messages

    turns_text = _build_turns_text(to_summarize)
    prompt = f"Summarize the following conversation turns:\n\n{turns_text}"

    try:
        summary_response = await llm.complete(  # type: ignore[attr-defined]
            [
                Message(role="system", content=_SUMMARIZE_SYSTEM),
                Message(role="user", content=prompt),
            ],
            model=model,
            temperature=0.0,
            max_tokens=512,
        )
        summary_text = (summary_response.content or "").strip()
    except Exception as e:
        logger.warning("Conversation summarization failed: %s", e)
        return messages

    # Use role="assistant" to avoid injecting a second system message, which
    # some providers reject or handle poorly in alternating-turn mode.
    summary_msg = Message(
        role="assistant",
        content=f"## Earlier Conversation Summary\n{summary_text}",
    )

    result = [*head, summary_msg, *tail]
    logger.debug(
        "Summarized %d messages → 1 summary + %d recent (total %d → %d)",
        len(to_summarize),
        len(tail),
        len(messages),
        len(result),
    )
    return result
