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

## Q181 — Conversation Templates & Workflows (tasks 1017–1021) ✅

**Theme:** Reusable conversation patterns, multi-step recipes, team-shared templates, approval gates.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1017 | Conversation Template | src/lidco/templates/conversation.py | Multi-turn templates with {{variables}}; conditional branches; YAML serialization |
| 1018 | Workflow Recipe Engine | src/lidco/templates/recipe_engine.py | Chain templates into recipes; step dependencies; resume on failure |
| 1019 | Team Template Registry | src/lidco/templates/team_registry.py | Shared repo (local/git); version; import/export; conflict resolution |
| 1020 | Approval Gate | src/lidco/templates/approval_gate.py | Checkpoints in workflows; timeout with default; audit log |
| 1021 | CLI Commands | src/lidco/cli/commands/q181_cmds.py | /template, /recipe, /team-templates, /approve |

Tests: tests/unit/test_q181/ — 82 tests

## Q182 — Token Economics & Cost Management (tasks 1022–1026) ✅

**Theme:** Per-request budgets, cost alerts, auto model downgrade, batch optimization.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1022 | Budget Enforcer | src/lidco/economics/budget_enforcer.py | Session/daily/monthly budgets; soft warn 80%, hard stop 100%; persist |
| 1023 | Cost Alert Engine | src/lidco/economics/cost_alerts.py | Threshold alerts (dollar, %, spike); console/webhook notification |
| 1024 | Model Downgrade Optimizer | src/lidco/economics/model_optimizer.py | Auto-switch cheaper model for simple tasks; A/B quality tracking |
| 1025 | Batch Request Optimizer | src/lidco/economics/batch_optimizer.py | Detect independent sub-tasks; batch; deduplicate context; report savings |
| 1026 | CLI Commands | src/lidco/cli/commands/q182_cmds.py | /budget, /cost-alerts, /model-optimizer, /batch-stats |

Tests: tests/unit/test_q182/ — 51 tests

## Q183 — Plugin SDK & Extension API (tasks 1027–1031) ✅

**Theme:** Stable extension points, lifecycle hooks, custom tool registration, plugin scaffold generator.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1027 | Extension Point Registry | src/lidco/sdk/extension_points.py | Named extension points; type-safe hooks; priority; async |
| 1028 | Plugin Lifecycle Manager | src/lidco/sdk/lifecycle.py | Init → activate → deactivate → uninstall; hot-reload |
| 1029 | Custom Tool Builder | src/lidco/sdk/tool_builder.py | Fluent API for new tools; auto-register; validation |
| 1030 | Plugin Scaffold Generator | src/lidco/sdk/scaffold.py | Generate project from template; pyproject.toml, tests, README |
| 1031 | CLI Commands | src/lidco/cli/commands/q183_cmds.py | /sdk, /extensions, /plugin-lifecycle, /tool-builder |

Tests: tests/unit/test_q183/ — 50 tests

---

# Phase 8 — Claude Code Feature Parity (Q184–Q208)

> Based on analysis of Claude Code source (anthropics/claude-code, claw-code port, CHANGELOG v2.1.88).
> Goal: implement all major Claude Code subsystems as native LIDCO modules.

## Q184 — Plugin Marketplace & Discovery (tasks 1032–1036) ✅

**Theme:** Full plugin marketplace — manifest format, discovery, install/uninstall, registry index. (Claude Code parity: `.claude-plugin/marketplace.json`)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1032 | Plugin Manifest | src/lidco/marketplace/manifest.py | PluginManifest dataclass; MarketplaceIndex search/filter; YAML/JSON load/save |
| 1033 | Plugin Discovery | src/lidco/marketplace/discovery.py | PluginDiscovery search by query/category; SourceType (GIT/NPM/LOCAL); resolve_source |
| 1034 | Plugin Installer | src/lidco/marketplace/installer.py | Install/uninstall/update; InstalledPlugin tracking; integrity verification |
| 1035 | Marketplace Registry | src/lidco/marketplace/registry.py | MarketplaceRegistry register/unregister/search; export/import index; categories |
| 1036 | CLI Commands | src/lidco/cli/commands/q184_cmds.py | /marketplace, /marketplace-search, /marketplace-install, /marketplace-uninstall |

Tests: tests/unit/test_q184/ — 113 tests

## Q185 — 7-Phase Feature Development Workflow (tasks 1037–1041) ✅

**Theme:** Structured feature implementation — Discovery → Exploration → Clarification → Architecture → Implementation → Review → Summary. (Claude Code parity: feature-dev plugin)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1037 | Phase Definitions | src/lidco/feature_dev/phases.py | Phase enum (7 phases); PhaseResult; PhaseConfig with timeout/max_agents |
| 1038 | Feature Dev Workflow | src/lidco/feature_dev/workflow.py | FeatureDevWorkflow run_phase/run_all/skip; phase handlers; history tracking |
| 1039 | Code Explorer Agent | src/lidco/feature_dev/explorer.py | CodeExplorerAgent explore/trace_execution/map_architecture/find_similar |
| 1040 | Code Architect Agent | src/lidco/feature_dev/architect.py | CodeArchitectAgent propose/recommend/generate_blueprint; trade-off analysis |
| 1041 | CLI Commands | src/lidco/cli/commands/q185_cmds.py | /feature-dev, /explore-code, /architect, /feature-summary |

Tests: tests/unit/test_q185/ — 99 tests

## Q186 — Multi-Agent PR Review Pipeline (tasks 1042–1046) ✅

**Theme:** 6 specialized review agents running in parallel — comments, tests, error handling, types, quality, simplification. (Claude Code parity: pr-review-toolkit plugin)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1042 | Review Pipeline | src/lidco/review/pipeline.py | ReviewPipeline builder; sequential/parallel modes; ReviewReport severity-categorized |
| 1043 | Comment & Test Analyzers | src/lidco/review/agents/comment_analyzer.py | CommentAnalyzer (stale/TODO); PRTestAnalyzer (coverage gaps, test quality) |
| 1044 | Failure & Type Hunters | src/lidco/review/agents/failure_hunter.py | SilentFailureHunter (bare except, swallowed); TypeDesignAnalyzer (Any, missing types) |
| 1045 | Quality & Simplifier | src/lidco/review/agents/quality.py | CodeQualityReviewer (nesting, magic numbers); CodeSimplifier (dead code, patterns) |
| 1046 | CLI Commands | src/lidco/cli/commands/q186_cmds.py | /review-pipeline, /review-comments, /review-failures, /review-types |

Tests: tests/unit/test_q186/ — 95 tests

## Q187 — Hookify Dynamic Rule Engine (tasks 1047–1051) ✅

