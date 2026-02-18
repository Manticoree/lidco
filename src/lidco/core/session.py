"""Session management - wires LLM, tools, agents together."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from lidco.agents.builtin import (
    create_architect_agent,
    create_coder_agent,
    create_debugger_agent,
    create_docs_agent,
    create_planner_agent,
    create_refactor_agent,
    create_researcher_agent,
    create_reviewer_agent,
    create_tester_agent,
)
from lidco.agents.loader import discover_yaml_agents
from lidco.agents.orchestrator import Orchestrator
from lidco.agents.registry import AgentRegistry
from lidco.core.clarification import ClarificationManager
from lidco.core.config import LidcoConfig, load_config
from lidco.core.memory import MemoryStore
from lidco.core.token_budget import TokenBudget
from lidco.llm.litellm_provider import LiteLLMProvider
from lidco.llm.router import ModelRouter
from lidco.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from lidco.index.context_enricher import IndexContextEnricher
    from lidco.rag.retriever import ContextRetriever

logger = logging.getLogger(__name__)


class Session:
    """A LIDCO session encapsulating all components."""

    def __init__(self, config: LidcoConfig | None = None, project_dir: Path | None = None) -> None:
        self.config = config or load_config(project_dir)
        self.project_dir = project_dir or Path.cwd()

        # LLM
        provider = LiteLLMProvider(
            default_model=self.config.llm.default_model,
            providers_config=self.config.llm_providers,
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

        # Clarification manager
        self.clarification_mgr = ClarificationManager(self.memory)

        # Project context
        self.project_context = self._build_project_context()

        # Agents
        self.agent_registry = AgentRegistry()
        self._register_builtin_agents()
        self._register_yaml_agents()

        # Orchestrator (try LangGraph, fallback to simple)
        self.orchestrator = self._create_orchestrator()

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

    def _create_orchestrator(self) -> Orchestrator:
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
            )
            orch.set_clarification_manager(self.clarification_mgr)
            if self.config.memory.auto_save:
                orch.set_memory_store(self.memory)
            if self.context_retriever:
                orch.set_context_retriever(self.context_retriever)
            return orch
        except ImportError:
            logger.info("LangGraph not available, using simple orchestrator")
            return Orchestrator(
                llm=self.llm,
                agent_registry=self.agent_registry,
                default_agent=self.config.agents.default,
                auto_plan=self.config.agents.auto_plan,
            )

    def _register_builtin_agents(self) -> None:
        """Register all built-in agents."""
        factories = [
            create_architect_agent,
            create_coder_agent,
            create_debugger_agent,
            create_docs_agent,
            create_planner_agent,
            create_refactor_agent,
            create_researcher_agent,
            create_reviewer_agent,
            create_tester_agent,
        ]
        for factory in factories:
            agent = factory(self.llm, self.tool_registry)
            self.agent_registry.register(agent)

    def _register_yaml_agents(self) -> None:
        """Discover and register YAML-defined custom agents."""
        agents = discover_yaml_agents(self.llm, self.tool_registry)
        for agent in agents:
            self.agent_registry.register(agent)

    def get_full_context(self, query: str = "") -> str:
        """Get combined project context + memory + decisions + RAG for agent prompts.

        Args:
            query: Optional query for RAG retrieval. When provided,
                   relevant code context is included.
        """
        parts: list[str] = []

        if self.project_context:
            parts.append(self.project_context)

        if self.config.memory.enabled:
            memory_ctx = self.memory.build_context_string()
            if memory_ctx:
                parts.append(memory_ctx)

        decisions_ctx = self.clarification_mgr.build_context_string()
        if decisions_ctx:
            parts.append(decisions_ctx)

        if self.index_enricher:
            try:
                index_ctx = self.index_enricher.get_context(query=query)
                if index_ctx:
                    parts.append(f"## Structural Index\n\n{index_ctx}")
            except Exception as exc:
                logger.debug("Index enricher failed: %s", exc)

        if query and self.context_retriever:
            try:
                rag_ctx = self.context_retriever.retrieve(
                    query=query,
                    max_results=self.config.rag.max_results,
                )
                if rag_ctx:
                    parts.append(rag_ctx)
            except Exception as e:
                logger.debug("RAG retrieval failed: %s", e)

        return "\n\n".join(parts)

    def index_project(self) -> int:
        """Index the project for RAG. Returns number of chunks indexed."""
        if not self.context_retriever:
            return 0
        try:
            return self.context_retriever.index_project()
        except Exception as e:
            logger.warning("Project indexing failed: %s", e)
            return 0
