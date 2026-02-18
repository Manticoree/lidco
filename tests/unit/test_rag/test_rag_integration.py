"""Tests for RAG integration in session and graph orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.core.config import LidcoConfig, RAGConfig


class TestSessionRAGInit:
    """Test RAG initialization in Session."""

    def test_rag_disabled_by_default(self):
        """When rag.enabled is False (default), context_retriever is None."""
        config = LidcoConfig()
        assert config.rag.enabled is False

    @patch("lidco.core.session.LiteLLMProvider")
    @patch("lidco.core.session.ModelRouter")
    @patch("lidco.core.session.ToolRegistry")
    def test_rag_not_initialized_when_disabled(
        self, mock_tools, mock_router, mock_provider
    ):
        """Session.context_retriever is None when RAG is disabled."""
        mock_tools.create_default_registry.return_value = MagicMock()
        config = LidcoConfig(rag=RAGConfig(enabled=False))

        with patch("lidco.core.session.load_config", return_value=config):
            from lidco.core.session import Session

            session = Session(config=config, project_dir=Path("/tmp/test"))

        assert session.context_retriever is None

    @patch("lidco.core.session.LiteLLMProvider")
    @patch("lidco.core.session.ModelRouter")
    @patch("lidco.core.session.ToolRegistry")
    def test_rag_initialized_when_enabled_and_chromadb_available(
        self, mock_tools, mock_router, mock_provider
    ):
        """When rag.enabled and chromadb is importable, retriever is created."""
        mock_tools.create_default_registry.return_value = MagicMock()
        config = LidcoConfig(rag=RAGConfig(enabled=True))

        mock_retriever = MagicMock()
        with (
            patch("lidco.core.session.load_config", return_value=config),
            patch("lidco.rag.store.VectorStore") as mock_store_cls,
            patch("lidco.rag.indexer.CodeIndexer") as mock_indexer_cls,
            patch("lidco.rag.retriever.ContextRetriever", return_value=mock_retriever),
        ):
            from lidco.core.session import Session

            session = Session(config=config, project_dir=Path("/tmp/test"))

        assert session.context_retriever is mock_retriever

    @patch("lidco.core.session.LiteLLMProvider")
    @patch("lidco.core.session.ModelRouter")
    @patch("lidco.core.session.ToolRegistry")
    def test_rag_graceful_when_chromadb_missing(
        self, mock_tools, mock_router, mock_provider
    ):
        """When chromadb is not installed, RAG is silently disabled."""
        mock_tools.create_default_registry.return_value = MagicMock()
        config = LidcoConfig(rag=RAGConfig(enabled=True))

        with (
            patch("lidco.core.session.load_config", return_value=config),
            patch.dict("sys.modules", {"chromadb": None}),
            patch(
                "lidco.rag.store.VectorStore",
                side_effect=ImportError("no chromadb"),
            ),
        ):
            from lidco.core.session import Session

            session = Session(config=config, project_dir=Path("/tmp/test"))

        assert session.context_retriever is None


class TestSessionGetFullContext:
    """Test RAG context injection in get_full_context."""

    @patch("lidco.core.session.LiteLLMProvider")
    @patch("lidco.core.session.ModelRouter")
    @patch("lidco.core.session.ToolRegistry")
    def test_rag_context_included_when_query_provided(
        self, mock_tools, mock_router, mock_provider
    ):
        """RAG context is appended when query is provided."""
        mock_tools.create_default_registry.return_value = MagicMock()
        config = LidcoConfig(rag=RAGConfig(enabled=False))

        with patch("lidco.core.session.load_config", return_value=config):
            from lidco.core.session import Session

            session = Session(config=config, project_dir=Path("/tmp/test"))

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = "## Relevant Code Context\nsome code"
        session.context_retriever = mock_retriever

        ctx = session.get_full_context(query="implement auth")
        assert "Relevant Code Context" in ctx
        mock_retriever.retrieve.assert_called_once()

    @patch("lidco.core.session.LiteLLMProvider")
    @patch("lidco.core.session.ModelRouter")
    @patch("lidco.core.session.ToolRegistry")
    def test_rag_context_not_included_without_query(
        self, mock_tools, mock_router, mock_provider
    ):
        """RAG context is NOT fetched when no query is provided."""
        mock_tools.create_default_registry.return_value = MagicMock()
        config = LidcoConfig(rag=RAGConfig(enabled=False))

        with patch("lidco.core.session.load_config", return_value=config):
            from lidco.core.session import Session

            session = Session(config=config, project_dir=Path("/tmp/test"))

        mock_retriever = MagicMock()
        session.context_retriever = mock_retriever

        session.get_full_context()
        mock_retriever.retrieve.assert_not_called()

    @patch("lidco.core.session.LiteLLMProvider")
    @patch("lidco.core.session.ModelRouter")
    @patch("lidco.core.session.ToolRegistry")
    def test_rag_retrieval_failure_is_silent(
        self, mock_tools, mock_router, mock_provider
    ):
        """RAG retrieval errors don't crash get_full_context."""
        mock_tools.create_default_registry.return_value = MagicMock()
        config = LidcoConfig(rag=RAGConfig(enabled=False))

        with patch("lidco.core.session.load_config", return_value=config):
            from lidco.core.session import Session

            session = Session(config=config, project_dir=Path("/tmp/test"))

        mock_retriever = MagicMock()
        mock_retriever.retrieve.side_effect = RuntimeError("vector store down")
        session.context_retriever = mock_retriever

        ctx = session.get_full_context(query="test query")
        # Should return context without RAG, no crash
        assert isinstance(ctx, str)


