# LIDCO Project Bug Audit

**Generated:** 2026-02-26
**Method:** 5 parallel deep-read agents covering all layers + manual code verification
**Scope:** `src/lidco/` — agents, CLI, core, LLM, RAG, tools, index, server

---

## Summary

| Priority | Count | Description |
|----------|-------|-------------|
| P0       | 1     | Data corruption / encapsulation violation |
| P1       | 12    | Incorrect behavior, silent failures, crashes under certain conditions |
| P2       | 10    | Medium: resource leaks, race conditions, robustness |
| P3       | 8     | Low: dead code, cosmetic, minor inconsistencies |
| **Total**| **31**|  |

> **Status:** ALL FIXED. P0+P1 fixed in `27e73ff`. P2+P3 fixed in `e594a60`. P1-05 was false positive (timeout=3 already present). |

---

## P0 — Critical

### P0-01 · config_reloader.py:142-143 — Direct mutation of private LLM provider attributes
**File:** `src/lidco/core/config_reloader.py`
**Lines:** 142–143
**Issue:** Hot-reload propagates `llm.default_model` changes by mutating private attributes directly:
```python
self._session.llm._default_model = new.llm.default_model
self._session.llm._provider._default_model = new.llm.default_model
```
Bypasses all public API, breaks encapsulation, and is unsafe if the LLM is active (concurrent async request). If `ModelRouter` or `LiteLLMProvider` ever rename `_default_model`, this silently creates a new attribute and stops working.
**Fix:** Add `set_default_model(model: str)` setter to `ModelRouter` and `LiteLLMProvider`; call those instead.

---

## P1 — High

### P1-01 · app.py:401+412 — Streaming finally missing `set_token_callback(None)`
**File:** `src/lidco/cli/app.py`
**Lines:** 401, 412–418
**Issue:** Streaming mode registers `set_token_callback(on_tokens_stream)` at line 401, but the `finally` block (lines 412–418) only clears status/stream/tool_event/phase callbacks. `set_token_callback(None)` is never called. After an exception (or normal completion), the stale token callback fires on the next turn.
**Fix:** Add `orch.set_token_callback(None)` to the streaming `finally` block alongside the other four clears.

### P1-02 · config_reloader.py:147-150 — Missing Q15/Q16 AgentsConfig fields in hot-reload
**File:** `src/lidco/core/config_reloader.py`
**Lines:** 147–150
**Issue:** The `agent_fields` tuple was last updated before Q15/Q16. Five fields added since then are not propagated on config file change:
```python
agent_fields = (
    "auto_review", "auto_plan", "max_review_iterations",
    "agent_timeout", "max_iterations", "default",
    # MISSING: "plan_critique", "plan_revise", "plan_max_revisions",
    #          "plan_memory", "preplan_snapshot"
)
```
**Fix:** Add all five missing fields to `agent_fields`.

### P1-03 · commands.py:810 — `git add -u` return code not checked
**File:** `src/lidco/cli/commands.py`
**Line:** 810
**Issue:** `subprocess.run(["git", "add", "-u"], timeout=10)` is called without checking `returncode`. If staging fails (permission error, merge conflict, repo lock), the error is silently discarded and commit proceeds with incomplete/wrong staged files.
**Fix:** Check `result.returncode != 0` and return an error string.

### P1-04 · db.py:362 — `_get_file_id()` returns `0` instead of `None`
**File:** `src/lidco/index/db.py`
**Line:** 362
**Issue:** Private helper returns `0` for missing files while the public `get_file_id()` (line 144) returns `None`. `0` is indistinguishable from a valid AUTOINCREMENT ID on an empty table.
```python
return row["id"] if row else 0   # WRONG
```
**Fix:** `return row["id"] if row else None`

### P1-05 · graph.py:1041-1050 — `_grep_symbol` subprocess has no timeout
**File:** `src/lidco/agents/graph.py`
**Lines:** 1041–1050
**Issue:** `subprocess.run(["grep", ...])` in `_grep_symbol` has no `timeout=` argument. The caller wraps it in `asyncio.wait_for(..., timeout=3.0)` which cancels the asyncio task — but the executor thread and subprocess keep running (they are not cancellable). Large repos can cause this to run indefinitely, leaking a thread per invocation.
**Fix:** Add `timeout=3` to `subprocess.run()` and handle `subprocess.TimeoutExpired`.

