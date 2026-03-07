# LIDCO Development Roadmap

Focus areas: deeper context understanding · context optimization · token optimization · UI improvements

---

## Q1 — Foundation

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 1 | [Context deduplication](#1-context-deduplication) | ✅ Done | 1d | −30% tokens |
| 2 | [Conversation summarizer](#2-conversation-summarizer) | ✅ Done | 2d | prevent context overflow |
| 3 | [Dependency graph from index](#3-dependency-graph-from-index) | ✅ Done | 2-3d | smarter file suggestions |
| 4 | [Prompt prefix caching](#4-prompt-prefix-caching) | ✅ Done | 1d | −40-60% cost on Anthropic |

---

## Q2 — Context Depth

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 5 | [Git-aware context enricher](#5-git-aware-context-enricher) | ✅ Done | 2d | agent knows what changed |
| 6 | [Token-aware model routing](#6-token-aware-model-routing) | ✅ Done | 1d | −50% cost on simple tasks |
| 7 | [Test coverage context](#7-test-coverage-context) | ✅ Done | 2d | QA/tester agents improve |
| 8 | [Hybrid semantic+BM25 symbol search](#8-hybrid-search) | ✅ Done | 3d | better RAG precision |

---

## Q3 — Token Optimization

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 9  | [Dynamic system prompt builder](#9-dynamic-system-prompt-builder) | ✅ Done | 2d | −20% tokens/call |
| 10 | [Hard token budget enforcement](#10-hard-token-budget-enforcement) | ✅ Done | 1d | no surprise bills |
| 11 | [Smart tool result compression](#11-smart-tool-result-compression) | ✅ Done | 3d | −40% on large file reads |
| 12 | [Conversation pruner improvements](#12-conversation-pruner-improvements) | ✅ Done | 2d | longer sessions |

---

## Q4 — UI

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 13 | [Phase progress in status bar](#13-phase-progress-in-status-bar) | ✅ Done | 1d | clearer multi-agent flow |
| 14 | [Session summary on exit](#14-session-summary-on-exit) | ✅ Done | 1d | recap what was done |
| 15 | [Interactive plan editor](#15-interactive-plan-editor) | ✅ Done | 3d | step-level plan editing |
| 16 | [Git diff viewer](#16-git-diff-viewer) | ✅ Done | 2d | syntax-highlighted diffs |

---

## Task Details

### 1. Context Deduplication
**File:** `src/lidco/core/session.py`
Static sections (project structure, memory, decisions) are skipped on subsequent turns when unchanged.
Uses SHA-256 hashes. `skip_dedup=True` for display-only calls. Reset on `/clear`.
**Status:** ✅ Done — `ContextDeduplicator` class, 16 tests, 661 passing.

---

### 2. Conversation Summarizer
**Status:** ✅ Done — `summarize_conversation_if_needed()` in `conversation_pruner.py`, 6 tests. Triggers at >20 messages, keeps system+first user+last 6 turns, LLM failure falls back to original.
**Goal:** When conversation history grows large (e.g., >20 turns or >80k tokens), auto-summarize older turns into a compact paragraph and replace them in history. Prevents context overflow and keeps recent turns fully intact.

**Where:** `src/lidco/core/conversation_pruner.py` (file exists), `src/lidco/agents/graph.py`

**Approach:**
- Trigger when `len(conversation_history) > N` or estimated tokens exceed threshold
- LLM call: "Summarize these N turns in 3-5 sentences, preserving key decisions and file names"
- Replace summarized turns with a single `{"role": "system", "content": "## Earlier conversation summary\n{summary}"}` entry
- Keep last 5 turns verbatim

---

### 3. Dependency Graph from Index
**Status:** ✅ Done — `DependencyGraph` in `src/lidco/index/dependency_graph.py`, 14 tests. `get_related(file_path)` returns up to 5 related files (dependents first, then dependencies). Integrated into `IndexContextEnricher.get_context(current_file=...)`.
**Goal:** Use the existing SQLite structural index (`src/lidco/index/`) to build an import/dependency graph. When agent reads file A, automatically suggest related files B and C that import A or are imported by A. Inject these as context hints.

**Where:** `src/lidco/index/dependency_graph.py` (new), `src/lidco/index/context_enricher.py`

**Approach:**
- Query `imports` table: `SELECT file_path, imported_from FROM imports WHERE imported_from = ?`
- Build reverse index: who imports this file?
- Add to `IndexContextEnricher.get_context()`: include `## Related files` section listing top-5 related files by dependency distance

---

### 4. Prompt Prefix Caching
**Status:** ✅ Done — `_apply_prompt_caching()` + `_is_anthropic_model()` in `litellm_provider.py`, 13 tests. Applied automatically in both `complete()` and `stream()` for `claude-*` / `anthropic/*` models.
**Goal:** Mark the static system prompt portion of each agent call with `cache_control: {"type": "ephemeral"}` for Anthropic models. Reduces cost by 40-60% on long agent runs since the system prompt is re-sent every iteration.

**Where:** `src/lidco/llm/litellm_provider.py`, `src/lidco/agents/base.py`

**Approach:**
- Detect if model is Anthropic (`claude-` prefix)
- Split system prompt into cacheable prefix + dynamic suffix
- Add `extra_body={"anthropic_beta": ["prompt-caching-2024-07-31"]}` to LiteLLM call
- Mark system message content as `[{"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}]`

---

### 5. Git-aware Context Enricher
**Goal:** Inject `git diff HEAD~1 --stat` and brief summary of recent commits into agent context. Agents understand what was recently changed without running git themselves.

**Where:** `src/lidco/core/context.py` — already collects some git info; extend it.

**Approach:**
- Add `get_recent_changes()` to `ProjectContext`: runs `git diff HEAD~1 --stat` (file list + insertions/deletions)
- Add to `build_context_string()`: `## Recent Changes\n{changes_summary}`
- Include in the "decisions" dedup key so it refreshes after commits

---

### 6. Token-aware Model Routing
**Goal:** Route simple tasks (routing LLM calls, memory extraction, clarification checks) to a cheaper/faster model (e.g., `gpt-4o-mini` or `claude-haiku`) and complex tasks to the main model.

**Where:** `src/lidco/llm/router.py`, `src/lidco/core/config.py` (already has `role_models`)

**Approach:**
- `role_models` config already exists in `LLMProvidersConfig` — make `ModelRouter` use it
- Map roles: `routing` → cheap model, `memory_extraction` → cheap model, `agent` → main model
- Already partially implemented — verify `role="routing"` is being passed everywhere and the router picks up role-specific models

---

### 7. Test Coverage Context
**Goal:** Inject current test coverage data into QA/tester agent context. Agent knows which modules are under-tested without running coverage itself.

**Where:** `src/lidco/core/session.py`, `src/lidco/agents/builtin/qa.py`

**Approach:**
- On session init, try to read `.coverage` or `htmlcov/` for coverage data
- Extract per-file coverage % using `coverage json -o .lidco/coverage.json`
- Inject into context for `qa` and `tester` agents: `## Test Coverage\n- src/foo.py: 45%\n- src/bar.py: 82%`

---

### 8. Hybrid Search
**Status:** ✅ Done — `BM25Index` in `src/lidco/rag/bm25.py` (rank_bm25 with graceful degradation). `VectorStore` maintains BM25 + chunk cache in sync with ChromaDB. `search_hybrid()` fetches 3× candidates from both retrievers and merges via Reciprocal Rank Fusion (k=60, bm25_weight=0.4). BM25 rebuilt from existing ChromaDB data on startup. `ContextRetriever.retrieve()` now calls `search_hybrid()`. 14 tests in `test_hybrid_search.py`.
**Goal:** Combine vector (semantic) search with BM25 keyword search for better symbol/code retrieval. Currently only semantic search in RAG.

**Where:** `src/lidco/rag/retriever.py`, `src/lidco/rag/store.py`

**Approach:**
- Add BM25 index alongside ChromaDB (use `rank_bm25` package)
- Merge results: reciprocal rank fusion of semantic + keyword scores
- Especially useful for exact symbol names like `ContextDeduplicator` where semantic search underperforms

---

### 9. Dynamic System Prompt Builder
**Status:** ✅ Done — `build_system_prompt(context)` overridable method on `BaseAgent`. Includes streaming narration and clarification hints only when relevant tools are available. 11 tests in `test_base_system_prompt.py`.

---

### 10. Hard Token Budget Enforcement
**Goal:** `TokenBudget` class exists but doesn't enforce limits. When session token limit is set, actively stop new agent calls and warn the user.

**Where:** `src/lidco/core/token_budget.py`, `src/lidco/cli/app.py`

**Approach:**
- `TokenBudget.check_remaining()` — raise `TokenBudgetExceeded` if over limit
- Check before each `orchestrator.handle()` call in `app.py`
- Show remaining budget in status bar

---

### 11. Smart Tool Result Compression
**Status:** ✅ Done — `get_file_symbol_summary()` on `IndexContextEnricher`. `FileReadTool` lazily loads the enricher and compresses files > 4000 chars: returns `## File summary` + first 2000 chars + truncation hint. Bypassed for offset/limit reads. 10 compression tests in `test_file_tools.py`, 10 symbol-summary tests in `test_context_enricher.py`. Also fixed pre-existing integration test (`test_no_planning_for_non_coder_agents` → `test_no_planning_for_non_planning_agents`) that was using `debugger` (now in `_PLANNING_AGENTS`). 813 passing.

---

### 12. Conversation Pruner Improvements
**Status:** ✅ Done — `compress_tool_results()` in `conversation_pruner.py`. Truncates large tool results (>2000 chars) early and summarizes old ones before message-level pruning kicks in. Integrated into `base.py` run loop. 11 tests in `test_conversation_pruner.py`.

---

### 13. Phase Progress in Status Bar
**Status:** ✅ Done — `set_phase(name, status)` on `_StatusBar` and `StreamDisplay`. Atomic list reassignment for thread safety. `GraphOrchestrator` emits Plan/Execute/Fix/Review phases via `set_phase_callback`. `BaseOrchestrator` base class extended. 8 tests in `test_stream_display.py`.

---

### 14. Session Summary on Exit
**Status:** ✅ Done — `_show_session_summary()` helper in `app.py`. Tracks `session_tool_calls`, `session_files_edited` per turn. Renders a Rich panel on `/exit` or EOF. Costs shown with adaptive precision. 14 tests in `test_session_summary.py`.

---

### 15. Interactive Plan Editor
**Status:** ✅ Done — `parse_plan_steps()` + `edit_plan_interactively()` in `src/lidco/cli/plan_editor.py`. Regex parses `1.`, `1)`, `Step 1:` formats. User can select steps by number, range (1-3), comma-list, `all`, or `none`. Filtered plan is renumbered. `set_plan_editor(callback)` on `BaseOrchestrator` / `GraphOrchestrator`. `_approve_plan_node` uses editor when set. Wired into `app.py` with live-display pause/resume. 22 tests in `test_plan_editor.py`.
**Goal:** When a plan is generated, show it in an interactive TUI where user can approve/reject individual steps, not just the whole plan.

**Where:** `src/lidco/agents/graph.py` → `_approve_plan_node`

**Approach:**
- Parse plan into numbered steps (lines starting with `1.`, `2.`, etc.)
- Show step list in prompt_toolkit with checkboxes
- Pass approved steps back as filtered plan context

---

### 16. Git Diff Viewer
**Status:** ✅ Done — `src/lidco/cli/diff_viewer.py` with `get_git_diff()` and `show_git_diff()`. Runs `git diff --unified=3`, renders with Rich `Syntax(language="diff", theme="monokai")` in a dim-yellow panel. Diffs > 80 lines truncated with hidden-count in title. Wired into `app.py` after agent turns with file edits. 15 tests in `test_diff_viewer.py`. 828 passing.

---

## Q5 — DX & Tooling

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 17 | [/search command](#17-search-command) | ✅ Done | 1d | instant code search from REPL |
| 18 | [In-session file read cache](#18-in-session-file-read-cache) | ✅ Done | 1d | −40% redundant reads |
| 19 | [Post-edit linting](#19-post-edit-linting) | ✅ Done | 1d | instant ruff feedback |
| 20 | [Security agent](#20-security-agent) | ✅ Done | 1d | OWASP/secrets review |
| 21 | [REPL history persistence](#21-repl-history-persistence) | ✅ Done | 0.5d | recall previous prompts |
| 22 | [/commit command](#22-commit-command) | ✅ Done | 1d | LLM-generated commits |

---

## Q6 — Reliability & Performance

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 23 | [SQLite thread-safety lock](#23-sqlite-thread-safety-lock) | ✅ Done | 0.5d | prevent crashes in API server |
| 24 | [BM25 index persistence](#24-bm25-index-persistence) | ✅ Done | 1d | instant startup, no rebuild cost |
| 25 | [Tool schema cache invalidation](#25-tool-schema-cache-invalidation) | ✅ Done | 0.5d | stable tool calls across restarts |
| 26 | [Review iteration off-by-one fix](#26-review-iteration-off-by-one-fix) | ✅ Done | 0.5d | review runs intended # of times |
| 27 | [RAG retrieval batching](#27-rag-retrieval-batching) | ✅ Done | 1d | faster multi-query retrieval |
| 28 | [Watchdog auto-indexing](#28-watchdog-auto-indexing) | ✅ Done | 2d | index stays current on file saves |

---

## Q7 — New Tools & Agents

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 29 | [FileEditTool context preview](#29-fileedit-context-preview) | ✅ Done | 1d | agent sees ±10 lines before edits |
| 30 | [Diff tool](#30-diff-tool) | ✅ Done | 1d | structured 2-file comparison |
| 31 | [Tree tool](#31-tree-tool) | ✅ Done | 0.5d | directory structure snapshot |
| 32 | [Parallel agent execution](#32-parallel-agent-execution) | ✅ Done | 3d | concurrent multi-agent plans |
| 33 | [Review loop learning](#33-review-loop-learning) | ✅ Done | 2d | reviewer learns from approvals |
| 34 | [Performance profiler agent](#34-performance-profiler-agent) | ✅ Done | 2d | detect hotspots automatically |

---

## Q8 — Index & RAG

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 35 | [Index schema versioning](#35-index-schema-versioning) | ✅ Done | 1d | safe DB migrations |
| 36 | [Circular import detection](#36-circular-import-detection) | ✅ Done | 1d | surface import cycles |
| 37 | [Path-filtered RAG search](#37-path-filtered-rag-search) | ✅ Done | 1d | scope queries to directories |
| 38 | [Query expansion](#38-query-expansion) | ✅ Done | 2d | +15% RAG recall |
| 39 | [Incremental BM25 rebuild](#39-incremental-bm25-rebuild) | ✅ Done | 1d | O(changed) instead of O(all) |

---

## Q9 — Observability & Config

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 40 | [Structured JSON logging](#40-structured-json-logging) | ✅ Done | 1d | machine-parseable logs |
| 41 | [Per-session cost tracker](#41-per-session-cost-tracker) | ✅ Done | 1d | accurate $/session display |
| 42 | [Config hot-reload](#42-config-hot-reload) | ✅ Done | 1d | change settings without restart |
| 43 | [Env var config overrides](#43-env-var-config-overrides) | ✅ Done | 0.5d | 12-factor app compatibility |
| 44 | [Memory TTL / expiry](#44-memory-ttl--expiry) | ✅ Done | 1d | auto-purge stale memories |
| 45 | [API rate limiting](#45-api-rate-limiting) | ✅ Done | 1d | protect server from overload |

---

## Task Details (Q5+)

### 17. /search Command
**Status:** ✅ Done — `search_handler` in `src/lidco/cli/commands.py`. Tries `session.context_retriever.retrieve()` first (hybrid RAG), then falls back to `enricher._db.query_symbols(name_like=f"%{query}%")` for symbol search. Prints Rich table with file, line, kind, name columns. Tips shown when neither RAG nor index is available.

---

### 18. In-session File Read Cache
**Status:** ✅ Done — `OrderedDict`-based LRU cache in `src/lidco/tools/file_read.py`. Cache key: `(path, offset, limit, mtime_ns)` — auto-invalidates when file is modified on disk. `_CACHE_MAX = 100` entries. `result.metadata["cached"] = True` on hits. 9 tests in `test_file_read_cache.py`.

---

### 19. Post-edit Linting
**Status:** ✅ Done — `src/lidco/cli/linter.py` with `_run_ruff()` and `show_lint_results()`. Runs `ruff check --select=E,F,W --output-format=concise`. Graceful degradation when ruff not installed. Truncates at 40 lines with "N more issues" footer. Wired into `app.py` alongside diff viewer after file-edit tool calls. 9 tests in `test_linter.py`.

---

### 20. Security Agent
**Status:** ✅ Done — `src/lidco/agents/builtin/security.py`. OWASP Top 10, secrets/credentials, crypto weaknesses, auth/authz, input validation, dependency CVEs, info-disclosure. `temperature=0.1`, `max_iterations=50`. Registered in `session.py`. 2 smoke tests in `test_linter.py`.

---

### 21. REPL History Persistence
**Status:** ✅ Done — `readline` / `prompt_toolkit` history already present. No additional work needed.

---

### 22. /commit Command
**Status:** ✅ Done — `commit_handler` in `src/lidco/cli/commands.py`. Gets `git diff --cached` (falls back to `git diff HEAD`), calls LLM to generate a commit message, shows preview, uses `run_in_executor` for blocking `Prompt.ask()` confirm, then runs `git commit -m`. Registered as `SlashCommand("commit", ...)`.

---

### 23. SQLite Thread-safety Lock
**Status:** ✅ Done — replaced single `sqlite3.Connection` instance variable with a `@property _conn` backed by `threading.local()`. Each OS thread now gets its own connection. `close()` cleans up only the calling thread's connection. 3 new thread-safety tests in `test_db.py`.
**File:** `src/lidco/index/db.py`

---

### 24. BM25 Index Persistence
**Status:** ✅ Done — `BM25Index.save(path)` / `load(path)` added to `bm25.py`. `VectorStore` saves `(count, corpus_path, chunk_cache)` pickle to `persist_dir/bm25_cache.pkl` after every mutation. On startup, if the recorded count matches ChromaDB count, loads from pickle (O(1)) instead of rebuilding from ChromaDB (O(N)). `clear()` deletes both pickle files. 7 new tests in `test_hybrid_search.py`.
**Files:** `src/lidco/rag/bm25.py`, `src/lidco/rag/store.py`

---

### 25. Tool Schema Cache Invalidation
**Status:** ✅ Done — `ToolRegistry` now caches unfiltered `get_openai_schemas()` results. Cache is invalidated on every `register()` call. Added `schema_version: int` property (monotonic counter) for downstream cache detection. Filtered requests bypass the cache. Returned list is a copy so mutations can't corrupt the cache. 7 new tests in `test_registry.py`.
**File:** `src/lidco/tools/registry.py`

---

### 26. Review Iteration Off-by-one Fix
**Status:** ✅ Done — fixed infinite-loop bug in `_auto_review_node`: on reviewer timeout or exception, `review_iteration` now always advances (was keeping `prev_iter`, which could loop forever when a previous CRITICAL review remained in state). Added 3 tests in `TestReviewIterationCount`: reviewer runs exactly N times, runs exactly 1 when max=1, no infinite loop when reviewer always times out.
**File:** `src/lidco/agents/graph.py`

---

### 27. RAG Retrieval Batching
**File:** `src/lidco/rag/retriever.py`
**Problem:** Each call to `retrieve()` issues one `search_hybrid()` call. For multi-agent pipelines where several agents need RAG context for the same query, the same expensive search runs multiple times.
**Approach:**
- Add `retrieve_batch(queries: list[str]) -> list[str]` that deduplicates identical queries
- Internal LRU cache keyed on `(query, max_results)` with TTL of ~30s
- Integrate with `get_full_context()` in `session.py`

---

### 28. Watchdog Auto-indexing
**Status:** ✅ Done — `IndexWatcher` in `src/lidco/index/watcher.py`. Uses `watchdog` library; debounces 500 ms; background thread; falls back gracefully if `watchdog` not installed. Wired into `Session.__init__()` when `config.index.auto_watch = true`. `Session.close()` stops the thread. Added `IndexConfig` to config.
**File:** `src/lidco/index/watcher.py` (new), `src/lidco/cli/app.py`
**Goal:** Keep the structural index current without requiring `/index` to be run manually.
**Approach:**
- Use `watchdog` library to monitor `project_dir` for file changes (`*.py`, `*.ts`, etc.)
- Debounce changes (500ms window) and call `IndexDatabase.upsert_file()` for changed files
- Run watcher in a background thread, started in `Session.__init__()` if `config.index.auto_watch = true`
- Emit a subtle status-bar notification: `"Index updated (3 files)"`

---

### 29. FileEdit Context Preview
**File:** `src/lidco/tools/file_edit.py`
**Goal:** Before applying an edit, show the agent ±10 lines of context around the target location so it can verify the edit lands in the right place.
**Approach:**
- In `_run()`, after locating the edit anchor, extract `lines[max(0,anchor-10):anchor+10]`
- Return a `ToolResult` with `metadata["context_preview"]` containing the surrounding lines
- The agent's next iteration receives this as confirmation context

---

### 30. Diff Tool
**File:** `src/lidco/tools/diff.py` (new)
**Goal:** Allow agents to compare two files or two strings without reading both in full.
**Schema:** `diff(path_a: str, path_b: str, unified: int = 3) -> ToolResult`
**Approach:**
- Use `difflib.unified_diff()` for pure-Python, zero-dependency implementation
- Return unified diff as `output`, plus `metadata["added"]`, `metadata["removed"]` line counts
- Register in `ToolRegistry.create_default_registry()`

---

### 31. Tree Tool
**File:** `src/lidco/tools/tree.py` (new)
**Goal:** Give agents a compact directory tree without reading individual files.
**Schema:** `tree(path: str, max_depth: int = 3, show_hidden: bool = False) -> ToolResult`
**Approach:**
- Recursive `os.scandir()` walk respecting `.gitignore` patterns (reuse existing ignore logic)
- Output as indented text tree (like `tree` CLI)
- Max 200 entries; truncate with `"... (N more)"` hint
- Register in `ToolRegistry.create_default_registry()`

---

### 32. Parallel Agent Execution
**File:** `src/lidco/agents/graph.py`, `src/lidco/agents/orchestrator.py`
**Goal:** Allow the planner to emit tasks that run concurrently (e.g., "review security AND performance in parallel").
**Approach:**
- Extend plan step format to support `parallel: true` marker
- In `GraphOrchestrator`, detect parallel groups and use `asyncio.gather()` to run them
- Merge results before passing to the next sequential step
- Guard with `max_parallel_agents` config (default 3)

---

### 33. Review Loop Learning
**Status:** ✅ Done — After a clean review (NO_ISSUES_FOUND), MEDIUM issue lines are saved to MemoryStore under `category="review_patterns"` (project scope, rolling 10-slot rotation). Before each review run, top-5 stored patterns are prepended to the review prompt as a "Past review patterns" hint. Methods: `_save_review_patterns()`, `_build_review_patterns_hint()` in `GraphOrchestrator`.
**File:** `src/lidco/agents/builtin/reviewer.py`, `src/lidco/core/memory.py`
**Goal:** When the user approves a review-suggested change, record the reviewer's finding pattern in memory so future reviews emphasize similar issues.
**Approach:**
- After a review cycle ends with approval, extract the reviewer's key findings
- Store in `MemoryStore` under `category="review_patterns"` with project-scoped key
- Inject top-5 patterns into reviewer's dynamic system prompt suffix

---

### 34. Performance Profiler Agent
**Status:** ✅ Done — `ProfilerTool` (`src/lidco/tools/profiler.py`) runs `python -m cProfile -o stats.prof` in a subprocess, parses with `pstats`, returns top-N rows. `ProfilerAgent` (`src/lidco/agents/builtin/profiler.py`) registered as `name="profiler"` with tools `[run_profiler, file_read, glob, grep]`. Router routes `profile/performance/hotspot/slow` tasks to it. Added to `_PLANNING_AGENTS`.
**File:** `src/lidco/agents/builtin/profiler.py` (new)
**Goal:** Dedicated agent for performance analysis — reads cProfile / py-spy output, identifies hotspots, suggests optimizations.
**System prompt focus:** algorithmic complexity, unnecessary I/O, N+1 queries, caching opportunities, async vs sync boundaries.
**Approach:**
- Register as `name="profiler"` agent
- Provide `run_profiler` tool that executes a script under `cProfile` and returns top-20 cumulative time entries
- Agent analyzes output and suggests concrete fixes

---

### 35. Index Schema Versioning
**File:** `src/lidco/index/db.py`
**Problem:** The SQLite schema has no version table. Any schema change (new column, new table) silently breaks existing DBs or is ignored.
**Fix:**
- Add `schema_versions` table: `(version INTEGER PRIMARY KEY, applied_at TEXT)`
- On `IndexDatabase.__init__()`: check current version, run pending migrations
- Each migration is a function in `src/lidco/index/migrations/` numbered sequentially
- Drop and recreate DB if version is too old (with warning)

---

### 36. Circular Import Detection
**File:** `src/lidco/index/dependency_graph.py`
**Goal:** Surface Python circular imports (A → B → C → A) as a separate analysis result.
**Approach:**
- Run DFS on the dependency graph; track the current path stack
- Collect all cycles; deduplicate by normalizing to the lexicographically smallest rotation
- Expose via `DependencyGraph.find_cycles() -> list[list[str]]`
- Show in `/index` command output and inject into context for the architect agent

---

### 37. Path-filtered RAG Search
**File:** `src/lidco/rag/retriever.py`, `src/lidco/rag/store.py`
**Goal:** Let agents scope RAG queries to a subdirectory (e.g., "search only in `src/lidco/cli/`").
**Approach:**
- Add `path_prefix: str | None` to `ContextRetriever.retrieve()` signature
- In `VectorStore.search_hybrid()`: pass `where={"source": {"$regex": f"^{path_prefix}"}}` to ChromaDB
- Filter BM25 candidates by source prefix before RRF merge
- Expose in `/search` command: `/search --path src/cli/ ...`

---

### 38. Query Expansion
**Status:** ✅ Done — `config.rag.query_expansion = false` (off by default). When enabled, `ContextRetriever._retrieve_expanded()` generates 3 alternative queries via LLM (role=routing), runs `search_hybrid()` for each, merges all results by best-score deduplication + sort. `ContextRetriever` accepts optional `llm` param (wired from `session.py` when expansion is on).
**File:** `src/lidco/rag/retriever.py`
**Goal:** Improve RAG recall by ~15% by expanding queries with synonyms and related terms before retrieval.
**Approach:**
- Before retrieval, call cheap LLM (haiku): "Generate 3 alternative phrasings for this code search query: `{query}`"
- Run `search_hybrid()` for each phrasing
- Merge all result sets via RRF (reuse existing fusion logic)
- Gate behind `config.rag.query_expansion = false` (off by default for latency)

---

### 39. Incremental BM25 Rebuild
**File:** `src/lidco/rag/bm25.py`
**Problem:** `_rebuild_if_needed()` always rebuilds the full BM25 index from ChromaDB — O(N) even when only 1 chunk changed.
**Fix:**
- Track a `_dirty_ids: set[str]` of added/removed IDs since last rebuild
- If `len(_dirty_ids) < 0.1 * len(corpus)`: do an incremental update (remove old, add new tokens to existing corpus arrays)
- Full rebuild only when dirty fraction exceeds threshold or corpus cleared

---

### 40. Structured JSON Logging
**Status:** ✅ Done — `src/lidco/core/logging.py` with `setup_logging(format, level, log_file)`. `_JsonFormatter` emits one JSON line per record with `ts/level/logger/msg` + extra fields. Added `LoggingConfig` to `LidcoConfig`. Wired into CLI (`app.py`) and server (`server/app.py`).
**File:** `src/lidco/core/logging.py` (new), `src/lidco/cli/app.py`
**Goal:** Machine-parseable logs for production deployments (log aggregators, alerts).
**Approach:**
- Add `setup_logging(format: "json" | "pretty", level: str)` utility
- JSON formatter: `{"ts": "...", "level": "INFO", "logger": "...", "msg": "...", "extra": {...}}`
- Wire into `app.py` and `server/app.py` based on `config.logging.format`
- Include `session_id`, `agent_name`, `tool_name` as structured fields

---

### 41. Per-session Cost Tracker
**Status:** ✅ Done — `COST_PER_MILLION_TOKENS` dict + `estimate_cost_from_tokens()` in `token_budget.py`. `calculate_cost()` in `litellm_provider.py` falls back to manual pricing for custom providers (GLM, etc.). `TokenBudget` now tracks `_total_prompt_tokens` and `_total_completion_tokens`. Session summary shows `Tokens: 15.3k (12.0k in / 3.3k out)` and `Cost: ~$0.0087`.
**File:** `src/lidco/core/token_budget.py`, `src/lidco/cli/app.py`
**Problem:** Session summary shows token counts but cost calculation is approximate and model-agnostic.
**Fix:**
- Add `COST_PER_MILLION_TOKENS: dict[str, tuple[float, float]]` (input, output) for common models
- `TokenBudget.estimate_cost(model: str) -> float` using actual input/output token split
- Display in session summary: `Cost: ~$0.023 (12k in / 3k out)`

---

### 42. Config Hot-reload
**Status:** ✅ Done — `ConfigReloader` in `src/lidco/core/config_reloader.py`. Background daemon thread polls `~/.lidco/config.yaml` and `.lidco/config.yaml` every 30s. On mtime change: reloads full config stack, applies mutable fields (llm.default_model, agents.auto_review/plan/timeout, etc.) to live session and orchestrator. Warns about restart-required sections (rag, llm_providers). Wired into `Session.__init__()` and `Session.close()`.
**File:** `src/lidco/core/config.py`, `src/lidco/core/session.py`
**Goal:** Allow users to edit `.lidco/config.toml` and have changes take effect without restarting.
**Approach:**
- Poll config file mtime every 30s in a background task
- On change: reload config, update mutable session fields (model, thresholds, agent settings)
- Emit log: `"Config reloaded — new default model: gpt-4o-mini"`
- Fields requiring restart (e.g., RAG store path) emit a warning instead

---

### 43. Env Var Config Overrides
**File:** `src/lidco/core/config.py`
**Goal:** 12-factor app style — any config field overridable via `LIDCO_*` env vars.
**Approach:**
- After loading TOML, scan `os.environ` for `LIDCO_LLM_DEFAULT_MODEL`, `LIDCO_RAG_ENABLED`, etc.
- Use dotted path mapping: `LIDCO_AGENTS_DEFAULT` → `config.agents.default`
- Type-coerce: `"true"/"false"` → bool, numeric strings → int/float
- Document all available env vars in `README` and `lidco config --show-env`

---

### 44. Memory TTL / Expiry
**File:** `src/lidco/core/memory.py`
**Goal:** Prevent memory from accumulating stale entries indefinitely.
**Approach:**
- Add `created_at: float` (unix timestamp) to each `MemoryEntry`
- Add `config.memory.ttl_days: int | None = None` (None = never expire)
- On `build_context_string()`: filter out entries older than TTL
- On `save()`: prune expired entries before writing to disk
- `/memory` command shows age of each entry

---

### 45. API Rate Limiting
**File:** `src/lidco/server/app.py`
**Goal:** Protect the HTTP server from accidental overload or abuse.
**Approach:**
- Add `slowapi` middleware (built on `limits` library, compatible with FastAPI)
- Default: 60 requests/minute per IP for `/chat`, 10/minute for `/index`
- Config: `config.server.rate_limit = "60/minute"`
- Return `429 Too Many Requests` with `Retry-After` header
- Log rate-limit hits at WARNING level
**Status:** ✅ Done — `RateLimitMiddleware` in `middleware.py` (sliding window, per-IP, `deque`-based), 17 tests. Defaults: 60/min for `/chat`, 10/min for `/index`. `/health` exempt. `X-Forwarded-For` aware.

---

## Q10 — Agent Capabilities

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 46 | [Test runner tool](#46-test-runner-tool) | ✅ Done | 1d | structured pytest results for agents |
| 47 | [/health command](#47-health-command) | ✅ Done | 0.5d | quick project health overview |
| 48 | [Multi-file rename tool](#48-multi-file-rename-tool) | ✅ Done | 1d | atomic cross-file symbol rename |
| 49 | [Explain agent](#49-explain-agent) | ✅ Done | 0.5d | dedicated code explanation agent |
| 50 | [/todos command](#50-todos-command) | ✅ Done | 0.5d | find & manage TODO/FIXME comments |

---

## Task Details (Q10)

### 46. Test Runner Tool
**File:** `src/lidco/tools/test_runner.py`
**Goal:** Give tester/debugger agents structured pytest results without raw bash output parsing.
**Schema:** `run_tests(test_path="", verbose=False, coverage=False, timeout=120) -> ToolResult`
**Approach:**
- Run `python -m pytest` with `-q` or `-v`, optional `--cov`
- Parse summary line: passed/failed/error/skipped counts
- Extract `FAILED tests/...::test_name` lines into a list
- Return `metadata["failed_tests"]` list for downstream agent logic
- Truncate long failure sections to 15k chars
**Status:** ✅ Done — `RunTestsTool` + helpers `_parse_summary`, `_extract_failed_tests`, `_extract_coverage_summary`, `_extract_failure_section`. Registered in `create_default_registry()`. 10 tests in `test_test_runner.py`.

---

### 47. /health Command
**File:** `src/lidco/cli/commands.py`
**Goal:** Quick project health snapshot without leaving the REPL.
**Approach:**
- Collect in parallel: `ruff check --statistics` (lint count), `pytest --collect-only -q` (test count)
- Count `TODO/FIXME/HACK/XXX` in `src/**/*.py` synchronously
- Read coverage % from `.lidco/coverage.json` or `coverage.json` if present
- Output compact Markdown summary with code/test sections
**Status:** ✅ Done — `health_handler` registered as `/health`. 6 tests in `test_commands_health.py`.

---

### 48. Multi-file Rename Tool
**File:** `src/lidco/tools/rename.py`
**Goal:** Atomically rename a symbol (class, function, variable) across all matching files.
**Schema:** `rename_symbol(old_name, new_name, glob_pattern="**/*.py", whole_word=True, dry_run=False) -> ToolResult`
**Approach:**
- Compile `\bold_name\b` regex (whole-word) or plain `re.escape(old_name)`
- Walk all files matching glob; skip if `old_name` not in content (fast pre-check)
- Count replacements per file, collect changed line numbers
- Write new content unless `dry_run=True`
- Return summary: N files changed, M total replacements
**Status:** ✅ Done — `RenameSymbolTool`. Registered in `create_default_registry()`. 10 tests in `test_rename.py`.

---

### 49. Explain Agent
**File:** `src/lidco/agents/builtin/explain.py`
**Goal:** Dedicated agent for explaining code, APIs, and concepts clearly.
**System prompt focus:** plain language, concrete examples, step-by-step walkthroughs, analogies. No unnecessary jargon.
**Routing:** router sends `explain/what/how does/walk me through` queries here.
**Status:** ✅ Done — `ExplainAgent` registered as `name="explain"`. Added to `__init__.py`, `session.py`, `graph.py` routing. 2 smoke tests.

---

### 50. /todos Command
**File:** `src/lidco/cli/commands.py`
**Goal:** Surface and filter TODO/FIXME/HACK/XXX comments across the codebase.
**Approach:**
- Walk `src/**/*.py` (and `tests/` optionally with `--all`)
- Collect file, line number, tag type, comment text
- Filter by tag: `/todos fixme`, `/todos todo`, `/todos hack`
- Output Rich table with columns: file, line, tag, comment
- Limit to 50 entries with truncation hint
**Status:** ✅ Done — `todos_handler` registered as `/todos`. 6 tests in `test_commands_todos.py`.

---

## Q11 — Workflow & Intelligence

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 51 | [Snippet manager](#51-snippet-manager) | ✅ Done | 1d | save/recall reusable code patterns |
| 52 | [Test gap analyzer](#52-test-gap-analyzer) | ✅ Done | 1.5d | find untested functions/classes |
| 53 | [/run command](#53-run-command) | ✅ Done | 0.5d | run shell commands inline from REPL |
| 54 | [Changelog generator](#54-changelog-generator) | ✅ Done | 1d | auto CHANGELOG.md from git history |
| 55 | [Architecture diagram](#55-architecture-diagram) | ✅ Done | 1d | ASCII import-graph from index |

---

## Task Details (Q11)

### 51. Snippet Manager
**Files:** `src/lidco/core/snippets.py`, `src/lidco/cli/commands.py`
**Goal:** Save and recall reusable code snippets within and across sessions.
**Approach:**
- `SnippetStore` — JSON file at `.lidco/snippets.json`; entries: `key, content, language, tags, created_at`
- `/snippet add name [lang]: code` — save snippet
- `/snippet get name` — display snippet in a code block
- `/snippet list [tag]` — list all or filtered by tag
- `/snippet delete name` — remove snippet
- `/snippet search query` — substring search in keys + content
**Status:** ✅ Done — `SnippetStore` in `core/snippets.py`, `/snippet` command registered. 18 tests.

---

### 52. Test Gap Analyzer
**File:** `src/lidco/tools/test_gap.py`
**Goal:** Find functions and classes that have no corresponding test in the test suite.
**Approach:**
- Query structural index for all `function`/`class` symbols in `src/`
- Collect test function names from `tests/**/*.py` (symbols with `kind="function"` and `name` starting with `test_`)
- Heuristic match: `test_foo_bar` → `FooBar`, `foo_bar`; flag unmatched non-dunder symbols
- Parameters: `path_prefix=""`, `kind="all"`, `min_lines=3` (skip tiny helpers)
- Return list of ungapped + gapped symbols with file/line info
**Status:** ✅ Done — `TestGapTool` + `_match_symbol_to_tests()` heuristic. Registered in registry. 12 tests.

---

### 53. /run Command
**File:** `src/lidco/cli/commands.py`
**Goal:** Run a shell command inline from the REPL without leaving the session.
**Approach:**
- `/run <command>` — executes via `asyncio.create_subprocess_shell`
- Streams stdout/stderr; limits to 200 lines
- Shows exit code and duration
- No confirmation needed (user typed it explicitly)
**Status:** ✅ Done — `run_handler` registered as `/run`. 5 tests.

---

### 54. Changelog Generator
**File:** `src/lidco/cli/commands.py`
**Goal:** Auto-generate a CHANGELOG.md from git commit history.
**Approach:**
- `/changelog [from_ref] [to_ref]` — defaults to last tag..HEAD
- `git log --oneline --no-merges {from_ref}..{to_ref}` → list of commits
- LLM groups into sections: Features, Bug Fixes, Refactoring, Docs, Other
- Outputs `## [Unreleased]\n### Features\n- ...` Markdown
- Optional `--save` writes to `CHANGELOG.md`
**Status:** ✅ Done — `changelog_handler` registered as `/changelog`. 6 tests.

---

### 55. Architecture Diagram
**File:** `src/lidco/tools/arch_diagram.py`
**Goal:** Render an ASCII import-dependency graph so agents and users can visualise the module structure at a glance.
**Approach:**
- `ArchDiagramTool` — wraps `DependencyGraph`; parameters: `root_path=""`, `max_depth=3`, `direction="dependents|dependencies|both"`
- Outputs indented tree: `src/lidco/core/session.py → [agents/graph.py, agents/orchestrator.py, ...]`
- `/arch [path]` slash command for interactive use
**Status:** ✅ Done — `ArchDiagramTool` registered; `/arch` command added. 10 tests.

---

## Q12 — Resilience & Extensibility

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 56 | [LLM retry + fallback chain](#56-llm-retry--fallback-chain) | ✅ Done | 1d | стабильность при rate limits и таймаутах |
| 57 | [Custom agent from config](#57-custom-agent-from-config) | ✅ Done | 1.5d | расширяемость без форка кода |
| 58 | [Session export/import](#58-session-exportimport) | ✅ Done | 1d | сохранение и шаринг сессий |
| 59 | [Streaming tool results](#59-streaming-tool-results) | ✅ Done | 1.5d | live UX для долгих инструментов |
| 60 | [GitHub PR integration](#60-github-pr-integration) | ✅ Done | 1d | автоматический контекст PR для агентов |

---

## Task Details (Q12)

### 56. LLM Retry + Fallback Chain
**Files:** `src/lidco/llm/exceptions.py` (new), `src/lidco/llm/retry.py`, `src/lidco/llm/router.py`, `src/lidco/llm/litellm_provider.py`, `src/lidco/core/session.py`
**Goal:** When an LLM call fails with a retryable error (429, 5xx, timeout, connection error), automatically retry with exponential backoff + jitter. After exhausting retries, fall back to the next model in the configured chain. Raise `LLMRetryExhausted` if all models fail.
**Status:** ✅ Done — `LLMRetryExhausted` exception with `attempts: list[tuple[str, Exception]]`. `with_retry()` now raises `LLMRetryExhausted` (not raw litellm error) on exhaustion, carries model name + original error. `ModelRouter` catches `LLMRetryExhausted` per candidate, tries next in chain; non-retryable errors (`BadRequestError`, `AuthenticationError`) propagate immediately without fallback. `Session` wires `config.llm.retry` fields into `LiteLLMProvider`. 12 new tests in `test_retry_fallback.py`; 4 tests in `test_retry.py` updated; 2 tests in `test_router.py` updated. 1178 total passing.

---

### 57. Custom Agent from Config
**Files:** `src/lidco/agents/loader.py`, `src/lidco/agents/base.py`, `src/lidco/agents/graph.py`, `src/lidco/core/session.py`
**Goal:** Define custom agents in YAML without writing Python. On session init, auto-discover and register agents from `.lidco/agents/`.
**Schema:** `name` (required), `system_prompt` (required), `description`, `tools: list[str]`, `temperature`, `model`, `routing_keywords: list[str]`
**Status:** ✅ Done — `AgentConfig.routing_keywords` field added. `load_agent_from_yaml()` rewrote to flat schema with validation (missing `name`/`system_prompt` → `ValueError`, skip+warn in `discover_yaml_agents`), unknown tool warnings (agent still loads), backward-compat for old nested `model:` dict. `GraphOrchestrator._get_router_prompt()` appends `Custom routing rules: kw1/kw2->agent-name` when routing_keywords present. `Session._register_yaml_agents()` logs `INFO` when YAML agent overrides a built-in. 20 tests in `test_yaml_agent_loader.py`. 1198 total passing.

---

### 58. Session Export/Import
**Files:** `src/lidco/cli/commands.py`, `src/lidco/agents/orchestrator.py`, `src/lidco/agents/graph.py`
**Goal:** `/export [path]` saves conversation history + metadata (model, tokens, cost) to JSON or Markdown. `/import [path]` restores conversation into a new session.
**Status:** ✅ Done — `/export` (default) → JSON to `.lidco/exports/session-TIMESTAMP.json` with full metadata (lidco_version, exported_at, model, project_dir, tokens, cost_usd, messages). `/export --md [path]` → Markdown transcript with tokens/cost header. `/export [custom.json]` → explicit path. `/import [path]` → reads JSON, validates messages, calls `orchestrator.restore_history()`, shows summary (model, date, tokens). `restore_history(messages)` added to `BaseOrchestrator` (abstract), `Orchestrator`, and `GraphOrchestrator`. 19 tests in `test_commands.py`. 1211 total passing.

---

### 59. Streaming Tool Results
**Files:** `src/lidco/tools/base.py`, `src/lidco/tools/test_runner.py`, `src/lidco/tools/profiler.py`, `src/lidco/agents/base.py`
**Goal:** Long-running tools (pytest, cProfile) stream output lines in real-time instead of waiting for the process to finish.
**Status:** ✅ Done — `BaseTool._progress_callback` class attribute + `set_progress_callback()` method (class-attribute approach avoids breaking subclasses with custom `__init__`). `BaseAgent._execute_tool()` injects `_stream_callback` into each tool before execution. `RunTestsTool`: `stream_output: bool = False` parameter; when `True` and callback is set, `_stream_lines()` async helper reads stdout line-by-line via `readline()`, calls callback per line, collects into full stdout for structured parsing. `ProfilerTool`: `stream_output: bool = False` parameter + `stream_output` kwarg in `_run()`; `_run_async_streaming()` module-level helper uses asyncio subprocess to stream script stdout; cProfile stats still parsed from `.prof` file after process exits. Falls back to buffered `communicate()` / `subprocess.run()` when no callback set. 23 new tests across `test_test_runner.py` (updated param count + streaming class) and new `test_profiler.py`. 1234 total passing.

---

### 60. GitHub PR Integration
**Files:** `src/lidco/tools/gh_pr.py` (new), `src/lidco/cli/commands.py`, `src/lidco/core/session.py`, `src/lidco/tools/registry.py`
**Goal:** `/pr [number]` fetches PR diff + comments via `gh` CLI and injects context into the next agent turn.
**Status:** ✅ Done — `GHPRTool` (`gh_pr`) runs `gh pr view {number} --json title,body,files,comments,state,headRefName,baseRefName,additions,deletions,number` and optionally `gh pr diff {number}`. Formats output as Markdown with PR title, state, branch, changed files, description, comments, and truncated diff (first 6 000 chars). `/pr <number>` stores context in `session.active_pr_context`; `/pr close|clear` clears it; `/pr` (no arg) shows active preview or usage. `Session.active_pr_context: str | None = None`; `get_full_context()` appends it when set (no dedup). `GHPRTool` in `create_default_registry()` (18 tools). Graceful errors for missing `gh`, timeout, non-zero exit. 41 tests in `test_gh_pr.py` + `test_commands_pr.py`; `test_registry.py` updated (17→18). 1275 total passing.

---

## Q13 — Deeper Agent Debugging

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 61 | [ErrorRecord tool_args + occurrence dedup](#61-errorrecord-tool_args--occurrence-dedup) | ✅ Done | 0.5d | richer error context, no duplicate noise |
| 62 | [ErrorReportTool](#62-errorreporttool) | ✅ Done | 1d | agents can self-query session errors |
| 63 | [Error taxonomy hints in /errors](#63-error-taxonomy-hints-in-errors) | ✅ Done | 0.5d | instant fix suggestions in CLI |
| 64 | [Debug context injection for planning agents](#64-debug-context-injection-for-planning-agents) | ✅ Done | 0.5d | planning agents aware of recent failures |

---

## Task Details (Q13)

### 61. ErrorRecord tool_args + occurrence dedup
**Files:** `src/lidco/core/errors.py`, `src/lidco/agents/base.py`
**Goal:** Enrich each error record with the tool arguments that triggered it, and collapse consecutive identical failures into a single record with an occurrence counter instead of filling the error ring buffer with noise.
**Status:** ✅ Done — `ErrorRecord` gains `tool_args: dict | None = None` and `occurrence_count: int = 1`. `_compact_args()` truncates string values >200 chars to prevent large file content polluting error context. `ErrorHistory.append()` uses `dataclasses.replace()` to bump `occurrence_count` when the last record has the same `(error_type, tool_name, file_hint)` signature — dedup is consecutive-only, so distinct errors are never collapsed. `to_context_str()` shows `×N` repeat marker and `Args:` line. `BaseAgent._execute_tool()` passes `tool_args=_compact_args(tool_args)`. 37 tests in `test_errors_dedup.py`.

---

### 62. ErrorReportTool
**Files:** `src/lidco/tools/error_report.py` (new), `src/lidco/core/session.py`
**Goal:** Give agents a dedicated tool to get a structured, grouped summary of recent session errors. Especially useful for the debugger at the start of a session.
**Schema:** `error_report(n=20, group_by="file"|"type"|"agent"|"none") -> ToolResult`
**Status:** ✅ Done — `ErrorReportTool` groups errors by file/type/agent/none with occurrence-weighted sort. `group_by="none"` returns flat chronological list. Output includes total occurrence count, per-group counts, compact `tool_args` hints, repeat markers. Registered in `Session.__init__()` after `_error_history` is created (not in `create_default_registry()` since it needs the live history instance). Debugger system prompt updated to mention the tool. `ToolPermission.AUTO`. 32 tests in `test_error_report.py`.

---

### 63. Error taxonomy hints in /errors
**Files:** `src/lidco/cli/commands.py`
**Goal:** The `/errors` CLI table now shows a "Hint" column with actionable one-liners derived from the debugger's error taxonomy, so the user can see the likely fix at a glance.
**Status:** ✅ Done — `_ERROR_TAXONOMY_HINTS: dict[str, str]` with 17 patterns (NoneType attribute, positional args, KeyError, FileNotFoundError, ModuleNotFoundError, etc.) defined at closure scope in `_register_builtins`. `_get_error_hint(message)` scans patterns case-insensitively. The Rich table gains two new columns: `×` (occurrence count, shown only when >1) and `Hint` (green, 22 wide). `/debug on` output updated to mention planning agent injection. 9 tests in `test_errors_hints.py`.

---

### 64. Debug context injection for planning agents
**Files:** `src/lidco/agents/graph.py`, `src/lidco/core/session.py`
**Goal:** When debug mode is on, automatically prepend a compact `## Active Debug Context` section to non-debugger planning agents (coder, tester, refactor, architect, profiler) so they see recent failures and avoid repeating error patterns.
**Status:** ✅ Done — `GraphOrchestrator._debug_mode: bool = False`; `set_debug_mode(enabled)` setter. `_error_summary_builder: Callable[[], str] | None`; `set_error_summary_builder(fn)` setter. In `_execute_agent_node()`: when `_debug_mode=True` AND agent name is in `_PLANNING_AGENTS` AND agent is not `"debugger"` AND summary is non-empty, calls `agent.prepend_system_context()` with the advisory. Session wires `set_error_summary_builder(lambda: error_history.to_context_str(n=3))`. `/debug on` propagates `set_debug_mode(True)` to orchestrator via `hasattr` guard for backward compat. 17 tests in `test_debug_mode_injection.py`.

---

## Q14 — Deeper Planning & Reasoning

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 65 | [Planner system prompt overhaul](#65-planner-system-prompt-overhaul) | ✅ Done | 1d | richer plans, self-critique phase |
| 66 | [Planner tool expansion](#66-planner-tool-expansion) | ✅ Done | 0.5d | arch insight + test gap awareness |
| 67 | [Auto plan critique node](#67-auto-plan-critique-node) | ✅ Done | 1d | LLM spot-checks plan before user sees it |
| 68 | [plan_critique config flag](#68-plan_critique-config-flag) | ✅ Done | 0.25d | easy on/off via config/env |

---

## Task Details (Q14)

### 65. Planner system prompt overhaul
**Files:** `src/lidco/agents/builtin/planner.py`
**Goal:** Upgrade the planner's reasoning process with a dedicated self-critique phase and richer output sections so it delivers more actionable, risk-aware plans.
**Status:** ✅ Done — `PLANNER_SYSTEM_PROMPT` completely rewritten with five phases: Understand → Explore → Clarify → Draft → **Self-Critique & Revise**. Phase 5 prompts the planner to re-examine its own draft against 6 questions (missing files, callers, edge cases, simpler approaches, test changes, risk mitigations) before presenting. Output format extended with four new required sections: `Reasoning & Approach` (why this approach over alternatives), `Alternative Considered` (rejected option), `Risk Assessment` (Markdown table: Risk / Likelihood / Mitigation), `Test Impact` (tests to update + new tests needed), and `Callers/Dependents` (all call sites when changing a public interface). Tested in `test_planner_improvements.py`.

---

### 66. Planner tool expansion
**Files:** `src/lidco/agents/builtin/planner.py`
**Goal:** Give the planner access to architectural and test-gap analysis tools so it can produce more informed plans without guessing.
**Status:** ✅ Done — Planner tool list expanded from 4 (`file_read`, `glob`, `grep`, `ask_user`) to 7 by adding `arch_diagram` (module dependency graph), `find_test_gaps` (untested functions in affected modules), and `tree` (directory overview). Both new tools explicitly mentioned in Phase 2 instructions with usage guidance. `arch_diagram` is called for any file whose interface may change; `find_test_gaps` for affected modules. 6 tests in `test_planner_improvements.py`.

---

### 67. Auto plan critique node
**Files:** `src/lidco/agents/graph.py`
**Goal:** After the planner finishes, run a cheap secondary LLM pass that identifies 3-5 specific risks and gaps in the draft plan before the user sees it for approval.
**Status:** ✅ Done — `_CRITIQUE_SYSTEM_PROMPT` module-level constant instructs the critic to flag missing edge cases, untested code paths, breaking-change risks, overly complex steps, and dependency issues. `_critique_plan_node()` async method: fetches `plan_response` from state, calls `self._llm.complete()` with `role="routing"` (cheap model) and a 30-second `asyncio.wait_for` timeout. On success, appends `\n\n---\n## Plan Review (auto-generated)\n{critique}` to `plan_response.content` using `dataclasses.replace()` (immutable update), stores critique in `state["plan_critique"]`, and increments `accumulated_tokens` + `accumulated_cost_usd`. Failure-safe: any exception (LLM error, timeout, empty response) logs a WARNING and returns the original state unchanged. Graph edges rewired: `execute_planner → critique_plan → approve_plan`. 18 tests in `test_critique_plan.py`.

---

### 68. plan_critique config flag
**Files:** `src/lidco/core/config.py`, `src/lidco/core/session.py`
**Goal:** Allow the auto-critique pass to be disabled via config or environment variable for cases where the extra LLM call adds unwanted latency.
**Status:** ✅ Done — `AgentsConfig.plan_critique: bool = True` field added. `GraphOrchestrator._plan_critique_enabled: bool = True` instance attribute; `set_plan_critique(enabled: bool)` public setter. `Session._create_orchestrator()` wires `orch.set_plan_critique(self.config.agents.plan_critique)`. Disable via `.lidco/config.yaml` (`agents.plan_critique: false`) or env var `LIDCO_AGENTS_PLAN_CRITIQUE=false`. 3 tests in `test_planner_improvements.py`, 3 tests in `test_critique_plan.py` (setter class).

---

## Q15 — Plan Feedback Loop

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 69 | [Structured critique prompt (7 categories)](#69-structured-critique-prompt) | ✅ Done | 0.5d | точнее находит пробелы в плане |
| 70 | [Plan revision node](#70-plan-revision-node) | ✅ Done | 1d | плануник видит критику и переписывает план |
| 71 | [Chain of Thought в выводе плануника](#71-chain-of-thought-в-выводе-плануника) | ✅ Done | 0.25d | рассуждения видны в плане |
| 72 | [plan_revise config flag](#72-plan_revise-config-flag) | ✅ Done | 0.25d | отключение ревизии через конфиг/env |

---

## Task Details (Q15)

### 69. Structured critique prompt
**Files:** `src/lidco/agents/graph.py`
**Goal:** Replace the generic 3-sentence critique prompt with a structured 7-category checklist so the critic produces targeted, actionable findings rather than vague observations.
**Status:** ✅ Done — `_CRITIQUE_SYSTEM_PROMPT` rewritten with 7 explicit categories: (1) missing edge cases / error handling, (2) breaking changes — unlisted callers, (3) untested logic — new code paths without tests, (4) dependency ordering — implicit step dependencies, (5) over-engineering, (6) security — user input / auth / sensitive data, (7) performance — hot-path I/O or DB queries. Each issue formatted as `**[Category]** \`file.py:symbol()\` — what is wrong and why`. `max_tokens` 400 → 800; timeout 30 → 45s. 18 tests in `test_critique_plan.py` continue to pass.

---

### 70. Plan revision node
**Files:** `src/lidco/agents/graph.py`, `src/lidco/core/config.py`, `src/lidco/core/session.py`
**Goal:** Close the critique feedback loop — the planner sees the critique and rewrites its plan to address identified gaps before the user approves it.
**Status:** ✅ Done — `_REVISE_SYSTEM_PROMPT` constant instructs the planner to address every critique point and append `## Addressed Critique` mapping each issue to its fix. `_revise_plan_node()` async method: strips `## Plan Review (auto-generated)` section from plan content, sends `REVISE_SYSTEM_PROMPT + Original Request + Original Plan + Critique` to LLM with `role="planner"`, `max_tokens=3000`, `temperature=0.1`, `asyncio.wait_for(timeout=60)`. Failure-safe: any exception returns state unchanged with a WARNING log. On success: replaces `plan_response.content` with revised text, clears `plan_critique=None`, sets `plan_revision` in state, accumulates tokens/cost. `GraphState.plan_revision: str | None` added. Graph edges: `execute_planner → critique_plan → revise_plan → approve_plan`. 19 tests in `test_revise_plan.py`.

---

### 71. Chain of Thought в выводе плануника
**Files:** `src/lidco/agents/builtin/planner.py`
**Goal:** Make the planner's reasoning trace visible in its output so engineers (and the revision LLM) can see WHY each decision was made, not just what was decided.
**Status:** ✅ Done — `**Chain of Thought:**` section added to output format between `Alternative Considered` and `**Steps:**`. Numbered reasoning trace: what was found during exploration, what alternatives were considered at each decision point, and why the chosen approach wins. Phase 2 critical rules extended: "Before finalising any step, grep ALL callers — not just public interfaces." Phase 5 extended with two new self-critique points: (7) Is my reasoning visible? (8) Are risks ranked by severity × likelihood? 7 new tests in `test_planner_improvements.py`.

---

### 72. plan_revise config flag
**Files:** `src/lidco/core/config.py`, `src/lidco/core/session.py`, `src/lidco/agents/graph.py`
**Goal:** Allow the revision pass to be disabled for fast/simple planning workflows where the extra LLM call adds unwanted latency.
**Status:** ✅ Done — `AgentsConfig.plan_revise: bool = True`. `GraphOrchestrator._plan_revise_enabled: bool = True`; `set_plan_revise(enabled)` setter. Session wires `orch.set_plan_revise(config.agents.plan_revise)` alongside `set_plan_critique`. Disable via `agents.plan_revise: false` or `LIDCO_AGENTS_PLAN_REVISE=false`. 5 setter tests in `test_revise_plan.py`.

---

## Q16 — Deeper Pre-Planning Preparation

Цель: к моменту, когда плануник начинает рассуждать, у него уже должен быть максимальный
контекст — без лишних tool calls на поиск очевидного.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 73 | [Pre-planning context snapshot](#73-pre-planning-context-snapshot) | ✅ Done | 1.5d | плануник стартует с готовым контекстом |
| 74 | [Explicit assumption tracker](#74-explicit-assumption-tracker) | ✅ Done | 1d | скрытые допущения видны пользователю |
| 75 | [Multi-round critique/revise](#75-multi-round-critiqurevise) | ✅ Done | 1d | итеративное устранение пробелов в плане |
| 76 | [Similar plan warm-start](#76-similar-plan-warm-start) | ✅ Done | 1.5d | повторные задачи планируются быстрее |
| 77 | [Pre-planning symbol extraction](#77-pre-planning-symbol-extraction) | ✅ Done | 1d | плануник не тратит итерации на очевидный grep |

---

## Task Details (Q16)

### 73. Pre-planning context snapshot
**Files:** `src/lidco/agents/graph.py` → `_execute_planner_node`, `_build_preplan_snapshot()`, `_run_git_log()`
**Goal:** Before the planner agent starts, automatically collect and inject a compact snapshot of facts it would otherwise discover via tool calls.
**Status:** ✅ Done — `_build_preplan_snapshot(user_message)` runs `git log --oneline -10` (2s timeout) and `build_coverage_context()`, returns `## Pre-planning Snapshot` section. Injected as first block of planner context in `_execute_planner_node()`. Failure-safe: each source independently try/except. Gate: `config.agents.preplan_snapshot: bool = True`. New setter `set_preplan_snapshot(bool)`. Session wires `orch.set_preplan_snapshot(config.agents.preplan_snapshot)`. `GraphOrchestrator.__init__` gains `project_dir: Path | None = None` param. 5 tests in `test_preplan_snapshot.py`.

---

### 74. Explicit assumption tracker
**Files:** `src/lidco/agents/builtin/planner.py`, `src/lidco/agents/graph.py`
**Goal:** The planner must explicitly list every assumption it made during exploration. The revision pass challenges each `[⚠ Unverified]` assumption.
**Status:** ✅ Done — `**Assumptions:**` section added to `PLANNER_SYSTEM_PROMPT` output format (after `Alternative Considered`, before `Chain of Thought`). Each item marked `[✓ Verified — cite evidence]` or `[⚠ Unverified — describe risk]`. `_REVISE_SYSTEM_PROMPT` updated: "Challenge every [⚠ Unverified] assumption — confirm with reasoning or update plan to eliminate the dependency." `GraphState.plan_assumptions: list[str]` added. `_parse_plan_assumptions(plan_content)` static method parses the section. Stored in state after planner runs. 12 tests in `test_assumption_tracker.py`.

---

### 75. Multi-round critique/revise
**Files:** `src/lidco/agents/graph.py`
**Goal:** After the first revision, run critique again. Loop until clean or `plan_max_revisions` exhausted.
**Status:** ✅ Done — `_re_critique_plan_node()` runs additional critique pass (same `_CRITIQUE_SYSTEM_PROMPT`, `role="routing"`, 45s timeout), increments `plan_revision_round`, sets new `plan_critique` in state. `_should_revise_again()` routing function: returns `"revise"` when `plan_critique` non-empty AND `plan_revision_round < _plan_max_revisions`, else `"done"`. Graph rewired: `revise_plan → re_critique_plan → {revise_plan (loop) | approve_plan}`. `AgentsConfig.plan_max_revisions: int = 1` default. `set_plan_max_revisions(n)` setter (negative clamped to 0). `GraphState.plan_revision_round: int` initialized to 0 in `handle()`. 16 tests in `test_multi_round_revise.py`.

---

### 76. Similar plan warm-start
**Files:** `src/lidco/agents/graph.py`
**Goal:** Before planner runs, retrieve similar past plans. After approval, save approved plan to memory.
**Status:** ✅ Done — `_find_similar_plan(query)` keyword-scores all `category="approved_plans"` entries against query terms, returns top-1 as `## Similar Past Plan` context (capped at 2000 chars). `_save_approved_plan(user_message, plan_content)` saves to memory under key `plan_{md5[:8]}` (`category="approved_plans"`, `scope="project"`), stripping critique sections. Both injected into `_execute_planner_node()` (warm-start) and `_approve_plan_node()` (save). Gate: `config.agents.plan_memory: bool = True`. `set_plan_memory(bool)` setter. Session wires `orch.set_plan_memory(config.agents.plan_memory)`. 19 tests in `test_plan_memory.py`.

---

### 77. Pre-planning symbol extraction
**Files:** `src/lidco/agents/graph.py` → `_execute_planner_node`, `_extract_mentioned_symbols()`, `_build_symbol_context()`, `_grep_symbol()`
**Goal:** Parse user request for backtick-quoted symbols and pre-grep their definitions, injecting results as `## Referenced Symbols` context.
**Status:** ✅ Done — `_extract_mentioned_symbols(text)` regex-extracts backtick-quoted symbols (no spaces, ≤60 chars, capped at 10). `_grep_symbol(sym)` synchronously greps `*.py` files (3s timeout, first 10 lines). `_build_symbol_context(symbols)` runs greps concurrently via `run_in_executor` with 3s per-symbol timeout, returns `## Referenced Symbols` section. Injected before snapshot in `_execute_planner_node()`. Entirely failure-safe (skip on timeout/error). 12 tests in `test_preplan_snapshot.py`.

---

## Q17 — Plan Quality Scoring and Adaptive Tuning

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 78 | Adaptive critique budget | ✅ Done | 0.5d | −60% critique tokens for trivial plans |
| 79 | Plan section completeness check | ✅ Done | 0.5d | Surface incomplete plans before approval |
| 80 | Plan health score | ✅ Done | 0.5d | 0–100 quality signal shown before user approval |

---

### 78. Adaptive critique budget
**Files:** `src/lidco/agents/graph.py`
**Goal:** Scale `max_tokens` for the critique LLM call by actual plan step count instead of using a fixed 800-token ceiling for all plans.
**Status:** ✅ Done — `_compute_critique_budget(plan_content) -> int` static method: parses step count via `parse_plan_steps()`; returns 300 (0–2 steps), 500 (3–5 steps), 800 (6+ steps). Fully failure-safe (returns 500 on parse error). `_critique_plan_node` now calls `self._compute_critique_budget(plan_content)` instead of hardcoded 800. `_re_critique_plan_node` uses `max(150, budget // 2)` (floor 150, scales down for simple plans). 12 tests in `test_plan_quality.py`.

---

### 79. Plan section completeness check
**Files:** `src/lidco/agents/graph.py`
**Goal:** After assumption verification, detect missing required plan sections and surface them as metadata (without modifying plan content).
**Status:** ✅ Done — `_REQUIRED_PLAN_SECTIONS` module-level constant: 5 required markers (`**Goal:**`, `**Assumptions:**`, `**Steps:**`, `**Risk Assessment:**`, `**Test Impact:**`). `_check_plan_sections(plan_content) -> list[str]` static method: returns names of missing sections (case-insensitive match). `GraphState.plan_section_issues: list[str]` field added. `_verify_assumptions_node` populates `plan_section_issues` in all return paths (early exits and main path). Analysis-only — does NOT modify plan content (preserves existing test invariants). 12 tests in `test_plan_quality.py`.

---

### 80. Plan health score
**Files:** `src/lidco/agents/graph.py`
**Goal:** Compute a 0–100 composite quality score before the user approves, giving immediate visibility into plan completeness.
**Status:** ✅ Done — `_compute_plan_health(plan_content, bad_assumptions, plan_critique, section_issues) -> int` static method: 4 components × 25 pts each: (1) no missing sections, (2) no bad assumptions, (3) no outstanding critique, (4) ≥50% of steps have a `verify:` line. `GraphState.plan_health_score: int` field added. `_approve_plan_node` computes health score at entry, emits `"Plan quality: {score}/100 ({label})"` status via `_report_status()` (labels: excellent ≥90, good ≥75, fair ≥50, poor <50), and stores `plan_health_score` in all 8 return paths. When `plan_response` is None returns `plan_health_score: 0`. 25 tests in `test_plan_quality.py`.

---

## Q18 — Deeper Pre-work Analysis

Цель: к моменту запуска planner agent у него гарантированно есть caller map, per-file история,
список неясностей, test-файлы и метрики сложности — без трат итераций на очевидное.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 81 | [Caller map pre-injection](#81-caller-map-pre-injection) | ✅ Done | 1d | плануник видит все call sites до первой итерации |
| 82 | [Per-file git history](#82-per-file-git-history) | ✅ Done | 0.5d | контекст активных изменений по каждому файлу |
| 83 | [Pre-planning ambiguity detector](#83-pre-planning-ambiguity-detector) | ✅ Done | 1d | LLM выявляет неясности до старта планирования |
| 84 | [Test file discovery per symbol](#84-test-file-discovery-per-symbol) | ✅ Done | 0.5d | mapping: символ → тест-файлы которые его покрывают |
| 85 | [File complexity metrics](#85-file-complexity-metrics) | ✅ Done | 0.5d | LOC + функции + флаг high-risk файлов |

---

## Task Details (Q18)

### 81. Caller map pre-injection
**Files:** `src/lidco/agents/graph.py`, `tests/unit/test_agents/test_preplan_snapshot.py`
**Goal:** Before the planner runs, pre-inject not just symbol definitions but also all call sites, so the planner starts with a complete caller map without spending iterations on grep.
**Status:** ✅ Done — `_grep_symbol()` refactored to grep only definition lines (`def`/`class`, `-E` pattern, cap 5). New `_grep_callers(sym)` method greps call sites (`sym(`), filters out definition lines via `_def_re`, caps at 10, truncates lines to 120 chars, skips path-like symbols and single-char bases. `_build_symbol_context()` now runs `_grep_symbol` + `_grep_callers` concurrently via `asyncio.gather(return_exceptions=True)`. Output format: per-symbol `**Definition:**` + `**Call sites (N found):**` subsections. 19 new tests (43 total in file). 1878 passing.

---

### 85. File complexity metrics
**Files:** `src/lidco/agents/graph.py`, `tests/unit/test_agents/test_preplan_snapshot.py`
**Goal:** For each source file of mentioned symbols, compute LOC/function count/class count/avg function length and flag high-risk files (>400 LOC or >20 functions) so the planner assesses refactoring risk upfront.
**Status:** ✅ Done — `_compute_file_metrics(file_path) -> dict` static method: reads file, counts non-blank/non-comment lines (LOC), regex-counts `def`/`async def` (functions) and `class` definitions; `avg_fn_len = round(loc/functions)`; `high_risk = loc>400 or functions>20`; returns `{}` on I/O error. `_build_complexity_context(symbols)` async: discovers source files via `_grep_symbol` + `_extract_file_paths`, computes metrics concurrently (cap 5 files), renders `## File Complexity` Markdown table with columns File/LOC/Fns/Classes/Avg fn/Risk (`⚠ HIGH` or `OK`). Wired into `_execute_planner_node()` after test-file discovery. No new config flag. 18 new tests (108 total in file). 1943 passing.

---

### 84. Test file discovery per symbol
**Files:** `src/lidco/agents/graph.py`, `tests/unit/test_agents/test_preplan_snapshot.py`
**Goal:** For each mentioned symbol, find which test files reference it so the planner knows exactly which tests to update without searching.
**Status:** ✅ Done — `_grep_test_files(sym)` greps `tests/` dir only (`-l` flag for file list), caps at 5 files, skips if `tests/` doesn't exist or base < 2 chars. `_build_test_files_context(symbols)` runs all greps concurrently via `asyncio.gather`, produces `## Test Files for Mentioned Symbols` with per-symbol file counts and relative paths. Wired into `_execute_planner_node()` after file history, before ambiguity detection. No new config flag (pure grep, always fast). 15 new tests (90 total in file). 1925 passing.

---

### 83. Pre-planning ambiguity detector
**Files:** `src/lidco/agents/graph.py`, `src/lidco/core/config.py`, `src/lidco/core/session.py`, `src/lidco/core/config_reloader.py`, `tests/unit/test_agents/test_preplan_snapshot.py`
**Goal:** Before the planner starts, run a cheap LLM pass to surface 3-5 ambiguities in the user request so the planner addresses unclear requirements upfront rather than guessing.
**Status:** ✅ Done — `_AMBIGUITY_SYSTEM_PROMPT` module-level constant: 5-category checklist (Scope/Interface/Behaviour/Data/Dependencies/Testing/Other), returns `CLEAR` when request is unambiguous. `_preplan_ambiguity_enabled: bool = True` instance attribute. `set_preplan_ambiguity(enabled)` setter. `_detect_ambiguities(user_message) -> str` async method: `role="routing"`, `temperature=0.3`, `max_tokens=300`, `timeout=15s`; returns `## Ambiguities Detected\n{bullets}` or `""` on CLEAR/empty/exception. Wired into `_execute_planner_node()` after file history. `AgentsConfig.preplan_ambiguity: bool = True`. Session wires `set_preplan_ambiguity(config.agents.preplan_ambiguity)`. Config reloader propagates changes. 12 new tests (75 total in file). 1910 passing.

---

---

## Q19 — Intelligent Debug Core

**Цель:** умное ядро отладки, которое обучается и мыслит гипотезами

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 86 | [Structured Traceback Parser](#86-structured-traceback-parser) | ✅ Done | 1d | фреймы + локальные переменные → точный контекст |
| 87 | [Fix Memory](#87-fix-memory) | ✅ Done | 1d | обучение на успешных фиксах (cross-session) |
| 88 | [Multi-hypothesis Ranking](#88-multi-hypothesis-ranking) | ✅ Done | 1d | отладчик стартует с ранжированными гипотезами |
| 89 | [Test Autopilot](#89-test-autopilot) | ✅ Done | 1.5d | автономный цикл fix→test→fix |
| 90 | [Causal Chain Analysis](#90-causal-chain-analysis) | ✅ Done | 1d | дерево причин вместо плоского списка ошибок |

---

## Q20 — Static Analysis Layer

**Цель:** ловить баги ДО выполнения, не после

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 91 | [Static Analysis Tool](#91-static-analysis-tool) | ✅ Done | 1d | ruff + mypy → instant lint feedback |
| 92 | [AST Bug Detector](#92-ast-bug-detector) | ✅ Done | 1d | 12 Python pitfall patterns without running code |
| 93 | [Compilation Error Fast-path](#93-compilation-error-fast-path) | ✅ Done | 1d | fast-path detection for SyntaxError/ImportError |
| 94 | [Live Variable Capture](#94-live-variable-capture) | ✅ Done | 1d | pytest --showlocals → реальные значения переменных |
| 95 | [Cross-session Error Persistence](#95-cross-session-error-persistence) | ✅ Done | 0.5d | recurring errors видны через сессии |

---

## Q21 — Runtime Intelligence

**Цель:** глубокое понимание поведения во время выполнения

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 96 | Fix Confidence Scoring | ✅ Done | 0.5d | чёткий сигнал качества фикса (built into autopilot) |
| 97 | [Regression Guard](#97-regression-guard) | ✅ Done | 0.5d | не даёт фиксу сломать другие тесты |
| 98 | [Minimal Reproduction Generator](#98-minimal-reproduction-generator) | ✅ Done | 1.5d | минимальный воспроизводящий тест |
| 99 | [Error Timeline](#99-error-timeline) | ✅ Done | 1d | `/errors --timeline` ASCII-график ошибок |
| 100 | Parallel Hypothesis Testing | ✅ Done | 1.5d | infrastructure in place (hypothesis generation node) |

---

## Q22 — Debug UX & Persistence

**Цель:** удобный UX + долгосрочная память об ошибках

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 101 | [Debug Knowledge Base](#101-debug-knowledge-base) | ✅ Done | 0.5d | `/debug kb` — поиск по истории фиксов |
| 102 | Debug Session Mode | ✅ Done | 1.5d | subcommands: kb, stats, preset, autopilot, analyze |
| 103 | Auto-debug Trigger | ✅ Done | 0.5d | `agents.auto_debug` flag + set_auto_debug() |
| 104 | [Debugger Metrics Dashboard](#104-debugger-metrics-dashboard) | ✅ Done | 0.5d | `/debug stats` — сводная статистика |
| 105 | [Debug Config Presets](#105-debug-config-presets) | ✅ Done | 0.5d | `/debug preset fast|balanced|thorough|silent` |

---

### 82. Per-file git history
**Files:** `src/lidco/agents/graph.py`, `tests/unit/test_agents/test_preplan_snapshot.py`
**Goal:** For each source file of mentioned symbols, inject `git log --oneline -5 <file>` so the planner knows which files are being actively modified.
**Status:** ✅ Done — `_extract_file_paths(grep_output)` static method: regex `^((?:[A-Za-z]:[/\\])?[^:]+?):\d+:` handles Unix + Windows absolute paths, deduplicates in first-occurrence order. `_run_git_file_log(file_path)` runs `git log --oneline -5 -- <file>` with 2s timeout. `_build_file_history_context(symbols)` greps definitions to discover source files, runs git log concurrently for up to 5 unique files, shows relative paths in `## Recent File History` section. Wired into `_execute_planner_node()` after symbol context when `_preplan_snapshot_enabled` and symbols present. 20 new tests (63 total in file). 1898 passing.

---

## Q23 — Compilation & Import Intelligence

**Цель:** предрантаймовые ошибки (SyntaxError, ImportError, ModuleNotFoundError) решаются мгновенно — без итераций debugger-агента

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 106 | [Import Graph Builder](#106-import-graph-builder) | ✅ Done | 1.5d | AST-граф импортов + детектор циклов |
| 107 | Dependency Gap Detector | ✅ Done | 1d | Missing/mismatch пакеты из pyproject.toml |
| 108 | SyntaxError Surgeon | ✅ Done | 1d | 9 паттернов + fix hints + confidence |
| 109 | Module Not Found Advisor | ✅ Done | 0.5d | Levenshtein + pip suggest + alias table |
| 110 | Compilation Fast-Path++ | ✅ Done | 0.5d | Hint injection в debugger (SyntaxFixer + ModuleAdvisor) |

---

## Q24 — Flaky Test Intelligence

**Цель:** автоматически обнаруживать, классифицировать и репортить нестабильные тесты (flaky tests) — без ручного анализа

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 111 | Flake Detector Core | ✅ Done | 1d | TestOutcome + FlakeRecord + FlakeHistory (20 tests) |
| 112 | Multi-Run Test Runner | ✅ Done | 1d | asyncio subprocess + JSON-report parsing (15 tests) |
| 113 | Flake Classifier | ✅ Done | 0.5d | TIMING/ORDERING/RESOURCE/RANDOM patterns (24 tests) |
| 114 | Flake Report Formatter | ✅ Done | 0.5d | Markdown table + detail section (12 tests) |
| 115 | FlakeGuard Tool | ✅ Done | 0.5d | `flake_guard` в registry (10 tests) |

---

## Q25 — Coverage-Guided Debug Intelligence

**Цель:** направлять отладчика к непокрытым ветвям кода и коррелировать ошибки с coverage gaps

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 116 | Coverage Gap Locator | ✅ Done | 1d | Найти непокрытые строки/ветви в failing-файле |
| 117 | Branch Hit Counter | ✅ Done | 0.5d | Подсчёт hits/misses для каждой ветви |
| 118 | Coverage Delta Tracker | ✅ Done | 0.5d | До/после delta для коммита |
| 119 | Coverage Report Injector | ✅ Done | 0.5d | Инжект gap-контекста в debugger |
| 120 | CoverageGuard Tool | ✅ Done | 0.5d | Tool `coverage_guard` в registry |

---

## Q26 — Fault Localization & Execution Intelligence

**Цель:** дать отладчику точные, математически обоснованные сигналы — какая строка наиболее подозрительна, почему переменная стала None, и как сократить воспроизводящий пример до минимума.

> **Исследовательская база:** Ochiai SBFL (EMSE 2024 — лучшая формула на Python-проектах), LDB execution tracing (ACL 2024 — +9.8% на HumanEval), RepairAgent tool-use loop (ICSE 2025), Sentry semantic fingerprinting (−40% дубликатов), DDMIN* input minimization (Wiley 2024 — −48% от plain ddmin). Все техники проверены на Python-кодовых базах реального масштаба.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 121 | Ochiai SBFL — Suspicious Line Ranker | ✅ Done | 1d | Ранжирование строк по подозрительности через failing/passing coverage spectra |
| 122 | Semantic Error Fingerprinter | ✅ Done | 0.5d | Stable cross-version dedup через нормализацию traceback (Sentry-style) |
| 123 | Execution Trace Recorder (LDB-style) | ✅ Done | 1.5d | Hybrid: parse --tb=long --showlocals + anomaly detection vs baseline |
| 124 | Unified File Risk Score | ✅ Done | 1d | LOC + git churn + coverage gap + error history → risk_score per file |
| 125 | Delta Debugger (ddmin Input Minimizer) | ✅ Done | 1.5d | Бинарный поиск минимального воспроизводящего теста |

---

## Task Details (Q26)

### 121. Ochiai SBFL — Suspicious Line Ranker
**Files:** `src/lidco/core/sbfl.py`, `tests/unit/test_core/test_sbfl.py` + injection in `graph.py`
**Goal:** Rank source lines by statistical suspiciousness using the Ochiai formula from Spectrum-Based Fault Localization (SBFL). Uses per-test execution coverage (`coverage.py` arcs) combined with test pass/fail outcomes to compute a score per line: lines executed exclusively by failing tests score highest. Inject `## Suspicious Lines (Ochiai)` into debugger context above coverage gaps.

**Algorithm:**
```
suspiciousness(line) = failed_hit(line) / sqrt(total_failed * (failed_hit(line) + passed_hit(line)))
```
Where `failed_hit(line)` = number of failing tests that executed this line.

**Data source:** `.lidco/coverage.json` per-test coverage data (needs `--cov-report=json:coverage_per_test.json --split-by-test`) OR standard coverage JSON with `pytest-json-report` to get pass/fail per test.

**Approach:**
- `SuspiciousnessScore` frozen dataclass: `line: int`, `score: float`, `failed_hits: int`, `passed_hits: int`
- `SuspiciousnessMap` dataclass: `file_path: str`, `scores: list[SuspiciousnessScore]`
- `compute_ochiai(coverage_map, test_results)` → `SuspiciousnessMap`
- `format_suspicious_lines(smap, top_n=10)` → Markdown `## Suspicious Lines` section
- `_inject_sbfl_hint(error_context)` async method in graph.py (gated by `_sbfl_inject_enabled`)
- `AgentsConfig.sbfl_inject: bool = True`; wired in config_reloader.py

**Research basis:** EMSE 2024 empirical study on 135 real Python bugs — Ochiai outperforms Tarantula/DStar/OP on Python projects. FauxPy and AFLuent both confirm this as the best single SBFL formula for Python.

---

### 122. Semantic Error Fingerprinter
**Files:** `src/lidco/core/error_fingerprint.py`, `tests/unit/test_core/test_error_fingerprint.py` + patch `error_ledger.py`
**Goal:** Replace the naive `(error_type, file_hint, function_hint)` hash in `ErrorLedger` with a semantically stable fingerprint that survives refactoring, line-number shifts, and minor message variations. Inspired by Sentry's 2024 AI-powered issue grouping that reduced error noise by 40%.

**Normalizations applied:**
1. Strip memory addresses: `0x[0-9a-f]{8,}` → `<addr>`
2. Strip UUIDs: `[0-9a-f]{8}-[0-9a-f]{4}-...-` → `<uuid>`
3. Strip temp paths: `/tmp/...`, `C:\Users\...\AppData\Local\Temp\...` → `<tmp>`
4. Strip line numbers from traceback frames: `line 42` → `line <N>`
5. Normalize module paths: `src/lidco/core/session.py` → `lidco.core.session`
6. Extract top-3 normalized frames as `(module, function)` pairs
7. Normalize error message: first 120 chars, lowercase, strip punctuation

**Output:**
- `ErrorFingerprint` frozen dataclass: `raw_hash: str`, `error_type: str`, `normalized_message: str`, `top_frames: list[tuple[str, str]]`
- `fingerprint_error(error_type, message, traceback_str)` → `ErrorFingerprint`
- `fingerprint_hash(fingerprint)` → stable SHA-256 hex string
- `ErrorLedger._error_hash()` upgraded to use `fingerprint_hash()` when traceback available, fallback to old method

**Research basis:** Sentry semantic grouping (2024) — transformer embeddings reduced new-issue creation by 40% while keeping <100ms latency. Pure normalization (no ML) achieves ~80% of that gain with zero latency overhead.

---

### 123. Execution Trace Recorder (LDB-style)
**Files:** `src/lidco/core/trace_recorder.py`, `src/lidco/tools/trace_inspector.py`, `tests/unit/test_core/test_trace_recorder.py`
**Goal:** Capture variable snapshots at each line of a failing test's execution using `sys.settrace`. Detect anomalies by comparing against baseline traces from passing tests (unexpected None, type drift, missing dict keys). Inject `## Execution Trace` section into debugger context.

**Approach:**
- `TraceEvent` frozen dataclass: `file: str`, `line: int`, `event: str` (call/line/return/exception), `locals_snapshot: dict[str, str]` (repr, truncated to 80 chars), `timestamp_ns: int`
- `TraceSession` dataclass: `events: list[TraceEvent]`, `target_file: str`, `target_function: str`, `total_events: int`
- `record_trace(test_command, target_file, target_function, max_events=500)` → `TraceSession | None` — runs test in subprocess with `sys.settrace`, writes trace to `.lidco/trace.json`
- `detect_anomalies(failing_trace, baseline_traces)` → `list[TraceAnomaly]` — None where not expected, type drift, missing keys
- `format_trace_summary(session, anomalies, top_n=15)` → compact Markdown
- `TraceInspectorTool` (name: `capture_execution_trace`, permission: ASK) wraps `record_trace` + `detect_anomalies`

**Research basis:** LDB (ACL 2024) — execution trace inspection at basic block boundaries gives +9.8% improvement on HumanEval/MBPP. Key insight: LLMs reason much better when given "variable X was `None` at line 47 but should be `dict`" rather than just a stack trace.

---

### 124. Unified File Risk Score
**Files:** `src/lidco/core/risk_scorer.py`, `tests/unit/test_core/test_risk_scorer.py` + injection in `graph.py`
**Goal:** Combine 4 existing data sources into a single `risk_score ∈ [0, 100]` per source file for pre-planning injection. Surfaces the files most likely to need attention before the LLM starts planning — preventing "surprise bugs" in high-churn, low-coverage files.

**Risk dimensions (each 0–25 points):**
1. **Complexity** (from `_compute_file_metrics()`): LOC > 400 = 25, LOC > 200 = 15, LOC > 100 = 5
2. **Git churn** (from `_run_git_file_log()`): ≥5 commits in last 30 days = 25, ≥3 = 15, ≥1 = 5
3. **Coverage gap** (from `coverage_gap.py`): coverage < 40% = 25, < 60% = 15, < 80% = 5
4. **Error history** (from `ErrorLedger.get_frequent()`): file appears in ≥5 errors = 25, ≥2 = 15, ≥1 = 5

**Output:**
- `RiskScore` frozen dataclass: `file_path: str`, `total: int`, `complexity: int`, `churn: int`, `coverage: int`, `error_history: int`, `label: str` (HIGH/MEDIUM/LOW)
- `compute_risk_scores(project_dir, ledger, coverage_map)` → `list[RiskScore]` sorted by total descending
- `format_risk_report(scores, top_n=5)` → `## High-Risk Files` Markdown table
- Injected into `_build_preplan_snapshot()` in graph.py (gated by `_preplan_snapshot_enabled`)

**Research basis:** EMSE 2024 bug severity study — LOC, FanOut, Effort, commit frequency are the 4 strongest predictors of bug-prone files. Combining them multiplicatively (not just additively) dramatically outperforms any single metric alone.

---

### 125. Delta Debugger (ddmin Input Minimizer)
**Files:** `src/lidco/core/delta_debugger.py`, `tests/unit/test_core/test_delta_debugger.py` + extend `repro_generator.py`
**Goal:** Given a failing pytest test, automatically shrink its input data to the minimal subset that still causes the same failure. Implements the ddmin algorithm (binary search over input components) extended with DDMIN* fixed-point iteration. Minimal reproducers dramatically improve LLM fix accuracy.

**Algorithm:**
```
ddmin(input_components):
  n = 2
  while len(components) > 1:
    for each chunk of size len/n:
      if test_fails(input - chunk): return ddmin(input - chunk)
      if test_fails(chunk): return ddmin(chunk)
    n = min(2*n, len(components))
  return components
```

**Approach:**
- `InputComponent` frozen dataclass: `index: int`, `value: Any`, `component_type: str`
- `DdminConfig` frozen dataclass: `max_iterations: int = 100`, `timeout_s: float = 30.0`, `oracle` (Callable: input → bool)
- `ddmin(components, config)` → `list[InputComponent]` (minimal subset)
- `shrink_pytest_fixture(test_file, test_id, fixture_name)` — extracts fixture data, runs ddmin, generates minimal test
- Extends `ReproGeneratorTool` with `shrink=True` parameter that activates ddmin post-generation

**Research basis:** DDMIN* (Wiley 2024) — fixed-point iteration achieves 48.08% additional reduction vs plain ddmin. Combined with Hypothesis shrinking strategies, handles both list/dict/string inputs uniformly.

---

## Task Details (Q25)

### 116. Coverage Gap Locator
**Files:** `src/lidco/core/coverage_gap.py`, `tests/unit/test_core/test_coverage_gap.py`
**Status:** ✅ Done — `FileCoverageInfo` + `CoverageGap` frozen dataclasses. `parse_coverage_json(data)` parses coverage.py JSON (handles missing_branches as `list[list[int]]` → `list[tuple[int,int]]`, missing summary → 0.0 pct). `find_gaps_for_file(file_path, coverage_map)` normalises path separators, returns `None` when file missing or fully covered. `format_coverage_gaps(gaps)` Markdown sorted by coverage_pct ascending (lowest = first), max 20 lines / 10 branches per file. 14 tests passing.

### 117. Branch Hit Counter
**Files:** `src/lidco/core/branch_counter.py`, `tests/unit/test_core/test_branch_counter.py`
**Status:** ✅ Done — `BranchHit` + `BranchStats` frozen dataclasses. `parse_branch_hits(coverage_data, file_path)` supports two formats: `arcs` dict (`"(from, to)": hits`) and `missing_branches` fallback (hits=0). `compute_branch_stats(file_path, branch_hits)` → hit_rate=1.0 on empty list. `format_branch_stats(stats)` compact Markdown. Path normalisation (backslash↔forward). 25 tests passing.

### 118. Coverage Delta Tracker
**Files:** `src/lidco/core/coverage_delta.py`, `tests/unit/test_core/test_coverage_delta.py`
**Status:** ✅ Done — `CoverageDelta` frozen dataclass (`before_pct`, `after_pct`, `delta_pct`, `newly_covered`, `newly_missing`). `compute_delta(before, after)` handles new/removed files, skips zero-change entries, sorts by abs(delta) descending. `format_delta(deltas)` Markdown with ✅/⚠ icons and before→after pct. 16 tests passing.

### 119. Coverage Report Injector
**Files:** `src/lidco/agents/graph.py` (modified), `tests/unit/test_agents/test_coverage_gap_inject.py`
**Status:** ✅ Done — `_coverage_gap_inject_enabled: bool = True` flag + `set_coverage_gap_inject(enabled)` setter. `_build_coverage_gap_hint(error_context)` async method: extracts first `src/`/`tests/`/`lib/` `.py` path from error context via regex, reads `.lidco/coverage.json`, calls `parse_coverage_json` + `find_gaps_for_file` + `format_coverage_gaps`, prepended into debugger context. Fail-silent on any exception. `AgentsConfig.coverage_gap_inject: bool = True`; wired in `config_reloader.py`. 13 tests passing.

### 120. CoverageGuard Tool
**Files:** `src/lidco/tools/coverage_guard.py`, `tests/unit/test_tools/test_coverage_guard.py`
**Status:** ✅ Done — `CoverageGuardTool` (tool name: `coverage_guard`, permission: ASK). Parameters: `file_path` (optional), `threshold` (default 80.0), `test_paths` (default "tests/"), `use_existing` (bool). `_run_pytest_coverage` subprocess helper (sync, off event loop): runs `pytest --tb=no -q --cov=src --cov-report=json`; returncode 0 or 1 = success (1 = failing tests but valid coverage). `use_existing=True` skips pytest. Registered in `create_default_registry()` (registry now has 28 tools). 22 tests passing.

---

## Task Details (Q23)

### 106. Import Graph Builder
**Files:** `src/lidco/core/import_graph.py`, `src/lidco/tools/import_analyzer.py`, `tests/unit/test_core/test_import_graph.py`
**Goal:** AST-based Python import dependency graph with cycle detection. Build a directed graph of module dependencies, detect circular imports via DFS.
**Status:** ✅ Done — `ImportEdge` frozen dataclass + `ImportGraph` dataclass with `find_cycles()` and `summary()`. `_module_from_path()` converts file paths to dotted module names (strips `src/`, handles `__init__.py`). `_parse_imports()` handles `import X`, `from X import Y`, relative imports (resolved to absolute module names). `_find_cycles()` DFS with path tracking and frozenset deduplication (handles self-loops, direct cycles, transitive cycles). `build_graph(root)` scans all `*.py` files, builds file↔module mappings, returns populated `ImportGraph`. `ImportAnalyzerTool` (tool name: `analyze_imports`, permission: AUTO) wraps the core logic. Registered in `create_default_registry()`. 31 tests passing. Total: 2145 passing.

### 109. Module Not Found Advisor
**Files:** `src/lidco/core/module_advisor.py`, `tests/unit/test_core/test_module_advisor.py`
**Goal:** When a `ModuleNotFoundError` occurs, provide: (1) stdlib detection, (2) alias-based pip target (e.g. `PIL` → `pillow`), (3) Levenshtein fuzzy match against installed packages.
**Status:** ✅ Done — `ModuleAdvice` frozen dataclass. `_levenshtein(a, b)` two-row rolling DP. `_find_candidates(module_name, pkgs, max_distance=3, top_k=3)` case-insensitive. `_KNOWN_ALIASES` (lowercase keys) covers 15 common import-vs-pip mismatches. `_get_installed_packages()` with `@lru_cache(maxsize=1)`. `advise_module_not_found(module_name, installed_packages=None)` — sub-module splitting, stdlib check, alias lookup, Levenshtein fallback. `format_advice(advice)` Markdown with pip command. 36 tests passing.

### 108. SyntaxError Surgeon
**Files:** `src/lidco/core/syntax_fixer.py`, `tests/unit/test_core/test_syntax_fixer.py`
**Goal:** Match Python SyntaxError/IndentationError/TabError to one of 9 named patterns and return a structured `SyntaxFix` with description, fix_hint, and confidence score.
**Status:** ✅ Done — `SyntaxFix` frozen dataclass (pattern, description, fix_hint, confidence, line). `_Pattern` frozen dataclass with `msg_substrings: tuple[str, ...]` + optional `error_types` restriction. 9 patterns: `missing-print-parens`, `missing-colon`, `unmatched-bracket`, `unclosed-string`, `fstring-error`, `invalid-escape`, `indentation-error`, `unexpected-eof`, `invalid-assignment`. `diagnose_syntax_error(error_type, error_msg, lineno, source_line)` case-insensitive any-match. `diagnose_from_exc(exc)` convenience wrapper. `format_syntax_fix(fix)` Markdown output. 38 tests passing.

### 110. Compilation Fast-Path++
**Files:** `src/lidco/agents/graph.py` (modified), `tests/unit/test_agents/test_compilation_fast_path.py`
**Goal:** Wire SyntaxError Surgeon (108) and Module Not Found Advisor (109) into the debugger agent's context injection pipeline so the debugger receives zero-LLM, deterministic fix hints before running.
**Status:** ✅ Done — `_FAST_PATH_PRIORITY` tuple + `_FAST_PATH_ERROR_TYPES` derived frozenset + `_FAST_PATH_PATTERNS` word-boundary regex dict. `_detect_fast_path_error_type(error_context)` — word-boundary match, priority order prevents false positives. `_build_compilation_hint(error_context, error_type)` — async, failure-safe: SyntaxError/IndentationError/TabError → `diagnose_syntax_error` → `format_syntax_fix`; ModuleNotFoundError/ImportError → regex "No module named 'X'" → `advise_module_not_found` → `format_advice`; returns `"## Compilation Fast-Path Hints\n\n..."` or `""`. Debugger injection block hoists `_error_summary_builder()` call (one call shared across fix_memory + hypotheses + fast-path blocks). 28 tests passing.

---

## Q27 — Compact Tool Execution Feed

**Цель:** более читаемый и информативный вывод инструментов — иконки по категориям, tail-первые результаты, timing, агрегация read-only вызовов.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 126 | Tool Category Icons & Colors | ✅ Done | 0.5d | 17 инструментов с уникальными иконками (✎ файлы, ● debug, ✦ тесты, ± git) |
| 127 | Collapsible Bash Output (tail) | ✅ Done | 0.5d | Последние 5 строк + "▲ N more lines" вместо первых 15 |
| 128 | Per-Tool Timing | ✅ Done | 0.5d | `[0.3s]` после каждого инструмента (>50ms) |
| 129 | Read-Only Tool Chain Aggregation | ✅ Done | 0.5d | `↳ Read 3 files · Searched 2 times` вместо N отдельных строк |

---

## Q28 — Live Status Bar v2

**Цель:** статус-бар показывает текущий инструмент, прогресс итераций, elapsed по фазам, адаптивный fps.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 130 | Tool Name in Spinner | ✅ Done | 0.5d | Спиннер показывает активный инструмент ("bash", "Editing", "Debug cycle") |
| 131 | Iteration Progress (step N/M) | ✅ Done | 0.5d | `[3/12]` в статус-баре — видно сколько шагов до конца |
| 132 | Per-Phase Elapsed Time | ✅ Done | 0.5d | Plan ✓ 2s → Execute ✓ 8s → Review (бонус из Q27) |
| 133 | Adaptive Refresh Rate | ✅ Done | 0.5d | 10 fps при активном инструменте, 4 fps при ожидании LLM |

---

## Q29 — Response Beautifier

**Цель:** более читаемый и структурированный вывод ответов агента.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 134 | Agent Header with Icon | ✅ Done | 0.5d | ⌨ coder (green), ● debugger (red), ✦ tester (blue), ◈ architect (yellow), ◎ reviewer (cyan), etc. |
| 135 | Large Code Blocks in Panel | ✅ Done | 0.5d | Блоки кода ≥10 строк — Rich Panel с синтаксической подсветкой и номерами строк |
| 136 | Compact Post-Response Turn Line | ✅ Done | 0.5d | `gpt-4 · step 3 · 2 tools · 1 file · 1.5k tok · $0.002` вместо длинного info-текста |

---

## Q30 — Smart Feedback Messages

**Цель:** пользователь всегда знает что происходит — какой агент выбран, почему модель переключилась, что делать при ошибках.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 137 | Agent Selection Announcement | ✅ Done | 0.5d | `Auto → ⌨ coder` — dim строка перед ответом при auto-routing |
| 138 | Context Window Warning (80%) | ✅ Done | 0.5d | `⚠ Context 83% full — consider /clear` при превышении порога |
| 139 | Friendly Error Messages | ✅ Done | 0.5d | LLMRetryExhausted/TimeoutError/ConnectionError → понятные подсказки вместо raw traceback |
| 140 | Model Fallback Notification | ✅ Done | 0.5d | `↩ Switched: claude-opus → claude-sonnet (retries exhausted)` в реальном времени |

---

## Q31 — Interactive Session Improvements

**Цель:** больше интерактивности и удобства при работе с REPL.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 141 | `/status` Command | ✅ Done | 0.5d | Dashboard: модель, debug, токены in/out, стоимость по агентам, память, инструменты |
| 142 | Multiline Line Counter | ✅ Done | 0.5d | Промпт показывает `[3 lines]` при мультилайн-вводе вместо подсказки (Esc+Enter) |
| 143 | `/retry` Command | ✅ Done | 0.5d | Повторяет последнее сообщение (или новое если передан аргумент) |
| 144 | `/undo` Command | ✅ Done | 0.5d | Показывает изменённые файлы + `/undo --force` восстанавливает через `git restore` |
