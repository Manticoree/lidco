"""Built-in agents."""

from lidco.agents.builtin.architect import create_architect_agent
from lidco.agents.builtin.coder import create_coder_agent
from lidco.agents.builtin.debugger import create_debugger_agent
from lidco.agents.builtin.docs import create_docs_agent
from lidco.agents.builtin.planner import create_planner_agent
from lidco.agents.builtin.refactor import create_refactor_agent
from lidco.agents.builtin.researcher import create_researcher_agent
from lidco.agents.builtin.reviewer import create_reviewer_agent
from lidco.agents.builtin.tester import create_tester_agent

__all__ = [
    "create_architect_agent",
    "create_coder_agent",
    "create_debugger_agent",
    "create_docs_agent",
    "create_planner_agent",
    "create_refactor_agent",
    "create_researcher_agent",
    "create_reviewer_agent",
    "create_tester_agent",
]
