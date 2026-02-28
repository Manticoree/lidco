# LIDCO Agent System Bug Audit — Round 2

**Generated:** 2026-02-27
**Method:** 4 parallel deep-read agents: orchestrator consistency, agent routing, graph state flow, session/LLM layer
**Scope:** `src/lidco/agents/`, `src/lidco/core/session.py`, `src/lidco/llm/`

---

## Summary

| Priority | Count |
|----------|-------|
| P0       | 1     |
| P1       | 14    |
| P2       | 14    |
| P3       | 6     |
| **Total**| **35**|

---

## P0 — Critical

### P0-01 · token_budget.record() never called — budget check always reads 0

**Files:** `src/lidco/cli/app.py:365`, `src/lidco/core/token_budget.py`
**Issue:** `lidco_session.token_budget.check_remaining()` is called every turn (app.py:365). But `token_budget.record(...)` is **never called anywhere** in the codebase. `_total_tokens` stays at 0 forever. `TokenBudgetExceeded` can never fire. Token counts shown in session summary come from the `_token_callback` accumulator, not from `token_budget`. The budget guard is dead code.
**Fix:** In `app.py`, after `on_tokens`/`on_tokens_stream` fires, also call `session.token_budget.record(tokens=total, prompt_tokens=p, completion_tokens=c, cost_usd=cost)`.

---

## P1 — High

### P1-01 · BaseOrchestrator missing no-ops for GraphOrchestrator-only setters → AttributeError on fallback

**File:** `src/lidco/agents/orchestrator.py:19`
**Issue:** `session.py` calls `orch.set_error_callback(...)`, `set_error_context_builder(...)`, `set_error_count_reader(...)`, `set_error_summary_builder(...)` without any guard. When LangGraph is not installed, `Orchestrator` is used instead of `GraphOrchestrator` — these methods don't exist on `Orchestrator`, causing `AttributeError` crash at session startup.
**Fix:** Add no-op stub methods to `BaseOrchestrator` for all 8 GraphOrchestrator-only setters: `set_error_callback`, `set_debug_mode`, `set_error_summary_builder`, `set_error_context_builder`, `set_error_count_reader`, `set_clarification_manager`, `set_memory_store`, `set_context_retriever`.

### P1-02 · `_plan_approved()` default `True` contradicts initial state `False`

**File:** `src/lidco/agents/graph.py:1495`
**Issue:** `handle()` initializes `"plan_approved": False` (line 1814), but `_plan_approved()` uses `state.get("plan_approved", True)` as default. If the key were ever missing, the guard would route to "sequential" instead of "rejected". Semantic inversion.
**Fix:** Change to `state.get("plan_approved", False)`.

### P1-03 · `_execute_planner_node` failure paths set `plan_approved: True` prematurely

**File:** `src/lidco/agents/graph.py:898, 961, 966`
**Issue:** When planner is not found, times out, or raises, nodes return `{**state, "plan_response": None, "plan_approved": True}`. This `plan_approved=True` flows through critique/revise nodes (which guard on `plan_response=None` and pass through), reaching `_approve_plan_node` with inconsistent state. Semantically wrong — `plan_approved` should only be set by `_approve_plan_node`.
**Fix:** Remove `"plan_approved": True` from all three failure branches; let `_approve_plan_node` set it.

### P1-04 · Parallel agent clones miss debug context injection

**File:** `src/lidco/agents/graph.py:791-802`
**Issue:** `_execute_agent_node` injects `## Active Debug Context` into planning agents and failure-site snippets into debugger via `prepend_system_context()`. The `_run_step` closure in `_execute_parallel_node` sets all callbacks on fresh clones but never calls `prepend_system_context`. In debug mode, all parallel agents run without the debug context injection.
**Fix:** After callback wiring in `_run_step`, add the same injection block from `_execute_agent_node` (lines 669-689).

### P1-05 · `restore_history()` has no input validation in both orchestrators