class TestSessionIndexProject:
    """Test project indexing."""

    @patch("lidco.core.session.LiteLLMProvider")
    @patch("lidco.core.session.ModelRouter")
    @patch("lidco.core.session.ToolRegistry")
    def test_index_project_returns_zero_when_no_retriever(
        self, mock_tools, mock_router, mock_provider
    ):
        mock_tools.create_default_registry.return_value = MagicMock()
        config = LidcoConfig()

        with patch("lidco.core.session.load_config", return_value=config):
            from lidco.core.session import Session

            session = Session(config=config, project_dir=Path("/tmp/test"))

        assert session.index_project() == 0

    @patch("lidco.core.session.LiteLLMProvider")
    @patch("lidco.core.session.ModelRouter")
    @patch("lidco.core.session.ToolRegistry")
    def test_index_project_delegates_to_retriever(
        self, mock_tools, mock_router, mock_provider
    ):
        mock_tools.create_default_registry.return_value = MagicMock()
        config = LidcoConfig()

        with patch("lidco.core.session.load_config", return_value=config):
            from lidco.core.session import Session

            session = Session(config=config, project_dir=Path("/tmp/test"))

        mock_retriever = MagicMock()
        mock_retriever.index_project.return_value = 42
        session.context_retriever = mock_retriever

        assert session.index_project() == 42
        mock_retriever.index_project.assert_called_once()


class TestGraphOrchestratorRAG:
    """Test RAG integration in GraphOrchestrator."""

    def _make_orchestrator(self):
        """Create a GraphOrchestrator with mocked dependencies."""
        from lidco.agents.graph import GraphOrchestrator

        mock_llm = MagicMock()
        mock_registry = MagicMock()
        mock_registry.list_agents.return_value = []
        mock_registry.get.return_value = None

        orch = GraphOrchestrator(
            llm=mock_llm,
            agent_registry=mock_registry,
            auto_plan=False,
            auto_review=False,
        )
        return orch

    def test_set_context_retriever(self):
        """set_context_retriever stores the retriever."""
        orch = self._make_orchestrator()
        mock_retriever = MagicMock()
        orch.set_context_retriever(mock_retriever)
        assert orch._context_retriever is mock_retriever

    def test_context_retriever_default_none(self):
        """By default, _context_retriever is None."""
        orch = self._make_orchestrator()
        assert orch._context_retriever is None


