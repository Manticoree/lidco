"""Persona definitions for debate agents."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Persona:
    """An agent persona with a system prompt template and traits."""

    name: str
    description: str
    system_prompt: str
    traits: tuple[str, ...] = ()
    expertise: tuple[str, ...] = ()

    def render_prompt(self, topic: str) -> str:
        """Render the system prompt with the given topic."""
        return self.system_prompt.replace("{{topic}}", topic)


# Built-in personas
OPTIMIST = Persona(
    name="optimist",
    description="Focuses on benefits and opportunities",
    system_prompt="You are an optimist debating: {{topic}}. Emphasize benefits, opportunities, and positive outcomes.",
    traits=("positive", "forward-looking", "encouraging"),
    expertise=("innovation", "growth"),
)

PESSIMIST = Persona(
    name="pessimist",
    description="Focuses on risks and downsides",
    system_prompt="You are a pessimist debating: {{topic}}. Highlight risks, costs, and potential failures.",
    traits=("cautious", "risk-aware", "critical"),
    expertise=("risk-assessment", "failure-analysis"),
)

PRAGMATIST = Persona(
    name="pragmatist",
    description="Focuses on practical implementation",
    system_prompt="You are a pragmatist debating: {{topic}}. Focus on feasibility, implementation details, and trade-offs.",
    traits=("practical", "balanced", "detail-oriented"),
    expertise=("implementation", "trade-offs"),
)

SECURITY_EXPERT = Persona(
    name="security",
    description="Focuses on security implications",
    system_prompt="You are a security expert debating: {{topic}}. Analyze attack surfaces, vulnerabilities, and mitigations.",
    traits=("thorough", "adversarial-thinking", "cautious"),
    expertise=("security", "threat-modeling"),
)

PERF_EXPERT = Persona(
    name="performance",
    description="Focuses on performance implications",
    system_prompt="You are a performance expert debating: {{topic}}. Analyze latency, throughput, resource usage, and scalability.",
    traits=("analytical", "data-driven", "optimization-focused"),
    expertise=("performance", "scalability"),
)

_BUILTINS = {
    p.name: p for p in [OPTIMIST, PESSIMIST, PRAGMATIST, SECURITY_EXPERT, PERF_EXPERT]
}


class PersonaRegistry:
    """Registry for debate personas."""

    def __init__(self) -> None:
        self._personas: dict[str, Persona] = dict(_BUILTINS)

    def register(self, persona: Persona) -> None:
        """Register a custom persona."""
        self._personas[persona.name] = persona

    def get(self, name: str) -> Persona | None:
        return self._personas.get(name)

    def list_all(self) -> list[Persona]:
        return list(self._personas.values())

    def names(self) -> list[str]:
        return sorted(self._personas.keys())

    def remove(self, name: str) -> bool:
        if name in self._personas:
            del self._personas[name]
            return True
        return False

    def builtin_names(self) -> list[str]:
        return sorted(_BUILTINS.keys())
