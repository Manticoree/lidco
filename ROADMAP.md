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
| 73 | [Pre-planning context snapshot](#73-pre-planning-context-snapshot) | ☐ Todo | 1.5d | плануник стартует с готовым контекстом |
| 74 | [Explicit assumption tracker](#74-explicit-assumption-tracker) | ☐ Todo | 1d | скрытые допущения видны пользователю |
| 75 | [Multi-round critique/revise](#75-multi-round-critiqurevise) | ☐ Todo | 1d | итеративное устранение пробелов в плане |
| 76 | [Similar plan warm-start](#76-similar-plan-warm-start) | ☐ Todo | 1.5d | повторные задачи планируются быстрее |
| 77 | [Pre-planning symbol extraction](#77-pre-planning-symbol-extraction) | ☐ Todo | 1d | плануник не тратит итерации на очевидный grep |

---

## Task Details (Q16)

### 73. Pre-planning context snapshot
**Files:** `src/lidco/agents/graph.py` → `_execute_planner_node`, new helper `_build_preplan_snapshot()`
**Goal:** Before the planner agent starts, automatically collect and inject a compact snapshot of facts it would otherwise discover via tool calls: arch diagram of mentioned files, coverage data for affected modules, last-3-commit summary for touched paths. This snapshot becomes the first block of the planner's context, letting Phase 2 start from a richer baseline and use its iteration budget for genuinely novel exploration.

**Approach:**
- In `_execute_planner_node()`, before calling `planner.run()`, call `_build_preplan_snapshot(user_message, context)` in a background gather
- Snapshot components (each failure-safe, max 1s timeout per component):
  - `arch_diagram` on files/modules mentioned in the user message (regex: `\bsrc/\S+\.py\b`, `\b\w+\.py\b`)
  - `find_test_gaps` for detected modules
  - `git log --oneline -5 -- <detected_files>` for recent history
  - Coverage % from `.lidco/coverage.json` for detected files
- Inject as `## Pre-Planning Snapshot\n{snapshot}` prepended to `context`
- Gate behind `config.agents.preplan_snapshot: bool = True`
- Cap snapshot at 3000 chars; skip silently if planner tool registry unavailable

**Config:** `AgentsConfig.preplan_snapshot: bool = True`

---

### 74. Explicit assumption tracker
**Files:** `src/lidco/agents/builtin/planner.py`, `src/lidco/agents/graph.py`
**Goal:** The planner must explicitly list every assumption it made during exploration (e.g., "I assume `Session` is always initialised before `handle()` is called"). The revision pass then challenges each assumption: if any assumption could be wrong, the revise prompt flags it as a risk. Visible to the user at approval time.

**Approach:**
- Add `**Assumptions:**` to `PLANNER_SYSTEM_PROMPT` output format (after `Chain of Thought`, before `Steps`):
  ```
  **Assumptions:**
  - [numbered list of things taken as given that were NOT verified by tool calls]
  - Mark each as: ✓ Verified (seen in code) | ⚠ Unverified (assumed)
  ```
- In `_REVISE_SYSTEM_PROMPT`: add instruction — "For every ⚠ Unverified assumption, either add a verification step to the plan or escalate it to the Risk Assessment table."
- `GraphState.plan_assumptions: list[str]` — parse `**Assumptions:**` section after planner runs; inject into critique prompt as extra context
- `/plan` command shows assumption count in the approval prompt header: `"Plan has 3 unverified assumptions"`

---

### 75. Multi-round critique/revise
**Files:** `src/lidco/agents/graph.py`
**Goal:** After the first revision, run the critique again. If it still finds HIGH-severity issues, do a second revision. Stop when no HIGH issues remain or `plan_max_revisions` is exhausted. Prevents plans that look fixed but still have critical gaps after one pass.

**Approach:**
- Add `plan_revision_round: int` to `GraphState` (starts at 0)
- After `_revise_plan_node()`, run a lightweight re-critique (same prompt, same model, same timeout)
- If re-critique finds lines starting with `**[` (any category) AND `plan_revision_round < max_rounds`: loop back to `_revise_plan_node()` with updated critique
- Implement as a conditional edge: `revise_plan → re_critique → revise_plan` (loop) or `re_critique → approve_plan` when clean
- `AgentsConfig.plan_max_revisions: int = 2` — default 2 rounds total (first revision + one re-pass)
- Phase status bar shows: `"Revising plan (round 2/2)"`
- Token accumulation continues across all rounds

**Config:** `AgentsConfig.plan_max_revisions: int = 2`

---

### 76. Similar plan warm-start
**Files:** `src/lidco/agents/graph.py`, `src/lidco/core/memory.py`
**Goal:** Before the planner runs, search the memory store for approved plans from similar past tasks. If a similar plan is found, inject it as `## Similar Past Plan` context so the planner can reuse decisions already validated by the user. After each plan approval, save the approved plan to memory.

**Approach:**
- `MemoryStore` already supports `category` — add `category="approved_plans"` entries
- Before `planner.run()`: call `memory.search(query=user_message, category="approved_plans", n=3)` (use BM25 over memory keys/content if RAG is off)
- If matches found: inject top-1 as `## Similar Past Plan\n{content}` in context (cap 2000 chars, add `[similarity: {score:.2f}]` header)
- After `_approve_plan_node()` returns `plan_approved=True`: save `{user_message[:100]}: {plan_content[:2000]}` to memory under `category="approved_plans"`, key = sha256(user_message)[:8]
- Gate behind `config.agents.plan_memory: bool = True`
- Stale plans (>30 days) excluded from retrieval via TTL filter

**Config:** `AgentsConfig.plan_memory: bool = True`

---

### 77. Pre-planning symbol extraction
**Files:** `src/lidco/agents/graph.py` → `_execute_planner_node`
**Goal:** Parse the user request for referenced symbols (`ClassName`, `method_name()`, `path/to/file.py`) and pre-grep their definitions, injecting `file:line:signature` tuples as `## Referenced Symbols` context. The planner skips redundant grep calls for symbols that are already resolved.

**Approach:**
- Regex extraction in `_extract_mentioned_symbols(user_message: str) -> list[str]`:
  - `\b([A-Z][a-zA-Z]+)\b` — likely class names
  - `` `([a-z_]+(?:\.[a-z_]+)*)\(\)` `` — method/function calls in backticks
  - `\b(src/[^\s]+\.py)\b` — explicit file paths
- For each extracted symbol (max 10): run `grep -n "def {sym}\|class {sym}" src/` via `ToolRegistry.get("grep")`
- Collect first match per symbol: `{symbol}: {file}:{line} — {signature}`
- Inject as `## Referenced Symbols\n{table}` prepended to planner context (before pre-planning snapshot)
- Skip symbols that match common builtins or are <3 chars
- Total budget: max 5s for all greps in parallel (`asyncio.gather` with timeout)