class TestGraphOrchestratorRAGIndexUpdate:
    """Test RAG index update in _finalize_node."""

    def _make_orchestrator(self):
        from lidco.agents.graph import GraphOrchestrator

        mock_llm = MagicMock()
        mock_registry = MagicMock()
        mock_registry.list_agents.return_value = []
        mock_registry.get.return_value = None

        return GraphOrchestrator(
            llm=mock_llm,
            agent_registry=mock_registry,
            auto_plan=False,
            auto_review=False,
        )

    def test_update_rag_index_on_file_write(self):
        """Files modified by file_write are re-indexed."""
        from lidco.agents.base import AgentResponse

        orch = self._make_orchestrator()
        mock_retriever = MagicMock()
        orch.set_context_retriever(mock_retriever)

        state = {
            "user_message": "create file",
            "selected_agent": "coder",
            "agent_response": AgentResponse(
                content="Done",
                iterations=1,
                tool_calls_made=[
                    {"tool": "file_write", "args": {"path": "/tmp/new.py"}, "result": "ok"},
                ],
            ),
        }

        orch._update_rag_index(state)
        mock_retriever.update_file.assert_called_once_with(Path("/tmp/new.py"))

    def test_update_rag_index_on_file_edit(self):
        """Files modified by file_edit are re-indexed."""
        from lidco.agents.base import AgentResponse

        orch = self._make_orchestrator()
        mock_retriever = MagicMock()
        orch.set_context_retriever(mock_retriever)

        state = {
            "user_message": "edit file",
            "selected_agent": "coder",
            "agent_response": AgentResponse(
                content="Done",
                iterations=1,
                tool_calls_made=[
                    {"tool": "file_edit", "args": {"path": "/tmp/existing.py"}, "result": "ok"},
                ],
            ),
        }

        orch._update_rag_index(state)
        mock_retriever.update_file.assert_called_once_with(Path("/tmp/existing.py"))

    def test_no_update_for_read_only_tools(self):
        """file_read and grep don't trigger index updates."""
        from lidco.agents.base import AgentResponse

        orch = self._make_orchestrator()
        mock_retriever = MagicMock()
        orch.set_context_retriever(mock_retriever)

        state = {
            "user_message": "read file",
            "selected_agent": "coder",
            "agent_response": AgentResponse(
                content="Contents",
                iterations=1,
                tool_calls_made=[
                    {"tool": "file_read", "args": {"path": "/tmp/a.py"}, "result": "ok"},
                    {"tool": "grep", "args": {"pattern": "foo"}, "result": "ok"},
                ],
            ),
        }

        orch._update_rag_index(state)
        mock_retriever.update_file.assert_not_called()

    def test_deduplicates_file_paths(self):
        """Same file edited multiple times is re-indexed once."""
        from lidco.agents.base import AgentResponse

        orch = self._make_orchestrator()
        mock_retriever = MagicMock()
        orch.set_context_retriever(mock_retriever)

        state = {
            "user_message": "edit file",
            "selected_agent": "coder",
            "agent_response": AgentResponse(
                content="Done",
                iterations=1,
                tool_calls_made=[
                    {"tool": "file_edit", "args": {"path": "/tmp/same.py"}, "result": "ok"},
                    {"tool": "file_edit", "args": {"path": "/tmp/same.py"}, "result": "ok"},
                ],
            ),
        }

        orch._update_rag_index(state)
        assert mock_retriever.update_file.call_count == 1

    def test_no_crash_when_no_retriever(self):
        """_update_rag_index is a no-op when no retriever is set."""
        from lidco.agents.base import AgentResponse

        orch = self._make_orchestrator()
        # No retriever set

        state = {
            "user_message": "edit",
            "selected_agent": "coder",
            "agent_response": AgentResponse(
                content="Done",
                iterations=1,
                tool_calls_made=[
                    {"tool": "file_write", "args": {"path": "/tmp/a.py"}, "result": "ok"},
                ],
            ),
        }

        # Should not crash
        orch._update_rag_index(state)
