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

---


## Q37 — Safety & Permissions

**Цель:** реализовать систему разрешений и контроля — фундаментальная функция всех конкурентов (Claude Code, Codex CLI, Droid). Без неё LIDCO небезопасно запускать в автономном режиме.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 244 | [LIDCO.md — инструкции проекта](#244-lidcomd) | ✅ Done | 2d | единый источник правил для агентов |
| 245 | [Система режимов разрешений](#245-permission-modes) | ✅ Done | 3d | безопасный автономный режим |
| 246 | [Per-tool правила с wildcards](#246-per-tool-rules) | ✅ Done | 2d | точный контроль разрешений |
| 247 | [Интерактивный approval flow](#247-approval-flow) | ✅ Done | 2d | y/n/always/never перед опасными ops |
| 248 | [/permissions команда](#248-permissions-command) | ✅ Done | 1d | просмотр и управление правилами |
| 249 | [Sandboxed shell execution](#249-sandboxed-shell) | ✅ Done | 3d | изоляция процессов, configurable writable roots |
| 250 | [Path-scoped правила](#250-path-scoped-rules) | ✅ Done | 1d | правила активны только для нужных файлов |
| 251 | [/init — auto-generate LIDCO.md](#251-init-command) | ✅ Done | 2d | анализ проекта и генерация готового файла инструкций |
| 252 | [Rule-based command allowlist](#252-command-allowlist) | ✅ Done | 1d | allow-list часто используемых команд без повторных запросов |

---

## Q38 — MCP Protocol

**Цель:** поддержка Model Context Protocol — стандарт для подключения внешних инструментов. Claude Code: 50+ серверов, Codex CLI: 40+. LIDCO: 0. Самый большой функциональный пробел.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 253 | [MCP stdio transport — ядро](#253-mcp-stdio) | ✅ DONE | 4d | подключение локальных MCP серверов (Browser, Playwright, etc.) |
| 254 | [MCP tool injection в агенты](#254-mcp-tool-injection) | ✅ DONE | 2d | MCP-инструменты автоматически доступны всем агентам |
| 255 | [MCP HTTP/SSE transport](#255-mcp-http) | ✅ DONE | 3d | удалённые MCP серверы (Linear, Slack, GitHub, Notion) |
| 256 | [/mcp команда — интерактивный UI](#256-mcp-command) | ✅ DONE | 1d | list/add/remove/status MCP серверов в сессии |
| 257 | [Per-project mcp.json конфиг](#257-mcp-config) | ✅ DONE | 1d | .lidco/mcp.json + ~/.lidco/mcp.json с приоритетами |
| 258 | [OAuth auth flow для HTTP MCP](#258-mcp-oauth) | ✅ DONE | 2d | авторизация в GitHub, Linear, Notion через браузер |
| 259 | [LIDCO как MCP сервер](#259-lidco-as-mcp) | ✅ DONE | 2d | expose собственных инструментов LIDCO для внешних агентов |
| 260 | [MCP hot-reload](#260-mcp-hotreload) | ✅ DONE | 1d | изменение mcp.json без рестарта сессии |

---

## Q39 — Headless Mode & CI/CD

**Цель:** неинтерактивный режим для автоматизации, CI/CD, pre-commit хуков. Все конкуренты имеют exec-режим. LIDCO работает только как REPL.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 261 | [lidco exec — headless режим](#261-lidco-exec) | ✅ DONE | 3d | неинтерактивное выполнение: lidco exec "fix all tests" |
| 262 | [JSON output mode (--json)](#262-json-output) | ✅ DONE | 1d | машиночитаемый вывод всех действий и результатов |
| 263 | [Правильные exit codes](#263-exit-codes) | ✅ DONE | 0.5d | 0=success, 1=task_failed, 2=config_error, 3=permission_denied |
| 264 | [GitHub Actions интеграция](#264-github-actions) | ✅ DONE | 2d | lidco-action: установка, proxy, lidco exec в CI |
| 265 | [Pre-commit hook режим](#265-precommit-hook) | ✅ DONE | 1d | code review и security scan перед каждым коммитом |
| 266 | [GitLab CI/CD поддержка](#266-gitlab-ci) | ✅ DONE | 1d | unified diff как .patch + git apply --check |
| 267 | [Pipe-friendly stdin/stdout](#267-pipe-mode) | ✅ DONE | 1d | echo "fix tests" | lidco exec, composable CLI |

---

## Q40 — YAML Agents & Worktrees

**Цель:** создание агентов через .md файлы без написания кода (как в Claude Code .claude/agents/ и Droid .factory/droids/), параллельные агенты в изолированных git worktrees.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 268 | [YAML-агенты (.lidco/agents/)](#268-yaml-agents) | ✅ Done | 4d | создание агентов через Markdown+YAML frontmatter |
| 269 | [Git worktree isolation](#269-worktree-isolation) | ✅ Done | 3d | каждый параллельный агент в отдельном git worktree |
| 270 | [Background agent execution](#270-background-agents) | ✅ Done | 2d | Ctrl+B переводит агента в фон, уведомление по завершению |
| 271 | [/agents команда](#271-agents-command) | ✅ Done | 1d | list/inspect/stop агентов, просмотр running threads |
| 272 | [Agent memory dirs](#272-agent-memory) | ✅ Done | 1d | персистентная память на агента (.lidco/memory/{agent_name}/) |
| 273 | [Tool allowlist/denylist в YAML](#273-agent-tools) | ✅ Done | 1d | tools: [read, grep, bash] + disallowed_tools: [file_write] |
| 274 | [Per-agent permission mode](#274-agent-permissions) | ✅ Done | 1d | permission_mode: plan для read-only аналитических агентов |
| 275 | [Agent forking через Task tool](#275-agent-forking) | ✅ Done | 2d | агент создаёт субагентов по имени через Task(subagent_type=name) |

---

## Q41 — UX Completeness

**Цель:** закрыть UX-пробелы по сравнению с конкурентами — команды для управления контекстом, файлами, темой, моделью.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 276 | [/compact [focus]](#276-compact-command) | ✅ Done | 1d | явная LLM-компрессия истории с указанием что сохранить |
| 277 | [/context — визуальный gauge](#277-context-gauge) | ✅ Done | 1d | цветовая шкала + % + разбивка токенов по слоям |
| 278 | [/mention — добавить файлы в контекст](#278-mention-command) | ✅ Done | 1d | /mention src/foo.py инжектирует файл в следующий turn |
| 279 | [/model — смена модели в сессии](#279-model-switch) | ✅ Done | 0.5d | без рестарта, немедленный эффект для следующего запроса |
| 280 | [/theme — выбор цветовой темы](#280-theme-command) | ✅ Done | 1d | preview + сохранение: dark/light/solarized/nord/monokai |
| 281 | [/add-dir — расширить доступные директории](#281-adddir-command) | ✅ Done | 1d | добавить внешние папки к сессии (--add-dir ../backend) |
| 282 | [@-mentions файлов в промпте](#282-at-mentions) | ✅ Done | 2d | @src/foo.py в тексте автоматически читает и инжектирует файл |
| 283 | [Checkpoint-based undo](#283-checkpoints) | ✅ Done | 2d | снапшот перед каждым file-write → /undo N шагов назад |
| 284 | [Interactive diff approval](#284-diff-approval) | ✅ Done | 2d | approve/reject/edit каждого file-write до реальной записи |
| 285 | [Session resume после crash](#285-session-resume) | ✅ Done | 2d | автосохранение состояния сессии → lidco --resume SESSION_ID |

---

## Q42 — TDD Pipeline & Batch

**Цель:** нативная TDD-оркестрация как в Droid (spec→test→code loop) и /batch для параллельной обработки больших задач как в Claude Code.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 286 | [Native TDD pipeline](#286-tdd-pipeline) | ✅ Done | 4d | spec-writer → tester (RED) → coder (GREEN) → verify loop |
| 287 | [/spec — specification mode](#287-spec-mode) | ✅ Done | 2d | генерация детальной спецификации перед реализацией |
| 288 | [/batch — параллельная декомпозиция](#288-batch-command) | ✅ Done | 4d | задача разбивается на 5-30 единиц, каждая в своём worktree |
| 289 | [/simplify — параллельный code review](#289-simplify-command) | ✅ Done | 2d | 3 параллельных reviewer → объединение и исправление замечаний |
| 290 | [Best-of-N code generation](#290-best-of-n) | ✅ Done | 2d | --attempts N → N вариантов решения → выбор лучшего по тестам |
| 291 | [Test-first enforcement](#291-test-first) | ✅ Done | 1d | предупреждение/блокировка если coder пишет без тестов |
| 292 | [Auto-coverage gap closure](#292-coverage-closure) | ✅ Done | 2d | tester агент автодописывает тесты для непокрытых строк |

---

## Q43 — Skills & Plugin System

**Цель:** переиспользуемые workflow-определения как в Codex CLI (SKILL.md) и Claude Code Skills. Пользователи создают и шарят автоматизации без написания кода.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 293 | [Skills система (.lidco/skills/)](#293-skills-system) | ✅ Done | 3d | SKILL.md с YAML frontmatter (name, desc, prompt, context, scripts) |
| 294 | [Skill discovery → slash-команды](#294-skill-discovery) | ✅ Done | 1d | авто-обнаружение из .lidco/skills/ и ~/.lidco/skills/ |
| 295 | [Skill chaining (pipeline)](#295-skill-chaining) | ✅ Done | 2d | /skill1 | /skill2 — результат одного передаётся следующему |
| 296 | [Custom slash commands (commands.yaml)](#296-custom-commands) | ✅ Done | 1d | .lidco/commands.yaml: name: /review, prompt: "review {args}" |
| 297 | [Global skill library (~/.lidco/skills/)](#297-global-skills) | ✅ Done | 1d | персональные skills, доступные во всех проектах |
| 298 | [/skills команда + popup](#298-skills-command) | ✅ Done | 1d | list/describe/run/edit; popup при вводе / в REPL |
| 299 | [Skill версионирование и зависимости](#299-skill-versioning) | ✅ Done | 1d | version: 1.2, requires: [git, pytest], авто-проверка |

---

## Q44 — API Server & IDE Integration

**Цель:** JSON-RPC сервер как API-слой для IDE-интеграций, базовый VS Code extension, remote доступ к сессиям.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 300 | [lidco server — JSON-RPC API](#300-api-server) | ✅ Done | 4d | HTTP+WebSocket сервер для IDE-коннекторов и внешних клиентов |
| 301 | [WebSocket streaming API](#301-ws-streaming) | ✅ Done | 2d | real-time стриминг ответов и статусов агента в IDE |
| 302 | [REST API для tool execution](#302-rest-api) | ✅ Done | 2d | POST /execute, GET /status, GET /history, GET /tools |
| 303 | [VS Code extension (MVP)](#303-vscode-extension) | ✅ Done | 5d | chat panel + diff viewer + inline suggestions через lidco server |
| 304 | [LSP bridge](#304-lsp-bridge) | ✅ Done | 3d | Language Server Protocol адаптер — поддержка любого LSP редактора |
| 305 | [Remote session (HTTPS tunnel)](#305-remote-session) | ✅ Done | 3d | подключение к lidco server с другой машины через токен |
| 306 | [Multi-session management](#306-multi-session) | ✅ Done | 2d | несколько параллельных сессий, /sessions для переключения |

---

## Q45 — Advanced Context & Memory

**Цель:** контекст как OS-ресурс (Droid-подход) — умное управление что включать, когда сжимать, как шарить между сессиями и командой.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 307 | [Adaptive context paging](#307-context-paging) | ✅ Done | 4d | динамическое ранжирование что включать — "OS for context" |
| 308 | [Path-scoped rule loading](#308-path-scoped-loading) | ✅ Done | 2d | rules/ грузятся только при работе с matching файлами — экономия токенов |
| 309 | [Multi-level memory hierarchy](#309-memory-hierarchy) | ✅ Done | 2d | session > project > user > org; конкретное перекрывает общее |
| 310 | [Memory search и browse](#310-memory-search) | ✅ Done | 1d | /memory search <query> по всем memory файлам с ранжированием |
| 311 | [Team/org shared memory](#311-shared-memory) | ✅ Done | 3d | .lidco/team-memory.md — общая база знаний команды в репо |
| 312 | [Context layers visualization](#312-context-layers) | ✅ Done | 1d | /context детально: LIDCO.md N tok, memory N tok, RAG N tok, history N tok |
| 313 | [Memory auto-compression](#313-memory-compression) | ✅ Done | 2d | при росте MEMORY.md > 500 строк — LLM сжимает старые записи |

---

## Q46 — Advanced AI Features

**Цель:** возможности, превышающие конкурентов — multi-model sampling, адаптивное планирование, режим глубокого мышления.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 314 | [Multi-model sampling (best-of-N)](#314-multimodel-sampling) | ✅ Done | 3d | N параллельных LLM-вызовов → выбор лучшего по critic |
| 315 | [/think — режим глубокого мышления](#315-think-mode) | ✅ Done | 1d | расширенный token budget на reasoning, extended thinking API |
| 316 | [Speculative tool pre-fetch](#316-speculative-prefetch) | ✅ Done | 3d | предсказать следующий tool call и начать выполнение заранее |
| 317 | [MPC-inspired adaptive planning](#317-mpc-planning) | ✅ Done | 4d | после каждого шага пересчитывать оптимальную траекторию плана |
| 318 | [Confidence-weighted routing](#318-confidence-routing) | ✅ Done | 2d | роутер выдаёт confidence score → re-route при низкой уверенности |
| 319 | [Plan rollback on failure](#319-plan-rollback) | ✅ Done | 2d | автоматический rollback на checkpoint при провале шага плана |
| 320 | [Self-consistency checking](#320-self-consistency) | ✅ Done | 2d | N независимых ответов → выбор наиболее консистентного |

---

## Q47 — Enterprise & Security

**Цель:** enterprise-grade безопасность и аудит. DroidShield-аналог. Пригодность для production-команд.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 321 | [AI Shield — pre-commit анализ](#321-ai-shield) | ✅ Done | 3d | LLM-анализ диффа перед коммитом: уязвимости, баги, секреты |
| 322 | [Full audit trail](#322-audit-trail) | ✅ Done | 2d | каждое действие агента логируется с reasoning в SQLite |
| 323 | [Session replay](#323-session-replay) | ✅ Done | 2d | воспроизведение прошлой сессии пошагово для отладки |
| 324 | [Secret detection (pre-commit)](#324-secret-detection) | ✅ Done | 1d | обнаружение API-ключей и паролей в изменённых файлах |
| 325 | [Role-based access control (RBAC)](#325-rbac) | ✅ Done | 3d | роли: viewer/editor/admin — ограничения tool access per role |
| 326 | [Usage analytics dashboard](#326-analytics) | ✅ Done | 2d | /analytics: top commands, cost по дням, agent usage, LLM calls |
| 327 | [Compliance reporting](#327-compliance) | ✅ Done | 2d | экспорт audit log в JSON/CSV для compliance и security отчётов |

---

## Q48 — Cloud & Async Execution

**Цель:** асинхронные фоновые задачи, персистентность сессий, multi-repo поддержка как в Codex CLI Cloud Tasks.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 328 | [Async task queue](#328-cloud-tasks) | ✅ Done | 5d | lidco exec --async → задача в очереди, lidco task status ID |
| 329 | [Session persistence (resume)](#329-session-persistence) | ✅ Done | 3d | сессия сохраняется при выходе → lidco --resume SESSION_ID |
| 330 | [Multi-repo support](#330-multi-repo) | ✅ Done | 2d | --add-repo ../backend — работа с несколькими репозиториями |
| 331 | [Task notification system](#331-notifications) | ✅ Done | 1d | desktop/webhook уведомления по завершению долгих задач |
| 332 | [Task result apply](#332-task-apply) | ✅ Done | 2d | lidco task apply TASK_ID — применение изменений из async задачи |
| 333 | [Parallel task management](#333-parallel-tasks) | ✅ Done | 2d | /tasks — список активных задач, cancel/pause/resume |
| 334 | [Best-of-N async runs](#334-best-of-n-async) | ✅ Done | 2d | --attempts 3 → 3 параллельных запуска, выбор лучшего по тестам |

---

## Q49 — Code Quality & Static Analysis

**Цель:** автономные модули анализа кода — сложность, дубли, мёртвый код, покрытие типами, возможности рефакторинга.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 335 | [CommitAnalyzer](#335-commit-analyzer) | ✅ Done | 1d | анализ истории коммитов: авторы, churn-файлы, качество сообщений |
| 336 | [DiffSummarizer](#336-diff-summarizer) | ✅ Done | 1d | парсинг unified diff → структурированная сводка по файлам |
| 337 | [ComplexityAnalyzer](#337-complexity) | ✅ Done | 2d | цикломатическая и когнитивная сложность на уровне функций (AST) |
| 338 | [DuplicateDetector](#338-duplicates) | ✅ Done | 2d | поиск дублированных блоков кода по хешу скользящего окна |
| 339 | [DeadCodeDetector](#339-dead-code) | ✅ Done | 2d | поиск неиспользуемых символов в файле через AST |
| 340 | [TypeCoverageChecker](#340-type-coverage) | ✅ Done | 1d | покрытие аннотациями типов: параметры и возвращаемые значения |
| 341 | [RefactorScanner](#341-refactor) | ✅ Done | 2d | поиск возможностей рефакторинга: длинные функции, глубокое вложение, магические числа |

---

## Q50 — Code Intelligence & Analysis

**Цель:** расширение анализа кода: lint-агрегация, граф зависимостей, индекс символов, анализ влияния изменений, покрытие документацией, проверка именования.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 342 | [LintRunner](#342-lint-runner) | ✅ Done | 1d | парсинг ruff/flake8/mypy → единый LintReport с deduplicated merge |
| 343 | [DependencyGraph](#343-dep-graph) | ✅ Done | 2d | граф зависимостей модулей, поиск циклов, транзитивные deps |
| 344 | [SymbolIndex](#344-symbol-index) | ✅ Done | 2d | кросс-файловый индекс символов: функции, классы, методы, импорты |
| 345 | [ChangeImpactAnalyzer](#345-impact) | ✅ Done | 2d | анализ влияния изменений через reversed dependency graph |
| 346 | [DocCoverageChecker](#346-doc-coverage) | ✅ Done | 1d | покрытие docstrings: функции + классы, AST-based |
| 347 | [NamingChecker](#347-naming) | ✅ Done | 1d | проверка соглашений об именах: snake_case/PascalCase/UPPER_CASE |

---

## Q51 — Deep Code Intelligence

**Цель:** продвинутый анализ безопасности, маппинг тестов на источники, API-экстракция, метрики проекта.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 348 | [SecurityScanner](#348-security-scanner) | ✅ Done | 2d | AST-детекция eval/exec/pickle/yaml.load/os.system/weak hashes + assert |
| 349 | [TestCoverageMapper](#349-test-map) | ✅ Done | 1d | маппинг test_X.py → X.py, извлечение тест-функций и Referenced символов |
| 350 | [ApiExtractor](#350-api-extractor) | ✅ Done | 2d | извлечение публичного API: сигнатуры, аннотации, docstrings, async |
| 351 | [CodeMetricsCollector](#351-metrics) | ✅ Done | 1d | LOC, blank/comment lines, функции, классы, avg/max длина функций; ProjectMetrics |

---

## Q52 — Advanced Code Analysis

**Цель:** детекция паттернов проектирования, анализ миграций API, оптимизация импортов, качество обработки исключений.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 352 | [MigrationDetector](#352-migration) | ✅ Done | 2d | сравнение API двух версий: удалённые/переименованные символы, изменения сигнатур |
| 353 | [PatternMatcher](#353-patterns) | ✅ Done | 2d | детекция Singleton/Factory/Observer/ContextManager/Iterator/Decorator |
| 354 | [ImportOptimizer](#354-imports) | ✅ Done | 1d | неиспользуемые/дублированные/star-импорты с рекомендациями |
| 355 | [ExceptionAnalyzer](#355-exceptions) | ✅ Done | 1d | bare except, broad except, swallowed exceptions, reraise from None |

---

## Q53 — Extended Code Analysis

**Цель:** расширение аналитической подсистемы — трекинг переменных, анализ классов, поток управления, унифицированный отчёт.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 356 | [StringAnalyzer](#356-strings) | ✅ Done | 1d | hardcoded URLs/IPs/paths, long strings, TODO in literals |
| 357 | [VariableTracker](#357-variables) | ✅ Done | 1d | unused variables, shadowing, global misuse |
| 358 | [ClassAnalyzer](#358-classes) | ✅ Done | 1d | inheritance depth, god class, missing docstrings |
| 359 | [FlowAnalyzer](#359-flow) | ✅ Done | 1d | unreachable code, missing return, inconsistent return, infinite loop |
| 360 | [ReportBuilder](#360-report) | ✅ Done | 1d | унифицированный агрегатор всех анализов с severity mapping |

---

## Q54 — Bug Fixes & Stability

**Цель:** устранение найденных багов во взаимодействии компонентов, утечек памяти, гонок потоков.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 361 | [Reminder pop index bug](#361-reminder-pop) | ✅ Done | 0.5d | crash при >1 напоминании в одном turn |
| 362 | [disallowed_tools enforcement](#362-disallowed-tools) | ✅ Done | 0.5d | безопасность: запрет инструментов действительно работает |
| 363 | [ConfigReloader thread-safety lock](#363-config-reloader-lock) | ✅ Done | 0.5d | гонка потоков при обновлении mtimes |
| 364 | [ConfigReloader asyncio.set_event_loop](#364-config-reloader-loop) | ✅ Done | 0.5d | корректный event loop при MCP hot-reload |
| 365 | [Agent tool schema cache versioning](#365-schema-cache-version) | ✅ Done | 1d | агенты видят новые MCP tools без рестарта |
| 366 | [Bounded collections in CommandRegistry](#366-bounded-collections) | ✅ Done | 0.5d | нет утечки памяти при длинных сессиях |
| 367 | [Error ledger warning on persistent failure](#367-ledger-warning) | ✅ Done | 0.5d | пользователь видит если DB недоступна |

---

## Q55 — Interactive UX Improvements

**Цель:** удобство работы в REPL — внешний редактор, автодополнение, уведомления, экспорт сессии.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 368 | [External editor for long input](#368-editor-popup) | ✅ Done | 1d | открыть $EDITOR для многострочного ввода |
| 369 | [Fuzzy slash-command completion](#369-fuzzy-complete) | ✅ Done | 2d | Tab-дополнение с fuzzy-поиском по командам |
| 370 | [@mention file auto-complete](#370-mention-complete) | ✅ Done | 1d | Tab после @ — fuzzy выбор файлов из проекта |
| 371 | [Hunk-level diff approval](#371-hunk-approve) | ✅ Done | 2d | accept/reject/edit каждый hunk по отдельности |
| 372 | [Desktop notifications](#372-notifications) | ✅ Done | 1d | системное уведомление когда агент завершил задачу |
| 373 | [Session export](#373-session-export) | ✅ Done | 1d | /export → markdown/HTML с подсветкой кода |
| 374 | [Context window meter](#374-context-meter) | ✅ Done | 1d | статус-бар: [████░░] 65% context используется |

---

## Q56 — Git Superpowers

**Цель:** полноценная работа с git из REPL — конфликты, PR, bisect, ветки, stash.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 375 | [AI conflict resolver](#375-conflict-resolver) | ✅ Done | 2d | /conflict — AI разрешает merge-конфликты с объяснением |
| 376 | [git bisect integration](#376-bisect) | ✅ Done | 2d | /bisect — AI находит коммит-виновник регрессии |
| 377 | [Branch management commands](#377-branch) | ✅ Done | 1d | /branch, /checkout, /stash list|pop|push из REPL |
| 378 | [Auto PR creation](#378-auto-pr) | ✅ Done | 2d | /pr-create — AI генерирует описание PR и создаёт через gh/API |
| 379 | [PR review mode](#379-pr-review) | ✅ Done | 2d | /pr-review <number> — загружает diff PR, AI комментирует |
| 380 | [--from-pr session start](#380-from-pr) | ✅ Done | 1d | lidco --from-pr 123 — стартовать сессию из контекста PR |
| 381 | [Commit message templates](#381-commit-templates) | ✅ Done | 1d | шаблоны commit message в .lidco/commit-template.md |

---

## Q57 — Session & Workspace Management

**Цель:** ветвление сессий, профили рабочих пространств, визуализация контекста.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 382 | [Session forking](#382-session-fork) | ✅ Done | 2d | /fork — разветвить текущий разговор, вернуться к ветке |
| 383 | [Named sessions with description](#383-named-sessions) | ✅ Done | 1d | lidco --session my-feature — именованные сессии |
| 384 | [Session search and filter](#384-session-search) | ✅ Done | 1d | /session list --query "auth" — поиск по истории сессий |
| 385 | [Workspace profiles](#385-workspace-profiles) | ✅ Done | 2d | профили (frontend/backend/data) с разными моделями и агентами |
| 386 | [Session replay](#386-session-replay) | ✅ Done | 2d | /replay — воспроизвести команды из сессии в новом контексте |
| 387 | [Context visualizer](#387-context-visual) | ✅ Done | 2d | /context tree — дерево что именно в контексте и сколько токенов |
| 388 | [Multi-repo support](#388-multi-repo) | ✅ Done | 2d | работа с несколькими репозиториями в одной сессии |

---

## Q58 — Multi-Agent Orchestration 2.0

**Цель:** сравнение агентов, pipeline builder, broadcast, human-in-the-loop.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 389 | [Agent comparison mode](#389-agent-compare) | 🔲 Todo | 3d | запустить задачу на N агентах параллельно, показать diff результатов |
| 390 | [Agent pipeline builder (YAML)](#390-pipeline-yaml) | 🔲 Todo | 3d | декларативное описание pipeline агентов в YAML с условиями |
| 391 | [Broadcast mode](#391-broadcast) | 🔲 Todo | 2d | /broadcast — разослать задачу всем агентам, агрегировать ответы |
| 392 | [Agent performance leaderboard](#392-leaderboard) | 🔲 Todo | 2d | /agents stats — рейтинг агентов по скорости/качеству/цене |
| 393 | [Human-in-the-loop checkpoints](#393-hitl) | 🔲 Todo | 2d | точки одобрения в pipeline: агент ждёт подтверждения |
| 394 | [Agent delegation with context](#394-delegation) | 🔲 Todo | 2d | агент передаёт задачу другому агенту с контекстом и ожидает результат |
| 395 | [Cross-session agent memory](#395-agent-memory) | 🔲 Todo | 2d | агент помнит решения из прошлых сессий через MemoryStore |

---

## Q59 — Code Execution & Runtime

**Цель:** выполнение кода прямо в REPL, дебаггер, sandbox, управление venv.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 396 | [In-REPL code execution](#396-repl-exec) | 🔲 Todo | 2d | /run python/js — выполнить сниппет с выводом + ошибками |
| 397 | [Interactive debugger (pdb)](#397-pdb) | 🔲 Todo | 3d | /debug run <file> — запустить с pdb, AI анализирует стек |
| 398 | [Test runner from REPL](#398-test-run) | 🔲 Todo | 1d | /test path/to/test.py::func — запустить конкретный тест |
| 399 | [Docker execution sandbox](#399-docker) | 🔲 Todo | 3d | выполнять bash команды в изолированном Docker-контейнере |
| 400 | [Virtual env manager](#400-venv) | 🔲 Todo | 2d | /venv create|activate|list — управление venv из REPL |
| 401 | [Dependency installer](#401-deps) | 🔲 Todo | 1d | /install pkg — установить зависимость с объяснением зачем она нужна |
| 402 | [Code output differ](#402-output-diff) | 🔲 Todo | 2d | сравнить вывод до и после изменений автоматически |

---

## Q60 — External Integrations

**Цель:** интеграция с GitHub Issues, CI/CD, Slack, OpenAPI.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 403 | [GitHub Issues integration](#403-gh-issues) | ✅ Done | 2d | /issue list|view|create|close — Issues прямо из REPL |
| 404 | [CI/CD pipeline status](#404-ci-status) | ✅ Done | 2d | /ci — статус GitHub Actions/GitLab CI для текущей ветки |
| 405 | [Slack notification integration](#405-slack) | ✅ Done | 1d | отправить результат задачи в Slack webhook |
| 406 | [Linear/Jira ticket integration](#406-tickets) | ✅ Done | 2d | /ticket view|update — задачи из Linear/Jira в контексте агента |
| 407 | [OpenAPI client generator](#407-openapi) | ✅ Done | 2d | импорт openapi.yaml — AI генерирует typed клиент на Python/TS |
| 408 | [API test runner](#408-api-test) | ✅ Done | 2d | /http METHOD /path — выполнить HTTP запрос и проанализировать ответ |
| 409 | [Web browser automation (basic)](#409-browser) | ✅ Done | 3d | playwright-based browser tool для AI: click/fill/screenshot |

---

## Q61 — Smart Proactive Assistance

**Цель:** проактивная помощь — детекция багов на лету, авторефакторинг, предложения следующего шага.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 410 | [Proactive bug detector (Bugbot)](#410-bugbot) | ✅ Done | 3d | при save файла — фоновая проверка, уведомление о багах |
| 411 | [Regression detector on save](#411-regression) | ✅ Done | 2d | запустить связанные тесты при сохранении, показать регрессии |
| 412 | [Smart auto-fix](#412-auto-fix) | ✅ Done | 2d | /fix — автоматически исправить простые lint/type ошибки |
| 413 | [Next-action suggestions](#413-suggestions) | ✅ Done | 2d | после ответа агента — 3 предложения следующего шага |
| 414 | [Security scan on save](#414-sec-scan) | ✅ Done | 2d | при сохранении файла — фоновая проверка секретов и OWASP |
| 415 | [Performance hint injection](#415-perf-hints) | ✅ Done | 2d | при edit — AI замечает N+1 запросы, ненужные циклы, подсказывает |
| 416 | [Code smell auto-refactor](#416-smell-refactor) | ✅ Done | 2d | /refactor suggest — показать code smells с preview рефакторинга |

---

## Q62 — Voice & Multimodal

**Цель:** голосовой ввод, анализ изображений, генерация диаграмм.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 417 | [Voice input (speech-to-text)](#417-voice) | ✅ Done | 3d | /voice — записать речь, конвертировать в промпт через Whisper |
| 418 | [Image/screenshot analysis](#418-image) | ✅ Done | 2d | /image path.png — AI анализирует скриншот ошибки или UI |
| 419 | [Diagram generation](#419-diagrams) | ✅ Done | 2d | /diagram — AI генерирует Mermaid/PlantUML диаграмму из кода |
| 420 | [Visual diff output](#420-visual-diff) | ✅ Done | 2d | side-by-side diff с inline Rich-рендерингом изменений |
| 421 | [PDF/document reader](#421-pdf) | ✅ Done | 1d | читать PDF/docx как контекст для агента |
| 422 | [Screen capture integration](#422-screen) | ✅ Done | 2d | /screenshot — захват экрана, отправка в vision-модель |

---

## Q63 — Cost & Model Optimization

**Цель:** расширенное мышление, адаптивный бюджет токенов, local LLM, сравнение моделей.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 423 | [Extended thinking support](#423-thinking) | ✅ Done | 2d | claude-3-7/claude-sonnet thinking budget для сложных задач |
| 424 | [Adaptive token budgeting](#424-adaptive-budget) | ✅ Done | 2d | автоматически увеличивать/уменьшать бюджет по сложности задачи |
| 425 | [Cache warming strategies](#425-cache-warm) | ✅ Done | 2d | предзагрузка системного промпта до первого запроса пользователя |
| 426 | [Model cost comparison tool](#426-cost-compare) | ✅ Done | 1d | /compare-models — одна задача → несколько моделей, сравнить цену/качество |
| 427 | [Local model support (Ollama)](#427-ollama) | ✅ Done | 3d | подключить Ollama для offline режима и дешёвых задач |
| 428 | [Batched parallel LLM calls](#428-batch-llm) | ✅ Done | 2d | объединять одновременные LLM-вызовы в batch API запросы |
| 429 | [Cost budget alerts](#429-budget-alerts) | ✅ Done | 1d | предупреждение при приближении к суточному/месячному лимиту |

---

## Q64 — Developer Experience & IDE

**Цель:** VS Code extension, LSP, настройка REPL, wizard инициализации.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 430 | [VS Code extension (basic)](#430-vscode) | ✅ Done | 5d | sidebar panel, встроенный чат, diff preview в editor |
| 431 | [LSP bridge improvements](#431-lsp) | ✅ Done | 3d | hover definitions, go-to-definition через lidco LSP server |
| 432 | [Keybinding customization](#432-keybindings) | ✅ Done | 1d | ~/.lidco/keybindings.json — переназначить горячие клавиши в REPL |
| 433 | [REPL theme improvements](#433-themes) | ✅ Done | 1d | 8 встроенных тем + поддержка custom theme через YAML |
| 434 | [Plugin/extension API](#434-plugin-api) | ✅ Done | 3d | стабильный public API для написания плагинов на Python |
| 435 | [Project setup wizard](#435-wizard) | ✅ Done | 2d | lidco init — интерактивный wizard: язык, фреймворк, агенты, конфиг |
| 436 | [Inline code actions](#436-inline-actions) | ✅ Done | 2d | нажать Ctrl+. на ошибке — меню быстрых действий AI |

---

## Q65 — Observability & Analytics

**Цель:** дашборд затрат, аналитика агентов, экспорт метрик, health check.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 437 | [Real-time cost dashboard](#437-cost-dashboard) | ✅ Done | 2d | /dashboard — TUI с графиками токенов/стоимости в реальном времени |
| 438 | [Agent performance analytics](#438-agent-analytics) | ✅ Done | 2d | /agents analytics — среднее время, успешность, стоимость по агентам |
| 439 | [Token usage heatmap](#439-heatmap) | ✅ Done | 2d | какие файлы/функции потребляют больше всего токенов контекста |
| 440 | [Coverage trend tracker](#440-coverage-trend) | ✅ Done | 1d | история изменений покрытия по коммитам, предупреждение о деградации |
| 441 | [Session analytics export](#441-analytics-export) | ✅ Done | 1d | /analytics export → JSON/CSV со всеми метриками сессии |
| 442 | [Health check command](#442-health) | ✅ Done | 1d | lidco health — проверить API ключи, модели, tools, RAG, DB |
| 443 | [Error pattern visualization](#443-error-viz) | ✅ Done | 2d | /errors viz — ASCII граф частоты ошибок по времени и типу |

---

## Task Details (Q54+)

### 361. Reminder pop index bug
**Файл:** `src/lidco/cli/app.py`
**Цель:** исправить краш `IndexError` при срабатывании нескольких напоминаний одновременно.
**Проблема:** после сбора индексов в `_fired: list[int]` и `reversed()` pop, первый `pop(0)` сдвигает список, следующие индексы становятся невалидными.
**Исправление:**
```python
# Заменить pop-цикл на list comprehension:
fired_set = set(_fired)
commands._reminders = [r for i, r in enumerate(commands._reminders) if i not in fired_set]
```
**Тесты:** 3 теста в `test_q54/test_reminder_pop.py`: один reminder, два одновременно, три одновременно.

---

### 362. disallowed_tools enforcement
**Файл:** `src/lidco/agents/base.py`
**Цель:** поле `AgentConfig.disallowed_tools` должно реально блокировать инструменты.
**Проблема:** `_get_tools()` только фильтрует по allowlist (`tools`), игнорируя `disallowed_tools`.
**Исправление:**
```python
def _get_tools(self) -> list[BaseTool]:
    tools = self._tool_registry.list_tools()
    if self._config.tools:
        tools = [t for t in tools if t.name in self._config.tools]
    if self._config.disallowed_tools:
        tools = [t for t in tools if t.name not in self._config.disallowed_tools]
    return tools
```
**Тесты:** 4 теста: allowlist only, denylist only, both, empty config.

---

### 363. ConfigReloader thread-safety lock
**Файл:** `src/lidco/core/config_reloader.py`
**Цель:** защитить `_mtimes` и `_agent_mtimes` от гонки потоков.
**Исправление:** добавить `self._lock = threading.Lock()` в `__init__`, оборачивать `_check()` в `with self._lock`.
**Тесты:** 2 теста: concurrent read+write не вызывает RuntimeError.

---

### 364. ConfigReloader asyncio.set_event_loop
**Файл:** `src/lidco/core/config_reloader.py`
**Цель:** при MCP hot-reload в background thread корректно задать event loop.
**Исправление:**
```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    loop.run_until_complete(_apply_mcp())
finally:
    loop.close()
    asyncio.set_event_loop(None)
```
**Тесты:** 1 тест: горячая перезагрузка MCP в thread не выбрасывает RuntimeError.

---

### 365. Agent tool schema cache versioning
**Файл:** `src/lidco/agents/base.py`
**Цель:** агенты замечают инжекцию новых MCP tools и инвалидируют свой кэш схем.
**Исправление:** добавить `_schema_cache_version: int = -1` в `BaseAgent.__init__()`. В `_get_tool_schemas()` проверять `registry.schema_version != self._schema_cache_version` и пересчитывать при несовпадении.
**Тесты:** 2 теста: кэш инвалидируется после `inject_mcp_tools()`, не инвалидируется без изменений.

---

### 366. Bounded collections in CommandRegistry
**Файл:** `src/lidco/cli/commands.py`
**Цель:** предотвратить неограниченный рост списков за длинную сессию.
**Исправление:** заменить `list` на `collections.deque` с maxlen:
- `_turn_times`: `deque(maxlen=500)`
- `_edited_files`: `deque(maxlen=200)`
**Тесты:** 2 теста: после N+1 записей длина не превышает maxlen.

---

### 367. Error ledger warning on persistent failure
**Файл:** `src/lidco/core/session.py`
**Цель:** пользователь видит предупреждение если ErrorLedger недоступен более 3 раз.
**Исправление:** счётчик `_ledger_failures: int`, при `>= 3` — `renderer.warning("ErrorLedger недоступен, история ошибок не сохраняется")`.
**Тесты:** 2 теста: одна ошибка — без предупреждения, три ошибки — предупреждение.

---

### 368. External editor for long input
**Файл:** `src/lidco/cli/app.py`
**Цель:** нажать Alt+E или ввести `\\edit` → открыть `$EDITOR` для редактирования промпта.
**Подход:**
- Записать текущий ввод во временный файл
- Запустить `os.environ.get("EDITOR", "nano")` через `subprocess.run()`
- После закрытия прочитать файл и использовать как промпт
- Показать `[N lines loaded from editor]` в статус-баре
**Тесты:** 3 теста в `test_q55/test_editor_popup.py`.

---

### 369. Fuzzy slash-command completion
**Файл:** `src/lidco/cli/app.py`, `src/lidco/cli/completer.py` (новый)
**Цель:** нажать Tab при вводе `/co` → показать `/commit`, `/compact`, `/cost`.
**Подход:**
- `LidcoCompleter(Completer)` для prompt_toolkit
- При вводе `/` — предложить все команды с fuzzy-matching (rapidfuzz или stdlib SequenceMatcher)
- При вводе `@` — предложить файлы из проекта (Glob `**/*.py`)
- Показывать описание команды справа от подсказки
**Тесты:** 4 теста в `test_q55/test_completer.py`.

---

### 370. @mention file auto-complete
**Файл:** `src/lidco/cli/completer.py`
**Цель:** после `@src/` — показать файлы директории с fuzzy-matching.
**Подход:** расширить `LidcoCompleter` — при `word_before_cursor.startswith("@")` сканировать файловую систему от CWD, показывать совпадения.
**Тесты:** 3 теста.

---

### 371. Hunk-level diff approval
**Файл:** `src/lidco/cli/diff_viewer.py`, `src/lidco/cli/app.py`
**Цель:** пользователь может принять/отклонить каждый hunk изменений отдельно.
**Подход:**
- Парсить unified diff на hunks (`@@` секции)
- Показывать каждый hunk с кнопками `[a]ccept / [s]kip / [e]dit`
- Применять только одобренные hunks через `FileWriteTool`
**Тесты:** 4 теста в `test_q55/test_hunk_approve.py`.

---

### 372. Desktop notifications
**Файл:** `src/lidco/cli/notifier.py` (новый)
**Цель:** системное уведомление когда агент завершил долгую задачу (>30 сек).
**Подход:**
- Windows: `win10toast` или `winotify` через subprocess `powershell.exe -Command ...`
- macOS: `osascript -e 'display notification ...'`
- Linux: `notify-send`
- Graceful fallback если ни одно не работает
- Конфиг `notifications.enabled: bool`, `notifications.min_task_seconds: int = 30`
**Тесты:** 3 теста в `test_q55/test_notifier.py`.

---

### 373. Session export
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/cli/session_exporter.py` (новый)
**Цель:** `/export [--format md|html|json] [filename]` — экспорт разговора.
**Подход:**
- Markdown: заголовок + turn-by-turn с code blocks
- HTML: самодостаточный файл с подсветкой (Pygments inline CSS)
- JSON: структурированный вывод с метаданными
- Открыть файл в браузере для HTML через `webbrowser.open()`
**Тесты:** 4 теста в `test_q55/test_session_export.py`.

---

### 374. Context window meter
**Файл:** `src/lidco/cli/stream_display.py`
**Цель:** в статус-баре показывать процент использования context window.
**Подход:**
- `_StatusBar.set_context_usage(used_tokens, max_tokens)`
- Прогресс-бар: `[████░░░░] 48%` — зелёный <70%, жёлтый 70-85%, красный >85%
- Обновлять после каждого LLM-ответа через token callback
**Тесты:** 3 теста в `test_q55/test_context_meter.py`.

---

### 375. AI conflict resolver
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/tools/conflict_resolver.py` (новый)
**Цель:** `/conflict [file]` — AI анализирует merge-конфликты и предлагает разрешение.
**Подход:**
- Найти файлы с маркерами `<<<<<<< / ======= / >>>>>>>`
- Для каждого конфликта вызвать LLM с обеими версиями + контекстом файла
- Показать предложение + объяснение, запросить подтверждение
- Применить выбранные разрешения
**Тесты:** 5 тестов в `test_q56/test_conflict_resolver.py`.

---

### 376. git bisect integration
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/bisect <failing-test>` — AI автоматизирует bisect для поиска регрессии.
**Подход:**
- Запустить `git bisect start`
- Автоматически запускать тест и отмечать good/bad
- AI анализирует найденный коммит и объясняет причину регрессии
**Тесты:** 3 теста в `test_q56/test_bisect.py`.

---

### 377. Branch management commands
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/branch [list|create|delete|rename]`, `/checkout <branch>`, `/stash [list|push|pop]`.
**Подход:** тонкие обёртки над git subprocess с Rich-форматированием вывода + AI-подсказки.
**Тесты:** 5 тестов в `test_q56/test_branch_commands.py`.

---

### 378. Auto PR creation
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/tools/gh_tool.py` (новый)
**Цель:** `/pr [--draft] [--base main]` — AI генерирует title + body PR, создаёт через `gh pr create`.
**Подход:**
- `git log main..HEAD --oneline` + `git diff main...HEAD --stat` → LLM
- Показать preview title+body, запросить подтверждение
- Запустить `gh pr create --title ... --body ...`
**Тесты:** 4 теста в `test_q56/test_auto_pr.py`.

---

### 379. PR review mode
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/pr-review <number>` — загрузить diff PR в контекст, AI пишет review комментарии.
**Подход:**
- `gh pr diff <number>` → распарсить на файлы и hunks
- Вызвать security+coder агентов с каждым файлом
- Форматировать как GitHub review comments (line-level)
- Опция `/pr-review submit` — отправить комментарии через `gh pr review`
**Тесты:** 4 теста в `test_q56/test_pr_review.py`.

---

### 380. --from-pr session start
**Файл:** `src/lidco/__main__.py`, `src/lidco/cli/app.py`
**Цель:** `lidco --from-pr 123` — стартовать сессию с контекстом PR #123.
**Подход:**
- Получить `gh pr view 123 --json title,body,files,diff`
- Инжектировать в начальный контекст сессии
- Установить initial prompt: "Review and help with PR #123: {title}"
**Тесты:** 3 теста в `test_q56/test_from_pr.py`.

---

### 381. Commit message templates
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `.lidco/commit-template.md` — шаблон для генерации commit messages.
**Подход:**
- Файл содержит примеры конвенций и запрещённые паттерны
- Инжектировать в prompt при вызове `/commit`
- Fallback на стандартный Conventional Commits если шаблона нет
**Тесты:** 2 теста в `test_q56/test_commit_templates.py`.

---

### 382. Session forking
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/cli/session_store.py`
**Цель:** `/fork [name]` — создать новую сессию-ответвление от текущей точки.
**Подход:**
- Сохранить текущую историю как `parent_session_id`
- Создать новую сессию с той же историей + метадатой `fork_of`
- `/session list` показывает дерево fork-ов
- `/fork back` — вернуться к родительской сессии
**Тесты:** 5 тестов в `test_q57/test_session_fork.py`.

---

### 383. Named sessions with description
**Файл:** `src/lidco/__main__.py`, `src/lidco/cli/session_store.py`
**Цель:** `lidco --session my-feature` — именованная сессия с автосохранением.
**Подход:**
- `--session <name>` загружает существующую или создаёт новую с этим именем
- `SessionStore` индексирует по имени + дата последнего изменения
- `/session rename <new-name>` переименовать текущую
**Тесты:** 4 теста в `test_q57/test_named_sessions.py`.

---

### 384. Session search and filter
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/session list --query "auth" --since 7d` — поиск по истории сессий.
**Подход:**
- Полнотекстовый поиск по JSON истории (ripgrep или stdlib)
- Фильтры: `--since`, `--agent`, `--has-files`, `--min-turns`
- Результат в Rich-таблице с превью первого сообщения
**Тесты:** 4 теста в `test_q57/test_session_search.py`.

---

### 385. Workspace profiles
**Файл:** `src/lidco/core/config.py`, `src/lidco/__main__.py`
**Цель:** `lidco --profile frontend` — набор настроек (модель, агенты, tools) для типа проекта.
**Подход:**
- `~/.lidco/profiles/frontend.yaml` — переопределяет config поверх базового
- Встроенные профили: `frontend`, `backend`, `data`, `devops`, `security`
- `/profile list|use|save|delete` — управление профилями
**Тесты:** 5 тестов в `test_q57/test_workspace_profiles.py`.

---

### 386. Session replay
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/replay [session-id] [--dry-run]` — воспроизвести все пользовательские сообщения.
**Подход:**
- Извлечь из `SessionStore` все user-сообщения
- Повторно отправить каждое в текущий контекст
- `--dry-run` — только показать что будет выполнено
- Полезно для регрессионного тестирования поведения агентов
**Тесты:** 3 теста в `test_q57/test_session_replay.py`.

---

### 387. Context visualizer
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/core/session.py`
**Цель:** `/context tree` — дерево из чего состоит текущий контекст с размерами.
**Подход:**
- Разбить context string на секции (## заголовки)
- Подсчитать токены каждой секции (cl100k estimate)
- Отобразить Rich Tree с `[N tok]` у каждого узла
- Суммарный счётчик и процент от лимита
**Тесты:** 4 теста в `test_q57/test_context_viz.py`.

---

### 388. Multi-repo support
**Файл:** `src/lidco/core/session.py`, `src/lidco/core/config.py`
**Цель:** работать с несколькими репозиториями одновременно.
**Подход:**
- `config.repos: list[str]` — дополнительные директории
- `MultiRepoContext` — объединяет контексты нескольких репо
- `/repos add <path>` — добавить репо в сессию
- Инструменты понимают `repo:<name>/path/file.py` синтаксис
**Тесты:** 4 теста в `test_q57/test_multi_repo.py`.

---

### 389. Agent comparison mode
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/agents/comparison.py` (новый)
**Цель:** `/compare <task>` — запустить задачу на N агентах параллельно, показать diff ответов.
**Подход:**
- `AgentComparator.run(task, agents: list[str])` — asyncio.gather
- Показать ответы side-by-side в Rich Columns
- Diff между ответами через difflib
- Пользователь выбирает лучший вариант
**Тесты:** 4 теста в `test_q58/test_agent_compare.py`.

---

### 390. Agent pipeline builder (YAML)
**Файл:** `src/lidco/agents/pipeline.py` (новый)
**Цель:** декларативное описание pipeline в YAML с условиями и ветвлением.
**Схема:**
```yaml
name: review-and-fix
steps:
  - agent: security
    output: security_report
  - agent: coder
    condition: "security_report contains CRITICAL"
    input: security_report
  - agent: tester
    parallel: true
  - agent: reviewer
    parallel: true
```
**Тесты:** 5 тестов в `test_q58/test_pipeline_yaml.py`.

---

### 391. Broadcast mode
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/broadcast <message>` — отправить одно сообщение всем зарегистрированным агентам.
**Подход:**
- Запустить все агенты параллельно с одним промптом
- Агрегировать ответы в единый отчёт: уникальные находки от каждого
- Дедупликация совпадающих выводов
**Тесты:** 3 теста в `test_q58/test_broadcast.py`.

---

### 392. Agent performance leaderboard
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/agents stats [--period 7d]` — рейтинг агентов по ключевым метрикам.
**Метрики:** среднее время ответа, токены/задача, успешность (нет ERROR в ответе), стоимость.
**Подход:** агрегировать из `ErrorHistory` + token callback + timing из `_agent_stats`.
**Тесты:** 3 теста в `test_q58/test_agent_leaderboard.py`.

---

### 393. Human-in-the-loop checkpoints
**Файл:** `src/lidco/agents/pipeline.py`, `src/lidco/cli/approval.py`
**Цель:** в pipeline добавить точки `type: checkpoint` — агент останавливается и ждёт одобрения.
**Подход:**
- `type: checkpoint` в YAML step → вызвать `approval.ask()`
- Показать что было сделано до этой точки
- Пользователь выбирает: continue / abort / modify
**Тесты:** 3 теста в `test_q58/test_hitl.py`.

---

### 394. Agent delegation with context
**Файл:** `src/lidco/tools/subagent.py`
**Цель:** агент A делегирует задачу агенту B, ждёт результат, продолжает.
**Подход:** расширить `SubagentTool` — добавить `wait=True` параметр, который блокирует до завершения subagent и возвращает его output как tool result.
**Тесты:** 3 теста в `test_q58/test_delegation.py`.

---

### 395. Cross-session agent memory
**Файл:** `src/lidco/core/memory.py`, `src/lidco/agents/base.py`
**Цель:** агент при старте загружает решения из прошлых сессий через MemoryStore.
**Подход:**
- При инициализации агента загрузить top-3 релевантных записи из `MemoryStore` по имени агента
- Инжектировать как `## Past decisions` в system prompt
- Автоматически сохранять ключевые решения после успешного выполнения
**Тесты:** 4 теста в `test_q58/test_agent_memory.py`.

---

### 396. In-REPL code execution
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/tools/code_runner.py` (новый)
**Цель:** `/run [python|js|bash] [code]` или блок кода в backticks → выполнить и показать вывод.
**Подход:**
- Python: через `exec()` в изолированном namespace (без доступа к globals)
- Bash: subprocess с timeout=30s и stdout/stderr capture
- JS: `node -e "..."` если доступен
- Показать stdout, stderr, return code в Rich Panel
**Тесты:** 4 теста в `test_q59/test_code_runner.py`.

---

### 397. Interactive debugger (pdb)
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/tools/debugger_tool.py` (новый)
**Цель:** `/debug run <file> [args]` — запустить файл с pdb, AI анализирует трейсбек.
**Подход:**
- Запустить `python -m pdb <file>` с перехватом traceback при crash
- AI получает traceback + локальные переменные, предлагает исправление
- Опция `--auto-fix` — применить предложение без вопросов
**Тесты:** 3 теста в `test_q59/test_debugger_tool.py`.

---

### 398. Test runner from REPL
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/test [path] [--watch]` — запустить тесты с Rich-выводом прямо из REPL.
**Подход:**
- `pytest <path> -v --tb=short` через subprocess
- Парсить JSON output (`--json-report`)
- `--watch` режим: перезапускать при изменении файлов
- При fail — автоматически показать контекст ошибки агенту
**Тесты:** 4 теста в `test_q59/test_test_runner.py`.

---

### 399. Docker execution sandbox
**Файл:** `src/lidco/tools/docker_sandbox.py` (новый)
**Цель:** выполнять bash-команды в изолированном Docker-контейнере.
**Подход:**
- `DockerSandbox(image="python:3.12-slim")` — запустить контейнер с tmpfs mount
- `exec(command, timeout=60)` — выполнить команду, вернуть stdout/stderr
- Автоматически удалять контейнер после выполнения
- Конфиг `sandbox.enabled: bool`, `sandbox.image: str`
**Тесты:** 3 теста в `test_q59/test_docker_sandbox.py`.

---

### 400. Virtual env manager
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/tools/venv_manager.py` (новый)
**Цель:** `/venv [create|activate|list|delete] [name]` — управление venv из REPL.
**Подход:**
- `create`: `python -m venv .lidco/venvs/<name>`
- `activate`: обновить `VIRTUAL_ENV` env var для subprocess-вызовов
- `list`: показать все venv с размером и датой создания
- При activate — показать `(name)` в prompt
**Тесты:** 4 теста в `test_q59/test_venv_manager.py`.

---

### 401. Dependency installer
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/install <package>` — установить с AI-объяснением зачем нужен пакет.
**Подход:**
- AI сначала объясняет что делает пакет и нужен ли он
- Проверить нет ли уже похожего пакета в requirements
- Запросить подтверждение, затем `pip install <package>`
- Автоматически обновить `requirements.txt` / `pyproject.toml`
**Тесты:** 3 теста в `test_q59/test_dependency_installer.py`.

---

### 402. Code output differ
**Файл:** `src/lidco/tools/output_differ.py` (новый)
**Цель:** сравнить вывод программы до и после изменений автоматически.
**Подход:**
- `OutputDiffer.capture_before()` — запустить и сохранить stdout/stderr
- Сделать изменения
- `OutputDiffer.capture_after()` — запустить снова
- `diff()` — unified diff выводов с highlight
**Тесты:** 3 теста в `test_q59/test_output_differ.py`.

---

### 403. GitHub Issues integration
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/tools/gh_tool.py`
**Цель:** `/issue [list|view N|create|close N|comment N]` — работа с Issues из REPL.
**Подход:**
- Через `gh issue ...` subprocess + JSON output
- `/issue create` — AI генерирует title+body из описания
- Rich-форматирование с лейблами, статусом, ассигни
- Инжектировать открытые issues в контекст агента при `/issue focus N`
**Тесты:** 5 тестов в `test_q60/test_gh_issues.py`.

---

### 404. CI/CD pipeline status
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/ci [--watch]` — статус GitHub Actions для текущей ветки.
**Подход:**
- `gh run list --branch $(git rev-parse --abbrev-ref HEAD) --json`
- Показать последние runs с иконками ✅❌🔄
- `--watch` — обновлять каждые 30 сек пока не завершится
- При fail — загрузить logs и предложить AI-анализ ошибки
**Тесты:** 3 теста в `test_q60/test_ci_status.py`.

---

### 405. Slack notification integration
**Файл:** `src/lidco/cli/notifier.py`, `src/lidco/core/config.py`
**Цель:** отправить результат задачи в Slack webhook при завершении.
**Подход:**
- `config.notifications.slack_webhook: str`
- Отправлять если задача заняла >60 сек и завершилась успешно
- Сообщение: task description + summary + ссылка на сессию
**Тесты:** 2 теста в `test_q60/test_slack_notifier.py`.

---

### 406. Linear/Jira ticket integration
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/tools/ticket_tool.py` (новый)
**Цель:** `/ticket [list|view ID|update ID]` — задачи из Linear/Jira в контексте.
**Подход:**
- Linear: GraphQL API через `config.linear.api_key`
- Jira: REST API через `config.jira.url + token`
- `/ticket focus ID` — инжектировать описание задачи в контекст агента
- При завершении — автоматически обновить статус тикета
**Тесты:** 4 теста в `test_q60/test_ticket_tool.py`.

---

### 407. OpenAPI client generator
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/tools/openapi_tool.py` (новый)
**Цель:** `/openapi <spec.yaml>` — AI генерирует typed client на Python/TypeScript.
**Подход:**
- Прочитать OpenAPI 3.x spec
- AI генерирует: dataclasses/Pydantic models + typed client с методами
- Сохранить в `src/<project>/api_client/`
- Поддержка async (httpx) и sync (requests)
**Тесты:** 4 теста в `test_q60/test_openapi_tool.py`.

---

### 408. API test runner
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/api <METHOD> <url> [--json body]` — выполнить HTTP запрос и проанализировать.
**Подход:**
- Использовать `httpx` для выполнения запросов
- Форматировать ответ: status, headers, body (pretty JSON)
- AI анализирует ответ при аномалиях (5xx, неожиданная схема)
- `/api mock <spec>` — запустить mock server из OpenAPI spec
**Тесты:** 3 теста в `test_q60/test_api_runner.py`.

---

### 409. Web browser automation
**Файл:** `src/lidco/tools/browser_tool.py` (новый)
**Цель:** `browser_tool` — Playwright-based браузер для AI: navigate/click/fill/screenshot.
**Подход:**
- `BrowserTool(BaseTool)` — permission=ASK, lazy Playwright init
- Методы: `goto(url)`, `click(selector)`, `fill(selector, text)`, `screenshot()`, `get_text()`
- Screenshot → base64 → vision model анализирует
- Конфиг `browser.headless: bool = True`
**Тесты:** 4 теста в `test_q60/test_browser_tool.py` (mock playwright).

---

### 410. Proactive bug detector (Bugbot)
**Файл:** `src/lidco/cli/app.py`, `src/lidco/analysis/bugbot.py` (новый)
**Цель:** при сохранении файла — фоновая проверка на баги, уведомление.
**Подход:**
- `BugBot` подписывается на `FileWriteTool` callback
- Запускает `CheckAstBugsTool` + `SecurityScanner` асинхронно
- Если находит CRITICAL/HIGH — показывает предупреждение в статус-баре
- Не блокирует основной поток
**Тесты:** 4 теста в `test_q61/test_bugbot.py`.

---

### 411. Regression detector on save
**Файл:** `src/lidco/cli/app.py`, `src/lidco/analysis/regression_watcher.py` (новый)
**Цель:** при сохранении файла — запустить связанные тесты, показать регрессии.
**Подход:**
- Использовать `TestCoverageMapper` для нахождения test_X.py по X.py
- Запустить pytest в фоне с timeout=60s
- При fail — показать diff упавших тестов с прошлым прогоном
- Конфиг `regression.enabled: bool = True`
**Тесты:** 4 теста в `test_q61/test_regression_watcher.py`.

---

### 412. Smart auto-fix
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/analysis/auto_fixer.py` (новый)
**Цель:** `/fix [file]` — автоматически исправить lint/type ошибки.
**Подход:**
- Запустить `ruff --fix` + `mypy` для сбора ошибок
- Для сложных ошибок вызвать coder агента
- Показать diff всех исправлений, запросить подтверждение
- Опция `--auto` — применить без вопросов
**Тесты:** 4 теста в `test_q61/test_auto_fixer.py`.

---

### 413. Next-action suggestions
**Файл:** `src/lidco/cli/app.py`, `src/lidco/cli/suggestions.py` (новый)
**Цель:** после ответа агента — показать 3 предложения следующего шага.
**Подход:**
- `SuggestionEngine.generate(last_response, context)` — LLM с `role="routing"` и дешёвой моделью
- Показать как кликабельные [1] [2] [3] варианты
- Пользователь нажимает цифру → отправить соответствующее сообщение
- Конфиг `suggestions.enabled: bool = True`, `suggestions.count: int = 3`
**Тесты:** 3 теста в `test_q61/test_suggestions.py`.

---

### 414. Security scan on save
**Файл:** `src/lidco/cli/app.py`
**Цель:** при FileWrite — фоновая проверка на секреты (API ключи, пароли).
**Подход:**
- Regex-паттерны: `sk-[A-Za-z0-9]{48}`, `ghp_[A-Za-z0-9]{36}`, `password\s*=\s*"[^"]+"` и т.д.
- Немедленное предупреждение в статус-баре если найдено
- Предложить использовать env var вместо hardcode
**Тесты:** 3 теста в `test_q61/test_security_scan.py`.

---

### 415. Performance hint injection
**Файл:** `src/lidco/agents/graph.py`, `src/lidco/analysis/perf_analyzer.py` (новый)
**Цель:** при редактировании — AI замечает N+1 запросы и неэффективные паттерны.
**Подход:**
- `PerfAnalyzer.analyze(diff)` — паттерны: цикл с DB-запросом, повторные импорты, O(n²) алгоритмы
- Инжектировать hints в pre-planning context для planning агентов
- Не блокировать, показывать как suggestion
**Тесты:** 3 теста в `test_q61/test_perf_analyzer.py`.

---

### 416. Code smell auto-refactor
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/refactor suggest [file]` — показать code smells с preview рефакторинга.
**Подход:**
- Использовать `RefactorScanner` (уже есть в Q49)
- Для каждого candidate — refactor агент генерирует исправление
- Показать side-by-side diff
- Пользователь выбирает что применить
**Тесты:** 3 теста в `test_q61/test_smell_refactor.py`.

---

### 417. Voice input (speech-to-text)
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/cli/voice_input.py` (новый)
**Цель:** `/voice` — записать речь, конвертировать в промпт через Whisper API.
**Подход:**
- `pyaudio` для записи (3 сек тишины = конец записи)
- Отправить WAV в OpenAI Whisper API (`openai.audio.transcriptions.create`)
- Показать транскрипцию для подтверждения перед отправкой
- Fallback: если `pyaudio` не установлен — показать инструкцию по установке
**Тесты:** 3 теста в `test_q62/test_voice_input.py` (mock pyaudio + mock API).

---

### 418. Image/screenshot analysis
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/tools/image_tool.py` (новый)
**Цель:** `/image <path>` или вставить путь к PNG/JPG — AI анализирует.
**Подход:**
- Прочитать изображение, конвертировать в base64
- Отправить в vision-capable модель (claude-3-5-sonnet / gpt-4o)
- Если это скриншот ошибки — автоматически предложить fix
- Если это UI — описать компоненты и предложить реализацию
**Тесты:** 3 теста в `test_q62/test_image_tool.py`.

---

### 419. Diagram generation
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/tools/diagram_tool.py` (новый)
**Цель:** `/diagram [--type flow|class|sequence|er] [file|module]` — генерация диаграммы.
**Подход:**
- AI анализирует код и генерирует Mermaid markdown
- Вывести в консоль + сохранить в `.lidco/diagrams/`
- `--type class` для UML-диаграммы классов
- `--type sequence` для flow вызовов функций
**Тесты:** 4 теста в `test_q62/test_diagram_tool.py`.

---

### 420. Visual diff output
**Файл:** `src/lidco/cli/diff_viewer.py`
**Цель:** side-by-side diff с Rich рендерингом изменений.
**Подход:**
- Парсить unified diff на hunks
- `rich.columns.Columns` — левая колонка (до), правая (после)
- Подсветка: красный фон для удалённых строк, зелёный для добавленных
- `/diff --side-by-side` флаг
**Тесты:** 3 теста в `test_q62/test_visual_diff.py`.

---

### 421. PDF/document reader
**Файл:** `src/lidco/tools/doc_reader.py` (новый)
**Цель:** читать PDF/docx/txt как контекст для агента.
**Подход:**
- PDF: `pdfplumber` (если установлен) или `pypdf` fallback
- DOCX: `python-docx` (если установлен)
- TXT/MD: прямое чтение
- Разбить на chunks если > 10000 символов
- Зарегистрировать как `DocReaderTool` в registry
**Тесты:** 3 теста в `test_q62/test_doc_reader.py`.

---

### 422. Screen capture integration
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/screenshot [--region]` — захват экрана, отправка в vision-модель.
**Подход:**
- `PIL.ImageGrab.grab()` или `mss` для захвата
- Сохранить во временный файл
- Автоматически вызвать `ImageTool.analyze()`
- `--region x,y,w,h` для захвата части экрана
**Тесты:** 2 теста в `test_q62/test_screenshot.py` (mock PIL).

---

### 423. Extended thinking support
**Файл:** `src/lidco/llm/litellm_provider.py`, `src/lidco/core/config.py`
**Цель:** использовать thinking budget для сложных задач (claude-3-7-sonnet и выше).
**Подход:**
- `config.llm.thinking_budget_tokens: int = 0` — 0 = выключено
- При `thinking_budget > 0` добавить `thinking: {"type": "enabled", "budget_tokens": N}`
- Автоматически включать для `role="planning"` при сложных задачах
- Показывать thinking в stream display (свёрнуто по умолчанию)
**Тесты:** 4 теста в `test_q63/test_thinking.py`.

---

### 424. Adaptive token budgeting
**Файл:** `src/lidco/core/token_budget.py`, `src/lidco/agents/graph.py`
**Цель:** автоматически регулировать max_tokens по сложности задачи.
**Подход:**
- Анализировать количество файлов в задаче, количество ошибок, длину plan
- `_compute_dynamic_budget(task, agent_name)` → `max_tokens`
- Диапазон: `config.llm.min_tokens` (256) — `config.llm.max_tokens` (8192)
- Логировать выбранный бюджет в `/status`
**Тесты:** 4 теста в `test_q63/test_adaptive_budget.py`.

---

### 425. Cache warming strategies
**Файл:** `src/lidco/core/session.py`, `src/lidco/llm/litellm_provider.py`
**Цель:** предзагрузка системного промпта в кэш Anthropic до первого запроса.
**Подход:**
- При старте сессии отправить dummy запрос с системным промптом + `max_tokens=1`
- Это прогревает кэш Anthropic (cache_creation_input_tokens)
- Опция `config.llm.warm_cache_on_start: bool = False`
- Логировать время прогрева
**Тесты:** 3 теста в `test_q63/test_cache_warm.py`.

---

### 426. Model cost comparison tool
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/llm/cost_compare.py` (новый)
**Цель:** `/compare-models <task>` — запустить задачу на нескольких моделях, показать цену/качество.
**Подход:**
- Запустить на 3 моделях параллельно (cheap, medium, best)
- Сравнить: токены, стоимость, время, длина ответа
- AI оценивает качество ответов по 10-балльной шкале
- Rich таблица с рекомендацией
**Тесты:** 3 теста в `test_q63/test_cost_compare.py`.

---

### 427. Local model support (Ollama)
**Файл:** `src/lidco/llm/ollama_provider.py` (новый), `src/lidco/core/config.py`
**Цель:** использовать Ollama для offline режима и дешёвых задач.
**Подход:**
- `OllamaProvider` реализующий `BaseLLMProvider`
- Auto-detect если `http://localhost:11434` доступен
- Использовать для `role="routing"` и `role="memory"` задач
- `/models local` — показать доступные Ollama модели
**Тесты:** 4 теста в `test_q63/test_ollama.py` (mock HTTP).

---

### 428. Batched parallel LLM calls
**Файл:** `src/lidco/llm/batch_client.py` (новый)
**Цель:** объединять одновременные LLM-вызовы через Anthropic Batch API.
**Подход:**
- `BatchLLMClient` собирает запросы в очередь 100мс
- Отправляет batch через `/v1/messages/batches`
- Раздаёт ответы ожидающим корутинам
- Fallback на обычные запросы при batch < 2
**Тесты:** 3 теста в `test_q63/test_batch_llm.py`.

---

### 429. Cost budget alerts
**Файл:** `src/lidco/cli/app.py`, `src/lidco/core/token_budget.py`
**Цель:** предупреждение при достижении дневного/месячного лимита расходов.
**Подход:**
- `config.budget.daily_limit_usd: float = 0` (0 = выключено)
- `config.budget.monthly_limit_usd: float = 0`
- Хранить расходы в `.lidco/costs.json` с датами
- При 80% лимита — warning, при 100% — error с блокировкой
**Тесты:** 4 теста в `test_q63/test_budget_alerts.py`.

---

### 430. VS Code extension (basic)
**Файл:** `vscode/` (новая директория)
**Цель:** базовый VS Code extension с sidebar chat и diff preview.
**Структура:**
```
vscode/
  package.json        — extension manifest
  src/extension.ts    — activation + commands
  src/chatPanel.ts    — WebviewPanel с chat UI
  src/diffDecorator.ts — inline diff highlights
  media/              — CSS + JS для webview
```
**Функции:**
- Cmd+Shift+L открывает Lidco sidebar
- Inline diff decorations после изменений агента
- Status bar с текущим агентом и токенами
- Коммуникация через JSON-RPC с `lidco server`
**Тесты:** 5 тестов в `test_q64/test_vscode_ext.py` (mock vscode API).

---

### 431. LSP bridge improvements
**Файл:** `src/lidco/server/lsp_bridge.py`
**Цель:** hover definitions и go-to-definition через lidco LSP server.
**Подход:**
- Обработать `textDocument/hover` — вернуть AI-объяснение символа
- `textDocument/definition` — использовать `SymbolIndex` для перехода к определению
- `textDocument/codeAction` — предлагать quick fixes через AI
**Тесты:** 4 теста в `test_q64/test_lsp_bridge.py`.

---

### 432. Keybinding customization
**Файл:** `src/lidco/cli/app.py`, `src/lidco/cli/keybindings.py` (новый)
**Цель:** `~/.lidco/keybindings.json` — переназначить горячие клавиши в REPL.
**Схема:**
```json
{
  "submit": "ctrl+enter",
  "editor": "alt+e",
  "history_prev": "ctrl+p",
  "clear": "ctrl+l",
  "abort": "ctrl+c"
}
```
**Подход:** загрузить при старте, применить к prompt_toolkit KeyBindings.
**Тесты:** 3 теста в `test_q64/test_keybindings.py`.

---

### 433. REPL theme improvements
**Файл:** `src/lidco/cli/renderer.py`, `src/lidco/cli/themes.py` (новый)
**Цель:** 8 встроенных тем + поддержка custom theme через YAML.
**Встроенные темы:** dark, light, solarized, nord, monokai, dracula, gruvbox, catppuccin.
**Схема custom theme:**
```yaml
name: my-theme
panel_border: bright_blue
code_theme: github-dark
agent_colors:
  coder: cyan
  security: red
```
**Тесты:** 4 теста в `test_q64/test_themes.py`.

---

### 434. Plugin/extension API
**Файл:** `src/lidco/plugins/` (новая директория), `src/lidco/plugins/api.py`
**Цель:** стабильный public API для написания плагинов на Python.
**API:**
```python
class LidcoPlugin:
    def on_tool_call(self, tool_name, args, result): ...
    def on_agent_response(self, agent, response): ...
    def register_tool(self, tool: BaseTool): ...
    def register_command(self, cmd: SlashCommand): ...
```
**Загрузка:** `~/.lidco/plugins/*.py` + `.lidco/plugins/*.py`
**Тесты:** 5 тестов в `test_q64/test_plugin_api.py`.

---

### 435. Project setup wizard
**Файл:** `src/lidco/__main__.py`, `src/lidco/cli/wizard.py` (новый)
**Цель:** `lidco init` — интерактивный wizard настройки нового проекта.
**Шаги:**
1. Определить язык/фреймворк (анализ файлов)
2. Выбрать модель (показать цены)
3. Настроить разрешения
4. Создать `.lidco/` структуру
5. Сгенерировать `LIDCO.md` через AI
**Тесты:** 4 теста в `test_q64/test_wizard.py`.

---

### 436. Inline code actions
**Файл:** `src/lidco/cli/app.py`, `src/lidco/cli/code_actions.py` (новый)
**Цель:** при показе ошибки в выводе — кнопки быстрых действий AI.
**Подход:**
- Распознать error patterns в выводе (traceback, lint errors)
- Показать `[F]ix  [E]xplain  [I]gnore` после ошибки
- F → запустить auto-fix, E → запустить explain агента
- Работает и для test failures
**Тесты:** 3 теста в `test_q64/test_code_actions.py`.

---

### 437. Real-time cost dashboard
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/cli/dashboard.py` (новый)
**Цель:** `/dashboard` — TUI с графиками токенов и стоимости.
**Подход:**
- Rich Live layout: токены/тёрн (bar chart), накопленная стоимость (line), топ агентов по цене
- Обновляется в реальном времени через callback
- Выход по `q` или `Ctrl+C`
**Тесты:** 3 теста в `test_q65/test_dashboard.py`.

---

### 438. Agent performance analytics
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/agents analytics [--period 7d]` — детальная статистика по агентам.
**Метрики:** среднее время отклика, медиана токенов, % задач завершённых без ошибок, средняя стоимость.
**Подход:** агрегировать из `ErrorLedger` (SQLite) + in-memory `_agent_stats`.
**Тесты:** 3 теста в `test_q65/test_agent_analytics.py`.

---

### 439. Token usage heatmap
**Файл:** `src/lidco/cli/commands.py`, `src/lidco/analysis/token_heatmap.py` (новый)
**Цель:** `/heatmap` — какие файлы/функции потребляют больше всего токенов.
**Подход:**
- Логировать в каком контексте использовались токены (по секциям)
- `TokenHeatmap` — агрегирует по файлам за сессию
- Rich Heatmap: файл → цвет от зелёного (мало) до красного (много)
**Тесты:** 3 теста в `test_q65/test_token_heatmap.py`.

---

### 440. Coverage trend tracker
**Файл:** `src/lidco/analysis/coverage_trend.py` (новый)
**Цель:** история изменений покрытия по коммитам.
**Подход:**
- При каждом `/test` — сохранять coverage % в `.lidco/coverage-history.json`
- `/coverage trend` — ASCII график изменения покрытия по времени
- Предупреждение если покрытие упало >2% за последний коммит
**Тесты:** 3 теста в `test_q65/test_coverage_trend.py`.

---

### 441. Session analytics export
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/analytics export [--format json|csv]` — экспорт метрик сессии.
**Данные:** turns, tokens_per_turn, cost_per_turn, agents_used, tools_called, files_edited, errors.
**Подход:** собрать из `_turn_times`, `_agent_stats`, `_edited_files`, token callback.
**Тесты:** 2 теста в `test_q65/test_analytics_export.py`.

---

### 442. Health check command
**Файл:** `src/lidco/__main__.py`, `src/lidco/cli/health.py` (новый)
**Цель:** `lidco health` — проверить все системы перед началом работы.
**Проверки:**
- API ключи (Anthropic, OpenAI) — валидность
- Доступность моделей (test call max_tokens=1)
- RAG/ChromaDB — статус
- SQLite index — целостность
- Watchdog — работает ли
- MCP серверы — ping
**Вывод:** Rich table со статусом каждой проверки (✅/❌/⚠️).
**Тесты:** 5 тестов в `test_q65/test_health.py`.

---

### 443. Error pattern visualization
**Файл:** `src/lidco/cli/commands.py`
**Цель:** `/errors viz` — ASCII визуализация ошибок по времени и типу.
**Подход:**
- Загрузить из `ErrorLedger` (SQLite) все записи за N дней
- ASCII-гистограмма по часам: высота = кол-во ошибок
- Top-5 типов ошибок с процентами
- Тренд: растёт/снижается
**Тесты:** 3 теста в `test_q65/test_error_viz.py`.

---

## Task Details (Q37+)

### 244. LIDCO.md
**Файлы:** `src/lidco/core/config.py`, `src/lidco/core/session.py`, `src/lidco/cli/app.py`
**Цель:** стандартный файл инструкций проекта по аналогии с CLAUDE.md (Claude Code) и AGENTS.md (Codex CLI / Droid). Агенты автоматически читают его при старте.
**Иерархия** (более конкретное перекрывает общее):
1. `C:\ProgramData\lidco\LIDCO.md` — managed (организационная политика)
2. `.lidco/LIDCO.md` или `LIDCO.md` — project level
3. `~/.lidco/LIDCO.md` — user level
**Подход:**
- Загружать при старте сессии через `LidcoMdLoader.load(cwd)` — обходит от CWD вверх до root
- Поддержка `@path/to/file.md` синтаксиса для включения внешних файлов
- Lazy-загрузка из поддиректорий (load on demand при работе с файлом в поддиректории)
- `LidcoMdExcludes` glob-паттерны в config для исключения файлов
- Инжектировать как первый system message с тегом `## Project Instructions`
- `/init` команда (задача 251) генерирует шаблон анализируя проект

---

### 245. Permission Modes
**Файлы:** `src/lidco/core/permissions.py` (новый), `src/lidco/core/config.py`, `src/lidco/agents/base.py`
**Цель:** система режимов разрешений с гранулярным контролем каждого инструмента.
**Режимы:**
- `default` — запрашивает разрешение при первом использовании каждого инструмента
- `accept_edits` — автоматически принимает все file edit разрешения
- `plan` — read-only: нет записи файлов, нет выполнения команд
- `dont_ask` — автоматически отклоняет если нет явного allow-правила
- `bypass` — пропускает все проверки (только для контейнеров/VM)
**Подход:**
- `PermissionManager` с методом `check(tool_name, args) -> PermissionResult`
- `PermissionResult`: allow / ask / deny + reason
- Порядок оценки: deny-правила → ask-правила → allow-правила → default режим
- Сохранение решений в `.lidco/permissions.json` (session-scoped)
- `config.permissions.mode: str` — режим по умолчанию

---

### 246. Per-Tool Rules
**Файлы:** `src/lidco/core/permissions.py`, `src/lidco/core/config.py`
**Цель:** точные правила разрешений для каждого инструмента с wildcard-паттернами.
**Синтаксис:**
```yaml
permissions:
  allow:
    - "Bash(pytest *)"
    - "Bash(git diff *)"
    - "FileRead(**)"
  ask:
    - "Bash(git *)"
    - "FileWrite(src/**)"
  deny:
    - "Bash(git push *)"
    - "FileWrite(.env)"
    - "Bash(rm -rf *)"
```
**Подход:**
- `RuleParser.parse(spec)` — разбирает `Tool(pattern)` синтаксис
- Wildcard: `*` = любой суффикс, `**` = рекурсивный путь
- Для Bash: аргументы как список через execvp-семантику
- Для FileRead/FileWrite: gitignore-паттерны путей
- Правила из `.lidco/settings.json` + `~/.lidco/settings.json` + managed config

---

### 247. Approval Flow
**Файлы:** `src/lidco/cli/approval.py` (новый), `src/lidco/cli/app.py`
**Цель:** интерактивный запрос разрешения перед опасными операциями.
**UI:**
```
 Bash  git push origin main
Allow? [y]es / [n]o / [a]lways / [A]lways for session / [N]ever / [e]xplain
```
**Подход:**
- `ApprovalPrompt.ask(tool_name, args, context) -> Decision`
- `Decision`: allow_once / allow_always / allow_session / deny_once / deny_always
- Сохранение allow_always в `.lidco/permissions.json`
- `explain` показывает почему инструмент требует разрешения
- Цветовое кодирование: зелёный=безопасно, жёлтый=обратимо, красный=необратимо
- При `plan` режиме — автоматически deny с объяснением

---

### 248. /permissions Command
**Файлы:** `src/lidco/cli/commands.py`
**Цель:** интерактивный просмотр и управление текущими правилами разрешений.
**UI:**
```
Permission Rules (session)
Mode: default

ALLOWED (3)
  ✓ Bash(pytest *)
  ✓ FileRead(**)

DENIED (1)
  ✗ Bash(git push *)

[a]dd rule  [r]emove  [m]ode  [c]lear session
```
**Подход:**
- Таблица Rich с текущими allow/ask/deny правилами
- Интерактивное добавление/удаление правил
- Смена режима (`/permissions mode plan`)
- Экспорт в `.lidco/settings.json`

---

### 249. Sandboxed Shell Execution
**Файлы:** `src/lidco/tools/bash.py`, `src/lidco/core/sandbox.py` (новый)
**Цель:** изоляция shell-команд агента — ограничение файловой системы и сети.
**Подход:**
- `SandboxConfig`: `writable_roots: list[str]`, `network_access: bool`, `allowed_domains: list[str]`
- На Windows: Job Objects для ограничения child процессов
- На Linux: seccomp/landlock через subprocess с ограниченными capabilities
- `writable_roots` по умолчанию: только CWD проекта
- `--add-dir` расширяет writable_roots
- Блокировка записи в `.git/`, `.lidco/` даже в writable_roots
- Конфигурация через `config.sandbox.*`

---

### 250. Path-Scoped Rules
**Файлы:** `src/lidco/core/config.py`, `src/lidco/core/session.py`
**Цель:** правила, которые активируются только при работе с определёнными файлами — экономия токенов на системных промптах.
**Синтаксис в LIDCO.md:**
```markdown
<!-- scope: src/api/**/*.py -->
Always validate input with Pydantic schemas.
Never use global state.
<!-- end scope -->
```
**Подход:**
- `PathScopedRule(pattern: str, content: str)`
- Активация при наличии текущего файла matching pattern в контексте
- `RuleActivator.get_active_rules(current_files: list[str]) -> list[str]`
- Инжекция активных правил в начало system prompt

---

### 251. /init Command
**Файлы:** `src/lidco/cli/commands.py`, `src/lidco/cli/init_generator.py` (новый)
**Цель:** автоматическая генерация LIDCO.md анализом текущего проекта.
**Анализ:**
- Язык/фреймворк (pyproject.toml, package.json, Cargo.toml, go.mod)
- Тест-фреймворк (pytest, jest, cargo test, go test)
- Линтеры (ruff, eslint, clippy)
- Команды сборки и запуска тестов
- Существующие соглашения из README.md
- Структура директорий
**Генерирует:**
```markdown
# LIDCO.md

## Project
Python CLI tool. Python 3.13, pytest, ruff.

## Commands
- Run tests: python -m pytest -q
- Lint: ruff check src/

## Conventions
- All tests in tests/unit/
- Use frozen dataclasses for data objects
- No mutation of arguments
```

---

### 252. Command Allowlist
**Файлы:** `src/lidco/core/config.py`, `src/lidco/core/permission_engine.py`
**Статус:** ✅ Done — `PermissionsConfig.command_allowlist: list[str]` с дефолтными безопасными командами (pytest, git status/diff/log, ruff, mypy). Автоматически раскрываются в `Bash(pattern)` allow-правила в `PermissionEngine`. Отображаются отдельной секцией в `/permissions`. 22 теста в `test_command_allowlist.py`.

---

### 253. MCP Stdio Transport
**Файлы:** `src/lidco/mcp/` (новый пакет), `src/lidco/core/session.py`
**Цель:** запуск MCP серверов как дочерних процессов, управление lifecycle.
**Подход:**
- `MCPServer`: dataclass с `name, command, args, env`
- `MCPClient`: запускает `command args` как subprocess, JSON-RPC по stdin/stdout
- Протокол: JSON-RPC 2.0, методы `initialize`, `tools/list`, `tools/call`
- `MCPManager`: singleton, управляет всеми серверами (start/stop/restart)
- Авто-старт при загрузке `mcp.json`
- Reconnect при падении сервера (exponential backoff)
- Timeout на initialize (5s), на tool call (30s, configurable)
- Пример: подключение `@playwright/mcp`, `@modelcontextprotocol/server-github`

---

### 254. MCP Tool Injection
**Файлы:** `src/lidco/mcp/tool_adapter.py` (новый), `src/lidco/core/tool_registry.py`
**Цель:** MCP-инструменты становятся доступны агентам наравне с встроенными.
**Подход:**
- `MCPToolAdapter.to_tool(mcp_tool_schema) -> BaseTool` — оборачивает MCP tool
- Namespace: `mcp__servername__toolname` для уникальности
- Инжекция в `ToolRegistry` при старте сессии
- `MCPTool.execute(args)` → JSON-RPC call → ответ как ToolResult
- Фильтрация по агентам: в YAML-агенте можно ограничить `mcp_servers: [github]`

---

### 261. lidco exec
**Файлы:** `src/lidco/cli/exec_mode.py` (новый), `pyproject.toml`
**Цель:** полноценный headless режим для CI/CD и автоматизации.
**CLI:**
```bash
lidco exec "fix all failing tests"
lidco exec --json "add docstrings to src/api/"
lidco exec --max-turns 20 --permission-mode bypass "refactor utils.py"
echo "task from stdin" | lidco exec
```
**Подход:**
- `ExecRunner.run(task, config) -> ExecResult`
- `ExecResult`: success: bool, changes: list[FileChange], output: str, cost: float
- Нет Rich/spinner — только plain text или JSON
- `--json` флаг: структурированный вывод всех действий
- Автоматический `permission_mode=bypass` если `--no-interactive`
- Сигналы: SIGTERM — graceful stop, SIGKILL — immediate

---

### 262. JSON Output Mode
**Файлы:** `src/lidco/cli/json_reporter.py` (новый)
**Формат:**
```json
{
  "session_id": "abc123",
  "task": "fix tests",
  "status": "success",
  "duration_s": 45.2,
  "cost_usd": 0.042,
  "changes": [
    {"file": "src/foo.py", "action": "edit", "lines_added": 3, "lines_removed": 1}
  ],
  "tool_calls": 12,
  "messages": [...]
}
```

---

### 264. GitHub Actions
**Файлы:** `.github/actions/lidco/action.yml` (новый), `docs/ci.md`
**Подход:**
```yaml
- uses: lidco/action@v1
  with:
    task: "review PR changes for bugs"
    permission-mode: "plan"
    model: "openai/glm-5"
  env:
    ZAI_API_KEY: ${{ secrets.ZAI_API_KEY }}
```
- Action: install lidco → `lidco exec --json "${{ inputs.task }}"`
- Результат: comment к PR с изменениями или отчётом
- Поддержка triggers: pull_request, push, schedule, issue_comment

---

### 268. YAML Agents
**Файлы:** `src/lidco/agents/yaml_loader.py` (новый), `src/lidco/agents/` директория
**Формат .lidco/agents/security-auditor.md:**
```markdown
---
name: security-auditor
description: Проверяет код на уязвимости OWASP Top 10. Используй проактивно после изменений API endpoints.
model: openai/glm-5
temperature: 0.0
max_turns: 10
permission_mode: plan
tools:
  - file_read
  - grep
  - web_search
disallowed_tools:
  - bash
  - file_write
hooks:
  post_response: "echo 'Audit complete'"
memory: project
---

You are a security expert specializing in Python web applications...
```
**Подход:**
- `YAMLAgentLoader.load_from_dir(path) -> list[AgentConfig]`
- Загрузка из `.lidco/agents/` (project) и `~/.lidco/agents/` (user)
- `AgentFactory.create_from_config(config) -> BaseAgent`
- Регистрация в `AgentRegistry` с именем
- Доступен через routing (`auto`) и явный вызов (`/agent security-auditor`)
- Hot-reload при изменении .md файла

---

### 269. Git Worktree Isolation
**Файлы:** `src/lidco/agents/worktree.py` (новый), `src/lidco/agents/graph.py`
**Цель:** каждый параллельный агент работает в отдельном git worktree без конфликтов.
**Подход:**
- `WorktreeManager.create(branch_name) -> WorktreePath`
- `git worktree add .lidco/worktrees/{agent_id} -b lidco/{agent_id}`
- Агент получает изолированную копию репозитория
- По завершению: `WorktreeManager.merge_or_cleanup(agent_id)`
- Если изменений нет → `git worktree remove` (авто-cleanup)
- Если есть изменения → возврат пути для review/merge
- `isolation: worktree` флаг в YAML агенте или в /batch

---

### 276. /compact
**Файлы:** `src/lidco/cli/commands.py`, `src/lidco/core/conversation_pruner.py`
**Цель:** явная пользовательская компрессия истории с указанием фокуса.
**Использование:**
```
/compact                    # стандартное сжатие
/compact "focus on the auth module changes"
/compact --keep-last 10    # оставить последние 10 сообщений
```
**Подход:**
- LLM-вызов: "Summarize this conversation in 5-7 sentences. Focus on: {focus}. Preserve: key decisions, file names, error messages."
- Замена старых сообщений на `{"role": "system", "content": "## Earlier Summary\n{summary}"}`
- Сохранение последних N сообщений без изменений
- Отображение: "Compacted 47 messages → 1 summary (saved ~12k tokens)"

---

### 277. /context Gauge
**Файлы:** `src/lidco/cli/commands.py`
**Цель:** визуальное отображение использования контекста с разбивкой по слоям.
**UI:**
```
Context Usage: 47,832 / 131,072 tokens (36%)

████████████░░░░░░░░░░░░░░░░░░░  36%

  LIDCO.md      1,234 tok   3%
  Memory        2,891 tok   6%
  History      28,442 tok  59%
  RAG context   8,120 tok  17%
  Tools         7,145 tok  15%

[c]ompact  [h]istory  [m]emory  [r]ag
```

---

### 282. @-Mentions
**Файлы:** `src/lidco/cli/app.py`, `src/lidco/cli/mention_parser.py` (новый)
**Цель:** упоминание файлов через @-синтаксис в REPL автоматически читает и инжектирует файл.
**Подход:**
- `MentionParser.extract(@path) -> list[str]` из пользовательского ввода
- Autocomplete: при вводе `@` показывать список файлов проекта (fuzzy)
- `@src/foo.py` → читать файл → добавить в контекст как `## File: src/foo.py\n{content}`
- `@src/` → инжектировать дерево директории
- Несколько @: `@tests/ @src/api.py` — все добавляются

---

### 283. Checkpoint-Based Undo
**Файлы:** `src/lidco/core/checkpoints.py` (новый), `src/lidco/agents/base.py`
**Цель:** снапшоты файловой системы перед каждым file-write → возможность отмены N шагов.
**Подход:**
- `CheckpointManager.snapshot(files: list[str]) -> checkpoint_id`
- Хранение в `.lidco/checkpoints/{id}/` как git stash или diff patches
- `CheckpointManager.restore(checkpoint_id)`
- `/undo` без аргументов: отменяет последний checkpoint
- `/undo 3`: откатывает 3 последних checkpoint
- `/undo list`: список снапшотов с временными метками и файлами
- Авто-cleanup: хранить не более 20 последних checkpoints

---

### 286. Native TDD Pipeline
**Файлы:** `src/lidco/agents/tdd_orchestrator.py` (новый), `src/lidco/cli/commands.py`
**Цель:** нативная TDD-оркестрация как в Droid: spec-writer → tester (RED) → coder (GREEN) → verify.
**Подход:**
- `/tdd "add user authentication"` запускает pipeline
- Шаг 1: spec-writer агент генерирует детальную спецификацию
- Шаг 2: tester агент пишет failing тесты (RED state)
- Шаг 3: LIDCO запускает тесты → убеждается что они FAIL
- Шаг 4: coder агент реализует минимальный код для прохождения
- Шаг 5: LIDCO запускает тесты → убеждается что они PASS (GREEN)
- Шаг 6: refactor агент улучшает код без нарушения тестов
- Шаг 7: review агент финальный review
- Весь цикл повторяется пока все acceptance criteria не выполнены

---

### 288. /batch Command
**Файлы:** `src/lidco/cli/commands.py`, `src/lidco/agents/batch_orchestrator.py` (новый)
**Цель:** декомпозиция большой задачи на 5-30 параллельных единиц в изолированных worktrees.
**Использование:**
```
/batch "add type annotations to all files in src/"
/batch --max-units 10 "write tests for every public function"
```
**Подход:**
- Шаг 1: planner агент декомпозирует задачу → список единиц (файлы/функции/модули)
- Шаг 2: показать пользователю список → approve/edit
- Шаг 3: создать N worktrees, запустить N агентов параллельно
- Шаг 4: сбор результатов, `/batch status` для мониторинга
- Шаг 5: merge всех изменений с разрешением конфликтов
- Шаг 6: reviewer агент проверяет финальный результат

---

### 293. Skills System
**Файлы:** `src/lidco/skills/` (новый пакет), `src/lidco/cli/commands.py`
**Формат .lidco/skills/security-review.md:**
```markdown
---
name: security-review
description: Проводит security review изменённых файлов
trigger: /security-review
context: git_diff
scripts:
  - bandit -r src/ -f json
---

Review the following code changes for security vulnerabilities.
Focus on: SQL injection, XSS, SSRF, hardcoded secrets, insecure crypto.
Report each finding with: severity, location, description, fix suggestion.
```
**Подход:**
- `SkillLoader.discover() -> list[Skill]` из .lidco/skills/ и ~/.lidco/skills/
- `Skill.execute(args, context) -> str`
- Автоматическая регистрация как slash-команды
- `context: git_diff` → автоматически инжектирует `git diff HEAD`
- `scripts:` — выполняются перед вызовом LLM, вывод добавляется в контекст

---

### 295. Skill Chaining
**Файлы:** `src/lidco/skills/chain.py` (новый)
**Цель:** результат одного skill передаётся как input следующему.
**Синтаксис:**
```
/lint | /fix-issues | /security-review
```
**Подход:**
- `SkillChain.parse("/lint | /fix | /review") -> list[Skill]`
- Выполнение последовательно: output[i] → input[i+1]
- Передача через `{previous_output}` placeholder в prompt следующего skill
- Прерывание цепи при ошибке с понятным сообщением

---

### 300. lidco server
**Файлы:** `src/lidco/server/` (новый пакет)
**Цель:** HTTP+WebSocket API сервер для IDE-интеграций и внешних клиентов.
**Endpoints:**
```
POST /api/execute          # выполнить задачу
GET  /api/session          # состояние сессии
GET  /api/history          # история разговора
GET  /api/tools            # список доступных инструментов
WS   /api/stream           # WebSocket для стриминга
POST /api/tools/{name}     # прямой вызов инструмента
```
**Подход:**
- FastAPI + WebSockets
- Аутентификация через Bearer токен (генерируется при старте)
- `lidco server --port 8765 --token-file .lidco/server.token`
- CORS для локальной разработки
- Все ответы агента стримятся через WebSocket

---

### 303. VS Code Extension
**Файлы:** `extensions/vscode/` (новый пакет)
**Цель:** нативная интеграция LIDCO в VS Code через lidco server API.
**Возможности MVP:**
- Chat панель (Ctrl+Shift+L) — полноценный REPL в IDE
- Inline diff viewer — показывает изменения в native VS Code diff
- Статус бар — текущая фаза/инструмент/стоимость
- @-mentions с autocomplete файлов проекта
- Approve/reject изменений прямо в diff view
- Открытие файлов упомянутых агентом одним кликом
**Технически:** TypeScript extension, подключается к `lidco server` по WebSocket

---

### 307. Adaptive Context Paging
**Файлы:** `src/lidco/core/context_pager.py` (новый)
**Цель:** динамическое управление тем, что попадает в контекст, как OS управляет памятью.
**Подход:**
- Каждый элемент контекста имеет `relevance_score` и `recency_score`
- `ContextPager.select(budget_tokens) -> list[ContextItem]`
- Алгоритм: BM25 по запросу + recency decay + explicit mentions boost
- Автоматически вытесняет менее релевантные элементы при нехватке токенов
- Инвалидация при изменении файлов (watchdog интеграция)
- Конфигурация: `config.context.paging_strategy: "bm25" | "recency" | "hybrid"`

---

### 314. Multi-Model Sampling
**Файлы:** `src/lidco/llm/sampler.py` (новый)
**Цель:** для критических решений запускать N параллельных LLM-вызовов, выбирать лучший.
**Подход:**
- `MultiModelSampler.sample(messages, n=3) -> str`
- N параллельных вызовов через `asyncio.gather`
- Critic-агент оценивает каждый ответ (correctness, completeness, clarity)
- Выбор ответа с максимальным critic score
- Применение: для planning nodes и final code generation
- Конфигурация: `config.agents.sampling.n: int` (по умолчанию 1, т.е. отключено)
- Активация: `/think --samples 3` или через флаг агента

---

### 315. /think Mode
**Файлы:** `src/lidco/cli/commands.py`, `src/lidco/llm/litellm_provider.py`
**Цель:** режим глубокого мышления с расширенным token budget на reasoning.
**Использование:**
```
/think on    # включить extended thinking
/think off
/think       # toggle
```
**Подход:**
- При включении: добавлять `"thinking": {"type": "enabled", "budget_tokens": 8000}` к API запросам
- Для GLM-5: увеличивать `max_tokens` и температуру до 1.0
- Индикация в статус-баре: `🧠 Deep Think` пока активно
- Автоматическое включение для planning nodes при сложных задачах

---

### 321. AI Shield
**Файлы:** `src/lidco/security/shield.py` (новый), `src/lidco/cli/hooks.py`
**Цель:** LLM-анализ диффа перед коммитом — уязвимости, баги, утечка секретов.
**Аналог DroidShield от Factory.**
**Подход:**
- Хук на `git commit` (через `.git/hooks/pre-commit`)
- `AIShield.analyze(diff: str) -> ShieldReport`
- Анализ: OWASP Top 10, hardcoded secrets, SQL injection, XSS, unsafe crypto
- `ShieldReport`: findings: list[Finding], risk_level: low/medium/high/critical
- При high/critical: показать предупреждение + запросить подтверждение
- Опции: `--shield-mode warn|block|off`
- Интеграция с ErrorLedger для отслеживания паттернов

---

### 322. Full Audit Trail
**Файлы:** `src/lidco/core/audit.py` (новый)
**Цель:** полная история всех действий агента с reasoning для enterprise-требований.
**Схема SQLite:**
```sql
CREATE TABLE audit_log (
  id TEXT PRIMARY KEY,
  session_id TEXT,
  timestamp REAL,
  agent_name TEXT,
  action_type TEXT,  -- tool_call / message / plan_step
  tool_name TEXT,
  tool_args TEXT,    -- JSON
  tool_result TEXT,
  reasoning TEXT,    -- почему агент выбрал это действие
  success INTEGER,
  duration_ms INTEGER
);
```
**Подход:**
- `AuditLogger.log(event)` вызывается из base.py после каждого tool call
- Reasoning извлекается из thinking блоков LLM ответа
- `/audit [--session ID] [--export csv]` для просмотра
- Автоматическая ротация: хранить 30 дней

---

### 328. Async Task Queue
**Файлы:** `src/lidco/tasks/` (новый пакет)
**Цель:** запуск задач в фоне с персистентностью и мониторингом.
**CLI:**
```bash
lidco exec --async "add tests for all public functions"
# → Task ID: task_abc123 | Status: queued

lidco task status task_abc123
# → Status: running | Progress: 3/12 files | Cost: $0.02

lidco task list
# → [running] task_abc123 "add tests..." | 5m ago

lidco task apply task_abc123
# → Applied 8 file changes to working directory

lidco task cancel task_abc123
```
**Подход:**
- SQLite-backed task queue в `.lidco/tasks.db`
- Background worker через `asyncio` + `multiprocessing`
- Статус: queued / running / done / failed / cancelled
- Результат: сохраняются file patches для последующего apply

---

## Q66 — Competitive Edge

**Goal:** close critical feature gaps vs Claude Code, Cursor, Windsurf, Aider, Continue — session continuity, autonomous flows, auto-commit, custom context, diff-first editing, workspace snapshots, next-edit prediction, architect-editor split.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 444 | [Session continuity (--continue / --resume)](#444-session-continuity) | ✅ Done | 2d | resume any past session from CLI flag — parity with Claude Code |
| 445 | [Autonomous task flows with checkpoints](#445-task-flows) | ✅ Done | 3d | multi-step autonomous execution with checkpoint + rollback — parity with Windsurf Flows |
| 446 | [Auto-commit mode](#446-auto-commit) | ✅ Done | 1d | git commit after each agent execution with descriptive message — parity with Aider |
| 447 | [Custom context providers](#447-context-providers) | ✅ Done | 2d | user-defined context sources via plugin protocol — parity with Continue |
| 448 | [Diff-first editing with selective apply](#448-diff-first) | ✅ Done | 2d | preview diff before applying, accept/reject per hunk — parity with Cursor inline diff |
| 449 | [Workspace snapshots](#449-workspace-snapshots) | ✅ Done | 2d | snapshot + restore full workspace: files, git stash, session state |
| 450 | [Inline next-edit prediction](#450-next-edit) | ✅ Done | 2d | predict likely next code edit without full conversation turn — parity with Cursor tab |
| 451 | [Architect-editor split model](#451-architect-editor) | ✅ Done | 1d | separate architect LLM (planning) from editor LLM (code gen) — parity with Aider |

---

### 444. Session continuity (--continue / --resume)

**Files:** `src/lidco/__main__.py`, `src/lidco/cli/app.py`, `src/lidco/cli/session_store.py`, `src/lidco/cli/commands/session.py`

**Goal:** Add `lidco --continue` (resume most-recent session) and `lidco --resume <ID|name>` CLI flags. On resume, load history from SessionStore, inject into orchestrator via `restore_history()`, and display a summary. On normal exit, auto-save session to SessionStore.

**Acceptance criteria:**
- `CLIFlags` gains `continue_session: bool = False` and `resume_id: str | None = None`
- `__main__.main()` parses `--continue` and `--resume <ID>` from argv
- `run_repl()` loads and restores history from SessionStore at startup when flag is set
- On REPL exit, auto-saves conversation history with `metadata.name` = current git branch
- `/sessions` lists available sessions with IDs, timestamps, message counts, and names
- 8+ tests in `tests/unit/test_q66/test_session_continuity.py`

---

### 445. Autonomous task flows with checkpoints

**Files:** `src/lidco/flows/__init__.py`, `src/lidco/flows/engine.py`, `src/lidco/flows/checkpoint.py`, `src/lidco/flows/rollback.py`, `src/lidco/cli/commands/runtime_cmds.py`

**Goal:** Windsurf-style autonomous multi-step task flows. A "flow" decomposes a user goal into ordered steps, each executed with a file-level checkpoint before execution. User can pause, rollback, or skip steps.

**Acceptance criteria:**
- `FlowEngine.plan(goal) -> Flow` decomposes goal into steps via LLM
- `FlowEngine.execute(flow) -> FlowResult` runs steps sequentially
- `FlowCheckpointManager.save()` snapshots all modified files before each step
- `FlowCheckpointManager.rollback(checkpoint_id)` restores files to named checkpoint
- Commands: `/flow start <goal>`, `/flow pause`, `/flow resume`, `/flow rollback [step_n]`, `/flow status`
- On step failure: auto-pause, show error, offer rollback or skip
- 12+ tests in `tests/unit/test_q66/test_task_flows.py`

---

### 446. Auto-commit mode

**Files:** `src/lidco/git/auto_commit.py` (new), `src/lidco/cli/commands/git_cmds.py`, `src/lidco/core/config.py`

**Goal:** After each agent execution that modifies files, automatically stage and commit with a descriptive message. Toggle via `/autocommit on|off` or `git.auto_commit: bool` config.

**Acceptance criteria:**
- `AutoCommitter.commit_if_dirty(description) -> str | None` — stages, commits, returns hash or None
- Commit message: use description directly if <=72 chars; else LLM summarize
- `LidcoConfig.git_auto_commit: bool = False` config field
- `/autocommit` slash command: on / off / no args toggles
- Wired in `app.py` after each `orchestrator.handle()` response
- 8+ tests in `tests/unit/test_q66/test_auto_commit.py`

---

### 447. Custom context providers

**Files:** `src/lidco/context/providers/__init__.py`, `base.py`, `file_provider.py`, `url_provider.py`, `command_provider.py`, `loader.py`

**Goal:** Users define custom context sources in `.lidco/context_providers.yaml`. Built-in types: `file` (glob), `url` (fetch with cache), `command` (shell output). All inject data into system prompt.

**Acceptance criteria:**
- `ContextProvider` abstract base: `name`, `async fetch() -> str`, `priority`, `max_tokens`
- `FileContextProvider`, `URLContextProvider`, `CommandContextProvider` implementations
- YAML config: `providers: [{type: file, name: docs, pattern: "docs/*.md"}, ...]`
- `ContextProviderRegistry.collect(budget_tokens) -> str` — all providers sorted by priority
- Wired in `session.py` if `.lidco/context_providers.yaml` exists
- `/context-providers list` and `/context-providers reload` commands
- 10+ tests in `tests/unit/test_q66/test_context_providers.py`

---

### 448. Diff-first editing with selective apply

**Files:** `src/lidco/editing/diff_engine.py` (new), `src/lidco/editing/hunk.py` (new), `src/lidco/tools/file_write.py`

**Goal:** Instead of writing files directly, show a unified diff preview first. Accept all, reject all, or accept/reject individual hunks. Only accepted hunks are applied.

**Acceptance criteria:**
- `DiffEngine.preview(path, new_content) -> DiffPreview` splits unified diff into `Hunk` objects
- `DiffPreview.apply(accepted_indices: set[int]) -> str` returns merged content
- `LidcoConfig.diff_first: bool = False`
- When enabled, `file_write` intercepts writes and emits preview
- `/diff-apply [all | none | 1,3,5]` and `/diff-mode on|off` commands
- 10+ tests in `tests/unit/test_q66/test_diff_first.py`

---

### 449. Workspace snapshots

**Files:** `src/lidco/workspace/snapshot.py` (new), `src/lidco/workspace/__init__.py` (new), `src/lidco/cli/commands/session.py`

**Goal:** Snapshot + restore full workspace: modified files, git stash ref, HEAD ref, and conversation history. Extends existing checkpoint infrastructure to full-workspace scope.

**Acceptance criteria:**
- `WorkspaceSnapshot` dataclass: `id`, `name`, `timestamp`, `files: dict[str, str]`, `git_ref`, `git_stash_ref`, `history`, `metadata`
- `WorkspaceSnapshotManager.save(name, history) -> WorkspaceSnapshot`
- `WorkspaceSnapshotManager.restore(name_or_id) -> RestoreResult`
- Storage: `.lidco/workspace_snapshots/<id>.json`, capped at 10MB total
- Commands: `/workspace save <name>`, `/workspace restore <name>`, `/workspace list`, `/workspace delete <name>`
- 10+ tests in `tests/unit/test_q66/test_workspace_snapshots.py`

---

### 450. Inline next-edit prediction

**Files:** `src/lidco/prediction/next_edit.py` (new), `src/lidco/prediction/__init__.py` (new)

**Goal:** After agent makes an edit, predict the most likely next edit location and content. Displayed as a ghost suggestion the user can accept or dismiss.

**Acceptance criteria:**
- `NextEditPredictor.predict(recent_edits, context) -> EditSuggestion | None`
- LLM call with `max_tokens=300`, `temperature=0.3`, JSON `{"file":..,"line":..,"old":..,"new":..}`
- Triggered automatically after each file_write/file_edit tool call when enabled
- Display: `[Tab] Accept suggested edit: {path}:{line}` or `[Esc] Dismiss`
- `LidcoConfig.predict_next_edit: bool = False`, `/predict on|off` command
- 5s hard timeout; async; prediction cached per edit pattern
- 8+ tests in `tests/unit/test_q66/test_next_edit.py`

---

### 451. Architect-editor split model

**Files:** `src/lidco/llm/architect_editor.py` (new), `src/lidco/core/config.py`, `src/lidco/agents/graph.py`

**Goal:** Use a separate LLM for architecture/planning decisions vs code generation. Architect model handles planner, critique, review nodes; editor model handles execution nodes. Parity with Aider architect mode.

**Acceptance criteria:**
- `LLMConfig.architect_model: str | None = None` and `editor_model: str | None = None`
- `ArchitectEditorRouter.get_model(role) -> str` — routes `planner/critique/review` to architect_model, `executor/code_gen` to editor_model, falls back to default
- `GraphOrchestrator` nodes use appropriate model via router
- Commands: `/architect <model>`, `/editor <model>`, updated `/models`
- Cost tracking distinguishes architect vs editor tokens in session summary
- 8+ tests in `tests/unit/test_q66/test_architect_editor.py`

---

## Q67 — Memory, PR Review & Shadow Workspace

**Goal:** три наиболее востребованных конкурентных фичи: персистентная память агента (как Cursor Memories), автоматическое ревью PR (как Cursor BugBot), и shadow workspace / dry-run (как Cursor shadow workspace).

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 452 | [Persistent Agent Memory](#452-agent-memory) | ✅ Done | 2d | cross-session memory — parity with Cursor/Windsurf Memories |
| 453 | [Automated PR Review CLI](#453-pr-review) | ✅ Done | 2d | `lidco review-pr` + GitHub Actions template — parity with Cursor BugBot |
| 454 | [Shadow Workspace / dry-run mode](#454-shadow-workspace) | ✅ Done | 2d | preview all edits before apply, selective accept — parity with Cursor shadow workspace |
| 455 | [File-watch annotation trigger](#455-watch-mode) | ✅ Done | 1d | `lidco watch` — detects `# LIDCO:` comments, runs agent — parity with Aider watch |
| 456 | [Notepads / persistent scratchpads](#456-notepads) | ✅ Done | 1d | `/notepad` command + `@notepad` context reference — parity with Cursor Notepads |
| 457 | [Microagent knowledge injection](#457-microagents) | ✅ Done | 1d | keyword-triggered `.md` knowledge files in `.lidco/microagents/` — parity with OpenHands |
| 458 | [Typed Action-Observation trajectory](#458-trajectory) | ✅ Done | 1d | structured JSON log of every tool action + result — parity with OpenHands trajectory export |

---

### 452. Persistent Agent Memory

**Files:** `src/lidco/memory/agent_memory.py` (new), `src/lidco/memory/__init__.py`, `src/lidco/core/session.py`, `src/lidco/cli/commands/context_cmds.py`

**Goal:** After each session, the agent automatically saves key observations, decisions, and learned preferences to a persistent memory store. At the start of each session, relevant memories are loaded and injected into the system prompt. Parity with Cursor Memories and Windsurf Memories.

**Acceptance criteria:**
- `AgentMemory` dataclass: `id`, `content`, `tags: list[str]`, `created_at`, `last_used`, `use_count`
- `AgentMemoryStore` (SQLite-backed in `.lidco/agent_memory.db`):
  - `add(content, tags) -> AgentMemory`
  - `search(query, limit=10) -> list[AgentMemory]` — BM25 keyword search
  - `list(limit=20) -> list[AgentMemory]`
  - `delete(id) -> bool`
  - `auto_extract(session_summary: str) -> list[AgentMemory]` — LLM call extracts key facts
- At session end: if session had >3 turns, call `auto_extract()` on session summary, save new memories
- At session start: inject top-10 relevant memories into system prompt as `## Agent Memory` block
- Commands: `/memory list`, `/memory add <text>`, `/memory delete <id>`, `/memory search <query>`, `/memory clear`
- `@memory` context reference injects all memories into next message
- 10+ tests in `tests/unit/test_q67/test_agent_memory.py`

---

### 453. Automated PR Review CLI

**Files:** `src/lidco/review/pr_reviewer.py` (new), `src/lidco/review/__init__.py`, `src/lidco/cli/commands/git_cmds.py`, `.github/workflows/lidco-review.yml` (template)

**Goal:** `lidco review-pr [PR_NUMBER|URL]` command that fetches the PR diff, runs LIDCO's security + code quality analysis, and posts inline review comments via GitHub API. A GitHub Actions workflow template enables CI-triggered automated review on every PR.

**Acceptance criteria:**
- `PRReviewer.review(pr_number_or_url: str) -> ReviewResult`
  - Fetches diff via `gh pr diff <n>` subprocess
  - Runs `SecurityScanner`, `BugBot`, and `CodeSmellDetector` on changed files
  - Calls LLM to synthesize findings into structured review comments with file+line references
  - Posts comments via `gh api` or GitHub REST API
- `ReviewResult` dataclass: `pr_number`, `comments: list[ReviewComment]`, `summary: str`, `severity_counts: dict`
- `ReviewComment`: `path`, `line`, `body`, `severity` (critical/high/medium/info)
- `/review-pr [NUMBER]` slash command in REPL
- `lidco review-pr <NUMBER>` top-level CLI subcommand (in `__main__.py`)
- GitHub Actions template at `.github/workflows/lidco-review.yml.template`:
  ```yaml
  on: [pull_request]
  jobs:
    review:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - run: lidco review-pr ${{ github.event.pull_request.number }}
  ```
- 8+ tests in `tests/unit/test_q67/test_pr_review.py`

---

### 454. Shadow Workspace / dry-run mode

**Files:** `src/lidco/shadow/workspace.py` (new), `src/lidco/shadow/__init__.py`, `src/lidco/tools/file_write.py`, `src/lidco/tools/file_edit.py`, `src/lidco/cli/app.py`

**Goal:** `--dry-run` flag and `/dry-run on|off` command that intercepts all file write/edit tool calls, accumulates them in a shadow buffer, renders a unified diff preview, and asks for confirmation before applying any changes to disk. Parity with Cursor shadow workspace.

**Acceptance criteria:**
- `ShadowWorkspace`:
  - `intercept(path, new_content) -> None` — stores pending write without touching disk
  - `get_diff() -> str` — unified diff of all pending changes vs current disk state
  - `apply(paths: list[str] | None = None) -> ApplyResult` — write accepted changes to disk
  - `discard(paths: list[str] | None = None) -> None` — clear pending changes
  - `pending_paths() -> list[str]` — list of files with pending changes
- `FileWriteTool` and `FileEditTool` check `session.shadow_workspace` — if active, intercept instead of writing
- `LidcoConfig.dry_run: bool = False`; `--dry-run` CLI flag sets it
- After agent response in dry-run mode: show diff summary `"N files pending: foo.py, bar.py"` + prompt `[a]pply / [d]iscard / [r]eview`
- `/dry-run on|off|status` slash command
- `/apply` applies all pending shadow changes; `/discard` discards them; `/review` shows full diff
- 10+ tests in `tests/unit/test_q67/test_shadow_workspace.py`

---

### 455. File-watch annotation trigger

**Files:** `src/lidco/watch/watcher.py` (new), `src/lidco/watch/__init__.py`, `src/lidco/__main__.py`

**Goal:** `lidco watch [PATH]` CLI subcommand that monitors the filesystem for files containing `# LIDCO: <instruction>` comments (or `// LIDCO:` for JS/TS). When detected, extracts the instruction, runs the agent on it, applies the result, and removes the annotation. Parity with Aider's `--watch-files` mode.

**Acceptance criteria:**
- `FileWatcher`:
  - `start(path: str | None = None) -> None` — watches `path` or CWD recursively (excludes `.git`, `node_modules`, `__pycache__`)
  - `scan_for_annotations(file_path: str) -> list[Annotation]` — finds `# LIDCO: ...` or `// LIDCO: ...` lines
  - On annotation found: extract instruction, call orchestrator headlessly, write result, remove annotation from source file
  - Supports multi-line annotations: `# LIDCO: |` starts block, ends at next non-comment line
- `Annotation` dataclass: `file_path`, `line_number`, `instruction`, `context_lines: list[str]`
- `lidco watch` top-level CLI subcommand
- Status display: Rich Live table showing watched dirs, last trigger time, last action
- Debounce: 500ms after file save before processing (handles editors that write multiple times)
- `--once` flag: process all current annotations and exit (useful for CI)
- 8+ tests in `tests/unit/test_q67/test_watch_mode.py`

---

### 456. Notepads / persistent scratchpads

**Files:** `src/lidco/notepads/store.py` (new), `src/lidco/notepads/__init__.py`, `src/lidco/cli/commands/context_cmds.py`

**Goal:** Named persistent scratchpads that users write to and that agents automatically incorporate as context. Reference with `@notepad:<name>` in messages. Parity with Cursor Notepads.

**Acceptance criteria:**
- `NotepadStore` (files in `.lidco/notepads/<name>.md`):
  - `create(name, content) -> Notepad`
  - `read(name) -> Notepad | None`
  - `update(name, content) -> Notepad`
  - `delete(name) -> bool`
  - `list() -> list[Notepad]`
- `@notepad:<name>` in user message injects the notepad content as context
- Commands: `/notepad new <name>`, `/notepad show <name>`, `/notepad edit <name>`, `/notepad list`, `/notepad delete <name>`
- `/notepad edit <name>` opens content in `$EDITOR` (or inline multi-line input if no editor set)
- Agent can write to notepads via a `notepad_write` tool (when enabled)
- 8+ tests in `tests/unit/test_q67/test_notepads.py`

---

### 457. Microagent knowledge injection

**Files:** `src/lidco/microagents/loader.py` (new), `src/lidco/microagents/__init__.py`, `src/lidco/core/session.py`

**Goal:** Small markdown knowledge files in `.lidco/microagents/` are automatically injected into the system prompt when their trigger keywords appear in the user's message. Parity with OpenHands microagents.

**Acceptance criteria:**
- Microagent file format (`.lidco/microagents/<name>.md`):
  ```markdown
  ---
  triggers: [deploy, deployment, kubernetes, k8s]
  priority: 10
  ---
  ## Deployment Guide
  Always use `helm upgrade --install` ...
  ```
- `MicroagentLoader.load_all(project_dir) -> list[Microagent]`
- `MicroagentMatcher.match(user_message, microagents) -> list[Microagent]` — case-insensitive keyword scan
- Matched microagents injected into system prompt as `## Project Knowledge` blocks, sorted by priority
- Global microagents in `~/.lidco/microagents/` (always loaded)
- `/microagents list` — shows all available microagents and their triggers
- `/microagents test <message>` — shows which microagents would fire for a given message
- 8+ tests in `tests/unit/test_q67/test_microagents.py`

---

### 458. Typed Action-Observation trajectory

**Files:** `src/lidco/trajectory/recorder.py` (new), `src/lidco/trajectory/__init__.py`, `src/lidco/core/session.py`, `src/lidco/cli/commands/session.py`

**Goal:** Record every tool call and its result as a typed `(action, observation)` pair. Export as JSON for debugging, compliance audit, or LLM fine-tuning. Parity with OpenHands trajectory export.

**Acceptance criteria:**
- `Action` dataclass: `type: str`, `tool: str`, `params: dict`, `timestamp: float`, `agent: str`
- `Observation` dataclass: `type: str`, `result: Any`, `success: bool`, `elapsed_ms: int`, `truncated: bool`
- `TrajectoryStep`: `action: Action`, `observation: Observation`
- `TrajectoryRecorder`:
  - `record(action, observation) -> None`
  - `export_json(path: str) -> None`
  - `export_jsonl(path: str) -> None` (one JSON object per line — fine-tuning format)
  - `summary() -> dict` — counts by action type, total elapsed, error rate
- Wired via `tool_event_callback` in `session.py`
- `/trajectory export [PATH]` — export current session trajectory to JSON
- `/trajectory summary` — show action count breakdown and timing
- `--trajectory <path>` CLI flag: auto-export on session end
- 8+ tests in `tests/unit/test_q67/test_trajectory.py`

---

## Q68 — Spec-Driven Development

**Goal:** Kiro (Amazon) — самый большой сдвиг парадигмы 2025-2026. Вместо "vibe coding" — формальные спецификации: requirements → design → tasks. Агент реализует по спеку, а не по свободному промпту.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 459 | [SpecWriter — NL prompt → requirements.md](#459-spec-writer) | ✅ Done | 2d | structured intent — parity with Kiro |
| 460 | [DesignDoc generator — requirements → design.md](#460-design-doc) | ✅ Done | 2d | architecture planning layer |
| 461 | [TaskDecomposer — design.md → tasks.md](#461-task-decomposer) | ✅ Done | 1d | ordered agent work queue |
| 462 | [/spec slash command — orchestrates 3-stage pipeline](#462-spec-command) | ✅ Done | 1d | UX entry point |
| 463 | [Spec-aware agent execution — reads requirements + tasks as context](#463-spec-context) | ✅ Done | 2d | closes the spec-to-code loop |
| 464 | [Spec drift detection — alert when code diverges from spec](#464-spec-drift) | ✅ Done | 1d | maintenance value |

---

### 459. SpecWriter — NL prompt → requirements.md

**Files:** `src/lidco/spec/writer.py` (new), `src/lidco/spec/__init__.py` (new)

**Goal:** Given a natural language description of a feature or task, generate a structured `requirements.md` with EARS-notation acceptance criteria. EARS = "The system shall..." format used in Kiro.

**Acceptance criteria:**
- `SpecWriter.generate(description: str, project_dir: Path) -> SpecDocument`
- `SpecDocument` dataclass: `title`, `overview`, `user_stories: list[str]`, `acceptance_criteria: list[str]`, `out_of_scope: list[str]`
- LLM call with `max_tokens=2000`, structured prompt requesting EARS-notation criteria
- Output saved to `.lidco/spec/requirements.md` (creates dir if needed)
- Existing `requirements.md` loaded as context for incremental updates
- 8+ tests in `tests/unit/test_q68/test_spec_writer.py`

---

### 460. DesignDoc generator — requirements → design.md

**Files:** `src/lidco/spec/design_doc.py` (new)

**Goal:** Given `requirements.md`, generate a technical design document identifying components, data models, API contracts, and implementation approach.

**Acceptance criteria:**
- `DesignDocGenerator.generate(spec_doc: SpecDocument, project_dir: Path) -> DesignDocument`
- `DesignDocument`: `components: list[Component]`, `data_models: list[str]`, `api_contracts: list[str]`, `implementation_notes: str`
- Uses codebase context (existing modules, patterns) to generate design consistent with current architecture
- Saved to `.lidco/spec/design.md`
- 8+ tests in `tests/unit/test_q68/test_design_doc.py`

---

### 461. TaskDecomposer — design.md → tasks.md

**Files:** `src/lidco/spec/task_decomposer.py` (new)

**Goal:** Decompose a design document into an ordered list of implementation tasks with file targets and acceptance criteria per task.

**Acceptance criteria:**
- `TaskDecomposer.decompose(design: DesignDocument, project_dir: Path) -> list[SpecTask]`
- `SpecTask`: `id`, `title`, `description`, `target_files: list[str]`, `depends_on: list[str]`, `done: bool`
- Tasks ordered by dependency (topological sort)
- Saved to `.lidco/spec/tasks.md` in checkbox format: `- [ ] T1: ...`
- `TaskDecomposer.mark_done(task_id, project_dir)` — toggles checkbox
- 8+ tests in `tests/unit/test_q68/test_task_decomposer.py`

---

### 462. /spec slash command

**Files:** `src/lidco/cli/commands/spec_cmds.py` (new)

**Goal:** Single entry point that orchestrates the 3-stage spec pipeline.

**Acceptance criteria:**
- `/spec new <description>` — runs SpecWriter → DesignDocGenerator → TaskDecomposer, shows output
- `/spec show` — prints current requirements.md + tasks.md status
- `/spec tasks` — lists tasks with done/todo status
- `/spec done <task_id>` — marks task as done
- `/spec reset` — clears all spec files with confirmation
- 8+ tests in `tests/unit/test_q68/test_spec_commands.py`

---

### 463. Spec-aware agent execution

**Files:** `src/lidco/core/session.py`, `src/lidco/agents/graph.py`

**Goal:** When `.lidco/spec/` exists, automatically inject requirements.md and current tasks.md (incomplete tasks only) into the system prompt as primary context.

**Acceptance criteria:**
- `SpecContextProvider.load(project_dir) -> str | None` — returns formatted spec block or None
- Injected as `## Project Specification` block before other context
- Only loads if `.lidco/spec/requirements.md` exists
- Token budget: max 2000 tokens for spec context
- 6+ tests in `tests/unit/test_q68/test_spec_context.py`

---

### 464. Spec drift detection

**Files:** `src/lidco/spec/drift_detector.py` (new)

**Goal:** Periodically check if implemented code still satisfies the acceptance criteria in requirements.md. Alert when drift detected.

**Acceptance criteria:**
- `DriftDetector.check(project_dir) -> DriftReport`
- `DriftReport`: `drifted_criteria: list[str]`, `ok_criteria: list[str]`, `confidence: float`
- Uses LLM to compare acceptance criteria text against recent git diff + test results
- `/spec check` command triggers check and shows report
- 6+ tests in `tests/unit/test_q68/test_drift_detector.py`

---

## Q69 — Codebase Wiki + Semantic Q&A

**Goal:** Devin Wiki + Devin Search — living auto-generated documentation and natural language Q&A against the codebase. Builds on LIDCO's existing RAG and code analysis pipeline.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 465 | [WikiGenerator — auto-doc from code + git history](#465-wiki-generator) | ✅ Done | 2d | Devin Wiki parity |
| 466 | [Incremental wiki updates on file change](#466-wiki-incremental) | ✅ Done | 1d | freshness |
| 467 | [CodebaseQA — natural language Q&A against indexed code](#467-codebase-qa) | ✅ Done | 2d | Devin Search parity |
| 468 | [/wiki command — generate and view module documentation](#468-wiki-command) | ✅ Done | 1d | CLI entry point |
| 469 | [/ask command — semantic codebase questions](#469-ask-command) | ✅ Done | 1d | Q&A entry point |
| 470 | [Wiki export — Markdown files per module](#470-wiki-export) | ✅ Done | 1d | portability |

---

### 465. WikiGenerator

**Files:** `src/lidco/wiki/generator.py` (new), `src/lidco/wiki/__init__.py` (new)

**Goal:** Auto-generate module/class/function documentation by combining static analysis (docstrings, signatures, type hints) with git history (who changed what, why) and LLM synthesis.

**Acceptance criteria:**
- `WikiGenerator.generate_module(path: str, project_dir: Path) -> WikiPage`
- `WikiPage`: `module_path`, `summary`, `classes: list[ClassDoc]`, `functions: list[FuncDoc]`, `recent_changes: list[str]`, `generated_at`
- Uses existing static analysis modules (Q49-Q53) for AST extraction
- Git log for change history context
- LLM call for natural language summary synthesis
- Saved to `.lidco/wiki/<module_path>.md`
- 8+ tests in `tests/unit/test_q69/test_wiki_generator.py`

---

### 466. Incremental wiki updates

**Files:** `src/lidco/wiki/updater.py` (new)

**Goal:** Watch for file changes and regenerate wiki pages for modified modules automatically.

**Acceptance criteria:**
- `WikiUpdater.update_on_change(changed_files: list[str], project_dir: Path) -> list[str]` — regenerates affected wiki pages
- Debounce: only update if file changed > 30s ago
- Hooked into existing FileWatcher (Task 455) or triggered post-tool-use
- Returns list of updated wiki page paths
- 6+ tests in `tests/unit/test_q69/test_wiki_updater.py`

---

### 467. CodebaseQA

**Files:** `src/lidco/wiki/qa.py` (new)

**Goal:** Answer natural language questions about the codebase using the vector index + wiki + code analysis results.

**Acceptance criteria:**
- `CodebaseQA.ask(question: str, project_dir: Path) -> QAAnswer`
- `QAAnswer`: `answer: str`, `sources: list[str]` (file paths), `confidence: float`
- Strategy: hybrid search (BM25 + vector) across code + wiki, then LLM synthesis
- Cites specific files/functions in the answer
- Falls back gracefully if index empty (runs grep-based search)
- 8+ tests in `tests/unit/test_q69/test_codebase_qa.py`

---

### 468. /wiki command

**Files:** `src/lidco/cli/commands/wiki_cmds.py` (new)

**Acceptance criteria:**
- `/wiki generate [path]` — generate wiki for module or entire project
- `/wiki show <module>` — display wiki page
- `/wiki status` — show which modules have/lack wiki pages
- `/wiki refresh` — regenerate all stale pages (mtime-based)
- 6+ tests in `tests/unit/test_q69/test_wiki_commands.py`

---

### 469. /ask command

**Files:** `src/lidco/cli/commands/wiki_cmds.py`

**Acceptance criteria:**
- `/ask <question>` — answers questions about the codebase
- Example: `/ask what does the auth flow do?` → structured answer with file citations
- `/ask how is X tested?` → points to test files
- Distinguishes "about the code" questions (CodebaseQA) from implementation requests (normal REPL)
- 6+ tests in `tests/unit/test_q69/test_ask_command.py`

---

### 470. Wiki export

**Files:** `src/lidco/wiki/exporter.py` (new)

**Acceptance criteria:**
- `WikiExporter.export(project_dir, output_dir) -> int` — writes all wiki pages as Markdown
- Generates index page (`README.md`) with module list and links
- Optional: export to JSON for external tools
- `/wiki export [output_dir]` command
- 6+ tests in `tests/unit/test_q69/test_wiki_exporter.py`

---

## Q70 — PR Autofix Agent + Enhanced Review

**Goal:** Complete the PR review loop with automated fix proposals (Cursor BugBot Autofix). LIDCO has basic PR review (Q67 T453) but no autofix agent that writes and tests a fix.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 471 | [AutofixAgent — spawns isolated agent per review comment](#471-autofix-agent) | ✅ Done | 3d | Cursor Autofix parity |
| 472 | [Fix verification — run tests after autofix, reject if failing](#472-fix-verify) | ✅ Done | 1d | quality gate |
| 473 | [GitHub PR comment posting — inline + summary](#473-gh-comment) | ✅ Done | 2d | integration |
| 474 | [Resolution tracking — mark comments resolved on re-review](#474-resolution) | ✅ Done | 1d | UX quality |
| 475 | [/review-pr --autofix flag](#475-autofix-flag) | ✅ Done | 1d | CLI entry point |

---

### 471. AutofixAgent

**Files:** `src/lidco/review/autofix_agent.py` (new)

**Goal:** For each critical/high review comment, spawn an isolated agent in a worktree, implement the fix, run tests, and propose the diff as a patch.

**Acceptance criteria:**
- `AutofixAgent.fix(comment: ReviewComment, project_dir: Path) -> FixProposal | None`
- `FixProposal`: `comment_id`, `patch: str` (unified diff), `test_result: str`, `confidence: float`
- Uses existing worktree support to isolate fixes
- Runs configured test command after fix, rejects if tests fail
- Returns None if fix couldn't be determined
- 10+ tests in `tests/unit/test_q70/test_autofix_agent.py`

---

### 472. Fix verification

**Files:** `src/lidco/review/fix_verifier.py` (new)

**Acceptance criteria:**
- `FixVerifier.verify(proposal: FixProposal, project_dir: Path) -> VerifyResult`
- Applies patch to temp copy, runs tests, checks for regressions
- `VerifyResult`: `passed: bool`, `test_output: str`, `regression_count: int`
- 6+ tests in `tests/unit/test_q70/test_fix_verifier.py`

---

### 473. GitHub PR comment posting

**Files:** `src/lidco/review/gh_poster.py` (new)

**Goal:** Post inline review comments and fix proposals directly to the GitHub PR using gh CLI.

**Acceptance criteria:**
- `GHPoster.post_review(pr_number, comments: list[ReviewComment], repo=None) -> PostResult`
- Inline comments with file+line references via `gh api`
- Summary comment with severity counts and autofix proposals
- Deduplication: don't re-post identical comments on re-review
- 8+ tests in `tests/unit/test_q70/test_gh_poster.py`

---

### 474. Resolution tracking

**Files:** `src/lidco/review/resolution_store.py` (new)

**Acceptance criteria:**
- `ResolutionStore` (SQLite in `.lidco/review_resolutions.db`): track comment hash → resolved status
- On re-review: skip comments matching resolved hashes
- `/review-pr --show-resolved` to include previously resolved items
- 6+ tests in `tests/unit/test_q70/test_resolution_store.py`

---

### 475. /review-pr --autofix flag

**Acceptance criteria:**
- `/review-pr <n> --autofix` — runs review, then spawns AutofixAgent for each critical/high comment
- Shows progress: `Fixing 3 issues...` with spinner
- Presents fix proposals with diff previews; user accepts/rejects each
- Rejected fixes discarded; accepted fixes applied to working tree
- 6+ tests in `tests/unit/test_q70/test_review_autofix_integration.py`

---

## Q71 — Agent-Spawning Agents + Runtime Orchestration

**Goal:** Replit Agent 3's unique capability — describe a workflow in NL → LIDCO synthesizes a specialized agent at runtime and registers it for reuse. Closes the gap between static YAML agents and truly adaptive multi-agent systems.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 476 | [AgentFactory — NL description → agent spec at runtime](#476-agent-factory) | ✅ Done | 2d | Replit Agent 3 parity |
| 477 | [Agent registry — persist and reuse synthesized agents](#477-agent-registry) | ✅ Done | 1d | persistence layer |
| 478 | [/spawn-agent command](#478-spawn-command) | ✅ Done | 1d | CLI entry point |
| 479 | [WorkflowAgent — recurring task scheduler](#479-workflow-agent) | ✅ Done | 2d | scheduled automation |
| 480 | [Agent lifecycle management — pause/resume/terminate](#480-lifecycle) | ✅ Done | 1d | operations |

---

### 476. AgentFactory

**Files:** `src/lidco/agents/factory.py` (new)

**Goal:** Given a natural language description, synthesize a complete agent specification (system prompt, tool list, permissions) and register it as a named agent.

**Acceptance criteria:**
- `AgentFactory.synthesize(description: str, project_dir: Path) -> AgentConfig`
- LLM call that produces `AgentConfig` with: `name`, `description`, `system_prompt`, `tools`, `model`, `max_iterations`
- Validates tool names against registry
- Writes spec to `.lidco/agents/<name>.yaml` for persistence
- 8+ tests in `tests/unit/test_q71/test_agent_factory.py`

---

### 477. Agent registry (runtime)

**Files:** `src/lidco/agents/runtime_registry.py` (new)

**Acceptance criteria:**
- `RuntimeAgentRegistry.register(config: AgentConfig) -> None`
- `RuntimeAgentRegistry.get(name: str) -> AgentConfig | None`
- `RuntimeAgentRegistry.list() -> list[AgentConfig]`
- Backed by `.lidco/agents/` directory (loads YAML files on startup)
- Hot-reload: new files appear without restart
- 6+ tests in `tests/unit/test_q71/test_runtime_registry.py`

---

### 478. /spawn-agent command

**Acceptance criteria:**
- `/spawn-agent <description>` — synthesizes and registers a new agent
- Example: `/spawn-agent An agent that weekly audits dependencies for outdated packages`
- Shows generated spec before registering, asks for confirmation
- After registration: `@<name>` syntax routes messages to it
- 6+ tests in `tests/unit/test_q71/test_spawn_command.py`

---

### 479. WorkflowAgent — recurring tasks

**Files:** `src/lidco/agents/workflow_agent.py` (new)

**Goal:** Purpose-built agent for recurring scheduled tasks (e.g., "every Monday: audit deps, run security scan, post Slack summary").

**Acceptance criteria:**
- `WorkflowAgent`: `name`, `schedule: str` (cron), `tasks: list[str]`, `notify: list[str]`
- Integration with existing Slack integration (Q60) for result posting
- `/workflow add <name> <schedule> <description>` command
- `/workflow run <name>` manual trigger
- 8+ tests in `tests/unit/test_q71/test_workflow_agent.py`

---

### 480. Agent lifecycle management

**Acceptance criteria:**
- `/agents list` — show all registered agents with status (idle/running/paused)
- `/agents pause <name>` — pause a running agent after current step
- `/agents resume <name>` — resume paused agent
- `/agents kill <name>` — terminate immediately
- Status persisted in `.lidco/agent_status.json`
- 6+ tests in `tests/unit/test_q71/test_agent_lifecycle.py`

---

## Q72 — Confidence-Based Clarification + Next-Edit Prediction

**Goal:** Two high-impact UX features: Devin 2.0's confidence-based interruption model (stops asking unnecessary questions) and JetBrains/Copilot's next-edit prediction (predicts where to edit next).

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 481 | [ConfidenceEstimator — per-action uncertainty scoring](#481-confidence) | ✅ Done | 2d | Devin 2.0 parity |
| 482 | [Clarification threshold — configurable ask-only-when-uncertain](#482-threshold) | ✅ Done | 1d | reduces interruptions |
| 483 | [--autonomous / --supervised / --interactive modes](#483-modes) | ✅ Done | 1d | UX control |
| 484 | [NextEditPredictor — predict next edit location + content](#484-next-edit) | ✅ Done | 2d | JetBrains/Copilot parity |
| 485 | [Edit graph — symbol relationship model for prediction context](#485-edit-graph) | ✅ Done | 2d | prediction accuracy |
| 486 | [REPL next-edit display — show prediction after each change](#486-next-edit-repl) | ✅ Done | 1d | UX integration |

---

### 481. ConfidenceEstimator

**Files:** `src/lidco/confidence/estimator.py` (new), `src/lidco/confidence/__init__.py` (new)

**Goal:** Score each agent action on a confidence scale (0–1) based on: ambiguity in task description, missing required context, risk level of the action (file delete vs read), presence of conflicting instructions.

**Acceptance criteria:**
- `ConfidenceEstimator.score(action_type: str, params: dict, context: str) -> ConfidenceScore`
- `ConfidenceScore`: `value: float`, `factors: dict[str, float]`, `should_ask: bool`
- Factors: `task_clarity`, `context_completeness`, `action_risk`, `conflict_detected`
- Risk table: `file_delete=0.3`, `file_write=0.6`, `bash=0.5`, `file_read=0.9`
- `should_ask = value < threshold` (default threshold=0.7)
- 8+ tests in `tests/unit/test_q72/test_confidence_estimator.py`

---

### 482. Clarification threshold

**Files:** `src/lidco/core/config.py`, `src/lidco/agents/base.py`

**Acceptance criteria:**
- `AgentsConfig.clarification_threshold: float = 0.7`
- Agent checks confidence before each risky action; asks targeted question if below threshold
- Clarification questions are specific: "Should I delete X or rename it?" not "What should I do?"
- Max 1 clarification per agent turn (avoid question spam)
- 6+ tests in `tests/unit/test_q72/test_clarification.py`

---

### 483. Autonomy modes

**Files:** `src/lidco/__main__.py`, `src/lidco/core/config.py`

**Acceptance criteria:**
- `--autonomous`: never ask, proceed on best guess (threshold=0.0)
- `--supervised`: ask when confidence < 0.7 (default)
- `--interactive`: ask before every risky action (threshold=0.9)
- `/mode autonomous|supervised|interactive` slash command
- Mode shown in session status bar
- 6+ tests in `tests/unit/test_q72/test_autonomy_modes.py`

---

### 484. NextEditPredictor

**Files:** `src/lidco/prediction/next_edit.py` (already planned in Q66 T450 — implement here)

**Goal:** After the agent makes an edit, predict the most likely next edit location and content based on the edit graph, conversation context, and symbol relationships.

**Acceptance criteria:**
- `NextEditPredictor.predict(recent_edits: list[EditRecord], context: str) -> EditSuggestion | None`
- LLM call with `max_tokens=300`, `temperature=0.3`, structured JSON response
- 5s hard timeout; fire-and-forget async
- Prediction cached per edit pattern (don't re-call for same change)
- `LidcoConfig.predict_next_edit: bool = False`, `/predict on|off`
- 8+ tests in `tests/unit/test_q72/test_next_edit_predictor.py`

---

### 485. Edit graph

**Files:** `src/lidco/prediction/edit_graph.py` (new)

**Goal:** Build a lightweight symbol relationship graph used to find related edit sites: call sites, implementations, type usages, test/impl pairs.

**Acceptance criteria:**
- `EditGraph.build(project_dir: Path) -> EditGraph` — scans Python/JS/TS files for symbol references
- `EditGraph.related_sites(symbol: str, file_path: str) -> list[EditSite]`
- `EditSite`: `file_path`, `line`, `relationship` (call_site, test, implementation, type_usage)
- Lightweight: in-memory, rebuilt on demand (no persistent index needed)
- 8+ tests in `tests/unit/test_q72/test_edit_graph.py`

---

### 486. REPL next-edit display

**Files:** `src/lidco/cli/app.py`, `src/lidco/cli/renderer.py`

**Acceptance criteria:**
- After each agent file edit, if prediction enabled: show `[Tab] Next edit: {path}:{line} — {summary}`
- User presses Tab: apply suggestion; Esc: dismiss
- Prediction displayed in dim style below the agent response
- Timeout: if prediction not ready in 5s, skip silently
- 6+ tests in `tests/unit/test_q72/test_next_edit_repl.py`

---

## Q73 — Ensemble Agents + Sandboxed Execution + Action Stream

**Goal:** Three highest-impact competitive gaps: Cursor 2.0 ensemble (run N agents, pick best), OpenHands/Cursor sandboxed bash, Windsurf live action stream as rolling context.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 487 | [EnsembleRunner — N parallel agents, auto-select best result](#487-ensemble) | ✅ Done | 2d | Cursor 2.0 parity |
| 488 | [Sandboxed bash execution](#488-sandbox) | ✅ Done | 2d | OpenHands/Cursor parity |
| 489 | [Live action stream context](#489-action-stream) | ✅ Done | 2d | Windsurf Flow parity |
| 490 | [Pre-PR security gate in agent loop](#490-security-gate) | ✅ Done | 1d | Copilot parity |
| 491 | [Agent self-review loop before PR](#491-self-review) | ✅ Done | 1d | Copilot parity |

---

### 487. EnsembleRunner

**Files:** `src/lidco/agents/ensemble.py` (new)

**Goal:** Run N parallel agents on the same task, collect all results, automatically select the best one based on test outcomes or LLM scoring. Parity with Cursor 2.0 8-parallel-agent ensemble.

**Acceptance criteria:**
- `EnsembleRunner.run(task: str, n: int = 3) -> EnsembleResult`
- `EnsembleResult`: `candidates: list[CandidateResult]`, `best: CandidateResult`, `selection_reason: str`
- `CandidateResult`: `agent_id`, `output: str`, `score: float`, `test_passed: bool`
- Selection strategy: prefer test-passing candidates; break ties by LLM quality score
- `EnsembleRunner.score(candidate: CandidateResult) -> float`
- 10+ tests in `tests/unit/test_q73/test_ensemble.py`

---

### 488. Sandboxed bash execution

**Files:** `src/lidco/tools/sandbox.py` (new)

**Goal:** Wrap the Bash tool with an optional subprocess-level sandbox: working directory restriction, env var allowlist, blocked command patterns, optional network disable flag.

**Acceptance criteria:**
- `ExecutionSandbox`: `allowed_dirs: list[str]`, `blocked_patterns: list[str]`, `allowed_env_vars: list[str]`, `network_disabled: bool`
- `ExecutionSandbox.check(cmd: str, cwd: str) -> SandboxVerdict`
- `SandboxVerdict`: `allowed: bool`, `reason: str`
- Built-in blocked patterns: `rm -rf /`, `dd if=`, fork bomb, `mkfs`
- `LidcoConfig.sandbox_enabled: bool = False`
- 10+ tests in `tests/unit/test_q73/test_sandbox.py`

---

### 489. Live action stream context

**Files:** `src/lidco/context/action_stream.py` (new)

**Goal:** Maintain a rolling buffer of recent agent actions and inject as `## Recent activity` into every agent turn. Parity with Windsurf Flow awareness.

**Acceptance criteria:**
- `ActionStreamBuffer`: ring buffer of last 20 `ActionEvent` objects
- `ActionEvent`: `type` (file_edit|test_run|git_op|shell_cmd|file_read), `target: str`, `summary: str`, `timestamp: float`
- `ActionStreamBuffer.record(event: ActionEvent) -> None`
- `ActionStreamBuffer.format_context(limit: int = 10) -> str`
- `ActionStreamBuffer.clear() -> None`
- 8+ tests in `tests/unit/test_q73/test_action_stream.py`

---

### 490. Pre-PR security gate in agent loop

**Files:** `src/lidco/review/security_gate.py` (new)

**Goal:** Before PR creation, run mandatory lightweight security scan (secrets, unsafe patterns). Block PR if critical findings.

**Acceptance criteria:**
- `SecurityGate.check(changed_files: list[str], project_dir: Path) -> GateResult`
- `GateResult`: `passed: bool`, `findings: list[SecurityFinding]`, `blocked_reason: str | None`
- `SecurityFinding`: `file`, `line`, `severity`, `description`
- Checks: hardcoded secrets regex, `eval(user_input)`, SQL concatenation, `shell=True` with user input
- `LidcoConfig.pr_security_gate: bool = True`
- 8+ tests in `tests/unit/test_q73/test_security_gate.py`

---

### 491. Agent self-review loop before PR

**Files:** `src/lidco/review/self_review.py` (new)

**Goal:** After code-writing agent completes, spawn review sub-agent to examine diff and iterate if needed before PR submission. GitHub Copilot coding agent parity.

**Acceptance criteria:**
- `SelfReviewer.review(diff: str, context: str) -> SelfReviewResult`
- `SelfReviewResult`: `issues: list[str]`, `score: float`, `needs_revision: bool`, `suggestions: str`
- `score >= 0.8` means no revision needed; max 2 iterations
- `agents.self_review_before_pr: bool = False` config flag
- 8+ tests in `tests/unit/test_q73/test_self_review.py`

---

## Q74 — Memory Hierarchy + Migration Agent + Issue Trigger

**Goal:** Windsurf dual-tier memory, Amazon Q migration agent, Jules issue-to-agent trigger, HTTP slash commands, mid-execution steering.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 492 | [Workspace-scoped vs. global memory hierarchy](#492-memory-hierarchy) | ✅ Done | 2d | Windsurf Memories parity |
| 493 | [MigrationAgent — automated codebase-wide refactor](#493-migration) | ✅ Done | 2d | Amazon Q parity |
| 494 | [GitHub Issues auto-agent trigger](#494-issue-trigger) | ✅ Done | 2d | Jules parity |
| 495 | [HTTP-backed slash commands](#495-http-commands) | ✅ Done | 1d | Continue.dev parity |
| 496 | [Mid-execution plan modification](#496-mid-plan) | ✅ Done | 1d | Jules parity |

---

### 492. Workspace-scoped vs. global memory hierarchy

**Files:** `src/lidco/memory/tiered_memory.py` (new)

**Acceptance criteria:**
- `TieredMemoryStore`: `workspace_store: AgentMemoryStore`, `global_store: AgentMemoryStore`
- `TieredMemoryStore.search(query, limit=10) -> list[AgentMemory]` — workspace results ranked above global
- `TieredMemoryStore.add(content, tags, scope="workspace") -> AgentMemory`
- `TieredMemoryStore.format_context() -> str`
- 10+ tests in `tests/unit/test_q74/test_tiered_memory.py`

---

### 493. MigrationAgent

**Files:** `src/lidco/agents/migration_agent.py` (new)

**Acceptance criteria:**
- `MigrationRule`: `name`, `description`, `find_pattern` (regex), `replace_template`, `file_glob = "**/*.py"`
- `MigrationAgent.plan(rule, project_dir) -> MigrationPlan`
- `MigrationPlan`: `rule`, `affected_files`, `change_count`, `preview: dict[str, str]`
- `MigrationAgent.execute(plan) -> MigrationResult`
- `MigrationResult`: `applied_files`, `skipped`, `test_result`, `success`
- 10+ tests in `tests/unit/test_q74/test_migration_agent.py`

---

### 494. GitHub Issues auto-agent trigger

**Files:** `src/lidco/integrations/issue_trigger.py` (new)

**Acceptance criteria:**
- `IssueTrigger.poll() -> list[Issue]` — returns newly assigned issues since last poll
- `Issue`: `number`, `title`, `body`, `url`, `labels`
- `IssueTrigger.create_branch(issue) -> str` — creates `lidco/issue-{number}` branch
- `IssueTrigger.on_issue` callback for wiring to agent execution
- 8+ tests in `tests/unit/test_q74/test_issue_trigger.py`

---

### 495. HTTP-backed slash commands

**Files:** `src/lidco/cli/http_commands.py` (new)

**Acceptance criteria:**
- `HTTPSlashCommand`: `name`, `url`, `method="POST"`, `timeout=30`, `headers: dict`
- `HTTPSlashCommand.execute(args: str) -> str`
- Registration via `.lidco/http_commands.yaml`
- Auto-loaded at startup
- 8+ tests in `tests/unit/test_q74/test_http_commands.py`

---

### 496. Mid-execution plan modification

**Files:** `src/lidco/flows/engine.py` (extend)

**Acceptance criteria:**
- `FlowEngine.inject_instruction(instruction: str) -> bool`
- Between each step, pending instructions are applied to remaining step descriptions
- `FlowEngine.pending_instructions: list[str]` property
- 6+ tests in `tests/unit/test_q74/test_mid_plan.py`

---

## Q75 — Session Diff + Agent Teams Mailbox + Chat Mode

**Goal:** Quality-of-life and architectural polish: session-wide diff review, Claude Code-style agent teams peer mailbox, memory staleness, brainstorm sub-agent.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 497 | [/review-changes — session-wide unified diff](#497-session-diff) | ✅ Done | 1d | Zed parity |
| 498 | [Agent teams peer-to-peer mailbox](#498-mailbox) | ✅ Done | 2d | Claude Code Agent Teams parity |
| 499 | [Memory staleness decay](#499-staleness) | ✅ Done | 1d | Claude Code memory timestamps parity |
| 500 | [Brainstorm sub-agent before planning](#500-brainstorm) | ✅ Done | 2d | GitHub Copilot Workspace parity |
| 501 | [Chat vs. Agent mode distinction](#501-modes) | ✅ Done | 1d | Continue.dev parity |

---

### 497. /review-changes — session-wide unified diff

**Files:** `src/lidco/review/session_diff.py` (new)

**Acceptance criteria:**
- `SessionDiffCollector.collect(project_dir, since_ref) -> SessionDiff`
- `SessionDiff`: `files: list[FileDiff]`, `total_additions: int`, `total_deletions: int`
- `FileDiff`: `path`, `diff`, `additions`, `deletions`
- Uses `git diff <since_ref>`; falls back to in-memory change log
- 8+ tests in `tests/unit/test_q75/test_session_diff.py`

---

### 498. Agent teams peer-to-peer mailbox

**Files:** `src/lidco/agents/mailbox.py` (new)

**Acceptance criteria:**
- `AgentMailbox`: thread-safe in-memory message queue per agent name
- `AgentMailbox.send(to, from_, message) -> None`
- `AgentMailbox.receive(agent_name, timeout=0) -> list[MailMessage]`
- `MailMessage`: `from_`, `to`, `message`, `timestamp`
- `AgentMailbox.broadcast(from_, message, recipients) -> None`
- 8+ tests in `tests/unit/test_q75/test_mailbox.py`

---

### 499. Memory staleness decay

**Files:** `src/lidco/memory/staleness.py` (new)

**Acceptance criteria:**
- `staleness_score(memory: AgentMemory) -> float` — `age_days / (1 + use_count)`
- `StalenessRanker.rank(memories: list[AgentMemory]) -> list[AgentMemory]` — sort by freshness desc
- `StalenessRanker.expire(memories, ttl_days) -> list[AgentMemory]` — filter out stale
- 6+ tests in `tests/unit/test_q75/test_memory_staleness.py`

---

### 500. Brainstorm sub-agent before planning

**Files:** `src/lidco/agents/brainstorm.py` (new)

**Acceptance criteria:**
- `BrainstormAgent.brainstorm(goal, context) -> BrainstormResult`
- `BrainstormResult`: `alternatives: list[str]`, `risks: list[str]`, `clarifying_questions: list[str]`, `recommended_approach: str`
- LLM call with `max_tokens=800`, `temperature=0.7`
- `agents.brainstorm_before_plan: bool = False` config flag
- 8+ tests in `tests/unit/test_q75/test_brainstorm.py`

---

### 501. Chat vs. Agent mode distinction

**Files:** `src/lidco/cli/mode.py` (new)

**Acceptance criteria:**
- `InteractionMode` enum: `CHAT`, `AGENT`
- `ModeController.set_mode(mode)`, `ModeController.current_mode`
- In CHAT mode: message goes directly to LLM, no tool calls, no graph pipeline
- In AGENT mode: full current pipeline
- `/chat` and `/agent` commands; mode shown in status bar
- 6+ tests in `tests/unit/test_q75/test_mode.py`

---

## Q76 — Code Intelligence and Context (T502–T506)

**Goal:** Give the agent deep, always-fresh codebase awareness so every LLM call has optimal context. Closes Aider, Jules, Cursor, and Continue.dev gaps.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 502 | [Ranked Repo-Map (PageRank over import graph)](#502-repo-map) | ✅ Done | 2d | Aider parity |
| 503 | [Watch Mode v2 — AI! / AI? inline comments](#503-ai-comments) | ✅ Done | 1d | Aider parity |
| 504 | [Session Auto-Seeding from Memory](#504-session-seeder) | ✅ Done | 1d | Jules parity |
| 505 | [Multi-Source Event Triggers (Sentry/Snyk/Slack/PagerDuty)](#505-event-triggers) | ✅ Done | 2d | Cursor Automations parity |
| 506 | [AI Contribution Metrics](#506-ai-contribution) | ✅ Done | 1d | Continue.dev parity |

---

### 502. Ranked Repo-Map

**Files:** src/lidco/context/repo_map.py (new)

**Acceptance criteria:**
- RepoMap(project_dir, token_budget=4096), RepoMapEntry(file, symbols, rank, token_estimate)
- build_import_graph() — ast-based, stdlib only
- compute_ranks(graph) — PageRank damping=0.85, max 50 iterations
- generate(changed_files, token_budget) — changed files get 2x rank boost
- ranked_entries() sorted by rank desc; format_for_prompt() truncated to token_budget
- 12+ tests in tests/unit/test_q76/test_repo_map.py

---

### 503. Watch Mode v2 — AI Comments

**Files:** src/lidco/watch/ai_comments.py (new)

**Acceptance criteria:**
- AIComment(file_path, line_number, instruction, mode, context_lines) — mode: execute or ask
- AICommentScanner with scan_file(), scan_directory(), remove_comments(), integrate_with_watcher()
- Pattern "# AI!" triggers execute; "# AI?" triggers ask
- 10+ tests in tests/unit/test_q76/test_ai_comments.py

---

### 504. Session Auto-Seeding from Memory

**Files:** src/lidco/memory/session_seeder.py (new)

**Acceptance criteria:**
- SeedContext(memories, prompt_block, token_estimate, source) — source: workspace, global, or both
- SessionSeeder(memory_store, token_budget=2048, tags_filter) with seed(), format_memories(), should_seed()
- Workspace memories ranked above global
- 8+ tests in tests/unit/test_q76/test_session_seeder.py

---

### 505. Multi-Source Event Triggers

**Files:** src/lidco/integrations/event_triggers.py (new)

**Acceptance criteria:**
- TriggerEvent(source, event_type, title, body, metadata, received_at, priority)
- TriggerAction(event, action, instruction) — action: start_session, start_flow, or notify
- EventTriggerRouter with register_source(), parse_event(), route(), add_rule()
- Built-in parsers: parse_sentry(), parse_snyk(), parse_slack(), parse_pagerduty()
- Default routing: critical/high to start_session; medium to start_flow; low to notify
- 10+ tests in tests/unit/test_q76/test_event_triggers.py

---

### 506. AI Contribution Metrics

**Files:** src/lidco/analytics/ai_contribution.py (new)

**Acceptance criteria:**
- ContributionRecord(file, lines_added, lines_removed, author, session_id, timestamp)
- ModuleMetrics(file, ai_lines, human_lines, ai_ratio)
- AIContributionTracker(db_path) with record(), module_metrics(), session_summary(), all_modules(), dashboard_data()
- SQLite-backed; ai_ratio = ai_lines / total, 0.0 if zero
- 8+ tests in tests/unit/test_q76/test_ai_contribution.py

---

## Q77 — Autonomous Pipelines (T507–T511)

**Goal:** Enable LIDCO to work unattended — from issue to PR, on a schedule, with standards enforcement.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 507 | [Issue-to-PR Autonomous Pipeline](#507-issue-to-pr) | ✅ Done | 2d | Copilot/Devin parity |
| 508 | [Scheduled Recurring Sessions (CronRunner)](#508-cron-runner) | ✅ Done | 2d | Devin parity |
| 509 | [Standards-as-Code Enforcement](#509-standards) | ✅ Done | 2d | Continue.dev parity |
| 510 | [AI Authorship Attribution](#510-ai-attribution) | ✅ Done | 1d | Continue.dev parity |
| 511 | [Arena / Comparison Mode](#511-arena) | ✅ Done | 1d | Windsurf parity |

---

### 507. Issue-to-PR Autonomous Pipeline

**Files:** src/lidco/pipelines/issue_to_pr.py (new)

**Acceptance criteria:**
- PipelineConfig(project_dir, assignee, label, test_cmd, auto_merge, require_security_gate, max_retries)
- PipelineResult(issue_number, branch, pr_number, status, security_passed, self_review_passed, error, steps_completed)
- IssueToPRPipeline with run(), run_step_branch(), run_step_fix(), run_step_security(), run_step_review(), run_step_pr(), poll_and_run()
- Wires IssueTrigger + ShadowWorkspace + AutofixAgent + SecurityGate + SelfReviewer + GHPoster
- status="blocked" if security gate fails; max_retries retries on fix failure
- 12+ tests in tests/unit/test_q77/test_issue_to_pr.py

---

### 508. Scheduled Recurring Sessions (CronRunner)

**Files:** src/lidco/scheduler/cron_runner.py (new)

**Acceptance criteria:**
- ScheduledTask(name, cron_expr, instruction, enabled, last_run, run_count)
- RunResult(task_name, started_at, finished_at, success, output, error)
- CronRunner(state_path) with add_task(), remove_task(), list_tasks(), is_due(), tick(), save_state(), load_state()
- Simplified 5-field cron: integers and wildcard only; JSON state at .lidco/scheduler.json
- 10+ tests in tests/unit/test_q77/test_cron_runner.py

---

### 509. Standards-as-Code Enforcement

**Files:** src/lidco/review/standards.py (new)

**Acceptance criteria:**
- StandardRule(id, name, description, pattern, severity, file_glob, fix_hint)
- Violation(rule_id, file, line, message, severity, fix_hint), CheckResult(passed, violations, rules_checked)
- StandardsEnforcer(rules_path) with load_rules(), add_rule(), check_file(), check_diff(), rules(), default_rules()
- YAML rules file; try import yaml with JSON fallback; passed=True only if zero error violations
- 10+ tests in tests/unit/test_q77/test_standards.py

---

### 510. AI Authorship Attribution

**Files:** src/lidco/analytics/ai_attribution.py (new)

**Acceptance criteria:**
- LineAttribution(file, line, author, session_id, timestamp, model)
- AIAttributionStore(db_path) with record_edit(), get_file_attribution(), ai_ratio(), session_attribution(), reconcile_with_diff(), clear_file()
- SQLite-backed; reconcile_with_diff shifts line numbers after edits
- 8+ tests in tests/unit/test_q77/test_ai_attribution.py

---

### 511. Arena / Comparison Mode

**Files:** src/lidco/agents/arena.py (new)

**Acceptance criteria:**
- ArenaEntry(model, output, duration, token_count, score), ArenaResult(task, entries, winner, selection_method)
- ArenaMode(models) with run(), select_winner(), auto_select(), format_comparison(), history(), win_rates()
- select_winner returns new ArenaResult (immutable); win_rates computed from history
- 8+ tests in tests/unit/test_q77/test_arena.py

---

## Q78 — Developer Experience and Tooling (T512–T516)

**Goal:** Polish DX — IaC scaffolding, swappable prediction backends, and wiring all Q76-Q77 modules into the CLI.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 512 | [Swappable Edit-Prediction Backend (Ollama/remote)](#512-prediction-backend) | ✅ Done | 1d | Zed parity |
| 513 | [IaC Scaffolding (Terraform / Docker)](#513-iac) | ✅ Done | 2d | Amazon Q parity |
| 514 | [Repo-Map Context Injector](#514-repo-map-injector) | ✅ Done | 1d | wires T502+T504 into LLM calls |
| 515 | [Pipeline CLI Commands (/pipeline, /schedule)](#515-pipeline-cmds) | ✅ Done | 1d | wires T507+T508 into CLI |
| 516 | [Standards Slash Command + Hook (/standards)](#516-standards-cmds) | ✅ Done | 1d | wires T509 into commit flow |

---

### 512. Swappable Edit-Prediction Backend

**Files:** src/lidco/prediction/backend.py (new)

**Acceptance criteria:**
- PredictionBackendConfig(backend, ollama_model, ollama_url, remote_model, timeout)
- PredictionBackend(config) with predict(), switch_backend(), active_backend property, call_ollama(), create_llm_fn()
- Ollama via urllib.request (stdlib); disabled backend returns empty string
- switch_backend replaces config immutably
- 10+ tests in tests/unit/test_q78/test_prediction_backend.py

---

### 513. IaC Scaffolding

**Files:** src/lidco/scaffold/iac.py (new)

**Acceptance criteria:**
- ScaffoldResult(files, description, template_used)
- IaCScaffolder(llm_fn) with generate_dockerfile(), generate_compose(), generate_terraform(), generate_from_description()
- Static methods: dockerfile_template(), compose_template(), terraform_template()
- Languages: python, node, go, rust, java; providers: aws, gcp, azure
- generate_from_description uses llm_fn if available, else keyword fallback
- 10+ tests in tests/unit/test_q78/test_iac.py

---

### 514. Repo-Map Context Injector

**Files:** src/lidco/context/repo_map_injector.py (new)

**Acceptance criteria:**
- RepoMapInjector(repo_map, session_seeder, enabled) with inject(), toggle(), build_context_block(), estimate_tokens()
- inject() prepends repo-map to first system message; inserts system message if absent
- Returns NEW messages list (immutable); disabled returns messages unchanged
- 8+ tests in tests/unit/test_q78/test_repo_map_injector.py

---

### 515. Pipeline CLI Commands

**Files:** src/lidco/cli/commands/pipeline_cmds.py (new)

**Acceptance criteria:**
- Commands: /pipeline run, /pipeline status, /schedule add, /schedule remove, /schedule list, /schedule tick
- register_pipeline_commands(registry) follows pattern in src/lidco/cli/commands/registry.py
- All handlers return human-readable strings
- 8+ tests in tests/unit/test_q78/test_pipeline_cmds.py

---

### 516. Standards Slash Command + Hook

**Files:** src/lidco/cli/commands/standards_cmds.py (new)

**Acceptance criteria:**
- Commands: /standards check, /standards rules, /standards add, /standards init
- pre_commit_check(project_dir) for git hook integration
- standards check reads staged files via git diff --cached --name-only
- standards init writes .lidco/standards.yaml with default_rules()
- 6+ tests in tests/unit/test_q78/test_standards_cmds.py

---

## Q79 — Watch Mode 3.0 + Architect Mode + Context Inspector (T517–T521)

**Goal:** Zero-friction AI interaction (Aider parity), dual-model efficiency (Aider Architect parity), and full context transparency (Zed AI parity).

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 517 | [Watch Mode 3.0 — AI! / AI? file-embedded triggers (full agent)](#517-watch-agent) | ✅ Done | 1d | Aider parity |
| 518 | [Architect Mode — dual-model plan+execute wiring](#518-architect-mode) | ✅ Done | 1d | Aider parity |
| 519 | [Context Inspector — transparent LLM request viewer](#519-context-inspector) | ✅ Done | 1d | Zed AI parity |
| 520 | [Per-Agent Persistent Memory (cross-session)](#520-agent-memory-scope) | ✅ Done | 1d | Claude Code parity |
| 521 | [PR Review Agent with GitHub Comment Threading](#521-pr-review-agent) | ✅ Done | 2d | Copilot parity |

---

### 517. Watch Mode 3.0 — AI! / AI? File-Embedded Triggers

**Files:** src/lidco/watch/agent_trigger.py (new)

**Acceptance criteria:**
- WatchAgentTrigger(project_dir, agent_fn, patterns) with start(), stop(), scan_file(), collect_all_comments(), process()
- scan_file(path) returns list of AIComment where each has file_path, line_number, instruction, mode ("execute" or "ask")
- Patterns: # AI!, # AI?, // AI!, // AI?, -- AI!, -- AI?
- process() calls agent_fn(task_str) then removes AI! comments from files; AI? appends answer as comment block
- collect_all_comments(changed_files) aggregates comments across all changed files into single task string
- 10+ tests in tests/unit/test_q79/test_watch_agent.py

---

### 518. Architect Mode — Dual-Model Plan + Execute

**Files:** src/lidco/llm/architect_mode.py (new)

**Acceptance criteria:**
- FileChangeSpec(file, action, description) and ArchitectPlan(rationale, file_changes)
- EditResult(file, success, content, error)
- ArchitectSession(architect_fn, editor_fn) with plan(task) -> ArchitectPlan, execute(plan) -> list[EditResult], run(task) -> list[EditResult]
- plan() calls architect_fn with task; parses JSON response into ArchitectPlan (fallback: treat as single-file task)
- execute() calls editor_fn per FileChangeSpec; returns EditResult per file
- 10+ tests in tests/unit/test_q79/test_architect_mode.py

---

### 519. Context Inspector

**Files:** src/lidco/context/inspector.py (new)

**Acceptance criteria:**
- ContextSection(name, content, token_estimate, source) — source: "system", "memory", "rules", "history", "tools"
- ContextSnapshot(sections, total_tokens, model_limit, session_id, timestamp)
- ContextInspector(session) with snapshot() -> ContextSnapshot, format_summary() -> str, drop(section_name) -> bool, pin(text, label) -> None, pinned_sections() -> list[ContextSection]
- snapshot() estimates tokens as len(content)//4 per section
- format_summary() returns human-readable breakdown with token counts and percentages
- 8+ tests in tests/unit/test_q79/test_context_inspector.py

---

### 520. Per-Agent Persistent Memory (cross-session)

**Files:** src/lidco/memory/agent_scope.py (new)

**Acceptance criteria:**
- AgentMemoryScope(agent_name, project_dir, global_dir) with load() -> str, save(content), append(entry), clear()
- Scope resolution: project .lidco/agent-memory/<name>/MEMORY.md overrides global ~/.lidco/agent-memory/<name>/MEMORY.md
- load() reads project-scope first; falls back to global; returns "" if neither exists
- save() writes to project-scope by default; global_dir scope when project_dir is None
- append(entry) adds a timestamped entry to the end (max 200 lines, trims oldest)
- 8+ tests in tests/unit/test_q79/test_agent_scope.py

---

### 521. PR Review Agent with GitHub Comment Threading

**Files:** src/lidco/review/pr_reviewer_v2.py (new)

**Acceptance criteria:**
- ReviewComment(path, line, severity, body, suggestion) — severity: "critical", "warning", or "suggestion"
- PRReviewResult(pr_number, summary, comments, verdict) — verdict: "approve", "request_changes", or "comment"
- PRReviewAgentV2(llm_fn, gh_token) with review(repo, pr_number) -> PRReviewResult, post_review(repo, pr_number, result) -> bool, format_review(result) -> str
- review() fetches diff via GitHub API (or mock), runs llm_fn on diff, parses structured response
- format_review() formats as Markdown with severity badges
- post_review() POSTs to GitHub pulls review API; returns True on success, False on error
- 10+ tests in tests/unit/test_q79/test_pr_reviewer_v2.py

---

## Q80 — @-Mention Providers + Event Automations + Arena Leaderboard (T522–T526)

**Goal:** Turn LIDCO into a platform — external context on demand, event-driven autonomous work, empirical model selection.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 522 | [@-Mention External Context Providers](#522-at-mention-providers) | ✅ Done | 2d | Continue.dev parity |
| 523 | [Event Automation YAML Engine](#523-automation-engine) | ✅ Done | 2d | Cursor Automations parity |
| 524 | [Arena Leaderboard + Adaptive Model Routing](#524-arena-leaderboard) | ✅ Done | 1d | Windsurf parity |
| 525 | [Next-Edit Ripple Propagation (post-edit analysis)](#525-ripple-propagation) | ✅ Done | 2d | Copilot NES parity |
| 526 | [Container Sandbox (Docker-backed isolation)](#526-container-sandbox) | ✅ Done | 2d | Devin/Jules parity |

---

### 522. @-Mention External Context Providers

**Files:** src/lidco/context/at_mention.py (new)

**Acceptance criteria:**
- AtMentionProvider(name, pattern, fetch_fn) — pattern is a regex matching @name identifier
- AtMentionResult(provider, identifier, content, token_estimate, error)
- AtMentionParser(providers) with parse(text) -> list[AtMentionResult], resolve(text) -> tuple[str, list[AtMentionResult]]
- Built-in providers: AtGitHubIssue (pattern @gh-issue NUMBER), AtURL (pattern @url URL), AtFile (pattern @file PATH), AtShell (pattern @shell COMMAND)
- resolve() returns (text_with_mentions_removed, resolved_results)
- 10+ tests in tests/unit/test_q80/test_at_mention.py

---

### 523. Event Automation YAML Engine

**Files:** src/lidco/scheduler/automation_engine.py (new)

**Acceptance criteria:**
- AutomationRule(name, trigger_type, trigger_config, task_template, output_type, enabled) — output_type: "pr", "comment", "message", or "log"
- AutomationResult(rule_name, triggered_at, task, output, success, error)
- AutomationEngine(rules_path, agent_fn) with load_rules() -> list[AutomationRule], evaluate(event) -> list[AutomationRule], run_rule(rule, event) -> AutomationResult, tick() -> list[AutomationResult]
- Trigger types: "cron", "github_issue", "github_pr", "webhook"
- task_template supports {event.title}, {event.body}, {event.number} placeholders
- YAML rules file at .lidco/automations.yaml
- 10+ tests in tests/unit/test_q80/test_automation_engine.py

---

### 524. Arena Leaderboard + Adaptive Model Routing

**Files:** src/lidco/agents/arena_leaderboard.py (new)

**Acceptance criteria:**
- VoteRecord(model_a, model_b, winner, task_type, prompt_hash, timestamp)
- ModelStats(model, wins, appearances, win_rate, task_type)
- ArenaLeaderboard(db_path) with record_vote(vote) -> None, stats(task_type) -> list[ModelStats], best_model(task_type) -> str or None, leaderboard() -> list[ModelStats], suggest_models(task_type) -> tuple[str,str]
- SQLite-backed; win_rate = wins/appearances; best_model returns None if fewer than 3 appearances
- suggest_models returns top-2 by win_rate for the task_type (or DEFAULT_MODELS if insufficient data)
- 8+ tests in tests/unit/test_q80/test_arena_leaderboard.py

---

### 525. Next-Edit Ripple Propagation

**Files:** src/lidco/prediction/ripple.py (new)

**Acceptance criteria:**
- RippleEdit(file, line, original, suggested, reason, symbol)
- RippleSuggestion(source_file, source_change, edits)
- RippleAnalyzer(edit_graph, llm_fn) with analyze(diff_text) -> list[RippleSuggestion], extract_changed_symbols(diff) -> list[str], find_references(symbol) -> list[tuple[str,int]], suggest_edit(file, line, symbol, context) -> RippleEdit
- extract_changed_symbols parses unified diff for +/- lines containing def/function/const/type keywords
- find_references delegates to edit_graph; suggest_edit calls llm_fn or returns stub if None
- 10+ tests in tests/unit/test_q80/test_ripple.py

---

### 526. Container Sandbox (Docker-backed)

**Files:** src/lidco/tools/container_sandbox.py (new)

**Acceptance criteria:**
- ContainerConfig(image, repo_path, env, timeout, network_disabled, memory_limit_mb)
- ContainerResult(exit_code, stdout, stderr, diff, duration)
- ContainerSandbox(config) with run(command) -> ContainerResult, get_diff() -> str, cleanup() -> None
- Uses subprocess to invoke docker run; falls back gracefully if Docker not available
- get_diff() runs git diff inside container against original state; returns unified diff text
- memory_limit_mb maps to --memory docker flag; network_disabled maps to --network none
- 10+ tests in tests/unit/test_q80/test_container_sandbox.py

---

## Q81 — CLI Wiring + DX Polish (T527–T531)

**Goal:** Surface all Q79-Q80 features in the CLI with /watch, /architect, /context, /arena, /auto commands.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 527 | [/watch + /architect CLI commands](#527-watch-architect-cmds) | ✅ Done | 1d | wires T517+T518 |
| 528 | [/context inspect/edit/drop/pin commands](#528-context-cmds) | ✅ Done | 1d | wires T519 |
| 529 | [/arena compare + leaderboard commands](#529-arena-cmds) | ✅ Done | 1d | wires T511+T524 |
| 530 | [/auto (automation engine) commands](#530-auto-cmds) | ✅ Done | 1d | wires T523 |
| 531 | [@-mention input pre-processing in REPL](#531-at-mention-repl) | ✅ Done | 1d | wires T522 into app.py |

---

### 527. /watch and /architect CLI Commands

**Files:** src/lidco/cli/commands/watch_cmds.py (new)

**Acceptance criteria:**
- Commands: /watch start, /watch stop, /watch status
- Commands: /architect <task> — runs ArchitectSession with config-defined architect_model/editor_model
- register_watch_commands(registry) and register_architect_commands(registry)
- /watch start accepts optional --patterns flag
- /architect returns plan summary + list of files changed
- 8+ tests in tests/unit/test_q81/test_watch_cmds.py

---

### 528. /context Commands

**Files:** src/lidco/cli/commands/context_cmds.py (new — note: context_cmds.py may exist, extend or rename)

**Acceptance criteria:**
- Commands: /context inspect, /context drop <section>, /context pin <text>, /context pinned, /context snapshot
- register_context_commands(registry)
- /context inspect returns ContextInspector.format_summary()
- /context snapshot saves to .lidco/context_snapshots/
- All handlers return human-readable strings
- 8+ tests in tests/unit/test_q81/test_context_cmds.py

---

### 529. /arena Commands

**Files:** src/lidco/cli/commands/arena_cmds.py (new)

**Acceptance criteria:**
- Commands: /arena compare <model_a> <model_b> <task>, /arena leaderboard, /arena vote <model>
- register_arena_commands(registry)
- /arena compare runs ArenaMode.run() then displays format_comparison()
- /arena leaderboard shows ArenaLeaderboard.leaderboard() as table
- /arena vote records vote to ArenaLeaderboard for last comparison
- 6+ tests in tests/unit/test_q81/test_arena_cmds.py

---

### 530. /auto (Automation Engine) Commands

**Files:** src/lidco/cli/commands/auto_cmds.py (new)

**Acceptance criteria:**
- Commands: /auto list, /auto run <name>, /auto tick, /auto enable <name>, /auto disable <name>
- register_auto_commands(registry)
- /auto list shows all rules with status and trigger type
- /auto run <name> triggers a specific automation rule immediately
- /auto tick triggers AutomationEngine.tick() and reports results
- 8+ tests in tests/unit/test_q81/test_auto_cmds.py

---

### 531. @-Mention Input Pre-Processing in REPL

**Files:** src/lidco/context/at_mention_middleware.py (new)

**Acceptance criteria:**
- AtMentionMiddleware(parser, max_tokens) with process(user_input) -> ProcessedInput
- ProcessedInput(clean_text, injected_context, total_tokens, errors)
- process() calls AtMentionParser.resolve(); injects resolved content as ContextSection items
- Respects max_tokens: drops lowest-priority mentions if budget exceeded
- Error-tolerant: failed fetches logged in errors, not raised
- 8+ tests in tests/unit/test_q81/test_at_mention_middleware.py

---

## Q82 — Code Transformation & Generation (T532–T536)

**Goal:** Add symbol rename, atomic multi-file edits, AI test generation, and project health reporting.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 532 | [Cross-file symbol rename](#532-symbol-rename) | ✅ Done | 1d | safer refactoring |
| 533 | [Multi-file atomic edit transactions](#533-multi-edit) | ✅ Done | 1d | coordinated edits |
| 534 | [AI test generator](#534-test-gen) | ✅ Done | 1d | TDD support |
| 535 | [Project health dashboard](#535-health-dashboard) | ✅ Done | 1d | code quality metrics |
| 536 | [CLI wiring: /rename /multi-edit /testgen /health](#536-transform-cmds) | ✅ Done | 0.5d | exposes T532–T535 |

---

### 532. Cross-file Symbol Rename

**Files:** src/lidco/refactor/__init__.py (new), src/lidco/refactor/symbol_rename.py (new)

**Acceptance criteria:**
- SymbolRenamer(root) with find_occurrences(name) and rename(old, new, dry_run=False)
- RenameResult(old_name, new_name, files_changed, occurrences, preview, errors)
- Whole-word regex matching (\b boundaries)
- dry_run=True computes changes without writing
- Skips .git, __pycache__, .venv dirs
- 8+ tests in tests/unit/test_q82/test_symbol_rename.py

---

### 533. Multi-file Atomic Edit Transactions

**Files:** src/lidco/editing/multi_edit.py (new)

**Acceptance criteria:**
- MultiEditTransaction with add_edit(), validate(), apply(), rollback()
- TransactionResult(applied, failed, errors, success)
- validate() returns errors without writing files
- rollback() restores all previously written files
- 8+ tests in tests/unit/test_q82/test_multi_edit.py

---

### 534. AI Test Generator

**Files:** src/lidco/scaffold/test_gen.py (new)

**Acceptance criteria:**
- TestGenerator(llm_client=None) with generate_for_module(path) and write_test_file(code, path)
- GeneratedTests(source_path, test_code, functions_covered, error)
- FunctionSignature extraction via AST (no exec/eval)
- Skips private functions (starting with _)
- async generate_async() falls back to AST if llm_client is None
- 8+ tests in tests/unit/test_q82/test_test_gen.py

---

### 535. Project Health Dashboard

**Files:** src/lidco/analytics/health_dashboard.py (new)

**Acceptance criteria:**
- ProjectHealthDashboard(root=".") with collect() -> HealthReport
- HealthReport(source_files, test_files, test_count, total_lines, avg_file_lines, large_files, score)
- score is 0.0-1.0 composite (test ratio 40%, large file ratio 30%, avg size 30%)
- format_table() returns human-readable string
- 8+ tests in tests/unit/test_q82/test_health_dashboard.py

---

### 536. CLI Wiring: /rename, /multi-edit, /testgen, /health

**Files:** src/lidco/cli/commands/transform_cmds.py (new)

**Acceptance criteria:**
- register_transform_commands(registry)
- /rename <old> <new> [--dry-run] — wraps SymbolRenamer
- /multi-edit <spec.yaml> — validates then applies MultiEditTransaction
- /testgen <path> [--write] — wraps TestGenerator
- /health — shows ProjectHealthDashboard report
- 8+ tests in tests/unit/test_q82/test_transform_cmds.py

---

## Q83 — Deep Intelligence & Autonomous Loops (T542–T546)

**Goal:** Add DeepWiki-style codebase indexing, interactive plan validation, auto-lint/test fix loop, and parallel worktree agents — achieving competitive parity with Cursor, Devin 2.0, Aider, and Claude Code.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 542 | [DeepWiki-style codebase indexer](#542-codebase-indexer) | ✅ Done | 1d | Devin DeepWiki parity |
| 543 | [Interactive plan validation loop](#543-plan-validator) | ✅ Done | 1d | Devin 2.0 parity |
| 544 | [Auto-lint + auto-test fix loop](#544-auto-fixer) | ✅ Done | 1d | Aider parity |
| 545 | [Worktree-isolated parallel agents](#545-worktree-runner) | ✅ Done | 1d | Cursor/Claude Code parity |
| 546 | [CLI wiring: /index /plan-validate /autofix /parallel](#546-intelligence-cmds) | ✅ Done | 0.5d | exposes T542–T545 |

## Q84 — Session Intelligence & Continuous Learning (T552–T556)

**Goal:** Windsurf Cascade Memory + GitHub Copilot Code Review + Devin 2.0 Worker Teams parity.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 552 | [Coding pattern extractor from session](#552-pattern-extractor) | ✅ Done | 1d | Windsurf Cascade Memory parity |
| 553 | [PR review suggestion auto-applier](#553-suggestion-applier) | ✅ Done | 1d | GitHub Copilot Code Review parity |
| 554 | [Async worker pool for sub-agents](#554-worker-pool) | ✅ Done | 1d | Devin 2.0 worker teams parity |
| 555 | [Session learning & context pinning](#555-session-pinner) | ✅ Done | 1d | Windsurf 48h learning parity |
| 556 | [CLI: /patterns /apply-review /workers /pin-session](#556-learning-cmds) | ✅ Done | 0.5d | exposes T552–T555 |

## Q85 — Enterprise Platform & IDE Integration (T557–T561)

**Goal:** Self-healing CI (Windsurf/Dagger parity) + Webhook automation (Cursor Automations parity) + Knowledge triggers (Devin 2.0 parity) + MCP Task Server for IDE integration.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 557 | [CI pipeline healer](#557-ci-healer) | ✅ Done | 1d | Windsurf/Dagger self-healing CI parity |
| 558 | [Webhook event bus](#558-webhook-bus) | ✅ Done | 1d | Cursor Automations parity |
| 559 | [Knowledge trigger injection](#559-knowledge-trigger) | ✅ Done | 1d | Devin 2.0 Knowledge Base parity |
| 560 | [MCP Task Server](#560-mcp-task-server) | ✅ Done | 1d | MCP Nov-2025 async tasks parity |
| 561 | [CLI: /ci-heal /webhook /knowledge /mcp-serve](#561-platform-cmds) | ✅ Done | 0.5d | exposes T557–T560 |

## Q86 — Smart Code Navigation & Refactoring Intelligence (T562–T566)

**Goal:** JetBrains AI "extract method" + GitHub Copilot "explain/fix" + Sourcegraph Cody "find symbol" parity.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 562 | [Cross-file symbol navigation](#562-code-navigator) | ✅ Done | 1d | Sourcegraph Cody parity |
| 563 | [AI code explainer](#563-code-explainer) | ✅ Done | 1d | GitHub Copilot "explain" parity |
| 564 | [Structural refactoring suggestor](#564-refactor-suggestor) | ✅ Done | 1d | JetBrains AI Assistant parity |
| 565 | [Error explainer + fix suggestions](#565-error-explainer) | ✅ Done | 1d | GitHub Copilot "fix error" parity |
| 566 | [CLI: /navigate /explain /refactor-suggest /fix-error](#566-nav-cmds) | ✅ Done | 0.5d | exposes T562–T565 |

## Q87 — Graph Intelligence & Semantic Search (T567–T571)

**Goal:** AST dependency graph + TF-IDF semantic search + Task DAG + approval engine — CodeCompass/Copilot/Replit parity.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 567 | [AST dependency graph (IMPORTS/CALLS/INHERITS)](#567-dependency-graph) | ✅ Done | 1d | CodeCompass / Augment Code parity |
| 568 | [TF-IDF semantic code search (stdlib)](#568-semantic-search) | ✅ Done | 1d | GitHub Copilot semantic search parity |
| 569 | [Long-horizon Task DAG with checkpoints](#569-task-dag) | ✅ Done | 1d | Replit Agent 3 / Devin parity |
| 570 | [Auto-approve rules engine](#570-approval-engine) | ✅ Done | 1d | GitHub Copilot / Cursor approval parity |
| 571 | [CLI: /graph /search /task-dag /approve-rules](#571-graph-cmds) | ✅ Done | 0.5d | exposes T567–T570 |

## Q88 — Browser Automation & Computer Use (T572–T576)

**Goal:** Playwright browser automation + visual regression testing + Plan/Act mode — Cline/Cursor/OpenHands parity.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 572 | [Playwright browser session](#572-browser-session) | ✅ Done | 1d | Cline/OpenHands computer use parity |
| 573 | [Screenshot visual analyzer](#573-screenshot-analyzer) | ✅ Done | 1d | Cursor cloud agent visual debug parity |
| 574 | [Plan/Act mode controller](#574-plan-act-controller) | ✅ Done | 1d | Cline Plan/Act parity |
| 575 | [Visual regression test runner](#575-visual-test-runner) | ✅ Done | 1d | Cursor visual testing parity |
| 576 | [CLI: /browser /visual-test /plan-act /screenshot-analyze](#576-browser-cmds) | ✅ Done | 0.5d | exposes T572–T575 |

## Q89 — Turbo Mode & Autonomous Execution (T577–T581)

**Goal:** Windsurf Turbo (auto-execute terminal without per-command approval) + Devin 2.0 role-specialized sub-agents + semantic memory search + long-horizon task planner with retry/resume.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 577 | [Turbo command runner (auto-approve allowlist)](#577-turbo-runner) | ✅ Done | 1d | Windsurf Turbo mode parity |
| 578 | [Role-specialized sub-agent factory](#578-role-agents) | ✅ Done | 1d | Devin 2.0 specialized agents parity |
| 579 | [Semantic memory store with priority + TTL](#579-semantic-memory) | ✅ Done | 1d | memory hierarchy improvement |
| 580 | [Long-horizon task planner with retry/resume](#580-horizon-planner) | ✅ Done | 1d | Replit Agent 3 long-horizon parity |
| 581 | [CLI: /turbo /role-agent /mem-search /horizon](#581-turbo-cmds) | ✅ Done | 0.5d | exposes T577–T580 |

---

## Q90 — Competitive Parity Sprint (T582–T586)

**Goal:** Close gaps with Cursor (per-directory `.lidco-rules`, multi-file changeset review), Aider (auto-lint-fix loop), Replit Agent (deployment scaffolding), and Windsurf (cost projection before long runs).

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 582 | [Per-directory AI rules (.lidco-rules)](#582-directory-rules) | ✅ Done | 1d | Cursor .cursorrules parity |
| 583 | [Auto-lint-fix loop](#583-lint-fix-loop) | ✅ Done | 1d | Aider auto-lint parity |
| 584 | [Deployment scaffolder (auto-detect + generate)](#584-deploy-scaffold) | ✅ Done | 1d | Replit Agent deploy parity |
| 585 | [Changeset reviewer (multi-file diff review)](#585-changeset-review) | ✅ Done | 1d | Cursor Composer parity |
| 586 | [Cost projector (estimate before long runs)](#586-cost-projector) | ✅ Done | 1d | Windsurf cost projection parity |

### 582. Directory Rules
**File:** `src/lidco/context/directory_rules.py`
`DirectoryRulesResolver` — walks from edited file up to project root, collects `.lidco-rules` files, merges with nearest-directory-wins priority. `inject_for_context()` deduplicates shared ancestors. mtime-based cache.

### 583. Lint Fix Loop
**File:** `src/lidco/editing/lint_fix_loop.py`
`LintFixLoop` — lint → call fix_fn callback → re-lint → repeat up to max_iterations. Auto-detects linter by extension (ruff/.py, eslint/.js/.ts, golangci-lint/.go). Returns `FixLoopReport` with error delta.

### 584. Deployment Scaffolder
**File:** `src/lidco/scaffold/deploy.py`
`DeploymentScaffolder` — auto-detects language (Python/Node/Go/Rust) and framework (FastAPI/Flask/Django/Express/Next.js/Gin) from marker files. Generates: Dockerfile, `.github/workflows/ci.yml`, `fly.toml`, `.env.example`.

### 585. Changeset Reviewer
**File:** `src/lidco/editing/changeset_review.py`
`ChangesetReviewer` — collects `{path: (old, new)}` into a `Changeset` with unified diffs, per-file stats. `format_summary()` / `format_full()`. `apply()` with `ChangesetDecision` (per-file and per-hunk accept/reject).

### 586. Cost Projector
**File:** `src/lidco/ai/cost_projector.py`
`CostProjector` — heuristic token estimation per step (base + context_files + output_lines). Uses pricing table (gpt-4o, claude-sonnet/opus/haiku). Historical calibration via `record_actual()`. `format_summary()` returns one-liner with confidence label (low/medium/high).

---

## Q91 — Session History, Smart Apply, Context Exclude, Memory Consolidation, Custom Plugins (T587–T591)

**Goal:** Cursor session history panel + smart code block apply + .lidcoignore exclusions (Aider) + memory consolidation (Windsurf) + custom tool plugin loader (Continue.dev/Cline).

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 587 | [Session history store (list/search/resume)](#587-session-history) | ✅ Done | 1d | Cursor chat history parity |
| 588 | [Smart code block apply (detect target + apply)](#588-smart-apply) | ✅ Done | 1d | Cursor "Apply in editor" parity |
| 589 | [.lidcoignore context exclude file](#589-exclude-file) | ✅ Done | 0.5d | Aider .aiderignore parity |
| 590 | [Memory consolidator (merge similar/stale)](#590-consolidator) | ✅ Done | 1d | Windsurf memory consolidation parity |
| 591 | [Custom tool plugin loader (.lidco/tools/*.py)](#591-plugin-loader) | ✅ Done | 1d | Continue.dev/Cline plugin parity |

### 587. Session History Store
**File:** `src/lidco/memory/session_history.py`
`SessionHistoryStore` — SQLite-backed session records. `save()`, `list()` (newest-first, paginated), `search()` (LIKE across topic/summary/tags), `resume_context()` (formatted for system prompt), `auto_topic()` (first 10 words of first user message). CLI: `/session-history [query]`.

### 588. Smart Code Apply
**File:** `src/lidco/editing/smart_apply.py`
`SmartApply` — parses triple-backtick fenced blocks from LLM text, detects language from fence info or content heuristics, finds target file by 3 signals (fence path=1.0, function match=0.6, extension=0.3), applies with dry-run support and path-traversal protection. CLI: `/smart-apply [--dry-run]`.

### 589. Context Exclude File
**File:** `src/lidco/context/exclude_file.py`
`ContextExcludeFile` — reads `.lidcoignore` (fallback `.lidco/ignore`), gitignore syntax (`*`, `**`, `!` negation, `#` comments, dir `/`). mtime cache. `filter_paths()` for bulk exclusion. `add_pattern()` / `remove_pattern()`. CLI: `/ignore [add|remove|list] [pattern]`.

### 590. Memory Consolidator
**File:** `src/lidco/memory/consolidator.py`
`MemoryConsolidator` — TF-IDF cosine similarity clustering, configurable threshold/TTL/max-group-size. `find_similar_groups()` (exempts use_count > 10), `merge_group()` (unique lines + union tags + earliest timestamp), `consolidate()` + `dry_run()`. CLI: `/mem-compact [--dry-run]`.

### 591. Custom Tool Plugin Loader
**File:** `src/lidco/tools/plugin_loader.py`
`ToolPluginLoader` — discovers `.lidco/tools/*.py` (project overrides global). AST-only validation (blocks `eval`/`exec`/`os.system`). Dynamic load via `importlib.util`. `load_all()` isolates failures. `get_tool_from_plugin()` instantiates first BaseTool subclass. CLI: `/plugins [list|reload]`.

---

## Q92 — Prompt Library, Terminal Capture, Export & Team Sync (T592–T596)

**Goal:** Cursor Prompt Files parity (reusable prompt templates), Devin terminal capture, session export to HTML/Markdown, team-shared `.lidco/team.yaml` config, and manual `/hot-reload` command.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 592 | [Prompt template library (.lidco/prompts/)](#592-prompt-library) | ✅ Done | 1d | Cursor Prompt Files / Continue.dev parity |
| 593 | [Live terminal output capture](#593-terminal-capture) | ✅ Done | 1d | Devin 2.0 terminal context parity |
| 594 | [Session/report exporter (HTML + Markdown)](#594-session-exporter) | ✅ Done | 1d | Cursor export / doc parity |
| 595 | [Team configuration loader (.lidco/team.yaml)](#595-team-config) | ✅ Done | 1d | Cursor Teams / shared config parity |
| 596 | [CLI: /prompt /export /team /hot-reload](#596-q92-cmds) | ✅ Done | 0.5d | exposes T592–T595 |

### 592. Prompt Template Library
**File:** `src/lidco/prompts/library.py`
`PromptTemplateLibrary` — discovers `.lidco/prompts/*.md` (project) + `~/.lidco/prompts/*.md` (global). Project overrides global by name. `{{var}}` interpolation via regex replace. `list()` returns all templates, `load(name)` returns `PromptTemplate`, `render(name, variables)` returns `RenderResult` with `missing_vars`, `save(name, content)` writes to project dir.

### 593. Terminal Capture
**File:** `src/lidco/execution/terminal_capture.py`
`TerminalCapture` — runs subprocess with timeout, captures stdout+stderr. `CaptureResult(command, stdout, stderr, returncode, elapsed_s)`. `run(command, timeout)` returns CaptureResult. `format_for_context(result)` formats for LLM injection. `run_and_format(command)` convenience wrapper. Max output truncated at `max_output_bytes`.

### 594. Session Exporter
**File:** `src/lidco/export/session_exporter.py`
`SessionExporter` — exports conversation `list[dict]` to Markdown or HTML. `ExportConfig(format, include_metadata, max_messages)`. `export(messages, config)` returns `ExportResult(content, format, message_count)`. `export_markdown()` / `export_html()` lower-level methods. `save(result, path)` writes to disk.

### 595. Team Config Loader
**File:** `src/lidco/config/team_config.py`
`TeamConfigLoader` — loads `.lidco/team.yaml` (project-shared, in git) + `.lidco/user.yaml` (personal, gitignored). `TeamConfig(model, tools, rules, permissions, members)` dataclass. `load_team()`, `load_personal()`, `merge(team, personal)` → `MergedConfig`. `validate(config)` returns list of error strings.

### 596. CLI: /prompt /export /team /hot-reload
**File:** `src/lidco/cli/commands/q92_cmds.py`
`register_q92_commands(registry)` — wires 4 commands:
- `/prompt list|run <name> [key=val ...]|save <name> <content>` → PromptTemplateLibrary
- `/export [html|md] [path]` → SessionExporter
- `/team show|validate` → TeamConfigLoader
- `/hot-reload` → reloads LidcoConfig from disk

---

## Q93 — Playbooks, Test Impact & AI Git Intelligence (T597–T601)

**Goal:** Devin Playbooks parity (reusable multi-step YAML workflows), Nx/Turborepo-style test-impact analysis (run only affected tests), CodeSee AI Git Blame (LLM-enhanced history), and GitHub Copilot-style PR description generation.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 597 | [Playbook Engine (.lidco/playbooks/*.yaml)](#597-playbook-engine) | ✅ Done | 1d | Devin Playbooks parity |
| 598 | [Test Impact Analyzer](#598-test-impact) | ✅ Done | 1d | Nx/Turborepo parity — run only affected tests |
| 599 | [AI Git Blame](#599-ai-blame) | ✅ Done | 1d | CodeSee parity — LLM-enhanced history |
| 600 | [PR Description Generator](#600-pr-desc) | ✅ Done | 1d | GitHub Copilot PR parity |
| 601 | [CLI: /playbook /test-impact /ai-blame /pr-desc](#601-q93-cmds) | ✅ Done | 0.5d | exposes T597–T600 |

### 597. Playbook Engine
**File:** `src/lidco/playbooks/engine.py`
`PlaybookEngine` — discovers `.lidco/playbooks/*.yaml` (project) + `~/.lidco/playbooks/*.yaml` (global). Project overrides global by name. Step types: `run` (shell), `prompt` (LLM), `tool` (slash command), `condition` (if/else). `{{var}}` interpolation. `list()`, `load(name)`, `execute(name, variables)` → `PlaybookResult`. Output from each step propagated as `{{output}}` to next step. Condition evaluation without exec/eval (equality + truthiness only).

### 598. Test Impact Analyzer
**File:** `src/lidco/testing/impact_analyzer.py`
`TestImpactAnalyzer` — builds reverse import graph via AST (stdlib-only, no deps). `ChangeSet(files)` → `ImpactResult(changed_files, affected_tests, skipped_tests, coverage_estimate)`. `analyze(changeset)` BFS from changed files through inverted import graph. `analyze_since(ref)` uses `git diff --name-only`. `get_minimal_test_command()` returns ready-to-run pytest command. CLI: `/test-impact [--run] [--since <ref>] [file ...]`.

### 599. AI Git Blame
**File:** `src/lidco/git/ai_blame.py`
`AIBlameAnalyzer` — combines `git blame --porcelain` + `git log` + LLM callback. `BlameEntry(file, line_start, line_end, author, commit, date, message, code_lines, ai_explanation)`. `analyze_file(path, line_range)` → list[BlameEntry]. `explain_history(path)` → LLM narrative. `find_introduction(symbol, path)` → BlameEntry of first commit introducing symbol. `get_file_history(path)` → `FileHistory`. LLM callback injected — stdlib-only without it.

### 600. PR Description Generator
**File:** `src/lidco/git/pr_description.py`
`PRDescriptionGenerator` — uses `git log` + `git diff --numstat` + LLM callback. `PRDescription(title, summary, changes, test_plan, breaking_changes)` dataclass. `generate(base_branch, head_branch)` → `PRDescription`. `format_markdown(desc)` + `format_github(desc)` (GitHub-ready body with checkbox test plan). Rule-based fallback (no LLM) with heuristic breaking-change detection. LLM structured response parsed via regex sections.

### 601. CLI: /playbook /test-impact /ai-blame /pr-desc
**File:** `src/lidco/cli/commands/q93_cmds.py`
`register_q93_commands(registry)` — wires 4 async commands:
- `/playbook list|show <name>|run <name> [key=val ...]` → PlaybookEngine
- `/test-impact [--run] [--since <ref>] [files...]` → TestImpactAnalyzer
- `/ai-blame <file> [<start>-<end>]` → AIBlameAnalyzer
- `/pr-desc [--base <branch>] [--format github|markdown]` → PRDescriptionGenerator

---

## Q94 — Dependency Intelligence & Automated Refactoring (T602–T606)

**Goal:** Dependabot/Snyk dependency analysis (outdated/unused/vulnerable), Codemod-style code migration engine with built-in py2to3/stdlib/pytest rulesets, conventional-changelog generation from git history, and dotenv-vault-style .env validation.

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 602 | [Dependency Analyzer](#602-deps) | ✅ Done | 1d | Dependabot/Snyk parity |
| 603 | [Code Migration Engine](#603-migrate) | ✅ Done | 1d | Codemod/ast-grep parity |
| 604 | [Changelog Generator](#604-changelog) | ✅ Done | 1d | conventional-changelog parity |
| 605 | [Env Validator](#605-env-check) | ✅ Done | 1d | dotenv-vault/infisical parity |
| 606 | [CLI: /deps /migrate /changelog /env-check](#606-q94-cmds) | ✅ Done | 0.5d | exposes T602–T605 |

### 602. Dependency Analyzer
**File:** `src/lidco/dependencies/analyzer.py`
`DependencyAnalyzer` — parses requirements*.txt, pyproject.toml, package.json. Detects: unpinned versions (low), known vulnerable packages (high, built-in DB for pillow/cryptography/requests/urllib3/django/flask/pyyaml/jinja2), unused packages (info, via AST import scan), undeclared imports (medium). `DependencyReport(packages, issues, import_names, manifest_names)`. Canonical name mapping (pillow→pil, pyyaml→yaml, etc.). CLI: `/deps [--no-unused] [--no-unpinned] [--no-vuln]`.

### 603. Code Migration Engine
**File:** `src/lidco/migration/engine.py`
`CodeMigrationEngine` — applies `MigrationRule` objects (regex or AST mode) to project files. Built-in rulesets: `py2to3` (6 rules: print/raise/except/unicode/has_key/iteritems), `stdlib` (4 rules: collections.abc/distutils/imp/optparse), `pytest` (2 rules). `apply_ruleset(name)` / `apply_rules(rules)` → `MigrationResult`. Dry-run by default. Excludes `.` directories. Callable replacements supported. CLI: `/migrate list|apply <ruleset> [--write]`.

### 604. Changelog Generator
**File:** `src/lidco/git/changelog.py`
`ChangelogGenerator` — parses `git log` for Conventional Commits (type/scope/breaking). Groups into sections: Features/Bug Fixes/Performance/Refactoring/Breaking Changes/etc. `generate()` → `ChangelogResult` with `to_markdown()`. `save(result, path)` writes CHANGELOG.md. `get_tags()` for `--since` selection. Unrecognized commits collected separately. CLI: `/changelog [--since <tag>] [--version <label>] [--save]`.

### 605. Env Validator
**File:** `src/lidco/env/validator.py`
`EnvValidator` — compares `.env` vs template (`.env.example` > `.env.template` > `.env.schema` > `.env.sample`). `ValidationResult` with `errors`/`warnings` properties. Checks: missing required vars (error), missing optional vars (warning), extra vars (info), empty required vars (error), placeholder/example secret values (warning). Schema format (required/optional:default:secret). `generate_template()` strips secret values. CLI: `/env-check [--env <file>] [--template <file>] [--gen-template]`.

### 606. CLI: /deps /migrate /changelog /env-check
**File:** `src/lidco/cli/commands/q94_cmds.py`
`register_q94_commands(registry)` — 4 async commands:
- `/deps` → DependencyAnalyzer
- `/migrate list|apply <ruleset> [--write]` → CodeMigrationEngine
- `/changelog [--since <tag>] [--version <label>] [--save]` → ChangelogGenerator
- `/env-check [--env <file>] [--template <file>] [--gen-template]` → EnvValidator

## Q95 — Code Statistics, TODO Scanner, License Checker & Git Hooks Manager (T607–T611)

| Task | Name | Status | Est. | Notes |
|---|------|--------|------|--------|
| 607 | [Code Statistics](#607-stats) | ✅ Done | 1d | cloc/tokei parity |
| 608 | [TODO/FIXME Scanner](#608-todo) | ✅ Done | 1d | grep-based tag scan |
| 609 | [License Checker](#609-licenses) | ✅ Done | 1d | FOSSA parity |
| 610 | [Git Hooks Manager](#610-hooks) | ✅ Done | 1d | husky/lefthook parity |
| 611 | [CLI: /stats /todo /licenses /hooks](#611-q95-cmds) | ✅ Done | 0.5d | exposes T607–T610 |

### 607. Code Statistics
**File:** `src/lidco/stats/code_stats.py`
`CodeStats` — walks project with `os.walk`, prunes `_SKIP_DIRS`. `LANGUAGE_MAP` covers 35+ extensions. `_count_lines(text, lang)` → `(code, comment, blank)` with block comment state machine. `CodeStatsReport(by_language, file_stats, total_files, total_lines, total_code, total_comments, total_blank)`. `top_languages(n)` sorted by code_lines. CLI: `/stats [--top n] [--json]`.

### 608. TODO/FIXME Scanner
**File:** `src/lidco/analysis/todo_scanner.py`
`TodoScanner` — `_TAG_RE` regex matches `# TODO(owner): text` / `// FIXME: text`. `TAG_SEVERITY` dict (FIXME/HACK=high, TODO/BUG=medium, NOTE/OPTIMIZE=info). `TodoItem(file, line, tag, severity, text, owner, context)`. `TodoReport(items, files_scanned, by_tag, by_file)`. Skips `_SKIP_DIRS`. Optional git blame attribution. `scan_file(path)` and `scan()` directory walk. CLI: `/todo [--tag TAG] [--severity LEVEL] [--blame]`.

### 609. License Checker
**File:** `src/lidco/compliance/license_checker.py`
`LicenseChecker` — reads dist-info METADATA, parses package.json. `_classify(license_str)` checks weak_copyleft BEFORE copyleft (critical: "lgpl" contains "gpl"). `PackageLicense(name, version, license, classification, homepage, source)`. `LicenseReport(packages, issues, project_license)` with `by_classification` property and `summary()`. Detects copyleft incompatibilities (error), weak copyleft (warning), unknown licenses (warning). CLI: `/licenses [--project-license L] [--no-unknown]`.

### 610. Git Hooks Manager
**File:** `src/lidco/git/hooks_manager.py`
`HooksManager` — manages `.git/hooks/`. `GitHook(name, path, enabled, script, is_standard)`. `STANDARD_HOOKS` tuple of 18 hooks. `install(name, script, overwrite)` adds shebang, makes executable. `remove(name)` → bool. `enable(name)` / `disable(name)` → rename to/from `.disabled`. `run(name, timeout)` → `HookResult(hook, success, returncode, stdout, stderr)`. `_make_executable(path)` platform-aware chmod. CLI: `/hooks list|install|remove|enable|disable|run`.

### 611. CLI: /stats /todo /licenses /hooks
**File:** `src/lidco/cli/commands/q95_cmds.py`
`register_q95_commands(registry)` — 4 async commands:
- `/stats [--top n] [--json]` → CodeStats
- `/todo [--tag TAG] [--severity LEVEL] [--blame]` → TodoScanner
- `/licenses [--project-license L] [--no-unknown]` → LicenseChecker
- `/hooks list|install <name> <script>|remove <name>|enable <name>|disable <name>|run <name>` → HooksManager

## Q96 — HTTP Tool, SQL Tool, Profiler & Undo Manager (T612–T616)

| Task | Name | Status | Est. | Notes |
|---|------|--------|------|--------|
| 612 | [HTTP Request Tool](#612-http) | ✅ Done | 1d | curl/HTTPie parity |
| 613 | [SQL Query Tool](#613-sql) | ✅ Done | 1d | SQLite-native |
| 614 | [Code Profiler](#614-profile) | ✅ Done | 1d | cProfile/pstats wrapper |
| 615 | [Undo/Redo Manager](#615-undo) | ✅ Done | 1d | file checkpoint system |
| 616 | [CLI: /http /sql /profile /undo](#616-q96-cmds) | ✅ Done | 0.5d | exposes T612–T615 |

### 612. HTTP Request Tool
**File:** `src/lidco/tools/http_tool.py`
`HttpTool` — stdlib urllib only (no requests/httpx). Supports GET/POST/PUT/DELETE/PATCH with params, headers, JSON body, form data, basic auth, bearer auth, configurable timeout. `HttpResponse(url, method, status, reason, headers, body, elapsed_ms, error)` with `.ok`, `.json()`, `.format_summary()`. CLI: `/http <METHOD> <url> [--header K=V] [--json '{...}'] [--form K=V] [--bearer TOKEN] [--timeout N]`.

### 613. SQL Query Tool
**File:** `src/lidco/tools/sql_tool.py`
`SqlTool` — sqlite3-based SQL execution. `execute(query, params)` / `execute_many(query, params_list)` / `execute_script(script)` → `SqlResult`. `list_tables()`, `table_info(name)` → `TableInfo`. `SqlResult.format_table()` ASCII table. Context manager support. CLI: `/sql [--db <path>] <query|tables|schema <name>>`.

### 614. Code Profiler
**File:** `src/lidco/profiling/profiler.py`
`CodeProfiler` — cProfile + pstats wrapper. `profile_callable(func, *args)`, `profile_code(code_str)`, `profile_file(path)` → `ProfileReport`. `FunctionStat(module, function, line, ncalls, tottime, cumtime, percall)`. `ProfileReport.format_table(n)` ASCII hotspot table. `top_hotspots(n)` by cumulative time. CLI: `/profile file <path> [--top N] | code <snippet>`.

### 615. Undo/Redo Manager
**File:** `src/lidco/editing/undo_manager.py`
`UndoManager` — file snapshot-based undo/redo. `watch(*paths)`, `checkpoint(label, extra_files)` → `Checkpoint`. `undo()` / `redo()` → `UndoResult(success, checkpoint, restored_files, error)`. `list_history()` / `list_redo()`. `can_undo` / `can_redo`. Max N checkpoints enforced. Best-effort restore on disk write errors. CLI: `/undo checkpoint|undo|redo|watch|history`.

### 616. CLI: /http /sql /profile /undo
**File:** `src/lidco/cli/commands/q96_cmds.py`
`register_q96_commands(registry)` — 4 async commands:
- `/http <METHOD> <url> [--header K=V] [--json] [--form] [--bearer] [--timeout]` → HttpTool
- `/sql [--db path] <query|tables|schema name>` → SqlTool
- `/profile file|code <target> [--top N]` → CodeProfiler
- `/undo checkpoint|undo|redo|watch|history` → UndoManager

## Q97 — Process Runner, File Watcher, Config Manager & Template Engine (T617–T621)

| Task | Name | Status | Est. | Notes |
|---|------|--------|------|--------|
| 617 | [Process Runner](#617-run) | ✅ Done | 1d | subprocess wrapper |
| 618 | [File Watcher](#618-watch) | ✅ Done | 1d | poll-based fs watcher |
| 619 | [Config Manager](#619-config) | ✅ Done | 1d | layered JSON/TOML config |
| 620 | [Template Engine](#620-template) | ✅ Done | 1d | Jinja2-like renderer |
| 621 | [CLI: /run /watch /config /template](#621-q97-cmds) | ✅ Done | 0.5d | exposes T617–T620 |

### 617. Process Runner
**File:** `src/lidco/execution/process_runner.py`
`ProcessRunner` — subprocess wrapper with timeout, cwd, env, stdin piping, streaming output via callback. `run(cmd)` → `ProcessResult(cmd, returncode, stdout, stderr, elapsed_ms, timed_out)`. `run_script(multi_line_script)` runs each line, stops on failure (unless prefixed with `-`). `which(name)`, `is_available(name)`. CLI: `/run <cmd> [--timeout N] [--cwd PATH] [--env K=V]`.

### 618. File Watcher
**File:** `src/lidco/watch/file_watcher.py`
`FileWatcher` — polling-based (os.stat mtime) file watcher. `WatchEvent(path, kind: created|modified|deleted)`. `register_handler(pattern, callback)` glob matching. `poll()` synchronous one-shot poll. `start()`/`stop()` background thread. Debounce support. CLI: `/watch start|stop|events|status [--pattern GLOB] [--interval N]`.

### 619. Config Manager
**File:** `src/lidco/core/config_manager.py`
`ConfigManager` — layered config: defaults → user (~/.lidco/config.*) → project (.lidco/config.*) → env vars → runtime overrides. Supports JSON + TOML (3.11+ tomllib). Dot-notation `get("llm.model")` / `set("llm.model", val)`. `save()` persists runtime to .lidco/config.json. `reload()` re-reads disk. Env prefix (LIDCO_LLM_MODEL → llm.model). CLI: `/config get|set|list|save|reload`.

### 620. Template Engine
**File:** `src/lidco/templates/engine.py`
`TemplateEngine` — Jinja2-like without deps. `{{ var }}` substitution, `{% if/elif/else/endif %}`, `{% for x in items %}...{% endfor %}` with `loop.index/first/last`, `{# comments #}`, `{% raw %}...{% endraw %}`, `{% include 'file' %}`. 15 built-in filters (upper/lower/len/default/truncate/join/first/last/etc.). `render(str, ctx)` / `render_file(path, ctx)`. CLI: `/template render|file|test`.

### 621. CLI: /run /watch /config /template
**File:** `src/lidco/cli/commands/q97_cmds.py`
`register_q97_commands(registry)` — 4 async commands:
- `/run <cmd> [--timeout N] [--cwd PATH] [--env K=V]` → ProcessRunner
- `/watch start|stop|events|status` → FileWatcher
- `/config get|set|list|save|reload` → ConfigManager
- `/template render|file|test [--var K=V]` → TemplateEngine

---

## Q98 — Secrets, Notifications, Scheduling & Data Pipeline (T622–T626)

| Task | Name | Status | Est. | Notes |
|---|------|--------|------|--------|
| 622 | [Secrets Manager](#622-secrets) | ✅ Done | 1d | XOR+base64 obfuscated vault |
| 623 | [Notification Center](#623-notify) | ✅ Done | 1d | multi-channel notifications |
| 624 | [Task Scheduler](#624-scheduler) | ✅ Done | 1d | persistent one-shot + recurring |
| 625 | [Data Pipeline](#625-data-pipeline) | ✅ Done | 1d | composable ETL |
| 626 | [CLI: /secrets /notify /scheduler /data-pipeline](#626-q98-cmds) | ✅ Done | 0.5d | exposes T622–T625 |

### 622. Secrets Manager
**File:** `src/lidco/security/secrets_manager.py`
`SecretsManager` — XOR+base64 obfuscated local secrets vault (obfuscation, not crypto). `set(key, value)`, `get(key) -> str|None`, `delete(key) -> bool`, `list() -> list[str]`, `export_env() -> dict`. Persists to `.lidco/secrets.json`. Key derived from `socket.gethostname()` via SHA-256 (override via `machine_key` ctor arg). `SecretEntry` dataclass with timestamps.

### 623. Notification Center
**File:** `src/lidco/notifications/center.py`
`NotificationCenter` — multi-channel notification dispatch: `log` (callback/print), `webhook` (urllib POST), `desktop` (notify-send/osascript/msg). Thread-safe. `send(title, body, level, channels)` → `Notification`. `add_webhook/remove_webhook/list_webhooks`. `get_history()` newest-first, `clear_history()`. Errors captured per-channel, not raised.

### 624. Task Scheduler
**File:** `src/lidco/scheduler/task_scheduler.py`
`TaskScheduler` — persistent one-shot + recurring task scheduler. `ScheduledTask` dataclass with id/name/command/schedule/next_run. Schedule formats: `"every Ns/Nm/Nh"` (recurring) or ISO datetime string (one-shot). `add/remove/list/get/run_due`. `start(poll_interval)/stop()` background daemon thread. Persists to `.lidco/scheduled_tasks.json`. `TaskRunResult.format_summary()`.

### 625. Data Pipeline
**File:** `src/lidco/data/pipeline.py`
`DataPipeline` — composable ETL pipeline. Steps: `FilterStep(predicate)`, `MapStep(transform)`, `SortStep(key, reverse)`, `LimitStep(n)`, `UniqueStep(key)`. Fluent `add_step()` returns self. `run(data) -> list`, `dry_run(data) -> list[StepResult]` (per-step counts, no side effects). `clear()`. Raises `RuntimeError` if `run()` called with no steps.

### 626. CLI: /secrets /notify /scheduler /data-pipeline
**File:** `src/lidco/cli/commands/q98_cmds.py`
`register_q98_commands(registry)` — 4 async commands:
- `/secrets set|get|delete|list|export` → SecretsManager
- `/notify send|webhook|history|clear` → NotificationCenter
- `/scheduler add|remove|list|run` → TaskScheduler
- `/data-pipeline run|steps [--sort KEY] [--limit N] [--unique]` → DataPipeline


---

## Q99 — Rate Limiter, Circuit Breaker, Event Bus & Job Queue (T627-T631)

| Task | Name | Status | Est. | Notes |
|---|------|--------|------|--------|
| 627 | Rate Limiter | Done | 1d | token bucket, thread-safe |
| 628 | Circuit Breaker | Done | 1d | CLOSED/OPEN/HALF_OPEN |
| 629 | Event Bus | Done | 1d | typed pub/sub |
| 630 | Job Queue | Done | 1d | priority + worker threads |
| 631 | CLI q99_cmds | Done | 0.5d | exposes T627-T630 |

## Q100 — Key-Value Store, Message Queue, State Machine & Retry (T632-T636)

| Task | Name | Status | Est. | Notes |
|---|------|--------|------|--------|
| 632 | Key-Value Store | Done | 1d | TTL + namespaces + persistence |
| 633 | Message Queue | Done | 1d | FIFO + dead-letter queue |
| 634 | State Machine | Done | 1d | FSM with guards + actions |
| 635 | Retry Decorator | Done | 1d | exponential/linear/fixed backoff |
| 636 | CLI q100_cmds | Done | 0.5d | exposes T632-T635 |

## Q101 — Cache, Object Pool, Observer & Command (tasks 637–641)

| # | Task | Module | Status |
|---|------|--------|--------|
| 637 | LRU Cache | src/lidco/core/cache.py | DONE |
| 638 | Object Pool | src/lidco/core/object_pool.py | DONE |
| 639 | Observer Pattern | src/lidco/patterns/observer.py | DONE |
| 640 | Command Pattern | src/lidco/patterns/command.py | DONE |
| 641 | CLI Commands | src/lidco/cli/commands/q101_cmds.py | DONE |

Tests: tests/unit/test_q101/ — 110 tests

## Q102 — DI Container, Plugin Registry, Feature Flags & Audit Logger (tasks 642–646)

| # | Task | Module | Status |
|---|------|--------|--------|
| 642 | DI Container | src/lidco/core/container.py | DONE |
| 643 | Plugin Registry | src/lidco/plugins/registry.py | DONE |
| 644 | Feature Flags | src/lidco/features/flags.py | DONE |
| 645 | Audit Logger | src/lidco/audit/logger.py | DONE |
| 646 | CLI Commands | src/lidco/cli/commands/q102_cmds.py | DONE |

Tests: tests/unit/test_q102/ — 108 tests

## Q103 — Event Sourcing, CQRS & Saga Pattern (tasks 647–651)

| # | Task | Module | Status |
|---|------|--------|--------|
| 647 | Event Store + Aggregate Root | src/lidco/eventsourcing/store.py, aggregate.py | DONE |
| 648 | CQRS Bus | src/lidco/cqrs/bus.py | DONE |
| 649 | Saga Coordinator | src/lidco/saga/coordinator.py | DONE |
| 650 | CLI Commands | src/lidco/cli/commands/q103_cmds.py | DONE |

Tests: tests/unit/test_q103/ — 88 tests

## Q104 — Repository, Unit of Work, Specification & Domain Service (tasks 652–656)

| # | Task | Module | Status |
|---|------|--------|--------|
| 652 | Repository | src/lidco/repository/base.py | DONE |
| 653 | Unit of Work | src/lidco/repository/unit_of_work.py | DONE |
| 654 | Specification Pattern | src/lidco/domain/specification.py | DONE |
| 655 | Domain Service Registry | src/lidco/domain/service.py | DONE |
| 656 | CLI Commands | src/lidco/cli/commands/q104_cmds.py | DONE |

Tests: tests/unit/test_q104/ — 94 tests

## Q105 — Value Objects, Entity, Domain Events Publisher (tasks 657–661)

| # | Task | Module | Status |
|---|------|--------|--------|
| 657 | Value Object + Money/Email/Phone | src/lidco/domain/value_object.py | DONE |
| 658 | Entity + TimestampedEntity | src/lidco/domain/entity.py | DONE |
| 659 | Domain Event Publisher | src/lidco/domain/events.py | DONE |
| 660 | CLI Commands | src/lidco/cli/commands/q105_cmds.py | DONE |

Tests: tests/unit/test_q105/ — 95 tests

## Q106 — Builder, Strategy, Template Method & Decorator Pattern (tasks 662–666)

| # | Task | Module | Status |
|---|------|--------|--------|
| 662 | Builder Pattern | src/lidco/patterns/builder.py | DONE |
| 663 | Strategy Pattern | src/lidco/patterns/strategy.py | DONE |
| 664 | Template Method Pattern | src/lidco/patterns/template_method.py | DONE |
| 665 | Decorator Pattern | src/lidco/patterns/decorator_pattern.py | DONE |
| 666 | CLI Commands | src/lidco/cli/commands/q106_cmds.py | DONE |

Tests: tests/unit/test_q106/ — 95 tests

## Q107 — Composer Mode, Context Optimizer, Workflow Engine & Code Actions (tasks 667–671)

| # | Task | Module | Status |
|---|------|--------|--------|
| 667 | Composer Session | src/lidco/composer/session.py | DONE |
| 668 | Context Optimizer | src/lidco/context/optimizer.py | DONE |
| 669 | Workflow Engine | src/lidco/workflow/engine.py | DONE |
| 670 | Code Actions Registry | src/lidco/code_actions/registry.py | DONE |
| 671 | CLI Commands | src/lidco/cli/commands/q107_cmds.py | DONE |

Tests: tests/unit/test_q107/ — 152 tests

## Q108 — Docgen, Snippet Manager, Import Resolver & Error Monitor (tasks 672–676)

| # | Task | Module | Status |
|---|------|--------|--------|
| 672 | Doc Generator | src/lidco/docgen/generator.py | DONE |
| 673 | Snippet Store | src/lidco/snippets/store.py | DONE |
| 674 | Import Resolver | src/lidco/imports/resolver.py | DONE |
| 675 | Error Monitor | src/lidco/monitoring/error_monitor.py | DONE |
| 676 | CLI Commands | src/lidco/cli/commands/q108_cmds.py | DONE |

Tests: tests/unit/test_q108/ — 153 tests

## Q109 — Type Annotator, Stash Manager, Fixture Generator & Liveness Checker (tasks 677–681)

| # | Task | Module | Status |
|---|------|--------|--------|
| 677 | Type Annotator | src/lidco/typing_/annotator.py | DONE |
| 678 | Stash Manager | src/lidco/git/stash_manager.py | DONE |
| 679 | Fixture Generator | src/lidco/testing/fixture_gen.py | DONE |
| 680 | Liveness Checker | src/lidco/liveness/checker.py | DONE |
| 681 | CLI Commands | src/lidco/cli/commands/q109_cmds.py | DONE |

Tests: tests/unit/test_q109/ — 147 tests

## Q110 — SemVer, Mock Generator, Conflict Resolver & Formatter Registry (tasks 682–686)

| # | Task | Module | Status |
|---|------|--------|--------|
| 682 | SemVer Manager | src/lidco/versioning/semver.py | DONE |
| 683 | Mock Generator | src/lidco/testing/mock_gen.py | DONE |
| 684 | Conflict Resolver | src/lidco/git/conflict_resolver.py | DONE |
| 685 | Formatter Registry | src/lidco/format/formatter.py | DONE |
| 686 | CLI Commands | src/lidco/cli/commands/q110_cmds.py | DONE |

Tests: tests/unit/test_q110/ — ~120 tests

## Q111 — Session Intelligence & Memory Extraction (tasks 687–691)

**Theme:** Close the Cursor/Windsurf "persistent memories" gap. Auto-mine conversations for reusable facts, manage their lifecycle, and add full session-level checkpoints (Cursor Checkpoints parity).

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 687 | ConversationMemoryExtractor | src/lidco/memory/conversation_extractor.py | Parse transcript for facts, score confidence, deduplicate vs AgentMemory, return ExtractedFact list |
| 688 | MemoryApprovalQueue | src/lidco/memory/approval_queue.py | Pending-approval queue; approve/reject/list_pending/auto_approve(threshold); JSON-persisted in .lidco/ |
| 689 | MemoryInjector | src/lidco/memory/injector.py | Compose system prompt block from approved memories; token-budget-aware; integrates with SessionSeeder |
| 690 | SessionCheckpointStore | src/lidco/memory/session_checkpoint.py | Full session-level checkpoint (messages + file refs + memory state); save/list/restore/diff; named labels |
| 691 | CLI Commands | src/lidco/cli/commands/q111_cmds.py | /memory extract, /memory approve, /memory list, /memory inject, /checkpoint save/list/restore/diff |

Tests: tests/unit/test_q111/ — ~125 tests

## Q112 — Live Task Orchestration & Chat Modes (tasks 692–696)

**Theme:** Windsurf "live todo" parity + Aider "four chat modes" parity + Devin child-session spawning.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 692 | LiveTodoTracker | src/lidco/tasks/live_todo.py | Real-time progress renderer; TodoBoard with pending/active/done/blocked states; render_ascii(); EventBus-driven |
| 693 | TodoPlanningAgent | src/lidco/tasks/planning_agent.py | NL task → TodoItem list via LLM; wraps TaskDAG; emits events for LiveTodoTracker; TodoPlan with deps |
| 694 | ChildSessionSpawner | src/lidco/agents/child_session.py | Parent spawns typed child sessions with OutputSchema (dataclass-based); ChildSessionHandle; schema validation |
| 695 | ChatModeManager | src/lidco/composer/chat_mode.py | Four modes: code/ask/architect/help; switch(mode); active_mode; mode persisted per ComposerSession |
| 696 | CLI Commands | src/lidco/cli/commands/q112_cmds.py | /todo plan/board/done/block, /mode <code|ask|architect|help>, /mode status, /spawn |

Tests: tests/unit/test_q112/ — ~125 tests

## Q113 — BugBot PR Autofix Pipeline (tasks 697–701)

**Theme:** Cursor BugBot Autofix parity: PR-triggered find-bugs → generate-fix → post-proposal loop. Plus session tagging and post-edit auto-lint.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 697 | BugBotPRTrigger | src/lidco/review/bugbot_pr_trigger.py | PR event listener; fetches diff; runs BugbotAnalyzer + PRReviewerV2; BugBotFinding list |
| 698 | BugBotFixAgent | src/lidco/review/bugbot_fix_agent.py | Finding → minimal patch via LLM; BugBotFixProposal with before/after + rationale + confidence |
| 699 | BugBotPRPoster | src/lidco/review/bugbot_pr_poster.py | Post fix proposals as inline PR comments; dry-run mode; duplicate detection via posted_ids |
| 700 | SessionTagStore | src/lidco/memory/session_tags.py | Tag sessions by labels + attributes (origin, time_range, agent); search/filter/untag; SQLite-backed |
| 701 | PostEditLintHook | src/lidco/editing/post_edit_lint.py | After-edit callback on SmartApply/ComposerSession; runs FormatterRegistry + LintFixLoop; LintHookResult |

Tests: tests/unit/test_q113/ — ~125 tests

## Q114 — Notebook Support & Web Grounding (tasks 702–706)

**Theme:** Jupyter notebook support (Cursor parity) + in-session web search grounding (Windsurf parity).

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 702 | NotebookParser | src/lidco/notebook/parser.py | Read/write .ipynb JSON; NotebookDoc + Cell dataclasses; parse/dump/diff; stdlib json only |
| 703 | NotebookEditor | src/lidco/notebook/editor.py | append/replace/delete/move cells; SmartApply-style diffs; immutable transforms; NotebookEditError |
| 704 | NotebookAgent | src/lidco/notebook/agent.py | NL instructions → cell operations via LLM; execute_plan(instruction, doc, llm_fn); TodoPlan trace |
| 705 | WebSearchGrounder | src/lidco/search/web_search.py | In-session web search (urllib.request); DuckDuckGo HTML scrape; pluggable provider; grounded_prompt() |
| 706 | CLI Commands | src/lidco/cli/commands/q114_cmds.py | /notebook open/add/replace/show/ask, /search web <query>, /search web --grounded <prompt> |

Tests: tests/unit/test_q114/ — ~125 tests

## Q115 — Deploy Pipeline, Diagram Renderer & Max Mode (tasks 707–711)

**Theme:** Windsurf one-click deploy parity + Cursor MCP Apps diagram rendering + Max Mode configuration (Cursor Max Mode parity).

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 707 | DeployProviderRegistry | src/lidco/scaffold/deploy_registry.py | Provider registry: Netlify/Railway/Fly.io/Heroku/custom; auto_detect(project_dir); .lidco/deploy.json |
| 708 | DeployPipeline | src/lidco/scaffold/deploy_pipeline.py | build→test→deploy via JobQueue; DeployJob/DeployResult; dry-run; rollback via FlowCheckpointManager |
| 709 | DiagramRenderer | src/lidco/multimodal/diagram_renderer.py | MermaidDiagram + AsciiDiagram; MCP tool adapter; render(spec) → RenderResult; pure stdlib, no subprocess |
| 710 | MaxModeManager | src/lidco/composer/max_mode.py | Named modes: normal/max/mini; activate() updates AdaptiveBudget + ComposerSession limits; usage metering |
| 711 | CLI Commands | src/lidco/cli/commands/q115_cmds.py | /deploy detect/run/status/rollback, /diagram mermaid/ascii/show, /max-mode <normal|max|mini>/status |

Tests: tests/unit/test_q115/ — ~125 tests

✅ **Q111–Q115 DONE** — Session Intelligence, Live Tasks, BugBot, Notebooks, Deploy/Diagram/MaxMode. ~703 tests.

## Q116 — Agent Teams (tasks 712–716)

**Theme:** Multi-agent squads where a lead coordinator delegates tasks from a shared pool; teammates communicate via AgentMailbox; results challenged before final delivery. Claude Code Agent Teams parity.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 712 | AgentTeamRegistry | src/lidco/agents/team_registry.py | AgentTeam(name, roles, mailbox); register/lookup; team-level broadcast() via AgentMailbox |
| 713 | SharedTaskList | src/lidco/agents/shared_task_list.py | Thread-safe SharedTask pool; claim(agent_name) atomic; complete(task_id, result); list_pending() |
| 714 | TeamCoordinator | src/lidco/agents/team_coordinator.py | Lead agent splits prompt→sub-tasks; dispatches via mailbox; collects results with timeout; CoordinationResult |
| 715 | TeammateChallengeProtocol | src/lidco/agents/teammate_challenge.py | ChallengeRequest/Response; routes through AgentMailbox; ChallengeLog records outcomes |
| 716 | CLI Commands | src/lidco/cli/commands/q116_cmds.py | /team create/assign/status/challenge |

Tests: tests/unit/test_q116/ — ~125 tests

## Q117 — Hooks System Expansion (tasks 717–721)

**Theme:** New lifecycle hook events (InstructionsLoaded, CwdChanged, FileChanged, TaskCreated/Completed, Elicitation, PostCompact/PreCompact, WorktreeCreate/Remove, UserPromptSubmit), conditional if: filters, HTTP delivery. Claude Code parity.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 717 | HookEventBus | src/lidco/hooks/event_bus.py | HookEvent(event_type, payload, timestamp); subscribe/emit; immutable subscriber list replacement |
| 718 | HookEventTypes | src/lidco/hooks/event_types.py | 12 frozen dataclass event types; event_type class-var; all 9 new lifecycle events |
| 719 | ConditionalHookFilter | src/lidco/hooks/conditional_filter.py | ConditionalFilter(if_pattern); re.search matching; HookRegistry with HookDefinition; wildcard "*" |
| 720 | HttpHookDelivery | src/lidco/hooks/http_delivery.py | HttpHookConfig(url, headers, timeout, retry); POST JSON via urllib.request; HttpDeliveryResult |
| 721 | CLI Commands | src/lidco/cli/commands/q117_cmds.py | /hook list/emit/add-http/add-filter |

Tests: tests/unit/test_q117/ — ~125 tests

## Q118 — Automations Platform v2 (tasks 722–726)

**Theme:** Unified AutomationTrigger registry wiring cron/GitHub PR/Slack/Linear/custom HTTP triggers to AutomationRunner with memory across runs and structured output routing. Cursor Automations Platform parity.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 722 | AutomationTriggerRegistry | src/lidco/scheduler/trigger_registry.py | AutomationTrigger(name, trigger_type, config, instructions_template, output_type, memory_key); register/match; JSON persistence |
| 723 | TriggerEventNormalizer | src/lidco/scheduler/trigger_normalizer.py | Normalize cron/GitHub/Slack/Linear/HTTP → NormalizedEvent(trigger_type, source_id, title, body, metadata) |
| 724 | AutomationRunner | src/lidco/scheduler/automation_runner.py | match triggers, render template, call agent_fn, persist RunRecord; RunSummary |
| 725 | AutomationOutputRouter | src/lidco/scheduler/output_router.py | OutputRouter maps output_type(pr/slack/linear/log/comment) → OutputHandler; stub impls; route(result) |
| 726 | CLI Commands | src/lidco/cli/commands/q118_cmds.py | /automation list/add/run/history |

Tests: tests/unit/test_q118/ — ~125 tests

## Q119 — Rules Directory + Effort Level + Session Color (tasks 727–731)

**Theme:** Glob-scoped .lidco/rules/*.md files, RulesResolver for context-aware loading, effort levels mapped to token budgets, per-session accent colors. Claude Code rules directory + /effort + /color parity.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 727 | RulesFileLoader | src/lidco/rules/rules_loader.py | Scan .lidco/rules/*.md; parse globs: frontmatter; mtime cache; default glob "*" |
| 728 | RulesResolver | src/lidco/rules/rules_resolver.py | fnmatch current_files vs rule glob; resolve_text() concatenates matched rules for prompt injection |
| 729 | EffortManager | src/lidco/config/effort_manager.py | EffortLevel LOW/MEDIUM/HIGH/AUTO; EffortBudget(max_tokens, thinking_tokens, temperature); persist to .lidco/effort.json; auto heuristic |
| 730 | SessionColorManager | src/lidco/config/session_color.py | 16 ANSI named colors; set_color/get_ansi_prefix/reset; persist to .lidco/session_color.json |
| 731 | CLI Commands | src/lidco/cli/commands/q119_cmds.py | /rules list/check, /effort [level], /color [name] |

Tests: tests/unit/test_q119/ — ~125 tests

## Q120 — Memory Consolidation + Session Forking + Transcript Search (tasks 732–736)

**Theme:** Async-safe memory consolidation (Auto Dream parity), session forking with divergence tracking, full-text transcript search with step-through navigation, stateful session summaries.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 732 | AsyncConsolidationScheduler | src/lidco/memory/consolidation_scheduler.py | Daemon thread wrapping MemoryConsolidator; schedule/cancel; ConsolidationJob status; emits PostCompact hook |
| 733 | SessionForkManager | src/lidco/memory/session_fork.py | SessionFork(id, parent_id, title, branch_point, turns); create by cloning; diff(fork_a, fork_b) → ForkDiff |
| 734 | TranscriptSearch | src/lidco/memory/transcript_search.py | Inverted word index; search(query) → SearchResultSet; Navigator with next/prev/current cursor |
| 735 | SessionSummarizer | src/lidco/memory/session_summarizer.py | Summarize on threshold; SummaryRecord persisted to SessionHistoryStore; inject_context() for prompt |
| 736 | CLI Commands | src/lidco/cli/commands/q120_cmds.py | /memory consolidate, /session fork/diff, /transcript search/next/prev, /summary show |

Tests: tests/unit/test_q120/ — ~125 tests