### P1-06 · graph.py:1062 — `asyncio.get_event_loop()` deprecated in async context
**File:** `src/lidco/agents/graph.py`
**Line:** 1061
**Issue:** `_build_symbol_context` is an `async def`. Calling `asyncio.get_event_loop()` inside it emits `DeprecationWarning` in Python 3.10+ and raises `RuntimeError` in 3.12+ when no current event loop is set (in some execution environments). Should use `asyncio.get_running_loop()` which is guaranteed to return the running loop inside an async function.
**Fix:** Replace `asyncio.get_event_loop()` with `asyncio.get_running_loop()`.

### P1-07 · memory.py:269 — Truncation indicator appended beyond max_lines
**File:** `src/lidco/core/memory.py`
**Lines:** 274–278
**Issue:**
```python
if len(lines) > max_lines:
    lines = lines[:max_lines]
    lines.append("\n... (memory truncated)")  # now has max_lines+1 elements
```
The indicator is appended AFTER the slice, making the result `max_lines + 1` lines long. If callers rely on the limit, this off-by-one can cause unexpected LLM context overflows.
**Fix:** `lines = lines[:max_lines - 1]` before appending the indicator.

### P1-08 · test_runner.py:198 — Stderr lost on timeout in streaming mode
**File:** `src/lidco/tools/test_runner.py`
**Lines:** 97–110, 198–203
**Issue:** In `_stream_lines`, `asyncio.wait_for(_read(), timeout=timeout)` at line 198 raises `asyncio.TimeoutError` on timeout. This propagates out of `_stream_lines` and is caught by the outer `except asyncio.TimeoutError` at line 107, which returns immediately — never reaching `process.wait()` (line 199) or `stderr_raw = await process.stderr.read()` (line 202). Result: stderr is completely lost and the subprocess is never waited.
**Fix:** Wrap `asyncio.wait_for` in `_stream_lines` with its own try/except so `process.wait()` and stderr read always execute.

### P1-09 · coverage_reader.py:139 — `sum(data.values())` crashes with None values
**File:** `src/lidco/core/coverage_reader.py`
**Line:** 139
**Issue:**
```python
overall = round(sum(data.values()) / len(data), 1)
```
If any coverage value is `None` (which happens when a file has no measurable lines), `sum()` raises `TypeError`. The `if overall is None and data` guard on line 138 only checks the `""` key absence, not individual values.
**Fix:** Filter out None: `vals = [v for v in data.values() if v is not None]; overall = round(sum(vals) / len(vals), 1) if vals else None`.

### P1-10 · graph.py:794 — Parallel agent cloning assumes exact 3-arg constructor
**File:** `src/lidco/agents/graph.py`
**Lines:** 794–798
**Issue:** `type(template_agent)(config=..., llm=..., tool_registry=...)` works only if the agent class uses exactly the standard `BaseAgent.__init__` signature. Custom YAML agents or future subclasses with additional `__init__` parameters will raise `TypeError` at runtime when scheduled as parallel steps.
**Fix:** Add a `clone()` factory method to `BaseAgent` and use it here.

### P1-11 · commands.py:1401 — `result.metadata.get()` without None check
**File:** `src/lidco/cli/commands.py`
**Lines:** 1401–1406
**Issue:** After `GHPRTool.execute()`, the code calls `result.metadata.get(...)` directly. `ToolResult.metadata` can be `None` if the tool returns early on error. An `AttributeError` crash results.
**Fix:** `metadata = result.metadata or {}` before accessing `.get()`.

### P1-12 · litellm_provider.py:231 — `response.choices[0]` without empty-list guard
**File:** `src/lidco/llm/litellm_provider.py`
**Line:** 231
**Issue:** If the LLM API returns a response with an empty `choices` list (malformed response, rate-limit-related partial response), `response.choices[0]` raises `IndexError` with no useful error message.
**Fix:** Add `if not response.choices: raise ValueError(f"Empty choices in LLM response for model {model!r}")`.

---

## P2 — Medium

### P2-01 · bash.py:104 — `process.kill()` not wrapped in try-except
**File:** `src/lidco/tools/bash.py`
**Line:** 104
**Issue:** On `asyncio.TimeoutError`, `process.kill()` is called without try-except. If the process is already dead or the OS call fails, an exception prevents the `ToolResult` from being returned to the caller.
**Fix:** Wrap in `try: process.kill() except Exception: pass`.

