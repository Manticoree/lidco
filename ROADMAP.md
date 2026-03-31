# LIDCO Development Roadmap

Focus areas: deeper context understanding · context optimization · token optimization · UI improvements

> Full details for Q1–Q153 (tasks 1–881) are archived in [ROADMAP_ARCHIVE.md](ROADMAP_ARCHIVE.md).

---

## Summary: Q1–Q153 (tasks 1–881) — ALL DONE ✅

| Quarter | Theme | Tasks |
|---------|-------|-------|
| Q1 | Foundation | 1–5 |
| Q2 | Context Depth | 6–10 |
| Q3 | Token Optimization | 11–15 |
| Q4 | UI | 16–20 |
| Q5 | DX & Tooling | 21–30 |
| Q6 | Reliability & Performance | 31–40 |
| Q7 | New Tools & Agents | 41–50 |
| Q8 | Index & RAG | 51–58 |
| Q9 | Observability & Config | 59–65 |
| Q10 | Agent Capabilities | 66–80 |
| Q11 | Workflow & Intelligence | 81–95 |
| Q12 | Resilience & Extensibility | 96–105 |
| Q13 | Deeper Agent Debugging | 106–113 |
| Q14 | Deeper Planning & Reasoning | 114–121 |
| Q15 | Plan Feedback Loop | 122–129 |
| Q16 | Deeper Pre-Planning | 130–137 |
| Q17 | Plan Quality Scoring | 138–145 |
| Q18 | Deeper Pre-work Analysis | 146–149 |
| Q19–Q26 | Debug Intelligence | 150–193 |
| Q27–Q31 | UX & Feedback | 194–243 |
| Q37–Q48 | Safety, MCP, Headless, Agents, UX, TDD, Skills, API, Context, AI, Enterprise, Cloud | 244–334 |
| Q49–Q53 | Code Analysis & Intelligence | 335–369 |
| Q54–Q56 | Bug Fixes & UX | 370–381 |
| Q57–Q60 | Session, Multi-Agent, Runtime, Integrations | 382–409 |
| Q61–Q65 | Proactive, Voice, Cost, DX, Observability | 410–443 |
| Q66–Q70 | Competitive Edge, Memory, PR Review, Spec, Wiki, Autofix | 444–475 |
| Q71–Q75 | Agent Spawning, Confidence, Ensemble, Memory Hierarchy, Session Diff | 476–501 |
| Q76–Q80 | Code Intel, Pipelines, Watch Mode, @-Mentions, Automations | 502–526 |
| Q81–Q85 | CLI Wiring, Code Transform, Deep Intelligence, Session Learning, Enterprise | 527–561 |
| Q86–Q90 | Navigation, Graph, Browser, Turbo Mode, Competitive Parity | 562–586 |
| Q91–Q95 | Session History, Smart Apply, Prompts, Playbooks, Dependencies, Stats | 587–611 |
| Q96–Q100 | HTTP/SQL Tools, Process Runner, Secrets, Rate Limiter, KV Store | 612–636 |
| Q101–Q105 | Cache, DI, Event Sourcing, Repository, Domain | 637–661 |
| Q106–Q110 | Patterns, Composer, Docgen, Type Annotator, SemVer | 662–686 |
| Q111–Q115 | Memory Extraction, Task Orchestration, BugBot, Notebook, Deploy | 687–711 |
| Q116–Q120 | Agent Teams, Hooks, Automations, Rules, Memory Consolidation | 712–736 |
| Q121–Q124 | Patch Editor, Token Budget, Code Generation, Async Runner | 737–756 |
| Q125–Q130 | Symbol Indexing, Proactive, Workspace, Config, Metrics, Memory Graph | 757–786 |
| Q131–Q135 | Prompts, Filesystem, Debugging, AST Transform, Network | 787–811 |
| Q136–Q140 | Scheduling, Text Processing, Error Recovery, Rich Output, Validation | 812–836 |
| Q141–Q145 | Session Resilience, Streaming, Diagnostics, Config Migration, History | 837–861 |
| Q146–Q149 | Undo/Redo, Notifications, Workspace Cleanup, Completion | 862–881 |
| Q150–Q153 | *(skipped — tasks renumbered to Q154+)* | — |

---

## Q154 — Critical Bug Fixes & Command Registration (tasks 882–886) ✅