**Theme:** Conversation-analysis-based rule generation — detect dangerous patterns, auto-generate warn/block rules. (Claude Code parity: hookify plugin)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1047 | Rule Definitions | src/lidco/hookify/rule.py | HookifyRule (frozen); EventType (BASH/FILE/STOP/PROMPT/ALL); ActionType (WARN/BLOCK) |
| 1048 | Rule Engine | src/lidco/hookify/engine.py | HookifyEngine evaluate/is_blocked/get_warnings; immutable add_rule/remove_rule |
| 1049 | Conversation Analyzer | src/lidco/hookify/analyzer.py | ConversationAnalyzer detect_patterns/suggest_rules; risk-level scoring |
| 1050 | Rule Persistence | src/lidco/hookify/persistence.py | YAML frontmatter + markdown; load_all/save/delete; hot-reload |
| 1051 | CLI Commands | src/lidco/cli/commands/q187_cmds.py | /hookify, /hookify-list, /hookify-analyze, /hookify-test |

Tests: tests/unit/test_q187/ — 83 tests

## Q188 — Autonomous Loop with Completion Promises (tasks 1052–1056) ✅

**Theme:** Ralph-loop pattern — autonomous iteration with honest completion verification, stuck detection, progress tracking. (Claude Code parity: ralph-wiggum plugin)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1052 | Loop Configuration | src/lidco/autonomous/loop_config.py | LoopConfig (frozen); LoopState enum (6 states); IterationResult |
| 1053 | Loop Runner | src/lidco/autonomous/loop_runner.py | AutonomousLoopRunner run/pause/resume/cancel; completion promise checking; timeout |
| 1054 | Promise Verifier | src/lidco/autonomous/promise_verifier.py | PromiseVerifier verify/extract_claims/check_honesty; flip-flop/stuck detection |
| 1055 | Progress Tracker | src/lidco/autonomous/progress_tracker.py | LoopProgressTracker (immutable); is_stuck/progress_rate/estimated_remaining |
| 1056 | CLI Commands | src/lidco/cli/commands/q188_cmds.py | /loop-run, /loop-status, /loop-cancel, /loop-history |

Tests: tests/unit/test_q188/ — 85 tests

## Q189 — Remote Control & Session Bridge (tasks 1057–1061) ✅

**Theme:** Bridge CLI sessions to web/mobile — WebSocket server, session sync, deep links. (Claude Code parity: /remote-control, mobile bridge)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1057 | Remote Session Server | src/lidco/remote/session_server.py | WebSocket server; session attach/detach; auth token; message relay |
| 1058 | Mobile Bridge | src/lidco/remote/mobile_bridge.py | QR code pairing; push notifications; permission relay to phone |
| 1059 | Session Sync | src/lidco/remote/session_sync.py | Bi-directional sync; conflict resolution; latency compensation |
| 1060 | Deep Link Handler | src/lidco/remote/deep_links.py | lidco://open?q=...; session resume; prompt injection; URI parser |
| 1061 | CLI Commands | src/lidco/cli/commands/q189_cmds.py | /remote-control, /mobile, /deep-link, /session-server |

Tests: tests/unit/test_q189/ — 91 tests

## Q190 — LSP Integration & Code Intelligence (tasks 1062–1066) ✅

**Theme:** Language Server Protocol client — go-to-definition, references, hover, diagnostics. (Claude Code parity: LSPTool)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1062 | LSP Client | src/lidco/lsp/client.py | Start/stop language servers; JSON-RPC over stdio; capability negotiation |
| 1063 | Definition Resolver | src/lidco/lsp/definitions.py | Go-to-definition; go-to-type-definition; go-to-implementation; multi-root |
| 1064 | Reference Finder | src/lidco/lsp/references.py | Find all references; rename symbol; call hierarchy; workspace symbols |
| 1065 | Diagnostics Collector | src/lidco/lsp/diagnostics.py | Collect errors/warnings from LSP; real-time update; severity mapping |
| 1066 | CLI Commands | src/lidco/cli/commands/q190_cmds.py | /lsp-start, /goto-def, /find-refs, /diagnostics |

Tests: tests/unit/test_q190/ — 114 tests

## Q191 — Multi-Edit & Batch File Operations (tasks 1067–1071) ✅

**Theme:** Multiple edits in single atomic operation — Claude Code's MultiEdit tool. (Claude Code parity: MultiEdit tool)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1067 | Multi-Edit Engine | src/lidco/editing/multi_edit.py | MultiEdit apply multiple edits to same file atomically; conflict detection; rollback |
| 1068 | Batch File Writer | src/lidco/editing/batch_writer.py | Write/create/delete multiple files atomically; dry-run; transaction log |
| 1069 | Edit Planner | src/lidco/editing/edit_planner.py | Plan edits across files; dependency ordering; parallel-safe grouping |
| 1070 | Atomic Transaction | src/lidco/editing/transaction.py | FileTransaction context manager; commit/rollback; journal for crash recovery |
| 1071 | CLI Commands | src/lidco/cli/commands/q191_cmds.py | /multi-edit, /batch-write, /edit-plan, /transaction |

Tests: tests/unit/test_q191/ — 86 tests

## Q192 — Output Styles & Display Modes (tasks 1072–1076) ✅

**Theme:** Configurable output personalities — explanatory, learning, brief, custom. (Claude Code parity: outputStyles subsystem)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1072 | Style Registry | src/lidco/output/style_registry.py | OutputStyle protocol; register/get/list styles; default/explanatory/learning/brief |
| 1073 | Explanatory Mode | src/lidco/output/explanatory.py | Inject educational context; why-not-just explanations; alternative approaches |
| 1074 | Learning Mode | src/lidco/output/learning.py | Interactive mode; quiz on decisions; encourage contribution; progressive hints |
| 1075 | Custom Formatter | src/lidco/output/formatter.py | Template-based output; Markdown/JSON/plain; color themes; width-aware |
| 1076 | CLI Commands | src/lidco/cli/commands/q192_cmds.py | /output-style, /explanatory, /learning, /brief |

Tests: tests/unit/test_q192/ — 98 tests

## Q193 — Vim Mode & Advanced Keybindings (tasks 1077–1081) ✅

**Theme:** Vim normal/insert mode in REPL, rebindable keys, chord sequences. (Claude Code parity: vim/, keybindings/ subsystems)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1077 | Vim Mode Engine | src/lidco/input/vim_mode.py | Normal/insert/visual modes; hjkl movement; dd/yy/p; /search; status indicator |
| 1078 | Keybinding Registry | src/lidco/input/keybindings.py | Rebindable keys; chord sequences (Ctrl+X Ctrl+E); conflict detection; JSON config |
| 1079 | Input Preprocessor | src/lidco/input/preprocessor.py | Macro recording/replay; abbreviations; input history with fuzzy search |
| 1080 | REPL Enhancements | src/lidco/input/repl_enhance.py | Multi-line editing; syntax highlight in input; auto-indent; bracket matching |
| 1081 | CLI Commands | src/lidco/cli/commands/q193_cmds.py | /vim, /keybindings, /macro, /repl-config |

Tests: tests/unit/test_q193/ — 106 tests

## Q194 — Real-Time Cost Tracking & Budget Hooks (tasks 1082–1086) ✅