### P2-02 · profiler.py:110 — Duplicate `import tempfile`
**File:** `src/lidco/tools/profiler.py`
**Line:** 110
**Issue:** `import tempfile` appears at line 100 and again at line 110 (inside a method). The inline import shadows the top-level one and is unnecessary.
**Fix:** Remove the inline import at line 110.

### P2-03 · profiler.py:137-161 — Stats temp file leaked on exception
**File:** `src/lidco/tools/profiler.py`
**Lines:** 111, 137–161
**Issue:** `tempfile.mktemp(suffix=".prof")` creates the path at line 111. If `subprocess.run()` or anything before line 146 (`Path(stats_file).unlink(...)`) raises an exception, the temp file remains on disk indefinitely.
**Fix:** Wrap from line 111 to end of method in `try: ... finally: Path(stats_file).unlink(missing_ok=True)`.

### P2-04 · stream_display.py:378 — Live object race on `finish()`
**File:** `src/lidco/cli/stream_display.py`
**Line:** 375–378
**Issue:** `_live.stop()` is called, then `_live = None`. Between those two lines, a callback can fire and access `self.live` (the property), receiving a stopped Live object and potentially crashing.
**Fix:** Set `self._live = None` before calling `stop()`, or use a local reference: `live, self._live = self._live, None; live.stop()`.

### P2-05 · config.py:370 — `__import__("os")` inline
**File:** `src/lidco/core/config.py`
**Line:** 370
**Issue:** `__import__("os")` is used inline to access the already-imported `os` module, making the code harder to read and confusing to static analysers.
**Fix:** Use the module-level `os` import directly.

### P2-06 · context_enricher.py:239 — DB not closed on exception in `from_project_dir()`
**File:** `src/lidco/index/context_enricher.py`
**Line:** 238–242
**Issue:** If `IndexDatabase(db_path)` succeeds but `cls(db)` raises, the database connection is never closed (no finally/with block).
**Fix:** `try: db = IndexDatabase(db_path); return cls(db) except Exception: db.close(); raise` or use a context manager.

### P2-07 · clarification.py:188-194 — Brittle JSON extraction
**File:** `src/lidco/core/clarification.py`
**Lines:** 188–194
**Issue:** JSON extraction from LLM response uses raw string slicing. `rindex("}")` finds the LAST `}` — if the response contains multiple JSON-like strings or trailing content, the wrong substring is extracted and `json.loads` crashes.
**Fix:** Use `re.search(r'\{.*\}', raw, re.DOTALL)` and wrap in try-except.

### P2-08 · retriever.py:122-128 — Empty search results are cached within TTL
**File:** `src/lidco/rag/retriever.py`
**Lines:** 122–128
**Issue:** If a query returns no results (empty index), an empty string is stored in the cache with a 30-second TTL. If the index is updated within that window, the stale empty result is returned from cache. No way to force a re-query.
**Fix:** Skip caching when `results` is empty, or use a shorter TTL for empty results.

### P2-09 · orchestrator.py:192-194 — Silent planning skip without logging
**File:** `src/lidco/agents/orchestrator.py`
**Lines:** 192–194
**Issue:** `_run_auto_planning()` returns early without logging when `planner` or `clarification_handler` is missing. The user doesn't know why planning was skipped.
**Fix:** Add `logger.info("Auto-planning skipped: planner/clarification not registered")`.

### P2-10 · plan_editor.py:106-108 — Reversed range silently produces empty selection
**File:** `src/lidco/cli/plan_editor.py`
**Lines:** 106–108
**Issue:** User inputs like `"5-1"` (reverse range) produce `range(5, 2)` which is empty. The plan editor silently selects nothing, then falls back to "approve all" at line 112. The user gets no error or indication.
**Fix:** Normalize: `if start > end: start, end = end, start`.

---

## P3 — Low

### P3-01 · retry.py:89-93 — Unreachable dead code
**File:** `src/lidco/llm/retry.py`
**Lines:** 89–93
**Issue:** The `raise LLMRetryExhausted(...)` after the for loop is dead code (the loop already raises on last attempt). The `# type: ignore` comments suggest this was intentional for the type checker, but it adds noise.
**Fix:** Add a comment `# pragma: no cover` or replace with `assert False, "unreachable"`.