**Files:** `src/lidco/agents/graph.py:1899`, `src/lidco/agents/orchestrator.py:312`
**Issue:** Both `GraphOrchestrator.restore_history()` and `Orchestrator.restore_history()` do `self._conversation_history = list(messages)` with no validation. Corrupt import files with missing `role`/`content` keys cause deferred `KeyError` inside `_execute_agent_node` line 613 (`m['role']`, `m['content']`).
**Fix:** Filter to valid messages and log warning for skipped ones.

### P1-06 · `_critique_plan_node` max_tokens=400 — regression from planned 800

**File:** `src/lidco/agents/graph.py:1209, 1350`
**Issue:** MEMORY.md documents `max_tokens 400→800` change for Q15. Both `_critique_plan_node` (line 1209) and `_re_critique_plan_node` (line 1350) still use `max_tokens=400`. The 7-category critique prompt with up to 5 issues regularly exceeds 400 tokens, truncating the critique mid-sentence.
**Fix:** `max_tokens=800`, `timeout=45` in `_critique_plan_node`. Keep `max_tokens=400` for `_re_critique_plan_node` (lighter prompt).

### P1-07 · `asyncio.get_event_loop()` inside async context — raises RuntimeError on Python 3.13

**File:** `src/lidco/agents/graph.py:446, 1104`
**Issue:** Two `async def` methods call `asyncio.get_event_loop()` inside a running event loop. Python 3.10+ emits `DeprecationWarning`; Python 3.13 (project target) may raise `RuntimeError`. `_build_symbol_context` (line 1057) and `_approve_plan_node` (lines 1411, 1445) correctly use `asyncio.get_running_loop()`.
**Fix:** Replace both occurrences with `asyncio.get_running_loop()`.

### P1-08 · `build_coverage_context()` blocks the event loop in async node

**File:** `src/lidco/agents/graph.py:1120`
**Issue:** `_build_preplan_snapshot` is `async def`. It calls `build_coverage_context(self._project_dir)` directly — this reads `coverage.json` from disk (blocking I/O). `_run_git_log` (also blocking) is correctly wrapped in `run_in_executor` at line 1108–1110.
**Fix:** `cov_ctx = await loop.run_in_executor(None, build_coverage_context, self._project_dir)`.

### P1-09 · `_revise_plan_node` exception path doesn't clear `plan_critique`

**File:** `src/lidco/agents/graph.py:1321-1323`
**Issue:** On exception, `_revise_plan_node` returns `state` unchanged. `plan_critique` stays non-empty, `_re_critique_plan_node` runs again (incrementing round), and `_should_revise_again` loops back. With `_plan_max_revisions >= 2` and persistent LLM errors (e.g. rate limit), this burns N × critique tokens with no benefit.
**Fix:** `return {**state, "plan_critique": None}` in the exception handler.

### P1-10 · Mid-stream LLM disconnections bypass retry/fallback chain

**Files:** `src/lidco/llm/litellm_provider.py:304`, `src/lidco/llm/model_router.py:163-181`
**Issue:** `with_retry()` in `LiteLLMProvider.stream()` only wraps the initial `acompletion()` call. If the stream drops mid-iteration, the raw exception (not `LLMRetryExhausted`) propagates through `ModelRouter.stream()` — which only catches `LLMRetryExhausted` for fallback — and surfaces as a hard error to the user with no fallback model attempted.
**Fix:** Wrap the `async for chunk in response:` iteration in a try/except in `LiteLLMProvider.stream()` that re-raises transient errors as `LLMRetryExhausted`.

### P1-11 · `_PLANNING_AGENTS` missing `"security"` — debug injection skipped for security agent

**File:** `src/lidco/agents/graph.py:29`
**Issue:** `_PLANNING_AGENTS = frozenset({"coder","architect","tester","refactor","debugger","profiler"})`. The security agent performs multi-file changes and benefits from pre-planning context. It is absent without explanation (the code comment only mentions reviewer/researcher/docs). In debug mode, security agent runs without `## Active Debug Context` injection.
**Fix:** Add `"security"` to `_PLANNING_AGENTS`.

### P1-12 · Coder agent has no tool list — receives all tools including dangerous/irrelevant ones

