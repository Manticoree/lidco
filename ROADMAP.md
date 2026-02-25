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
| 8 | [Hybrid semantic+BM25 symbol search](#8-hybrid-search) | ⬜ Todo | 3d | better RAG precision |

---

## Q3 — Token Optimization

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 9  | [Dynamic system prompt builder](#9-dynamic-system-prompt-builder) | ✅ Done | 2d | −20% tokens/call |
| 10 | [Hard token budget enforcement](#10-hard-token-budget-enforcement) | ✅ Done | 1d | no surprise bills |
| 11 | [Smart tool result compression](#11-smart-tool-result-compression) | ⬜ Todo | 3d | −40% on large file reads |
| 12 | [Conversation pruner improvements](#12-conversation-pruner-improvements) | ✅ Done | 2d | longer sessions |

---

## Q4 — UI

| # | Task | Status | Est. | Impact |
|---|------|--------|------|--------|
| 13 | [Phase progress in status bar](#13-phase-progress-in-status-bar) | ✅ Done | 1d | clearer multi-agent flow |
| 14 | [Session summary on exit](#14-session-summary-on-exit) | ✅ Done | 1d | recap what was done |
| 15 | [Interactive plan editor](#15-interactive-plan-editor) | ⬜ Todo | 3d | step-level plan editing |
| 16 | [Git diff viewer](#16-git-diff-viewer) | ⬜ Todo | 2d | syntax-highlighted diffs |

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
**Goal:** When an agent reads a large file, compress the result using AST index: return symbol summaries instead of full file content when the agent only needs to understand the structure.

**Where:** `src/lidco/tools/file_read.py`, `src/lidco/index/context_enricher.py`

**Approach:**
- If file > N chars AND index exists for that file: return `## File summary\n{symbols_list}\n\n## Full content\n{content[:2000]}\n...[truncated]`
- Agent can always call `file_read` again with line range if it needs details

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
**Goal:** When a plan is generated, show it in an interactive TUI where user can approve/reject individual steps, not just the whole plan.

**Where:** `src/lidco/agents/graph.py` → `_approve_plan_node`

**Approach:**
- Parse plan into numbered steps (lines starting with `1.`, `2.`, etc.)
- Show step list in prompt_toolkit with checkboxes
- Pass approved steps back as filtered plan context

---

### 16. Git Diff Viewer
**Goal:** After agent makes changes, show a syntax-highlighted diff of what was changed before the review pass.

**Where:** `src/lidco/cli/stream_display.py` or new `src/lidco/cli/diff_viewer.py`

**Approach:**
- After `execute_agent` node, run `git diff --unified=3`
- Render with Rich `Syntax` widget (language=diff)
- Show in collapsed panel user can expand