**Theme:** Per-tool-call cost tracking, real-time dashboard, budget enforcement hooks. (Claude Code parity: costHook, cost-tracker)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1082 | Cost Hook | src/lidco/economics/cost_hook.py | Hook into every LLM call; compute cost from token counts; per-model pricing |
| 1083 | Cost Dashboard | src/lidco/economics/cost_dashboard.py | Real-time cost display; per-tool breakdown; session/daily/weekly trends |
| 1084 | Budget Hook | src/lidco/economics/budget_hook.py | Pre-call budget check; soft warn at 80%; hard block at 100%; override |
| 1085 | Cost Projector | src/lidco/economics/cost_projector.py | Estimate remaining cost; predict session total; alert on anomalies |
| 1086 | CLI Commands | src/lidco/cli/commands/q194_cmds.py | /cost-track, /cost-dashboard, /budget-hook, /cost-project |

Tests: tests/unit/test_q194/ — 97 tests

## Q195 — Prompt Caching & Token Optimization (tasks 1087–1091) ✅

**Theme:** System-level prompt cache, cache warming, breakpoint optimization. (Claude Code parity: prompt caching system)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1087 | Prompt Cache | src/lidco/cache/prompt_cache.py | Hash-based cache; TTL; max size; hit/miss stats; system-prompt dedup |
| 1088 | Cache Warmer | src/lidco/cache/cache_warmer.py | Pre-warm cache on session start; predict next queries; background refresh |
| 1089 | Breakpoint Optimizer | src/lidco/cache/breakpoint_optimizer.py | Find optimal cache breakpoints; minimize re-computation; adaptive placement |
| 1090 | Token Compressor | src/lidco/cache/token_compressor.py | Compress tool results; summarize repeated patterns; dedup file reads |
| 1091 | CLI Commands | src/lidco/cli/commands/q195_cmds.py | /cache-stats, /cache-warm, /cache-clear, /token-optimize |

Tests: tests/unit/test_q195/ — 94 tests

## Q196 — Agent Summary & Magic Docs (tasks 1092–1096) ✅

**Theme:** Auto-summarize agent work, generate documentation from code. (Claude Code parity: AgentSummary, MagicDocs services)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1092 | Agent Summarizer | src/lidco/agents/summarizer.py | Summarize agent actions; key decisions; files modified; time/cost; Markdown |
| 1093 | Magic Docs Generator | src/lidco/docgen/magic_docs.py | Auto-generate docs from code; function signatures; usage examples; API ref |
| 1094 | README Generator | src/lidco/docgen/readme_gen.py | Auto-README from project structure; badges; install; usage; contributing |
| 1095 | Doc Sync Engine | src/lidco/docgen/doc_sync.py | Watch code changes; auto-update docs; flag stale docs; diff detection |
| 1096 | CLI Commands | src/lidco/cli/commands/q196_cmds.py | /agent-summary, /magic-docs, /readme-gen, /doc-sync |

Tests: tests/unit/test_q196/ — 99 tests

## Q197 — Prompt Suggestion & Speculation (tasks 1097–1101) ✅

**Theme:** Predict next prompts, auto-complete suggestions, prompt history analysis. (Claude Code parity: PromptSuggestion service)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1097 | Suggestion Engine | src/lidco/prompts/suggestion_engine.py | Context-aware prompt suggestions; ranked by relevance; recent actions as input |
| 1098 | Prompt Speculator | src/lidco/prompts/speculator.py | Predict likely next query; pre-fetch context; speculative execution |
| 1099 | History Analyzer | src/lidco/prompts/history_analyzer.py | Analyze prompt patterns; frequent workflows; time-of-day patterns |
| 1100 | Auto-Complete | src/lidco/prompts/auto_complete.py | Inline suggestions; Tab to accept; fuzzy matching; command/file/symbol sources |
| 1101 | CLI Commands | src/lidco/cli/commands/q197_cmds.py | /suggest, /speculate, /prompt-history, /auto-complete |

Tests: tests/unit/test_q197/ — 91 tests

## Q198 — Project Onboarding & Init Wizard (tasks 1102–1106) ✅

**Theme:** Guided project setup, CLAUDE.md generation, starter templates. (Claude Code parity: /init, projectOnboardingState)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1102 | Project Detector | src/lidco/onboarding/detector.py | Detect project type (Python/Node/Rust/Go/Java); framework; build system; monorepo |
| 1103 | Init Wizard | src/lidco/onboarding/wizard.py | Interactive /init; questions → config; CLAUDE.md generation; .lidco/ setup |
| 1104 | Template Library | src/lidco/onboarding/templates.py | Starter templates per project type; customizable; Git-sourced; versioned |
| 1105 | Onboarding State | src/lidco/onboarding/state.py | Track onboarding progress; resume interrupted; skip completed steps |
| 1106 | CLI Commands | src/lidco/cli/commands/q198_cmds.py | /init, /onboard, /project-type, /setup-check |

Tests: tests/unit/test_q198/ — 90 tests

## Q199 — Query Engine & Structured Search (tasks 1107–1111) ✅

**Theme:** Structured queries against codebase — SQL-like syntax for code. (Claude Code parity: QueryEngine, query subsystem)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1107 | Query Parser | src/lidco/query/parser.py | Parse structured queries; SELECT symbols WHERE kind=function; filter/sort/limit |
| 1108 | Query Executor | src/lidco/query/executor.py | Execute against symbol index; join across files; aggregate (count, group-by) |
| 1109 | AST Query | src/lidco/query/ast_query.py | XPath-like AST queries; pattern matching; tree traversal predicates |
| 1110 | Query Cache | src/lidco/query/cache.py | Cache query results; invalidate on file change; incremental update |
| 1111 | CLI Commands | src/lidco/cli/commands/q199_cmds.py | /query, /ast-query, /query-cache, /query-explain |

Tests: tests/unit/test_q199/ — 57 tests

## Q200 — Task Management Tools (tasks 1112–1116) ✅

**Theme:** Full task lifecycle — create, track, update, stop background tasks. (Claude Code parity: TaskCreate/Get/List/Update/Stop/Output tools)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1112 | Task Store | src/lidco/tasks/store.py | Persistent task storage; SQLite; status (pending/running/done/failed/cancelled) |
| 1113 | Task Executor | src/lidco/tasks/executor.py | Background execution; timeout; output capture; progress callbacks |
| 1114 | Task Dependencies | src/lidco/tasks/dependencies.py | DAG-based dependency resolution; parallel execution of independent tasks |
| 1115 | Task Output | src/lidco/tasks/output.py | Stream output; tail mode; output filtering; export to file |
| 1116 | CLI Commands | src/lidco/cli/commands/q200_cmds.py | /task-create, /task-list, /task-status, /task-stop, /task-output |

Tests: tests/unit/test_q200/ — 51 tests

## Q201 — Cron & Scheduled Execution (tasks 1117–1121) ✅

**Theme:** Cron-style scheduling — persistent tasks, recurring agents, trigger system. (Claude Code parity: CronCreate/Delete/List tools)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1117 | Cron Parser | src/lidco/cron/parser.py | Parse cron expressions; next_run; human-readable describe; validate |
| 1118 | Cron Scheduler | src/lidco/cron/scheduler.py | Register/unregister jobs; persistent SQLite; missed-run catchup; timezone |
| 1119 | Cron Executor | src/lidco/cron/executor.py | Execute cron jobs; capture output; retry on failure; max_retries |
| 1120 | Trigger System | src/lidco/cron/triggers.py | Event-based triggers (file change, git push, time); compound triggers (AND/OR) |
| 1121 | CLI Commands | src/lidco/cli/commands/q201_cmds.py | /cron-create, /cron-list, /cron-delete, /cron-run |

