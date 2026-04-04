"""Q279 — Multi-Agent Debate: orchestrator, personas, evaluator, consensus."""

from lidco.debate.orchestrator import DebateOrchestrator
from lidco.debate.personas import PersonaRegistry, Persona
from lidco.debate.evaluator import ArgumentEvaluator
from lidco.debate.consensus import ConsensusBuilder

__all__ = [
    "DebateOrchestrator",
    "PersonaRegistry",
    "Persona",
    "ArgumentEvaluator",
    "ConsensusBuilder",
]