**Theme:** Fix critical runtime bugs: broken agent reload, missing command registration for Q91-Q153, sync handler failures, Russian text in error messages.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 882 | Fix AgentRegistry.register() call signature | src/lidco/core/config_reloader.py | Pass agent_obj only, not (name, agent_obj) |
| 883 | Register all Q91-Q153 command modules | src/lidco/cli/commands/registry.py | Import and call register_q*_commands for 63 missing modules |
| 884 | Fix sync handlers in q91_cmds.py | src/lidco/cli/commands/q91_cmds.py | Convert 4 sync handlers to async |
| 885 | Fix Russian text in error messages | src/lidco/core/session.py, agents/base.py | Replace Cyrillic strings with English |
| 886 | Fix restore_planner.py apply() bug | src/lidco/workspace/restore_planner.py | Store content in RestoreAction, not reason |

Tests: tests/unit/test_q154/ — 33 tests

## Q155 — Dead Code Cleanup & Class Deduplication (tasks 887–891) ✅

**Theme:** Remove dead modules, fix naming collisions, clean up dead code blocks.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 887 | Add public API to SymbolIndex for references | src/lidco/analysis/symbol_index2.py | Add list_references() method |
| 888 | Remove dead code in edit_transaction.py | src/lidco/editing/edit_transaction.py | Delete unused variable block |
| 889 | Add thread safety to LRUCache | src/lidco/core/cache.py | Add threading.Lock to operations |
| 890 | Deduplicate _LEVEL_ORDER in logging | src/lidco/logging/ | Define once, import in both modules |
| 891 | Deduplicate format_bytes | src/lidco/ui/, maintenance/ | Extract shared helper |

Tests: tests/unit/test_q155/ — 36 tests

## Q156 — Integration Fixes & Module Wiring (tasks 892–896) ✅

**Theme:** Wire orphaned modules, add missing exports, connect resilience to execution.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 892 | Add __all__ exports to orphaned __init__.py | resilience/, network/, streaming/, perf/ | Define public API |
| 893 | Connect MemoryConfig to memory systems | src/lidco/memory/agent_memory.py | Read defaults from config |
| 894 | Fix event bus error swallowing | src/lidco/events/bus.py | Capture handler errors |
| 895 | Fix unused SagaStatus states | src/lidco/saga/coordinator.py | Set RUNNING/COMPENSATING during execution |
| 896 | Add StructuredLogger level validation | src/lidco/logging/structured_logger.py | Validate level parameter |

Tests: tests/unit/test_q156/ — 48 tests

## Q157 — Dead Code Removal & Naming Deduplication (tasks 897–901) ✅

**Theme:** Remove dead/legacy modules, rename colliding classes.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 897 | Remove dead symbol_index.py | src/lidco/analysis/ | Superseded by symbol_index2 |
| 898 | Remove dead change_impact.py | src/lidco/analysis/ | Depends on dead symbol_index |
| 899 | Remove dead proactive/suggestions.py | src/lidco/proactive/ | LLM-based, never imported |
| 900 | Remove legacy snapshot.py v1 | src/lidco/workspace/ | v2 has better API |
| 901 | Rename ApplyResult classes | src/lidco/editing/ | PatchApplyResult, SmartApplyResult, etc. |

Tests: tests/unit/test_q157/ — 25 tests

## Q158 — Config System Consolidation (tasks 902–906) ✅

**Theme:** ConfigManager and ProfileManager delegate to LidcoConfig.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 902 | ConfigManager wraps LidcoConfig | src/lidco/core/config_manager.py | get()/set() as adapters over Pydantic |
| 903 | ProfileManager stores LidcoConfig snapshots | src/lidco/config/profile.py | activate() merges profile settings |
| 904 | Wire MemoryConfig to AgentMemoryStore | src/lidco/memory/agent_memory.py | Read from config.memory |
| 905 | Wire MemoryConfig to SemanticMemoryStore | src/lidco/memory/semantic_memory.py | Read config.memory settings |
| 906 | Unify config storage paths | src/lidco/core/config.py | Path constants for .lidco/ layout |

Tests: tests/unit/test_q158/ — 57 tests

## Q159 — Resilience Integration & Execution Stability (tasks 907–911) ✅