Tests: tests/unit/test_q201/ — 51 tests

## Q202 — Team Collaboration Tools (tasks 1122–1126) ✅

**Theme:** Shared sessions, collaborative editing, team permissions. (Claude Code parity: TeamCreate/Delete, Agent Teams)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1122 | Team Registry | src/lidco/teams/registry.py | Create/delete teams; member management; roles (owner/editor/viewer) |
| 1123 | Shared Session | src/lidco/teams/shared_session.py | Multi-user session; cursor tracking; turn-based or concurrent; conflict resolve |
| 1124 | Team Permissions | src/lidco/teams/permissions.py | Per-team tool allow/deny; project-scoped; inherit from org |
| 1125 | Team Analytics | src/lidco/teams/analytics.py | Per-member usage; cost allocation; activity timeline; contribution stats |
| 1126 | CLI Commands | src/lidco/cli/commands/q202_cmds.py | /team-create, /team-invite, /team-stats, /team-session |

Tests: tests/unit/test_q202/ — 48 tests

## Q203 — Managed Settings & Enterprise Policy (tasks 1127–1131) ✅

**Theme:** Organization-wide settings enforcement, drop-in policy fragments. (Claude Code parity: managed-settings.json, managed-settings.d/)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1127 | Managed Settings Loader | src/lidco/enterprise/managed_settings.py | Load managed-settings.json; merge managed-settings.d/*.json; precedence rules |
| 1128 | Policy Enforcer | src/lidco/enterprise/policy_enforcer.py | Enforce org policies; deny overrides; audit violations; warn on drift |
| 1129 | Settings Hierarchy | src/lidco/enterprise/settings_hierarchy.py | User → project → org → managed; merge strategy; conflict resolution |
| 1130 | Admin Controls | src/lidco/enterprise/admin_controls.py | Force-disable plugins; deny MCP servers; model restrictions; audit log |
| 1131 | CLI Commands | src/lidco/cli/commands/q203_cmds.py | /managed-settings, /policy, /settings-hierarchy, /admin |

Tests: tests/unit/test_q203/ — 66 tests

## Q204 — Transcript & Session Search (tasks 1132–1136) ✅

**Theme:** Searchable conversation history, transcript mode, session timeline. (Claude Code parity: transcript mode, Ctrl+O, /search)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1132 | Transcript Store | src/lidco/transcript/store.py | Append-only JSONL; index by timestamp/role/tool; full-text search |
| 1133 | Transcript Search | src/lidco/transcript/search.py | Regex + fuzzy search; highlight matches; navigate (n/N); filter by role |
| 1134 | Session Timeline | src/lidco/transcript/timeline.py | Visual timeline; tool calls, edits, errors as events; zoom in/out |
| 1135 | Transcript Export | src/lidco/transcript/export.py | Export to Markdown/JSON/HTML; filter by time range; redact sensitive data |
| 1136 | CLI Commands | src/lidco/cli/commands/q204_cmds.py | /transcript, /transcript-search, /timeline, /transcript-export |

Tests: tests/unit/test_q204/ — 42 tests

## Q205 — Terminal UX & Rendering Engine (tasks 1137–1141) ✅

**Theme:** Flicker-free rendering, virtual scrollback, adaptive terminal detection. (Claude Code parity: ink, screens, CLAUDE_CODE_NO_FLICKER)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1137 | Render Engine | src/lidco/terminal/render_engine.py | Alt-screen mode; virtual scrollback; diff-based redraws; flicker-free |
| 1138 | Terminal Detector | src/lidco/terminal/detector.py | Detect terminal type (iTerm2/WezTerm/Kitty/Ghostty/Windows Terminal); capabilities |
| 1139 | Adaptive Renderer | src/lidco/terminal/adaptive.py | Feature-detect (256-color, truecolor, unicode, sixel); fallback gracefully |
| 1140 | Status Line | src/lidco/terminal/status_line.py | Custom status line; rate limit info; model name; session color; vim mode indicator |
| 1141 | CLI Commands | src/lidco/cli/commands/q205_cmds.py | /render-mode, /terminal-info, /status-line, /color |

Tests: tests/unit/test_q205/ — 63 tests

## Q206 — Computer Use & Visual Automation (tasks 1142–1146) ✅

**Theme:** Mouse/keyboard control, screenshot analysis, visual testing. (Claude Code parity: computer use, screenshot analysis)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1142 | Screen Controller | src/lidco/computer_use/controller.py | Mouse move/click/drag; keyboard type/hotkey; coordinate system; multi-monitor |
| 1143 | Screenshot Analyzer | src/lidco/computer_use/screenshot.py | Capture screen; OCR text extraction; element detection; visual diff |
| 1144 | Visual Test Runner | src/lidco/computer_use/visual_test.py | Screenshot-based assertions; tolerance; baseline management; report |
| 1145 | Automation Script | src/lidco/computer_use/automation.py | Record/replay UI actions; conditional logic; wait for element; retry |
| 1146 | CLI Commands | src/lidco/cli/commands/q206_cmds.py | /screenshot, /click, /type-text, /visual-test |

Tests: tests/unit/test_q206/ — 53 tests

## Q207 — MCP OAuth & Advanced Auth (tasks 1147–1151) ✅

**Theme:** OAuth flows for MCP servers, keychain storage, token management. (Claude Code parity: MCP OAuth, RFC 9728)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1147 | OAuth Flow | src/lidco/auth/oauth_flow.py | Authorization code grant; PKCE; callback server; token exchange |
| 1148 | Token Manager | src/lidco/auth/token_manager.py | Store/refresh tokens; TTL tracking; auto-refresh before expiry; revoke |
| 1149 | Keychain Storage | src/lidco/auth/keychain.py | OS keychain (Windows Credential Vault / macOS Keychain / Secret Service); fallback encrypted file |
| 1150 | MCP Auth Adapter | src/lidco/auth/mcp_auth.py | RFC 9728 resource metadata; step-up auth; per-server credentials; env var injection |
| 1151 | CLI Commands | src/lidco/cli/commands/q207_cmds.py | /oauth-login, /tokens, /keychain, /mcp-auth |

Tests: tests/unit/test_q207/ — 45 tests

## Q208 — Bootstrap & Migration System (tasks 1152–1156) ✅

**Theme:** Version migrations, system bootstrap, deferred initialization. (Claude Code parity: bootstrap, migrations, setup subsystems)

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1152 | Migration Runner | src/lidco/migrations/runner.py | Versioned migrations; up/down; dry-run; rollback; migration history |
| 1153 | Bootstrap Manager | src/lidco/bootstrap/manager.py | System init sequence; dependency ordering; health checks; retry on failure |
| 1154 | Deferred Initializer | src/lidco/bootstrap/deferred.py | Lazy module init; register dependencies; resolve on first use; circular detection |
| 1155 | Setup Wizard | src/lidco/bootstrap/setup_wizard.py | First-run setup; API key config; model selection; preferences; test connection |
| 1156 | CLI Commands | src/lidco/cli/commands/q208_cmds.py | /migrate, /bootstrap, /setup, /doctor |

Tests: tests/unit/test_q208/ — 52 tests

---

# Phase 9 — Advanced Intelligence & Ecosystem (Q209–Q218)

> Goal: deep code understanding, AI pair programming, project analytics, smart refactoring, documentation/testing/security/performance intelligence, collaboration, ecosystem integration.

## Q209 — Code Understanding & Semantic Search (tasks 1157–1161) ✅

**Theme:** Deep semantic code search, intent understanding, natural language queries over codebase.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1157 | Semantic Code Search | src/lidco/understanding/semantic_search.py | TF-IDF + token similarity index; NL queries; ranked results; file/symbol/snippet scope filters |
| 1158 | Intent Classifier | src/lidco/understanding/intent_classifier.py | Classify queries (find, explain, refactor, fix, generate); confidence scoring; multi-intent; fallback routing |
| 1159 | Code Query Engine | src/lidco/understanding/query_engine.py | NL-to-AST query translation; "find all functions that call X"; structural pattern matching |
| 1160 | Context Assembler | src/lidco/understanding/context_assembler.py | Auto-gather relevant files; dependency-aware expansion; token budget respect; relevance scoring |
| 1161 | CLI Commands | src/lidco/cli/commands/q209_cmds.py | /semantic-search, /intent, /code-query, /context-assemble |

Tests: tests/unit/test_q209/ — 56 tests

## Q210 — AI Pair Programming (tasks 1162–1166) ✅

**Theme:** Collaborative editing, suggestion streams, inline code explanation and completion.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1162 | Suggestion Stream | src/lidco/pairing/suggestion_stream.py | Real-time suggestions; debounced LLM calls; diff-based patches; accept/reject/modify flow |
| 1163 | Code Explainer | src/lidco/pairing/code_explainer.py | Explain code at chosen detail level (brief/detailed/ELI5); per-line annotations; complexity notes |
| 1164 | Collaborative Editor | src/lidco/pairing/collaborative_editor.py | Shared editing session; cursor tracking; conflict resolution; operation transform; undo per participant |
| 1165 | Completion Provider | src/lidco/pairing/completion_provider.py | Context-aware multi-line completions; fill-in-middle; signature help; import suggestions |
| 1166 | CLI Commands | src/lidco/cli/commands/q210_cmds.py | /pair, /explain-code, /suggest, /complete |

Tests: tests/unit/test_q210/ — 54 tests

## Q211 — Project Analytics & Health Dashboard (tasks 1167–1171) ✅

**Theme:** Codebase health metrics, technical debt tracking, complexity analysis, trend monitoring.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1167 | Health Scorer | src/lidco/project_analytics/health_scorer.py | Composite health score (0-100); weighted dimensions (complexity, coverage, debt, churn); trend |
| 1168 | Tech Debt Tracker | src/lidco/project_analytics/debt_tracker.py | TODO/FIXME/HACK markers; remediation cost estimate; priority ranking; per-module breakdown |
| 1169 | Complexity Analyzer | src/lidco/project_analytics/complexity_analyzer.py | Cyclomatic + cognitive complexity; halstead metrics; maintainability index; hotspots |
| 1170 | Churn Analyzer | src/lidco/project_analytics/churn_analyzer.py | Git log analysis; file change frequency; author distribution; bug-prone file detection |
| 1171 | CLI Commands | src/lidco/cli/commands/q211_cmds.py | /health-score, /tech-debt, /complexity, /churn |

Tests: tests/unit/test_q211/ — 50 tests

## Q212 — Smart Refactoring (tasks 1172–1176) ✅

**Theme:** AI-powered refactoring suggestions, extract method/class, rename propagation.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1172 | Refactoring Detector | src/lidco/smart_refactor/detector.py | Detect long methods, large classes, feature envy, data clumps; confidence; suggested refactoring type |
| 1173 | Extract Engine | src/lidco/smart_refactor/extract_engine.py | Extract method/class/variable from selection; parameter object |
| 1174 | Rename Propagator | src/lidco/smart_refactor/rename_propagator.py | Cross-file rename; string literal refs; import updates; docstring updates; preview diff; rollback |
| 1175 | Inline Engine | src/lidco/smart_refactor/inline_engine.py | Inline variable/method/constant; dead parameter removal; simplify conditionals |
| 1176 | CLI Commands | src/lidco/cli/commands/q212_cmds.py | /detect-refactor, /extract, /rename-symbol, /inline |

Tests: tests/unit/test_q212/ — 57 tests

## Q213 — Documentation Intelligence (tasks 1177–1181) ✅

**Theme:** Auto-generate docs from code, API reference builder, changelog automation.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1177 | Docstring Generator | src/lidco/doc_intel/docstring_gen.py | Generate/update docstrings; Google/NumPy/Sphinx styles; param types; examples |
| 1178 | API Reference Builder | src/lidco/doc_intel/api_reference.py | Scan package; build structured API docs; group by module; Markdown output |
| 1179 | Changelog Automator | src/lidco/doc_intel/changelog_auto.py | Parse git commits; group by type; Keep-a-Changelog format; link PRs; version bumps |
| 1180 | Usage Example Miner | src/lidco/doc_intel/example_miner.py | Find examples in tests/codebase; rank by clarity; extract minimal snippets |
| 1181 | CLI Commands | src/lidco/cli/commands/q213_cmds.py | /gen-docstring, /api-ref, /changelog, /find-examples |

Tests: tests/unit/test_q213/ — 53 tests

## Q214 — Testing Intelligence (tasks 1182–1186) ✅

**Theme:** AI test case generation, property-based testing, mutation testing integration.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1182 | Test Case Generator | src/lidco/test_intel/case_generator.py | Generate unit tests from function signature + docstring; edge cases; mock external deps |
| 1183 | Property Test Builder | src/lidco/test_intel/property_builder.py | Hypothesis-style property tests; infer input strategies from types; invariant detection |
| 1184 | Mutation Runner | src/lidco/test_intel/mutation_runner.py | AST-based mutation operators; run tests per mutant; survival report; weak test detection |
| 1185 | Coverage Gap Finder | src/lidco/test_intel/coverage_gap.py | Parse coverage JSON; identify uncovered branches; prioritize by complexity; suggest tests |
| 1186 | CLI Commands | src/lidco/cli/commands/q214_cmds.py | /gen-test, /property-test, /mutate, /coverage-gaps |

Tests: tests/unit/test_q214/ — 76 tests

## Q215 — Security Intelligence (tasks 1187–1191) ✅

**Theme:** Vulnerability scanning, dependency audit, secret detection, SAST.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1187 | Vulnerability Scanner | src/lidco/sec_intel/vuln_scanner.py | OWASP Top 10 patterns; SQL injection, XSS, path traversal; severity rating; fix suggestions |
| 1188 | Dependency Auditor | src/lidco/sec_intel/dep_auditor.py | Parse requirements/pyproject/package.json; advisory DB; CVE lookup; upgrade recommendations |
| 1189 | Secret Detector | src/lidco/sec_intel/secret_detector.py | Regex + entropy-based detection; API keys, tokens, passwords; .gitignore-aware |
| 1190 | SAST Engine | src/lidco/sec_intel/sast_engine.py | Taint analysis; source-to-sink paths; configurable rules; suppression comments; SARIF output |
| 1191 | CLI Commands | src/lidco/cli/commands/q215_cmds.py | /vuln-scan, /audit-deps, /detect-secrets, /sast |

Tests: tests/unit/test_q215/ — 79 tests

## Q216 — Performance Intelligence (tasks 1192–1196) ✅

**Theme:** Profiling integration, bottleneck detection, optimization suggestions, memory analysis.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1192 | Profile Analyzer | src/lidco/perf_intel/profile_analyzer.py | Parse cProfile/py-spy output; flame graph data; hot function ranking; compare two profiles |
| 1193 | Bottleneck Detector | src/lidco/perf_intel/bottleneck_detector.py | O(n^2) loops, repeated DB calls, unnecessary copies; pattern library; severity scoring |
| 1194 | Optimization Advisor | src/lidco/perf_intel/optimization_advisor.py | Suggest caching, lazy loading, batch ops; estimate impact; generate refactored snippets |
| 1195 | Memory Analyzer | src/lidco/perf_intel/memory_analyzer.py | Memory leak patterns; large object tracking; circular reference finder; gc pressure estimation |
| 1196 | CLI Commands | src/lidco/cli/commands/q216_cmds.py | /profile-analyze, /bottlenecks, /optimize, /memory-check |

Tests: tests/unit/test_q216/ — 52 tests

## Q217 — Collaboration Hub (tasks 1197–1201) ✅

**Theme:** Shared workspaces, integrated code review, real-time pair sessions, team knowledge sharing.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1197 | Shared Workspace | src/lidco/collab/shared_workspace.py | Room-based; file lock/unlock; conflict detection; participant roster; activity feed |
| 1198 | Review Integration | src/lidco/collab/review_integration.py | Inline comment threads; approve/request-changes; diff navigation; suggestion application |
| 1199 | Pair Session Manager | src/lidco/collab/pair_session.py | Create/join/leave; driver/navigator roles; turn-based control; shared terminal view |
| 1200 | Knowledge Share | src/lidco/collab/knowledge_share.py | Team snippet library; searchable solutions; upvote/tag; auto-suggest from past solutions |
| 1201 | CLI Commands | src/lidco/cli/commands/q217_cmds.py | /collab, /review, /pair-session, /knowledge |

Tests: tests/unit/test_q217/ — 97 tests

## Q218 — Ecosystem Integration (tasks 1202–1206) ✅

**Theme:** GitHub Actions generation, CI/CD pipeline management, deployment automation, cloud integration.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1202 | Actions Generator | src/lidco/ecosystem/actions_generator.py | Generate GH Actions from project analysis; test/lint/build/deploy jobs; matrix strategy; caching |
| 1203 | Pipeline Manager | src/lidco/ecosystem/pipeline_manager.py | Unified CI/CD interface (GH Actions, GitLab CI, CircleCI); status polling; trigger builds |
| 1204 | Deploy Automator | src/lidco/ecosystem/deploy_automator.py | Deploy to Vercel/Netlify/Fly.io; environment management; rollback; health check |
| 1205 | Cloud Connector | src/lidco/ecosystem/cloud_connector.py | AWS/GCP/Azure resource listing; log tailing; serverless invoke; credential management |
| 1206 | CLI Commands | src/lidco/cli/commands/q218_cmds.py | /gen-actions, /pipeline, /deploy, /cloud |

Tests: tests/unit/test_q218/ — 120 tests

---

# Phase 10 — Deep Intelligence & Production Hardening (Q219–Q228)

> Goal: semantic context compression, subagent orchestration, session continuity, streaming protocol, tool result caching, conversation branching, permission escalation, model routing intelligence, background job persistence, API gateway.

## Q219 — Semantic Context Compression (tasks 1207–1211) ✅

**Theme:** Intelligent context summarization when approaching token limits — preserve key info, discard noise.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1207 | Semantic Summarizer | src/lidco/context/semantic_summarizer.py | Summarize conversation turns preserving key decisions; configurable compression ratio; keep code blocks intact |
| 1208 | Priority Scorer | src/lidco/context/priority_scorer.py | Score context entries by recency, relevance, reference count; decay function; user-pinned items immune |
| 1209 | Incremental Compactor | src/lidco/context/incremental_compactor.py | Compact oldest turns first; merge similar tool results; preserve system prompts; watermark tracking |
| 1210 | Compression Strategy | src/lidco/context/compression_strategy.py | Strategy pattern for compression (aggressive/balanced/conservative); pluggable algorithms; stats tracking |
| 1211 | CLI Commands | src/lidco/cli/commands/q219_cmds.py | /compact, /compact-stats, /compact-preview, /context-budget |

Tests: tests/unit/test_q219/ — 63 tests

## Q220 — Subagent Orchestration v2 (tasks 1212–1216) ✅

**Theme:** Advanced agent spawning — dependency graphs, result aggregation, budget splitting, cancellation.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1212 | Agent DAG Runner | src/lidco/agents/dag_runner.py | Execute agents as DAG; parallel independent nodes; propagate results downstream; topological sort |
| 1213 | Result Aggregator | src/lidco/agents/result_aggregator.py | Merge multiple agent results; conflict resolution; ranked by confidence; structured output |
| 1214 | Budget Splitter | src/lidco/agents/budget_splitter.py | Split token/cost budget across subagents; proportional/equal/priority modes; rebalance on completion |
| 1215 | Agent Cancellation | src/lidco/agents/cancellation.py | Cancel running agents; cascading cancel for DAGs; grace period; cleanup hooks |
| 1216 | CLI Commands | src/lidco/cli/commands/q220_cmds.py | /agent-dag, /agent-results, /agent-budget, /agent-cancel |

Tests: tests/unit/test_q220/ — 57 tests

## Q221 — Streaming Protocol & Event System (tasks 1217–1221) ✅

**Theme:** Server-Sent Events protocol for streaming output — tool calls, progress, errors as typed events.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1217 | Event Protocol | src/lidco/streaming/event_protocol.py | Typed events (text, tool_call, tool_result, error, progress); serialize/deserialize; version header |
| 1218 | Stream Multiplexer | src/lidco/streaming/fanout_multiplexer.py | Multiple output streams (terminal, file, websocket); fan-out; back-pressure; reconnect |
| 1219 | Progress Reporter | src/lidco/streaming/progress_reporter.py | Structured progress events; percentage, ETA, phase; nested progress for subagents |
| 1220 | Event Replay | src/lidco/streaming/event_replay.py | Record events to journal; replay for debugging; seek to timestamp; filter by type |
| 1221 | CLI Commands | src/lidco/cli/commands/q221_cmds.py | /stream-mode, /stream-replay, /stream-export, /progress |

Tests: tests/unit/test_q221/ — 59 tests

## Q222 — Tool Result Caching & Dedup (tasks 1222–1226) ✅

**Theme:** Cache and deduplicate tool results — file reads, grep, glob results across conversation turns.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1222 | Tool Result Cache | src/lidco/tools/result_cache.py | Hash-based cache keyed on tool+args; TTL; max size; invalidate on file change; stats |
| 1223 | File Read Cache | src/lidco/tools/file_cache.py | Cache file contents by path+mtime; partial read support; LRU eviction; preload hints |
| 1224 | Dedup Engine | src/lidco/tools/dedup_engine.py | Detect duplicate tool calls in conversation; return cached result; log savings |
| 1225 | Cache Invalidator | src/lidco/tools/cache_invalidator.py | Watch file changes; invalidate affected cache entries; batch invalidation; dependency tracking |
| 1226 | CLI Commands | src/lidco/cli/commands/q222_cmds.py | /tool-cache, /cache-stats, /cache-invalidate, /dedup-stats |

Tests: tests/unit/test_q222/ — 57 tests

## Q223 — Permission Escalation & Audit (tasks 1227–1231)

**Theme:** Fine-grained permission escalation, session-scoped overrides, full audit trail.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1227 | Escalation Manager | src/lidco/permissions/escalation.py | Request elevated permissions; time-limited grants; scope (file/dir/tool); approval workflow |
| 1228 | Session Permissions | src/lidco/permissions/session_perms.py | Per-session permission overrides; sticky decisions; reset on session end; export |
| 1229 | Permission Audit | src/lidco/permissions/audit.py | Log all permission decisions; who/what/when/why; export to JSON; query history |
| 1230 | Trust Levels | src/lidco/permissions/trust_levels.py | Trust tiers (untrusted/basic/elevated/admin); auto-escalate based on history; decay over time |
| 1231 | CLI Commands | src/lidco/cli/commands/q223_cmds.py | /escalate, /session-perms, /perm-audit, /trust-level |

## Q224 — Model Routing Intelligence (tasks 1232–1236)

**Theme:** Smart model selection based on task complexity, cost, latency requirements.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1232 | Complexity Estimator | src/lidco/routing/complexity_estimator.py | Estimate task complexity from prompt; token count, tool hints, code patterns; low/medium/high/expert |
| 1233 | Model Selector | src/lidco/routing/model_selector.py | Select model from complexity + budget + latency; configurable routing rules; fallback chain |
| 1234 | Quality Tracker | src/lidco/routing/quality_tracker.py | Track response quality per model; user satisfaction signals; A/B comparison; regression detection |
| 1235 | Cost-Quality Optimizer | src/lidco/routing/cost_quality.py | Pareto-optimal model selection; budget-constrained quality maximization; historical data |
| 1236 | CLI Commands | src/lidco/cli/commands/q224_cmds.py | /route, /model-stats, /quality-track, /cost-quality |

## Q225 — Background Job Persistence (tasks 1237–1241)

**Theme:** Persist background jobs across restarts — SQLite store, recovery, progress tracking.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1237 | Job Persistence Store | src/lidco/jobs/persistence.py | SQLite-backed job store; serialize/deserialize state; query by status; cleanup old |
| 1238 | Job Recovery | src/lidco/jobs/recovery.py | Detect interrupted jobs on startup; resume or mark failed; checkpoint support |
| 1239 | Job Progress | src/lidco/jobs/progress.py | Structured progress tracking; percentage, message, substeps; persist to DB; query |
| 1240 | Job Scheduler | src/lidco/jobs/scheduler.py | Priority queue; max concurrent; rate limiting; dependency-aware scheduling |
| 1241 | CLI Commands | src/lidco/cli/commands/q225_cmds.py | /jobs, /job-status, /job-recover, /job-clean |

## Q226 — API Gateway & Rate Management (tasks 1242–1246)

**Theme:** Unified API gateway for all LLM providers — rate limiting, key rotation, usage tracking.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1242 | API Gateway | src/lidco/gateway/api_gateway.py | Route requests to providers; load balancing; health checks; circuit breaker per endpoint |
| 1243 | Key Rotator | src/lidco/gateway/key_rotator.py | Multiple API keys per provider; round-robin/least-used rotation; detect exhausted keys |
| 1244 | Usage Tracker | src/lidco/gateway/usage_tracker.py | Per-key usage tracking; daily/monthly aggregation; quota warnings; export to CSV |
| 1245 | Request Queue | src/lidco/gateway/request_queue.py | Queue requests when rate limited; priority ordering; timeout; retry with backoff |
| 1246 | CLI Commands | src/lidco/cli/commands/q226_cmds.py | /gateway, /api-keys, /api-usage, /api-queue |

---

# Phase 11 — Deep Token Budget Management (Q227–Q230)

> Goal: production-grade token budget system — real-time tracking, auto-compaction, adaptive budgets, smart eviction.

## Q227 — Context Window Meter & Model Registry (tasks 1247–1251) ✅

**Theme:** Real-time context window utilization tracking, model-to-window-size registry, usage dashboard.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1247 | Model Context Registry | src/lidco/budget/model_registry.py | Map model names to context window sizes; provider-aware; auto-detect from API; override config |
| 1248 | Context Window Meter | src/lidco/budget/window_meter.py | Track tokens used/remaining per session; per-message accounting; live % utilization; watermark tracking |
| 1249 | Usage Dashboard | src/lidco/budget/usage_dashboard.py | Rich terminal dashboard; breakdown by role (system/user/assistant/tool); trend over turns; peak tracking |
| 1250 | Threshold Alerter | src/lidco/budget/threshold_alerter.py | Configurable thresholds (70%/85%/95%); alert callbacks; escalation levels (info/warn/critical); cooldown |
| 1251 | CLI Commands | src/lidco/cli/commands/q227_cmds.py | /context-meter, /model-limits, /usage-dashboard, /budget-alerts |

Tests: tests/unit/test_q227/ — 64 tests

## Q228 — Auto-Compaction Orchestrator (tasks 1252–1256) ✅

**Theme:** Automatic context compaction triggered by utilization thresholds — strategy selection, orchestration, journal.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1252 | Compaction Orchestrator | src/lidco/budget/compaction_orchestrator.py | Monitor context usage; trigger compaction at thresholds; select strategy based on pressure level; hook into LLM pipeline |
| 1253 | Strategy Selector | src/lidco/budget/strategy_selector.py | Choose compaction strategy (trim-oldest, summarize-middle, collapse-tools, aggressive-prune) based on pressure %; configurable rules |
| 1254 | Compaction Journal | src/lidco/budget/compaction_journal.py | Log every compaction event; before/after token counts; strategy used; messages removed/summarized; undo support |
| 1255 | Tool Result Compressor | src/lidco/budget/tool_compressor.py | Compress tool results in conversation; keep recent full, summarize old; per-tool strategies (file→head/tail, grep→top-N, bash→truncate) |
| 1256 | CLI Commands | src/lidco/cli/commands/q228_cmds.py | /auto-compact, /compaction-log, /compact-tools, /compaction-config |

Tests: tests/unit/test_q228/ — 65 tests

## Q229 — Adaptive Budget Engine (tasks 1257–1261) ✅

**Theme:** Dynamic token budget per task — complexity scoring, auto-scaling max_tokens, pre-call estimation, forecasting.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1257 | Task Complexity Scorer | src/lidco/budget/task_scorer.py | Score task complexity from prompt (simple/moderate/complex/expert); heuristics: code references, file count, multi-step indicators |
| 1258 | Dynamic Budget Scaler | src/lidco/budget/dynamic_scaler.py | Scale max_tokens based on complexity score; min/max bounds; learning from actual usage; per-model adjustment |
| 1259 | Pre-Call Estimator | src/lidco/budget/pre_call_estimator.py | Estimate tokens a tool call will consume before execution; file size lookup, grep result count prediction; budget check before call |
| 1260 | Budget Forecaster | src/lidco/budget/budget_forecaster.py | Predict tokens remaining at current burn rate; session lifespan estimate; recommend compaction timing; trend analysis |
| 1261 | CLI Commands | src/lidco/cli/commands/q229_cmds.py | /task-score, /budget-scale, /estimate-cost, /budget-forecast |

Tests: tests/unit/test_q229/ — 57 tests

## Q230 — Message Collapsing & Smart Eviction (tasks 1262–1266) ✅

**Theme:** Intelligent message merging and eviction — semantic similarity, importance scoring, budget allocator completion, token debt.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1262 | Message Collapser | src/lidco/budget/message_collapser.py | Merge similar adjacent messages; combine repeated tool calls; summarize multi-turn exchanges into single turn; preserve key decisions |
| 1263 | Importance Scorer | src/lidco/budget/importance_scorer.py | Score messages by importance (code changes=high, confirmations=low, errors=high); reference counting; user-marked pins; decay by age |
| 1264 | Smart Evictor | src/lidco/budget/smart_evictor.py | Evict lowest-importance messages first; never evict system/pinned; batch eviction to target; eviction log; undo support |
| 1265 | Token Debt Tracker | src/lidco/budget/token_debt.py | Track "over budget" turns as debt; carry forward; repay via aggressive compaction next turn; debt ceiling; session debt summary |
| 1266 | CLI Commands | src/lidco/cli/commands/q230_cmds.py | /collapse, /importance, /evict, /token-debt |

Tests: tests/unit/test_q230/ — 63 tests

---

# Phase 12 — Token Budget Integration & Pipeline Wiring (Q231–Q234)

> Goal: wire budget modules into Session/LLM pipeline, create unified budget controller, add budget-aware tool execution, session-level budget lifecycle.

## Q231 — Unified Budget Controller (tasks 1267–1271) ✅

**Theme:** Single entry point that orchestrates all budget modules — meter, alerter, compaction, forecaster, debt.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1267 | Budget Controller | src/lidco/budget/controller.py | Facade over meter+alerter+orchestrator+forecaster+debt; single process_turn() call; auto-compact on threshold |
| 1268 | Budget Pipeline | src/lidco/budget/pipeline.py | Ordered pipeline: estimate→check→execute→record→compact; middleware-style hooks; skip on budget exceeded |
| 1269 | Budget Config | src/lidco/budget/config.py | BudgetConfig dataclass; load from LidcoConfig; threshold/strategy/ceiling defaults; per-model overrides |
| 1270 | Budget Reporter | src/lidco/budget/reporter.py | Human-readable budget reports; session summary; per-turn breakdown; export to JSON; Rich formatting |
| 1271 | CLI Commands | src/lidco/cli/commands/q231_cmds.py | /budget-status, /budget-report, /budget-config, /budget-reset |

Tests: tests/unit/test_q231/ — 59 tests

## Q232 — Budget-Aware Tool Execution (tasks 1272–1276) ✅

**Theme:** Check budget before tool calls, truncate results adaptively, track per-tool token consumption.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1272 | Tool Budget Gate | src/lidco/budget/tool_gate.py | Pre-execution budget check; deny if insufficient; warn if tight; override for critical tools |
| 1273 | Adaptive Truncator | src/lidco/budget/adaptive_truncator.py | Truncate tool results based on remaining budget; smart truncation (keep head+tail for files, top-N for grep) |
| 1274 | Tool Token Tracker | src/lidco/budget/tool_tracker.py | Per-tool token accounting; input/output separately; cumulative stats; hottest tools ranking |
| 1275 | Result Size Limiter | src/lidco/budget/result_limiter.py | Hard limit on tool result size; configurable per tool; progressive limits as budget shrinks |
| 1276 | CLI Commands | src/lidco/cli/commands/q232_cmds.py | /tool-budget, /tool-stats, /truncation-config, /result-limits |

Tests: tests/unit/test_q232/ — 61 tests

## Q233 — Session Budget Lifecycle (tasks 1277–1281) ✅

**Theme:** Budget tracking across full session — init, per-turn, checkpoint, resume, end-of-session report.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1277 | Session Budget Init | src/lidco/budget/session_init.py | Initialize budget from model+config; set context window; warm prompt cache budget; reserve system prompt tokens |
| 1278 | Turn Budget Manager | src/lidco/budget/turn_manager.py | Per-turn lifecycle: pre-turn budget check, during-turn tracking, post-turn compaction decision, inter-turn summary |
| 1279 | Budget Checkpoint | src/lidco/budget/checkpoint.py | Save budget state to disk; restore on resume; detect stale state; merge with current |
| 1280 | End-of-Session Report | src/lidco/budget/session_report.py | Final report: total tokens, cost, compactions, peak usage, efficiency score, recommendations for next session |
| 1281 | CLI Commands | src/lidco/cli/commands/q233_cmds.py | /session-budget, /turn-budget, /budget-checkpoint, /session-report |

Tests: tests/unit/test_q233/ — 54 tests

## Q234 — Budget Analytics & Optimization (tasks 1282–1286) ✅

**Theme:** Historical budget analytics, optimization recommendations, A/B comparison, efficiency scoring.

| # | Task | Module | Key Features |
|---|------|--------|--------------|
| 1282 | Budget History | src/lidco/budget/history.py | SQLite store for session budget snapshots; query by date/model/project; trend analysis |
| 1283 | Efficiency Scorer | src/lidco/budget/efficiency.py | Score session efficiency (useful tokens / total tokens); rank sessions; identify waste patterns |
| 1284 | Optimization Advisor | src/lidco/budget/optimization_advisor.py | Recommend: model downgrade, more aggressive compaction, fewer tool calls; based on history patterns |
| 1285 | A/B Comparator | src/lidco/budget/ab_comparator.py | Compare two sessions/models by token efficiency; statistical significance; cost-quality tradeoff |
| 1286 | CLI Commands | src/lidco/cli/commands/q234_cmds.py | /budget-history, /efficiency, /optimize-budget, /compare-budgets |

Tests: tests/unit/test_q234/ — 72 tests