**File:** `src/lidco/agents/builtin/coder.py:24`
**Issue:** No `tools=` key in `AgentConfig` → `_get_tools()` returns the full registry (18+ tools) including `run_profiler`, `rename_symbol`, `gh_pr`, `arch_diagram`. Coder is the most-invoked agent. Bloats tool context on every request; may invoke irrelevant tools.
**Fix:** Add explicit `tools=["file_read","file_write","file_edit","bash","glob","grep","git","ask_user","run_tests"]`.

### P1-13 · Refactor agent has no tool list — same as P1-12

**File:** `src/lidco/agents/builtin/refactor.py:24`
**Fix:** `tools=["file_read","file_write","file_edit","bash","glob","grep","git","run_tests","rename_symbol"]`.

### P1-14 · `set_debug_mode` never called on orchestrator during session init

**File:** `src/lidco/core/session.py:220-252`
**Issue:** `GraphOrchestrator._debug_mode` always starts `False`. The only way to enable it is `/debug on` in the CLI. There is no config-driven default. If LIDCO is restarted while debug was on in the previous session, debug injection is silently disabled until the user issues the command again.
**Fix:** Either add `agents.debug_mode: bool = False` to `AgentsConfig` and call `orch.set_debug_mode(self.config.agents.debug_mode)`, or document the runtime-only behavior.

---

## P2 — Medium

### P2-01 · `asyncio.Semaphore(0)` deadlocks all parallel steps

**File:** `src/lidco/agents/graph.py:788`
**Issue:** `asyncio.Semaphore(self._max_parallel_agents)`. If `max_parallel_agents=0` (e.g., misconfigured), the semaphore is size 0 and every `async with semaphore:` blocks forever — silent deadlock.
**Fix:** `asyncio.Semaphore(max(1, self._max_parallel_agents))` and clamp in `__init__`.

### P2-02 · Parallel steps beyond `max_parallel_agents` silently discarded

**File:** `src/lidco/agents/graph.py:747-748`
**Issue:** `steps_to_run = parallel_steps[:self._max_parallel_agents]` hard-cuts the list. If plan has 6 steps and max=3, the last 3 are silently dropped with no warning. Users get partial plan execution with no indication.
**Fix:** Log a warning. Consider running all steps with semaphore as concurrency limiter (not count cap).

### P2-03 · `_parse_parallel_steps` no deduplication; `[PARALLEL]`-as-prefix drops step

**File:** `src/lidco/agents/graph.py:968-987`
**Issue:** (1) Duplicate steps in plan → same agent runs same operation twice, possible file write race. (2) If `[PARALLEL]` is at the START of a line (e.g. `[PARALLEL] Do X`), `stripped[:idx]` is empty string → step silently dropped.
**Fix:** Add `return list(dict.fromkeys(steps))` for dedup. Also strip the marker from either end.

### P2-04 · `_save_approved_plan` (sync) blocks event loop in async node

**File:** `src/lidco/agents/graph.py:1435, 1441, 1455, 1467, 1490`
**Issue:** Called directly from `_approve_plan_node` (async). Calls `self._memory_store.add(...)` which writes to SQLite — blocking I/O.
**Fix:** `await asyncio.get_running_loop().run_in_executor(None, self._save_approved_plan, msg, plan)`.

### P2-05 · `_update_rag_index` (sync) blocks event loop in async `_finalize_node`

**File:** `src/lidco/agents/graph.py:1697-1698`
**Issue:** `_finalize_node` calls `self._update_rag_index(state)` directly. This calls `context_retriever.update_file()` in a loop — ChromaDB/BM25 updates are blocking I/O.
**Fix:** Wrap in `run_in_executor`.

### P2-06 · No shared `_propagate_callbacks` helper — identical block copy-pasted 4 times

**File:** `src/lidco/agents/graph.py:658-665, 901-908, 1523-1530, 794-802`
**Issue:** The 8-line callback wiring block is duplicated in `_execute_agent_node`, `_execute_planner_node`, `_auto_review_node`, and `_run_step`. `_auto_review_node` already has a different order (B9). Every new callback must be added in 4 places.
**Fix:** Extract `_propagate_callbacks(self, agent: BaseAgent) -> None` and call it in all 4 sites.