### P3-02 · graph.py:1493 — Parallel steps parsed from user-edited plan text
**File:** `src/lidco/agents/graph.py`
**Line:** 1493
**Issue:** When user edits the plan, `_parse_parallel_steps(plan_response.content + "\n" + answer)` parses both the original plan AND the user's freeform edit text. If the user types `[PARALLEL]` in their edit note, it gets incorrectly parsed as a plan step.
**Fix:** Only parse parallel steps from the approved plan content, not user edits.

### P3-03 · base.py:671 — `get_system_prompt()` abstract but never called
**File:** `src/lidco/agents/base.py`
**Lines:** 670–672
**Issue:** `@abstractmethod get_system_prompt()` is defined but `build_system_prompt()` doesn't call it. Subclasses override both independently, making the abstract method a documentation artifact rather than a contract.
**Fix:** Either call `get_system_prompt()` from `build_system_prompt()` as a default implementation, or document the redundancy.

### P3-04 · orchestrator.py:264 — Hard-coded 5-message context window
**File:** `src/lidco/agents/orchestrator.py`
**Line:** 264
**Issue:** `recent = self._conversation_history[-5:]` silently drops context for long conversations. The value `5` is arbitrary and undocumented.
**Fix:** Extract as a configurable constant or class attribute.

### P3-05 · bm25.py:194-201 — Import attempted on every search call
**File:** `src/lidco/rag/bm25.py`
**Lines:** 194–201
**Issue:** Each call to `_rebuild_if_needed()` attempts `from rank_bm25 import BM25Okapi` if `_bm25 is None`. When `rank_bm25` is not installed, the import fails every time — no caching of the "unavailable" state.
**Fix:** Add a class-level flag `_rank_bm25_unavailable: bool = False`; set it on first ImportError.

### P3-06 · commands.py:687,711 — Silent search exception swallowing
**File:** `src/lidco/cli/commands.py`
**Lines:** 687, 711
**Issue:** `except Exception: pass` in the search handler silently discards failures from RAG retriever and symbol index. Users get no feedback when search backends fail.
**Fix:** `except Exception as e: logger.debug("Search source failed: %s", e)`.

### P3-07 · app.py:512 — Generic exception handling hides tracebacks
**File:** `src/lidco/cli/app.py`
**Line:** 512–513
**Issue:** `except Exception as e: renderer.error(f"Agent error: {e}")` swallows the full traceback. Debugging agent failures becomes difficult.
**Fix:** Add `logger.exception("Agent error")` before `renderer.error(...)`.

### P3-08 · config_reloader.py — Missing documentation for separate llm_providers loading
**File:** `src/lidco/core/config.py`
**Lines:** 195–197
**Issue:** `_SECTION_NAMES` does not include `llm_providers` because it is loaded separately in `_load_llm_providers()`. This inconsistency is confusing for contributors.
**Fix:** Add a comment in `_SECTION_NAMES` explaining the omission.

---

## Already Fixed in This Session (reference)

| Issue | Commit |
|-------|--------|
| bash.py: subprocess not killed on TimeoutError | `6fce2c6` |
| git.py: no try/except, process leaked on timeout | `6fce2c6` |
| retriever.py: fire-and-forget LLM task with discarded result | `6fce2c6` |
| app.py non-streaming: `set_token_callback(None)` missing | `6fce2c6` |
| graph.py: dead code in `_parse_parallel_steps` | `0f37f83` |
| orchestrator.py: incomplete ROUTER_SYSTEM_PROMPT | `0f37f83` |
| graph.py: custom routing keywords appended after built-ins | `0f37f83` |

---

## Fix Order (recommended)

1. **P0-01** — config_reloader private mutation (add setters)
2. **P1-01** — streaming finally missing token callback clear
3. **P1-02** — config_reloader missing new agent fields
4. **P1-03** — git add return code unchecked
5. **P1-04** — db.py returns 0 instead of None
6. **P1-07** — memory.py truncation off-by-one
7. **P1-08** — test_runner stderr lost on timeout
8. **P1-09** — coverage_reader division by zero
9. **P1-05** — grep_symbol subprocess no timeout
10. **P1-06** — get_event_loop() in async context
11. **P1-11** — commands.py metadata None check
12. **P1-12** — litellm_provider choices empty guard
13. **P2-01..P2-10** — medium priority, batch by file
14. **P3-01..P3-08** — low priority, cosmetic batch
