"""Session management - wires LLM, tools, agents together."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lidco.agents.builtin import (
    create_architect_agent,
    create_coder_agent,
    create_debugger_agent,
    create_docs_agent,
    create_explain_agent,
    create_planner_agent,
    create_profiler_agent,
    create_qa_agent,
    create_refactor_agent,
    create_researcher_agent,
    create_reviewer_agent,
    create_security_agent,
    create_tester_agent,
)
from lidco.agents.loader import discover_yaml_agents
from lidco.agents.orchestrator import BaseOrchestrator, Orchestrator
from lidco.agents.registry import AgentRegistry
from lidco.core.clarification import ClarificationManager
from lidco.core.config import LidcoConfig, load_config
from lidco.core.errors import ErrorHistory
from lidco.core.memory import MemoryStore
from lidco.core.token_budget import TokenBudget
from lidco.llm.litellm_provider import LiteLLMProvider
from lidco.llm.retry import RetryConfig as LLMRetryConfig
from lidco.llm.router import ModelRouter
from lidco.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from lidco.index.context_enricher import IndexContextEnricher
    from lidco.rag.retriever import ContextRetriever

logger = logging.getLogger(__name__)


class ContextDeduplicator:
    """Tracks which context sections were already sent to avoid re-sending unchanged content.

    Each section is identified by a key (e.g., "project", "memory", "decisions").
    A section is included the first time it appears and whenever its content changes.
    Unchanged sections are skipped, reducing token usage in multi-turn sessions.

    Call reset() when conversation history is cleared so the next turn gets full context.
    """

    def __init__(self) -> None:
        self._sent_hashes: dict[str, str] = {}

    def is_new_or_changed(self, key: str, content: str) -> bool:
        """Return True if this section should be included (new or content changed)."""
        h = hashlib.sha256(content.encode()).hexdigest()
        if self._sent_hashes.get(key) == h:
            return False
        self._sent_hashes[key] = h
        return True

    def reset(self) -> None:
        """Clear all tracked hashes — next call to is_new_or_changed will include everything."""
        self._sent_hashes.clear()


class Session:
    """A LIDCO session encapsulating all components."""

    def __init__(self, config: LidcoConfig | None = None, project_dir: Path | None = None) -> None:
        self.config = config or load_config(project_dir)
        self.project_dir = project_dir or Path.cwd()

        # LLM
        _retry_cfg = LLMRetryConfig(
            max_retries=self.config.llm.retry.max_retries,
            base_delay=self.config.llm.retry.base_delay,
            max_delay=self.config.llm.retry.max_delay,
            jitter=self.config.llm.retry.jitter,
        )
        provider = LiteLLMProvider(
            default_model=self.config.llm.default_model,
            providers_config=self.config.llm_providers,
            retry_config=_retry_cfg,
        )
        self.llm = ModelRouter(
            provider=provider,
            default_model=self.config.llm.default_model,
            fallback_models=self.config.llm.fallback_models,
            llm_providers=self.config.llm_providers,
        )

        # Tools
        self.tool_registry = ToolRegistry.create_default_registry()

        # Memory
        self.memory = MemoryStore(
            project_dir=self.project_dir,
            max_entries=self.config.memory.max_entries,
        )

        # Token budget
        self.token_budget = TokenBudget(
            session_limit=self.config.llm.session_token_limit,
        )

        # RAG context retriever (optional — requires chromadb)
        self.context_retriever: ContextRetriever | None = self._init_rag()

        # Structural index enricher (optional — requires /index to have been run)
        self.index_enricher: IndexContextEnricher | None = self._init_index_enricher()

        # Snippet store
        from lidco.core.snippets import SnippetStore
        self.snippets = SnippetStore(self.project_dir / ".lidco" / "snippets.json")

        # Clarification manager
        self.clarification_mgr = ClarificationManager(self.memory)

        # Project context
        self.project_context = self._build_project_context()

        # Context deduplication — skips unchanged sections on subsequent turns
        self._dedup = ContextDeduplicator()

        # Active GitHub PR context — set via /pr command, cleared via /pr close.
        # Always injected into agent context when set (no dedup — user-triggered).
        self.active_pr_context: str | None = None

        # Error history — captures tool failures for debugger context
        self._error_history = ErrorHistory(max_size=50)

        # Cross-session error ledger (SQLite, persistent)
        from lidco.core.error_ledger import ErrorLedger
        self._error_ledger = ErrorLedger(self.project_dir / ".lidco" / "error_ledger.db")

        # Fix memory — learns from successful bug fixes
        from lidco.core.fix_memory import FixMemory
        self._fix_memory = FixMemory(self.memory)

        # Register error_report tool with access to the live error history.
        # Must be done after _error_history is created, before agents start.
        from lidco.tools.error_report import ErrorReportTool
        self.tool_registry.register(ErrorReportTool(self._error_history))

        # Debug mode — when True, StreamDisplay renders full tracebacks inline
        self.debug_mode: bool = self.config.agents.debug_mode

        # Agents
        self.agent_registry = AgentRegistry()
        self._register_builtin_agents()
        self._register_yaml_agents()

        # Orchestrator (try LangGraph, fallback to simple)
        self.orchestrator = self._create_orchestrator()

        # Auto-indexing watcher (optional — requires watchdog + index)
        from lidco.index.watcher import IndexWatcher
        self._index_watcher: IndexWatcher | None = None
        if self.config.index.auto_watch:
            db_path = self.project_dir / ".lidco" / "project_index.db"
            self._index_watcher = IndexWatcher(self.project_dir, db_path)
            self._index_watcher.start()

        # Config hot-reload — polls .lidco/config.yaml every 30s
        from lidco.core.config_reloader import ConfigReloader
        self._config_reloader = ConfigReloader(self, project_dir=self.project_dir)
        self._config_reloader.start()

    def _init_index_enricher(self) -> IndexContextEnricher | None:
        """Open the structural index enricher if the index DB exists."""
        try:
            from lidco.index.context_enricher import IndexContextEnricher
            enricher = IndexContextEnricher.from_project_dir(self.project_dir)
            if enricher and enricher.is_indexed():
                logger.info("Structural index loaded (%d files)", enricher._db.get_stats().total_files)
            return enricher
        except Exception as exc:
            logger.debug("Could not init index enricher: %s", exc)
            return None

    def _init_rag(self) -> ContextRetriever | None:
        """Initialize RAG context retriever if enabled and chromadb is available."""
        if not self.config.rag.enabled:
            return None

        try:
            from lidco.rag.indexer import CodeIndexer
            from lidco.rag.retriever import ContextRetriever
            from lidco.rag.store import VectorStore

            persist_dir = self.project_dir / ".lidco" / "rag_index"
            store = VectorStore(persist_dir=persist_dir)
            indexer = CodeIndexer(
                project_dir=self.project_dir,
                chunk_size=self.config.rag.chunk_size,
                chunk_overlap=self.config.rag.chunk_overlap,
            )
            retriever = ContextRetriever(
                store=store,
                indexer=indexer,
                project_dir=self.project_dir,
                llm=self.llm if self.config.rag.query_expansion else None,
            )
            logger.info("RAG context retriever initialized")
            return retriever
        except ImportError:
            logger.info("chromadb not available, RAG disabled")
            return None
        except Exception as e:
            logger.warning("Failed to initialize RAG: %s", e)
            return None

    def _build_project_context(self) -> str:
        """Build project context string for agents."""
        try:
            from lidco.core.context import ProjectContext
            ctx = ProjectContext(self.project_dir)
            return ctx.build_context_string()
        except Exception as e:
            logger.debug("Could not build project context: %s", e)
            return ""

    def _create_orchestrator(self) -> BaseOrchestrator:
        """Create the best available orchestrator."""
        try:
            from lidco.agents.graph import GraphOrchestrator
            logger.info("Using LangGraph orchestrator")
            orch = GraphOrchestrator(
                llm=self.llm,
                agent_registry=self.agent_registry,
                default_agent=self.config.agents.default,
                auto_review=self.config.agents.auto_review,
                auto_plan=self.config.agents.auto_plan,
                max_review_iterations=self.config.agents.max_review_iterations,
                agent_timeout=self.config.agents.agent_timeout,
                max_parallel_agents=self.config.agents.max_parallel_agents,
                project_dir=self.project_dir,
            )
            orch.set_clarification_manager(self.clarification_mgr)
            orch.set_error_callback(self._on_error_record)
            orch.set_error_context_builder(lambda: self._error_history.get_file_snippets(n=5))
            orch.set_error_count_reader(lambda: len(self._error_history))
            orch.set_error_summary_builder(
                lambda: self._error_history.to_context_str(n=3, extended=False)
            )
            orch.set_plan_critique(self.config.agents.plan_critique)
            orch.set_plan_revise(self.config.agents.plan_revise)
            orch.set_plan_max_revisions(self.config.agents.plan_max_revisions)
            orch.set_plan_memory(self.config.agents.plan_memory)
            orch.set_preplan_snapshot(self.config.agents.preplan_snapshot)
            orch.set_preplan_ambiguity(self.config.agents.preplan_ambiguity)
            orch.set_debug_mode(self.config.agents.debug_mode)
            orch.set_debug_hypothesis(self.config.agents.debug_hypothesis)
            orch.set_debug_fast_path(self.config.agents.debug_fast_path)
            orch.set_auto_debug(self.config.agents.auto_debug)
            orch.set_debug_preset(self.config.agents.debug_preset)
            orch.set_sbfl_inject(self.config.agents.sbfl_inject)
            orch.set_fix_memory(self._fix_memory)
            orch.set_error_ledger(self._error_ledger)
            if self.config.memory.auto_save:
                orch.set_memory_store(self.memory)
            if self.context_retriever:
                orch.set_context_retriever(self.context_retriever)
            return orch
        except ImportError:
            logger.warning(
                "LangGraph not available — falling back to simple orchestrator. "
                "Auto-review and plan approval will not work."
            )
            return Orchestrator(
                llm=self.llm,
                agent_registry=self.agent_registry,
                default_agent=self.config.agents.default,
                auto_plan=self.config.agents.auto_plan,
                agent_timeout=self.config.agents.agent_timeout,
            )

    def _register_builtin_agents(self) -> None:
        """Register all built-in agents."""
        factories = [
            create_architect_agent,
            create_coder_agent,
            create_debugger_agent,
            create_docs_agent,
            create_explain_agent,
            create_planner_agent,
            create_profiler_agent,
            create_qa_agent,
            create_refactor_agent,
            create_researcher_agent,
            create_reviewer_agent,
            create_security_agent,
            create_tester_agent,
        ]
        for factory in factories:
            agent = factory(self.llm, self.tool_registry)
            self.agent_registry.register(agent)

    def _register_yaml_agents(self) -> None:
        """Discover and register YAML-defined custom agents."""
        agents = discover_yaml_agents(self.llm, self.tool_registry, project_dir=self.project_dir)
        for agent in agents:
            if self.agent_registry.get(agent.name) is not None:
                logger.info(
                    "YAML agent '%s' overrides built-in agent", agent.name
                )
            self.agent_registry.register(agent)

    def _on_error_record(self, record: Any) -> None:
        """Handle a new error record — append to history and persist to ledger."""
        self._error_history.append(record)
        # Also record in cross-session ledger
        try:
            self._error_ledger.record(
                error_type=record.error_type,
                file_hint=record.file_hint,
                function_hint=None,
                message=record.message,
                session_id="session",
            )
        except Exception as _e:
            logger.debug("ErrorLedger.record failed: %s", _e)

    def clear_context_cache(self) -> None:
        """Reset deduplication cache so the next turn re-sends all static context."""
        self._dedup.reset()

    def get_full_context(self, query: str = "", skip_dedup: bool = False) -> str:
        """Get combined project context + memory + decisions + RAG for agent prompts.

        Static sections (project structure, memory, decisions) are deduplicated:
        they are only included when their content has changed since the last call,
        reducing repeated token usage across multi-turn sessions.

        Args:
            query: Optional query for RAG retrieval. When provided,
                   relevant code context is included.
            skip_dedup: When True, bypass deduplication and always include all
                sections. Use this for display-only calls (e.g., /context command)
                that must not advance the dedup state.
        """
        parts: list[str] = []

        if self.project_context:
            if skip_dedup or self._dedup.is_new_or_changed("project", self.project_context):
                parts.append(self.project_context)

        if self.config.memory.enabled:
            memory_ctx = self.memory.build_context_string()
            if memory_ctx:
                if skip_dedup or self._dedup.is_new_or_changed("memory", memory_ctx):
                    parts.append(memory_ctx)

        decisions_ctx = self.clarification_mgr.build_context_string()
        if decisions_ctx:
            if skip_dedup or self._dedup.is_new_or_changed("decisions", decisions_ctx):
                parts.append(decisions_ctx)

        if self.index_enricher:
            try:
                index_ctx = self.index_enricher.get_context(query=query)
                if index_ctx:
                    parts.append(f"## Structural Index\n\n{index_ctx}")
            except Exception as exc:
                logger.debug("Index enricher failed: %s", exc)

        # Test coverage context — injected once per session (deduped)
        try:
            from lidco.core.coverage_reader import build_coverage_context
            cov_ctx = build_coverage_context(self.project_dir)
            if cov_ctx:
                if skip_dedup or self._dedup.is_new_or_changed("coverage", cov_ctx):
                    parts.append(cov_ctx)
        except Exception as exc:
            logger.debug("Coverage context failed: %s", exc)

        if query and self.context_retriever:
            try:
                rag_ctx = self.context_retriever.retrieve(
                    query=query,
                    max_results=self.config.rag.max_results,
                    query_expansion=self.config.rag.query_expansion,
                )
                if rag_ctx:
                    parts.append(rag_ctx)
            except Exception as e:
                logger.debug("RAG retrieval failed: %s", e)

        # Active PR context — injected whenever set, always fresh (no dedup).
        if self.active_pr_context:
            parts.append(self.active_pr_context)

        # Recent error history — always fresh, no dedup (content changes every run).
        # In debug mode the error section is more verbose and surfaced at the top
        # of the context so the agent receives it with higher priority.
        if self.debug_mode:
            error_ctx = self._error_history.to_context_str(n=10, extended=True)
            if error_ctx:
                parts.insert(0, error_ctx)
        else:
            error_ctx = self._error_history.to_context_str(n=5)
            if error_ctx:
                parts.append(error_ctx)

        return "\n\n".join(parts)

    def close(self) -> None:
        """Shut down background workers (index watcher, config reloader, etc.)."""
        if self._index_watcher is not None:
            self._index_watcher.stop()
        if self._config_reloader is not None:
            self._config_reloader.stop()
        try:
            self._error_ledger.close()
        except Exception:
            pass

    def index_project(self) -> int:
        """Index the project for RAG. Returns number of chunks indexed."""
        if not self.context_retriever:
            return 0
        try:
            return self.context_retriever.index_project()
        except Exception as e:
            logger.warning("Project indexing failed: %s", e)
            return 0