### P2-07 · Architect agent missing `tree`, `arch_diagram`, `find_test_gaps` tools

**File:** `src/lidco/agents/builtin/architect.py:30`
**Issue:** `tools=["file_read","glob","grep","ask_user"]`. The planner gets `arch_diagram`, `tree`, `find_test_gaps` for the same kind of codebase analysis. Architect lacks them.
**Fix:** `tools=["file_read","glob","grep","ask_user","tree","arch_diagram","find_test_gaps"]`.

### P2-08 · YAML agent loader only loads `.yaml`, ignores `.yml`

**File:** `src/lidco/agents/loader.py:117`
**Issue:** `directory.glob("*.yaml")` — `.yml` files are silently ignored.
**Fix:** `list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))`.

### P2-09 · YAML loader uses `Path.cwd()` instead of `project_dir`

**File:** `src/lidco/agents/loader.py:109`
**Issue:** `Path.cwd() / ".lidco" / "agents"` evaluated at call time. If started with `--project-dir /some/path`, finds wrong project's agents.
**Fix:** Pass `project_dir` from `Session._register_yaml_agents()` to `discover_yaml_agents()`.

### P2-10 · `config_reloader`: `agents.default` change never propagated to orchestrator

**File:** `src/lidco/core/config_reloader.py:146-154`
**Issue:** `agent_fields` includes `"default"` and `"max_iterations"` but neither has a propagation block. Hot-reloading to change the default agent is silently ignored.
**Fix:** Add `orch._default_agent = new.agents.default` to propagation. Remove `"max_iterations"` (per-agent, not live-propagatable).

### P2-11 · `config_reloader` propagates 4 fields via private attribute mutation

