# LIDCO — Claude Code Guidance

Practical notes for Claude Code working on this project. Read before making changes.

## Architecture Overview

| File | Role |
|------|------|
| `src/lidco/cli/commands.py` | 13,000+ lines, 94 slash commands, ALL registered in `_register_builtins()` |
| `src/lidco/cli/app.py` | REPL loop, streaming, `process_slash_command()` |
| `src/lidco/core/session.py` | Session wiring: LLM + tools + agents + context |
| `src/lidco/agents/graph.py` | LangGraph orchestrator (plan → critique → revise → approve → execute → review) |
| `src/lidco/agents/base.py` | `BaseAgent` with ReAct loop, `build_system_prompt()` override |
| `src/lidco/core/config.py` | `AgentsConfig`, `LidcoConfig`, `LLMConfig`, `MemoryConfig` |
| `src/lidco/core/config_reloader.py` | 30s poll, propagates config changes via public setters |
| `src/lidco/tools/registry.py` | Tool registry, `create_default_registry()` |

## How to Add a New Slash Command

1. **Search for name conflicts first** (duplicate names silently override):
   ```bash
   grep -n 'SlashCommand("name"' src/lidco/cli/commands.py
   ```

2. **Add handler closure** inside `_register_builtins()` in `commands.py`. Follow the existing pattern:
   ```python
   async def mycommand_handler(args: str) -> str:
       # args is everything after the command name
       return "result text"
   ```

3. **Register it** at the end of `_register_builtins()`:
   ```python
   self.register(SlashCommand("mycommand", "Short description", mycommand_handler))
   ```

4. **Add tests** in `tests/unit/test_cli/` — see existing test files for patterns.

## How to Add a New Q-Quarter (Q54+)

1. Add a section in `ROADMAP.md` with the task table (task numbers, names, acceptance criteria).
2. Create `tests/unit/test_qNN/` directory with an `__init__.py`.
3. Create source modules in the appropriate `src/lidco/` subdirectory.
4. **Read the source file before writing tests** — constructor signatures and method names differ from spec.
5. Run `python -m pytest tests/unit/test_qNN/ -q` to verify all tests pass.
6. Update `MEMORY.md` with the new Q status, test count delta, and any new architecture notes.

## Known Gotchas (Critical)

**Duplicate SlashCommand names**: registering the same name twice silently overrides the original. The second registration wins. Always grep before adding.

**asyncio in tests**: use `asyncio.run(coro)`, NOT `asyncio.get_event_loop().run_until_complete(coro)`. The latter fails when `test_cli` runs first and closes the event loop.

**BaseTool abstract method**: every `BaseTool` subclass must implement `_run(self, **kwargs) -> ToolResult`. Missing it causes instantiation errors at import time.

**Module-level import fallbacks**: for optional deps (PIL, playwright, etc.) always add `AttrName = None` fallback after a failed import so tests can patch it:
```python
try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]
```

**Test API accuracy**: ALWAYS read the actual source file before writing tests. Constructor signatures, method names, and return types often differ from the spec description in ROADMAP.md.

**ConfigReloader threading**: uses `threading.Lock` for `_mtimes` dict — do not iterate `_mtimes` without acquiring the lock.

**`context` command registered twice**: `commands.py` registers `/context` at line ~1891 (project context) and again at ~9651 (context window gauge). The second registration overrides the first. This is intentional.

**`commit`, `model`, `agents`, `run`, `debug` registered twice**: same pattern — later registration overrides earlier. Check which line is active before debugging behavior.

## Test Conventions

- Tests live in `tests/unit/test_qNN/` where NN is the Q-number (e.g., `test_q54/`).
- Each Q typically has 2–10 test files, each testing one source module.
- Use `unittest.mock.patch` for external deps (subprocess, file I/O, PIL, network).
- For async handlers: `asyncio.run(handler(args))` — do not use `loop.run_until_complete`.
- Common fixtures are in `tests/conftest.py` (project-level) and `tests/unit/conftest.py` (unit-level).

## Test Run Commands

```bash
# Full suite (~5159+ tests, ~5 min)
python -m pytest -q

# Specific Q-quarter
python -m pytest tests/unit/test_qNN/ -q

# CLI tests only
python -m pytest tests/unit/test_cli/ -q

# With traceback on failure
python -m pytest tests/unit/test_qNN/ -v --tb=short
```

## Memory System

Auto memory lives in `~/.claude/projects/F--projects-lidco/memory/`:
- `MEMORY.md` — index file, **hard limit: 200 lines** (lines after 200 are silently cut).
- Detailed architecture notes go in separate topic files: `arch_core.md`, `arch_cli.md`, etc.
- After adding a new Q, update `MEMORY.md` with: Q status line, test count, new commands list, new attrs list.

## Tool Registry Notes

- `create_default_registry()` in `tools/registry.py` creates 29 tools.
- `ErrorReportTool` is added separately in `Session.__init__()` (not in registry factory).
- Total tools in a session: 30.
- Agent tool lists are explicit subsets — agents do NOT get accidental full-registry access.

## LLM Layer Notes

- GLM/OpenAI-compatible APIs: use `content: null` (not `""`) for assistant messages with `tool_calls`; omit `name` from `tool` role messages.
- Anthropic models: prompt caching applied automatically via `_maybe_apply_caching()`.
- `LLMRetryExhausted` raised by `with_retry()` on exhaustion; `ModelRouter` catches per-candidate and tries next.
- Stream fallback: both `RETRYABLE_EXCEPTIONS` and raw exceptions during stream iteration are wrapped in `LLMRetryExhausted` so `ModelRouter` falls back.
