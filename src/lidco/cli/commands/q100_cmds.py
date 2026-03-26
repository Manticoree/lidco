"""
Q100 CLI commands — /kv, /mq, /state-machine, /retry

Registered via register_q100_commands(registry).
"""
from __future__ import annotations

import json
import shlex


def register_q100_commands(registry) -> None:
    """Register Q100 slash commands onto the given registry."""

    _kv_state: dict[str, object] = {}
    _mq_state: dict[str, object] = {}
    _sm_state: dict[str, object] = {}

    # ------------------------------------------------------------------
    # /kv — Key-Value Store
    # ------------------------------------------------------------------
    async def kv_handler(args: str) -> str:
        """
        Usage: /kv set <key> <value> [--ttl N]
               /kv get <key>
               /kv delete <key>
               /kv list [prefix]
               /kv flush
               /kv clear
        """
        from lidco.storage.kv_store import KVStore

        if "store" not in _kv_state:
            _kv_state["store"] = KVStore(path=None)  # in-memory for CLI session

        store: KVStore = _kv_state["store"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /kv <subcommand>\n"
                "  set <key> <value> [--ttl N]  store a value (optional TTL in seconds)\n"
                "  get <key>                    retrieve a value\n"
                "  delete <key>                 delete a key\n"
                "  list [prefix]                list all keys\n"
                "  flush                        remove expired keys\n"
                "  clear                        remove all keys"
            )

        subcmd = parts[0].lower()

        if subcmd == "set":
            if len(parts) < 3:
                return "Error: Usage: /kv set <key> <value> [--ttl N]"
            key, value_str = parts[1], parts[2]
            ttl = None
            i = 3
            while i < len(parts):
                if parts[i] == "--ttl" and i + 1 < len(parts):
                    i += 1
                    try:
                        ttl = float(parts[i])
                    except ValueError:
                        return f"Error: --ttl must be a number, got {parts[i]!r}"
                i += 1
            # Try JSON decode for structured values
            try:
                value = json.loads(value_str)
            except json.JSONDecodeError:
                value = value_str
            store.set(key, value, ttl=ttl)
            ttl_note = f" (TTL={ttl}s)" if ttl else ""
            return f"Set {key!r} = {value!r}{ttl_note}"

        if subcmd == "get":
            if len(parts) < 2:
                return "Error: key required. Usage: /kv get <key>"
            val = store.get(parts[1])
            if val is None:
                return f"Key '{parts[1]}' not found (or expired)."
            return f"{parts[1]} = {val!r}"

        if subcmd == "delete":
            if len(parts) < 2:
                return "Error: key required. Usage: /kv delete <key>"
            existed = store.delete(parts[1])
            return f"Deleted '{parts[1]}'." if existed else f"Key '{parts[1]}' not found."

        if subcmd == "list":
            prefix = parts[1] if len(parts) > 1 else None
            keys = store.list(prefix)
            if not keys:
                return "No keys stored." if not prefix else f"No keys with prefix '{prefix}'."
            return f"Keys ({len(keys)}):\n" + "\n".join(f"  {k}" for k in keys)

        if subcmd == "flush":
            count = store.flush_expired()
            return f"Flushed {count} expired key(s)."

        if subcmd == "clear":
            count = store.clear()
            return f"Cleared {count} key(s)."

        return f"Unknown subcommand '{subcmd}'. Use set/get/delete/list/flush/clear."

    registry.register_async("kv", "Persistent key-value store with TTL", kv_handler)

    # ------------------------------------------------------------------
    # /mq — Message Queue
    # ------------------------------------------------------------------
    async def mq_handler(args: str) -> str:
        """
        Usage: /mq enqueue <topic> <json_payload>
               /mq dequeue <topic>
               /mq ack <id>
               /mq nack <id>
               /mq topics
               /mq dlq [topic]
               /mq size <topic>
        """
        from lidco.messaging.queue import MessageQueue

        if "queue" not in _mq_state:
            _mq_state["queue"] = MessageQueue(path=None)

        mq: MessageQueue = _mq_state["queue"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /mq <subcommand>\n"
                "  enqueue <topic> <json>  add a message\n"
                "  dequeue <topic>         consume next message\n"
                "  ack <id>                acknowledge message\n"
                "  nack <id>               negative-acknowledge (re-enqueue or DLQ)\n"
                "  topics                  list all topics\n"
                "  dlq [topic]             show dead-letter messages\n"
                "  size <topic>            show queue size"
            )

        subcmd = parts[0].lower()

        if subcmd == "enqueue":
            if len(parts) < 3:
                return "Error: Usage: /mq enqueue <topic> <json_payload>"
            topic = parts[1]
            try:
                payload = json.loads(parts[2])
            except json.JSONDecodeError:
                payload = {"raw": parts[2]}
            msg = mq.enqueue(topic, payload)
            return f"Enqueued to '{topic}': id={msg.id[:8]}..."

        if subcmd == "dequeue":
            if len(parts) < 2:
                return "Error: topic required. Usage: /mq dequeue <topic>"
            msg = mq.dequeue(parts[1])
            if msg is None:
                return f"Topic '{parts[1]}' is empty."
            return f"Dequeued id={msg.id[:8]}  attempts={msg.attempts}  payload={msg.payload}"

        if subcmd == "ack":
            if len(parts) < 2:
                return "Error: message ID required."
            acked = mq.ack(parts[1])
            return f"Acknowledged {parts[1][:8]}." if acked else f"Message '{parts[1]}' not found in processing."

        if subcmd == "nack":
            if len(parts) < 2:
                return "Error: message ID required."
            nacked = mq.nack(parts[1])
            return f"Nack'd {parts[1][:8]}." if nacked else f"Message '{parts[1]}' not found in processing."

        if subcmd == "topics":
            topics = mq.list_topics()
            if not topics:
                return "No topics."
            return "Topics:\n" + "\n".join(f"  {t} (size={mq.queue_size(t)})" for t in topics)

        if subcmd == "dlq":
            topic = parts[1] if len(parts) > 1 else None
            dead = mq.dead_letters(topic)
            if not dead:
                return "No dead-letter messages."
            lines = [f"  [{m.topic}] id={m.id[:8]} attempts={m.attempts} payload={m.payload}" for m in dead]
            return f"Dead letters ({len(lines)}):\n" + "\n".join(lines)

        if subcmd == "size":
            if len(parts) < 2:
                return "Error: topic required."
            return f"Topic '{parts[1]}' size: {mq.queue_size(parts[1])}"

        return f"Unknown subcommand '{subcmd}'. Use enqueue/dequeue/ack/nack/topics/dlq/size."

    registry.register_async("mq", "Persistent message queue with dead-letter support", mq_handler)

    # ------------------------------------------------------------------
    # /state-machine
    # ------------------------------------------------------------------
    async def sm_handler(args: str) -> str:
        """
        Usage: /state-machine create <initial_state>
               /state-machine add-transition <from> <to> --on <trigger>
               /state-machine trigger <event>
               /state-machine status
               /state-machine history
               /state-machine reset
        """
        from lidco.core.state_machine import InvalidTransition, StateMachine

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /state-machine <subcommand>\n"
                "  create <initial>                        create state machine\n"
                "  add-transition <from> <to> --on <event> add a transition\n"
                "  trigger <event>                         fire an event\n"
                "  status                                  show current state\n"
                "  history                                 show transition history\n"
                "  reset                                   reset to initial state"
            )

        subcmd = parts[0].lower()

        if subcmd == "create":
            if len(parts) < 2:
                return "Error: initial state required. Usage: /state-machine create <state>"
            initial = parts[1]
            _sm_state["sm"] = StateMachine(initial)
            return f"State machine created. Initial state: '{initial}'"

        if "sm" not in _sm_state:
            return "No state machine created. Use: /state-machine create <initial>"

        sm: StateMachine = _sm_state["sm"]  # type: ignore[assignment]

        if subcmd == "add-transition":
            if len(parts) < 3:
                return "Error: Usage: /state-machine add-transition <from> <to> --on <trigger>"
            from_s, to_s = parts[1], parts[2]
            trigger_name = ""
            i = 3
            while i < len(parts):
                if parts[i] == "--on" and i + 1 < len(parts):
                    i += 1
                    trigger_name = parts[i]
                i += 1
            if not trigger_name:
                return "Error: --on <trigger> required."
            sm.add_transition(from_s, to_s, trigger_name)
            return f"Transition added: {from_s!r} --{trigger_name}--> {to_s!r}"

        if subcmd == "trigger":
            if len(parts) < 2:
                return "Error: event name required."
            try:
                new_state = sm.trigger(parts[1])
                return f"Triggered '{parts[1]}'. New state: '{new_state}'"
            except InvalidTransition as exc:
                return f"Error: {exc}"

        if subcmd == "status":
            available = sm.available_triggers()
            return (
                f"Current state: '{sm.current_state}'\n"
                f"Available triggers: {available or 'none'}"
            )

        if subcmd == "history":
            history = sm.history
            if not history:
                return "No transitions recorded."
            lines = [f"  {h.from_state!r} --{h.trigger}--> {h.to_state!r}" for h in history]
            return f"Transition history ({len(lines)}):\n" + "\n".join(lines)

        if subcmd == "reset":
            sm.reset()
            return f"State machine reset. Current state: '{sm.current_state}'"

        return f"Unknown subcommand '{subcmd}'. Use create/add-transition/trigger/status/history/reset."

    registry.register_async("state-machine", "Finite state machine", sm_handler)

    # ------------------------------------------------------------------
    # /retry
    # ------------------------------------------------------------------
    async def retry_handler(args: str) -> str:
        """
        Usage: /retry test [--attempts N] [--backoff TYPE] [--delay F]
               /retry policy [--attempts N] [--backoff TYPE] [--delay F]
        """
        from lidco.core.retry import RetryExhausted, RetryPolicy, retry_call

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /retry <subcommand>\n"
                "  test [--attempts N] [--backoff exponential|linear|fixed] [--delay F]\n"
                "     Run a demo function that fails N-1 times then succeeds.\n"
                "  policy [options]\n"
                "     Show computed delays for a policy."
            )

        subcmd = parts[0].lower()

        max_attempts = 3
        backoff = "exponential"
        base_delay = 0.0  # use 0 for fast demo
        i = 1
        while i < len(parts):
            if parts[i] == "--attempts" and i + 1 < len(parts):
                i += 1
                try:
                    max_attempts = int(parts[i])
                except ValueError:
                    pass
            elif parts[i] == "--backoff" and i + 1 < len(parts):
                i += 1
                backoff = parts[i]
            elif parts[i] == "--delay" and i + 1 < len(parts):
                i += 1
                try:
                    base_delay = float(parts[i])
                except ValueError:
                    pass
            i += 1

        policy = RetryPolicy(
            max_attempts=max_attempts,
            backoff=backoff,
            base_delay=base_delay,
            max_delay=base_delay * 10 if base_delay > 0 else 0.0,
            jitter=False,
        )

        if subcmd == "test":
            call_count = [0]
            fail_until = max_attempts - 1

            def flaky():
                call_count[0] += 1
                if call_count[0] <= fail_until:
                    raise RuntimeError(f"Simulated failure #{call_count[0]}")
                return f"success on attempt {call_count[0]}"

            try:
                result = retry_call(flaky, policy=policy)
                return (
                    f"Retry test complete:\n"
                    f"  Attempts: {call_count[0]}  Result: {result}\n"
                    f"  Policy: max={max_attempts} backoff={backoff} delay={base_delay}s"
                )
            except RetryExhausted as exc:
                return (
                    f"Retry exhausted after {exc.stats.attempts} attempt(s):\n"
                    f"  Last error: {exc.stats.last_error}"
                )

        if subcmd == "policy":
            lines = [f"Policy: max_attempts={max_attempts} backoff={backoff} base_delay={base_delay}s"]
            for attempt in range(max(max_attempts - 1, 1)):
                d = policy.compute_delay(attempt)
                lines.append(f"  After attempt {attempt+1}: sleep {d:.3f}s")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use test/policy."

    registry.register_async("retry", "Configurable retry with backoff policies", retry_handler)