**File:** `src/lidco/core/config_reloader.py:167-174`
**Issue:** `orch._agent_timeout = ...`, `orch._auto_review = ...` etc. with `# type: ignore`. Crashes silently on fallback `Orchestrator` (attribute doesn't exist). Bypasses the public setter interface.
**Fix:** Add public setters to `BaseOrchestrator` / `Orchestrator` for these fields.

### P2-12 · Token accumulation in critique/revise may miss `total_tokens` key

**File:** `src/lidco/agents/graph.py:1229, 1312, 1361`
**Issue:** `critique_response.usage.get("total_tokens", 0)` — Anthropic and some providers report `prompt_tokens + completion_tokens` but not `total_tokens`. Silently accounts 0 tokens for all critique/revise LLM calls.
**Fix:** `total = usage.get("total_tokens") or (usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))`.

### P2-13 · `if cost:` guard is falsy for 0.0 — zero-cost models fall through incorrectly

**File:** `src/lidco/llm/litellm_provider.py:105`
**Issue:** `if cost:` returns `False` for `0.0` (local/Ollama models). Falls through to manual table unnecessarily. Negative costs (refunds from some providers) are silently accepted.
**Fix:** `if cost is not None and cost >= 0.0: return cost`.

### P2-14 · `_auto_review_node` sets callbacks in different order than other nodes

**File:** `src/lidco/agents/graph.py:1523-1530`
**Issue:** `set_tool_event_callback` and `set_clarification_handler` are swapped vs. `_execute_agent_node` order. No runtime error today, but signals callback blocks are out of sync. Fixed by P2-06.

---

## P3 — Low

### P3-01 · `TokenUsage` fields mutated in-place in `_execute_parallel_node`

**File:** `src/lidco/agents/graph.py:843-844`
**Issue:** `merged_usage.prompt_tokens = ...` mutates a dataclass instance. Violates project immutability rule.
**Fix:** Construct `TokenUsage(prompt_tokens=..., completion_tokens=..., total_tokens=..., total_cost_usd=...)` directly.

### P3-02 · Variable `l` in `_build_review_patterns_hint` — PEP 8 violation

**File:** `src/lidco/agents/graph.py:1668`
**Fix:** Rename to `line` or `entry`.

### P3-03 · Redundant `import asyncio` inside `_pre_analyze_node` function body

**File:** `src/lidco/agents/graph.py:443`
**Issue:** `asyncio` is already imported at module level (line 5).
**Fix:** Remove the inline import.

### P3-04 · Tester agent doesn't use `run_tests` tool — uses `bash` to run pytest directly

**File:** `src/lidco/agents/builtin/tester.py:33`
**Issue:** `tools=["file_read","file_write","file_edit","bash","glob","grep"]` — no `run_tests`. The tester uses `bash` to run pytest, bypassing the structured output parsing that `RunTestsTool` provides (pass/fail counts, FAILED list, coverage table) that the QA agent already benefits from.
**Fix:** Add `"run_tests"` to tester tools list.

### P3-05 · Router prompt has no positive keyword for `"coder"` — description ambiguity with debugger

**File:** `src/lidco/agents/builtin/coder.py:25`, `src/lidco/agents/graph.py:107`
**Issue:** Coder is `else`-only. Coder description says "Code writing, debugging, modification" — the word "debugging" may confuse small routing models that score by description similarity.
**Fix:** Change description to "Code writing and file modification." Add explicit `implement/create/write→coder` to router rules.

### P3-06 · Debugger `AgentConfig` has no explicit tool list — `error_report` not guaranteed

**File:** `src/lidco/agents/builtin/debugger.py:84`
**Issue:** Debugger has no `tools=` key, gets full registry. System prompt instructs it to call `run_tests` and `error_report`. `error_report` is registered in `Session.__init__()` separately from `create_default_registry()` — not guaranteed in standalone/test contexts.
**Note:** Low priority since the full registry includes both tools in production. But explicit is better.

---

## Round-3 Bugs (found in session 10, fixed in same session)

| ID | File | Issue | Fix |
|----|------|-------|-----|
| R3-01 | `llm/litellm_provider.py:350` | Only `RETRYABLE_EXCEPTIONS` caught during stream iteration; non-retryable errors (malformed chunks, AttributeError) leak as raw exceptions, bypassing ModelRouter fallback | Added `except Exception: raise LLMRetryExhausted(...)` |
| R3-02 | `llm/router.py:174` | Stream fallback only catches `LLMRetryExhausted`; raw exceptions bypass fallback chain entirely | Added `except Exception` block after `LLMRetryExhausted` |
| R3-03 | `agents/base.py:396` | Only `LLMRetryExhausted` recorded in error_callback; non-retryable LLM errors invisible in `/errors` | Changed guard from `isinstance(..., LLMRetryExhausted)` to unconditional |
| R3-04 | `core/config.py`, `core/session.py:143`, `core/config_reloader.py` | `debug_mode` not in `AgentsConfig`; always False on startup, not config-driven (P1-14) | Added `debug_mode: bool = False` to AgentsConfig; session reads from config + calls `set_debug_mode`; config_reloader propagates changes |

> Status: ALL FIXED in session 10.

## Fix Priority Order

1. **P0-01** — wire `token_budget.record()` in app.py callbacks
2. **P1-01** — add no-op stubs to `BaseOrchestrator` (prevents crash on fallback)
3. **P1-06** — restore `max_tokens=800` in `_critique_plan_node` (regression fix)
4. **P1-02/P1-03** — `_plan_approved` default + planner failure state
5. **P1-07** — `asyncio.get_running_loop()` (Python 3.13 crash)
6. **P1-08/P2-04/P2-05** — async node blocking I/O
7. **P1-04** — parallel clone debug injection
8. **P1-09** — revise exception clears critique
9. **P1-05** — restore_history validation
10. **P1-10** — mid-stream error fallback
11. **P2-01** — Semaphore(0) deadlock guard
12. **P2-06** — extract `_propagate_callbacks`
13. **P2-02/P2-03** — parallel step drop warning + dedup
14. **P1-11/P1-12/P1-13** — agent tool lists
15. **P2-07..P2-14** — medium fixes in batch
16. **P3-01..P3-06** — low priority cleanup