**Theme:** Connect resilience modules to execution/scheduler; improve stability.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 907 | Wrap ProcessRunner with RetryExecutor | src/lidco/execution/process_runner.py | Retry on transient failures |
| 908 | Add ErrorBoundary to TurboRunner | src/lidco/execution/turbo_runner.py | Structured error results |
| 909 | Make TaskScheduler timeout configurable | src/lidco/scheduler/task_scheduler.py | Add timeout field to ScheduledTask |
| 910 | Rename duplicate classes | src/lidco/scheduler/cron_runner.py | CronTask, CronRunResult |
| 911 | Create unified event bus protocol | src/lidco/events/protocol.py | EventBusProtocol ABC |

Tests: tests/unit/test_q159/ — 41 tests

## Q160 — AI Permission Classifier & Session Checkpointing (tasks 912–916) ✅

**Theme:** AI safety classifier for tool calls + checkpoint/rewind for safe experimentation.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 912 | AI Permission Classifier | src/lidco/permissions/ai_classifier.py | Classify tool calls as safe/risky; configurable rules |
| 913 | Classifier integration | src/lidco/core/permissions.py | Wire into permission flow |
| 914 | Session Checkpoint Manager | src/lidco/checkpoint/manager.py | Auto-snapshot before each edit |
| 915 | Selective Rewind | src/lidco/checkpoint/rewind.py | Rewind code/conversation/both |
| 916 | CLI Commands | src/lidco/cli/commands/q160_cmds.py | /auto-mode, /rewind, /checkpoints |

Tests: tests/unit/test_q160/ — 88 tests

## Q161 — Infinite Output & Lazy Tool Loading (tasks 917–921) ✅

**Theme:** Prefill continuation for unlimited output + deferred tool loading for context savings.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 917 | Prefill Continuation Engine | src/lidco/llm/prefill_continuation.py | Auto-send continuation on truncation |
| 918 | Integration with LLM layer | src/lidco/llm/litellm_provider.py | Wire into streaming/non-streaming |
| 919 | Lazy Tool Schema Registry | src/lidco/tools/lazy_registry.py | Register names only; fetch on demand |
| 920 | MCP Lazy Tool Integration | src/lidco/mcp/lazy_tools.py | MCP tools as stubs |
| 921 | CLI Commands | src/lidco/cli/commands/q161_cmds.py | /continuation, /tools lazy/eager, /tool-search |

Tests: tests/unit/test_q161/ — 71 tests

## Q162 — Side Questions, Plan Mode & Markdown Workflows (tasks 922–926) ✅

**Theme:** /btw for side questions, read-only plan mode, workflow files from directory convention.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 922 | /btw Side-Question Fork | src/lidco/session/side_question.py | Fork context; revert after answer |
| 923 | Read-Only Plan Mode | src/lidco/modes/plan_mode.py | Block writes; output markdown plan |
| 924 | Markdown Workflow Loader | src/lidco/workflows/md_loader.py | Scan .lidco/workflows/*.md |
| 925 | Model Aliases | src/lidco/llm/model_aliases.py | Short names for models |
| 926 | CLI Commands | src/lidco/cli/commands/q162_cmds.py | /btw, /plan-mode, /workflows, /model-alias |

Tests: tests/unit/test_q162/ — 90 tests

## Q163 — Tree-sitter Multi-Language AST Support (tasks 927–931) ✅

**Theme:** Tree-sitter powered AST for universal repo maps, cross-language indexing, language-aware linting.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 927 | Tree-sitter Language Pack | src/lidco/ast/treesitter_parser.py | Parse any language; regex fallback |
| 928 | Universal Symbol Extractor | src/lidco/ast/universal_extractor.py | Functions/classes/imports via tree-sitter |
| 929 | Multi-Language Repo Map | src/lidco/ast/repo_map.py | Ranked by context relevance |
| 930 | AST-Aware Lint-After-Edit | src/lidco/ast/ast_linter.py | Detect syntax errors before linters |
| 931 | CLI Commands | src/lidco/cli/commands/q163_cmds.py | /ast, /repomap, /ast-lint |

Tests: tests/unit/test_q163/ — 89 tests

## Q164 — OS-Level Sandboxing & Secure Execution (tasks 932–936) ✅

**Theme:** Filesystem/network restrictions at process level for autonomous safety.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 932 | Sandbox Policy Engine | src/lidco/sandbox/policy.py | Allowed/denied paths, network whitelist |
| 933 | Filesystem Jail | src/lidco/sandbox/fs_jail.py | Block escapes (symlinks, ../) |
| 934 | Network Restrictor | src/lidco/sandbox/net_restrictor.py | Domain allowlist, block by default |
| 935 | Process Sandbox Runner | src/lidco/sandbox/runner.py | Execute with restrictions |
| 936 | CLI Commands | src/lidco/cli/commands/q164_cmds.py | /sandbox |

Tests: tests/unit/test_q164/ — 77 tests

## Q165 — Conversation Forking & Session Branching (tasks 937–941) ✅

**Theme:** /fork + session branching for experimentation without losing main context.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 937 | Session Branch Manager | src/lidco/session/branch_manager.py | Create/switch/merge/delete branches |
| 938 | Branch Diff Engine | src/lidco/session/branch_diff.py | Conversation diff, file diff |
| 939 | Branch Merge | src/lidco/session/branch_merge.py | Conflict resolution |
| 940 | /loop Recurring Command | src/lidco/session/loop_runner.py | Run on interval (min 30s) |
| 941 | CLI Commands | src/lidco/cli/commands/q165_cmds.py | /fork, /branch, /loop |

Tests: tests/unit/test_q165/ — 74 tests

## Q166 — Flow-Aware Context & Smart Suggestions (tasks 942–946) ✅

**Theme:** Windsurf-style flow tracking — infer intent from actions, provide proactive suggestions.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 942 | Action Tracker | src/lidco/flow/action_tracker.py | Track edits, commands, errors |
| 943 | Intent Inferrer | src/lidco/flow/intent_inferrer.py | Infer current goal from patterns |
| 944 | Proactive Hint Engine | src/lidco/flow/hint_engine.py | Contextual suggestions |
| 945 | Flow State Manager | src/lidco/flow/state_manager.py | Persistent flow state |
| 946 | CLI Commands | src/lidco/cli/commands/q166_cmds.py | /flow, /intent |

Tests: tests/unit/test_q166/ — 69 tests

## Q167 — MCP Marketplace & Plugin Discovery (tasks 947–951) ✅

**Theme:** Browse, install, manage MCP servers/plugins with trust verification.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 947 | Plugin Manifest Schema | src/lidco/marketplace/manifest.py | Name, version, trust_level, capabilities |
| 948 | Plugin Discovery | src/lidco/marketplace/discovery.py | Search/browse, version compatibility |
| 949 | Plugin Installer | src/lidco/marketplace/installer.py | Install/uninstall/update, rollback |
| 950 | Trust & Security Gate | src/lidco/marketplace/trust_gate.py | Verified/community/unverified levels |
| 951 | CLI Commands | src/lidco/cli/commands/q167_cmds.py | /marketplace, /trust |

Tests: tests/unit/test_q167/ — 88 tests

## Q168 — Claude Code Plugin Compatibility Layer (tasks 952–956) ✅

**Theme:** Run Claude Code plugins in LIDCO without modification.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 952 | Claude Code Manifest Parser | src/lidco/compat/cc_manifest.py | Parse manifest.json → LIDCO format |
| 953 | MCP Config Adapter | src/lidco/compat/cc_mcp_adapter.py | Read .claude/settings.json mcpServers |
| 954 | CLAUDE.md Convention Support | src/lidco/compat/cc_conventions.py | Read CLAUDE.md as project instructions |
| 955 | Hooks Adapter | src/lidco/compat/cc_hooks.py | Convert CC hooks to LIDCO events |
| 956 | CLI Commands | src/lidco/cli/commands/q168_cmds.py | /cc-import, /cc-compat, /cc-hooks |

Tests: tests/unit/test_q168/ — 81 tests

## Q169 — Cloud Background Agents & Async PR Pipeline (tasks 957–961) ✅

**Theme:** Spawn sandboxed background agents that produce PRs autonomously.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 957 | Background Agent Spawner | src/lidco/cloud/agent_spawner.py | Isolated worktree; status polling |
| 958 | Agent Status Tracker | src/lidco/cloud/status_tracker.py | Track running/completed/failed |
| 959 | PR Assembler | src/lidco/cloud/pr_assembler.py | Branch + PR creation via git |
| 960 | Agent Pool Manager | src/lidco/cloud/pool_manager.py | Up to N agents in parallel |
| 961 | CLI Commands | src/lidco/cli/commands/q169_cmds.py | /agent-run, /agent-status, /agent-list, /agent-cancel |

Tests: tests/unit/test_q169/ — 80 tests

## Q170 — Smart Clipboard & Browser Bridge (tasks 962–966) ✅

**Theme:** Copy/paste mode + @browser bridge for web dev workflows.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 962 | Clipboard Manager | src/lidco/bridge/clipboard.py | Read/write clipboard, history |
| 963 | Browser Page Reader | src/lidco/bridge/page_reader.py | Fetch URL, extract text/code |
| 964 | Web Context Provider | src/lidco/bridge/web_context.py | @url mentions in prompts |
| 965 | Copy/Paste Mode | src/lidco/bridge/paste_mode.py | Roundtrip bridge for web LLM |
| 966 | CLI Commands | src/lidco/cli/commands/q170_cmds.py | /copy, /paste, /browse, /clipboard |

Tests: tests/unit/test_q170/ — 81 tests

## Q171 — Bare Mode & Scripting API (tasks 967–971) ✅

**Theme:** Embeddable Python library for CI/CD + ultra-lightweight mode for scripted calls.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 967 | Bare Mode Runner | src/lidco/modes/bare_mode.py | Skip hooks/LSP/plugins for speed |
| 968 | Python Library API | src/lidco/api/library.py | lidco.run(), lidco.edit(), lidco.ask() |
| 969 | Batch Prompt Runner | src/lidco/api/batch_runner.py | Multiple prompts, parallel, JSON output |
| 970 | CI/CD Integration Helpers | src/lidco/api/ci_helpers.py | GitHub Actions, GitLab CI helpers |
| 971 | CLI Commands | src/lidco/cli/commands/q171_cmds.py | /bare-mode, /batch, /ci-report |

Tests: tests/unit/test_q171/ — 65 tests

## Q172 — Embeddings-Powered Semantic Retrieval (tasks 972–976) ✅

**Theme:** Local embeddings, vector storage, hybrid retrieval for context-aware prompts.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 972 | Embedding Generator | src/lidco/embeddings/generator.py | Chunk by function/class; local or API |
| 973 | Vector Store | src/lidco/embeddings/vector_store.py | SQLite-backed cosine similarity |
| 974 | Hybrid Retriever | src/lidco/embeddings/retriever.py | Vector + BM25 + recency; RRF re-rank |
| 975 | Auto-Context Injector | src/lidco/embeddings/auto_context.py | Top-N snippets per prompt |
| 976 | CLI Commands | src/lidco/cli/commands/q172_cmds.py | /index, /search, /context-sources |

Tests: tests/unit/test_q172/ — 70 tests

## Q173 — Test Amplification & Mutation Testing (tasks 977–981) ✅

**Theme:** Mutation testing, property-based tests, coverage gaps, change-aware test priority.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 977 | Mutation Test Runner | src/lidco/testing/mutation_runner.py | Boundary/negate/remove mutations |
| 978 | Property-Based Test Generator | src/lidco/testing/property_gen.py | Hypothesis strategies from signatures |
| 979 | Coverage Gap Analyzer | src/lidco/testing/coverage_gap.py | Rank untested code by risk |
| 980 | Change-Aware Test Prioritizer | src/lidco/testing/test_prioritizer.py | Rank tests by regression likelihood |
| 981 | CLI Commands | src/lidco/cli/commands/q173_cmds.py | /mutate, /proptest, /coverage-gaps, /test-order |

Tests: tests/unit/test_q173/ — 99 tests

## Q174 — Parallel Exploration & Best-Pick Agent (tasks 982–986) ✅

**Theme:** Try multiple approaches in isolated worktrees, evaluate, merge the winner.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 982 | Exploration Spawner | src/lidco/explore/spawner.py | N variant prompts in worktrees |
| 983 | Result Evaluator | src/lidco/explore/evaluator.py | Score by tests/lint/diff/complexity |
| 984 | Diff Presenter | src/lidco/explore/diff_presenter.py | Side-by-side comparison |
| 985 | Auto-Merge Winner | src/lidco/explore/merger.py | Apply winner, clean up branches |
| 986 | CLI Commands | src/lidco/cli/commands/q174_cmds.py | /explore, /explore-status, /explore-pick, /explore-diff |

Tests: tests/unit/test_q174/ — 90 tests

## Q175 — Real-Time File Awareness & Edit Coordination (tasks 987–991) ✅

**Theme:** Detect external file changes, reconcile context, prevent stale edits.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 987 | Live File Monitor | src/lidco/awareness/file_monitor.py | Mtime polling, debounced events |
| 988 | Context Reconciler | src/lidco/awareness/reconciler.py | Diff + update context on change |
| 989 | Stale Edit Guard | src/lidco/awareness/stale_guard.py | Verify file unchanged before edit |
| 990 | Git Event Listener | src/lidco/awareness/git_listener.py | Branch switch/pull/merge detection |
| 991 | CLI Commands | src/lidco/cli/commands/q175_cmds.py | /watch-files, /changes, /refresh-context, /conflicts |

Tests: tests/unit/test_q175/ — 99 tests

---

## Q176 — Input Preprocessing & Context Enrichment (tasks 992–996) ✅

**Theme:** Smart prompt rewriting and auto-context — classify intent, rewrite vague prompts, auto-attach relevant files, compress context before LLM.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 992 | Intent Classifier | src/lidco/input/intent_classifier.py | Classify prompt intent (edit, ask, debug, generate, refactor, explain); confidence score; suggest slash command if better fit |
| 993 | Prompt Rewriter | src/lidco/input/prompt_rewriter.py | Expand vague prompts ("fix it" → "fix the TypeError in utils.py line 42"); inject error context from last traceback |
| 994 | Auto-Attach Resolver | src/lidco/input/auto_attach.py | Analyze prompt for implicit file references; attach ranked by relevance; respect token budget |
| 995 | Context Compressor | src/lidco/input/context_compressor.py | Summarize large files; keep signatures+docstrings, drop irrelevant bodies; configurable ratio |
| 996 | CLI Commands | src/lidco/cli/commands/q176_cmds.py | /rewrite, /classify, /auto-attach, /compress-context |

Tests: tests/unit/test_q176/ — ~30 tests

## Q177 — Diff Visualization & Change Intelligence (tasks 997–1001) ✅

**Theme:** Rich diff rendering and change explanation — semantic summaries, impact heatmaps, before/after previews.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 997 | Rich Diff Renderer | src/lidco/ui/diff_renderer.py | Syntax-highlighted side-by-side/unified diffs; word-level highlighting; fold unchanged |
| 998 | Change Explainer | src/lidco/ui/change_explainer.py | Natural-language diff summary; group changes by semantic intent |
| 999 | Impact Heatmap | src/lidco/ui/impact_heatmap.py | Color-code affected files/functions by risk (coverage × complexity) |
| 1000 | Before/After Preview | src/lidco/ui/before_after.py | Toggle view; accept/reject individual hunks; dry-run mode |
| 1001 | CLI Commands | src/lidco/cli/commands/q177_cmds.py | /rich-diff, /explain-changes, /heatmap, /preview |

Tests: tests/unit/test_q177/ — ~30 tests

## Q178 — Error Recovery & Self-Healing (tasks 1002–1006) ✅

**Theme:** Crash recovery and graceful degradation — write-ahead journal, state restoration, subsystem health, adaptive retry.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1002 | Crash Journal | src/lidco/resilience/crash_journal.py | Write-ahead log before each tool call; replay or rollback on restart |
| 1003 | State Restorer | src/lidco/resilience/state_restorer.py | Reconstruct session from journal + git + conversation history |
| 1004 | Graceful Degrader | src/lidco/resilience/graceful_degrader.py | Disable failed subsystems with warning; auto-re-enable on health check |
| 1005 | Adaptive Retry | src/lidco/resilience/adaptive_retry.py | Per-endpoint jitter+backoff; learn failure patterns; circuit-break |
| 1006 | CLI Commands | src/lidco/cli/commands/q178_cmds.py | /recover, /health, /retry-stats, /degrade |

Tests: tests/unit/test_q178/ — ~30 tests

## Q179 — Multi-Repo & Monorepo Support (tasks 1007–1011) ✅

**Theme:** Workspace detection, cross-repo search, dep graph across repos, shared config.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1007 | Workspace Detector | src/lidco/workspace/detector.py | Detect nx/turborepo/lerna/cargo/go.work; map package boundaries |
| 1008 | Cross-Repo Search | src/lidco/workspace/cross_search.py | Search across repos; unified results; parallel |
| 1009 | Cross-Repo Dep Graph | src/lidco/workspace/cross_deps.py | Build dep graph; detect circular deps; affected packages from file change |
| 1010 | Shared Config Resolver | src/lidco/workspace/shared_config.py | Inherit parent config; merge with overrides; validate |
| 1011 | CLI Commands | src/lidco/cli/commands/q179_cmds.py | /workspace, /search-all, /cross-deps, /shared-config |

Tests: tests/unit/test_q179/ — ~30 tests

## Q180 — Code Review Intelligence (tasks 1012–1016) ✅

**Theme:** Automated review checklists, style consistency, security patterns, perf anti-patterns.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1012 | Review Checklist Generator | src/lidco/review/checklist_gen.py | Context-aware checklist from diff; customizable rules; Markdown output |
| 1013 | Style Consistency Checker | src/lidco/review/style_checker.py | Learn project style; flag deviations; suggest fixes |
| 1014 | Security Pattern Scanner | src/lidco/review/security_scanner.py | Hardcoded secrets, SQL concat, eval, unsafe deser; OWASP-mapped |
| 1015 | Perf Anti-Pattern Detector | src/lidco/review/perf_detector.py | N+1, unbounded loops, missing pagination, regex in loops |
| 1016 | CLI Commands | src/lidco/cli/commands/q180_cmds.py | /review-checklist, /style-check, /security-scan, /perf-check |

Tests: tests/unit/test_q180/ — 97 tests

## Q181 — Conversation Templates & Workflows (tasks 1017–1021)

**Theme:** Reusable conversation patterns, multi-step recipes, team-shared templates, approval gates.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1017 | Conversation Template | src/lidco/templates/conversation.py | Multi-turn templates with {{variables}}; conditional branches; YAML serialization |
| 1018 | Workflow Recipe Engine | src/lidco/templates/recipe_engine.py | Chain templates into recipes; step dependencies; resume on failure |
| 1019 | Team Template Registry | src/lidco/templates/team_registry.py | Shared repo (local/git); version; import/export; conflict resolution |
| 1020 | Approval Gate | src/lidco/templates/approval_gate.py | Checkpoints in workflows; timeout with default; audit log |
| 1021 | CLI Commands | src/lidco/cli/commands/q181_cmds.py | /template, /recipe, /team-templates, /approve |

Tests: tests/unit/test_q181/ — ~30 tests

## Q182 — Token Economics & Cost Management (tasks 1022–1026)

**Theme:** Per-request budgets, cost alerts, auto model downgrade, batch optimization.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1022 | Budget Enforcer | src/lidco/economics/budget_enforcer.py | Session/daily/monthly budgets; soft warn 80%, hard stop 100%; persist |
| 1023 | Cost Alert Engine | src/lidco/economics/cost_alerts.py | Threshold alerts (dollar, %, spike); console/webhook notification |
| 1024 | Model Downgrade Optimizer | src/lidco/economics/model_optimizer.py | Auto-switch cheaper model for simple tasks; A/B quality tracking |
| 1025 | Batch Request Optimizer | src/lidco/economics/batch_optimizer.py | Detect independent sub-tasks; batch; deduplicate context; report savings |
| 1026 | CLI Commands | src/lidco/cli/commands/q182_cmds.py | /budget, /cost-alerts, /model-optimizer, /batch-stats |

Tests: tests/unit/test_q182/ — ~30 tests

## Q183 — Plugin SDK & Extension API (tasks 1027–1031)

**Theme:** Stable extension points, lifecycle hooks, custom tool registration, plugin scaffold generator.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1027 | Extension Point Registry | src/lidco/sdk/extension_points.py | Named extension points; type-safe hooks; priority; async |
| 1028 | Plugin Lifecycle Manager | src/lidco/sdk/lifecycle.py | Init → activate → deactivate → uninstall; hot-reload |
| 1029 | Custom Tool Builder | src/lidco/sdk/tool_builder.py | Fluent API for new tools; auto-register; validation |
| 1030 | Plugin Scaffold Generator | src/lidco/sdk/scaffold.py | Generate project from template; pyproject.toml, tests, README |
| 1031 | CLI Commands | src/lidco/cli/commands/q183_cmds.py | /sdk, /extensions, /plugin-lifecycle, /tool-builder |

Tests: tests/unit/test_q183/ — ~30 tests
