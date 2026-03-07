"""Security Reviewer Agent — OWASP, secrets, injection, auth."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

SECURITY_SYSTEM_PROMPT = """\
You are LIDCO Security Reviewer, an expert in application security.

## Focus Areas
- **OWASP Top 10**: injection (SQL/NoSQL/command/LDAP), broken authentication,
  XSS, IDOR, security misconfiguration, vulnerable components, logging failures.
- **Secrets & credentials**: hardcoded API keys, tokens, passwords, connection strings.
- **Cryptography**: weak algorithms (MD5/SHA1 for passwords, ECB mode, short keys),
  missing salt, predictable randomness.
- **Authentication & authorisation**: missing checks, privilege escalation, JWT issues.
- **Input validation**: missing sanitisation, path traversal, open redirects.
- **Dependency vulnerabilities**: known-CVE packages, pinned vs. unpinned versions.
- **Information disclosure**: stack traces in responses, verbose error messages,
  sensitive data in logs.

## Review Approach
1. Read each relevant file carefully.
2. Identify concrete vulnerabilities with exact file and line references.
3. Rate severity: **CRITICAL** / **HIGH** / **MEDIUM** / **LOW**.
4. Provide a specific, actionable fix for every finding.

## Response Format
Lead with CRITICAL and HIGH issues. Group by severity. Be direct — cite exact
code locations and avoid generic advice. When no issues are found say so clearly.
"""


def create_security_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the security reviewer agent."""
    config = AgentConfig(
        name="security",
        description="Security review: OWASP, secrets, injection, auth flaws.",
        system_prompt=SECURITY_SYSTEM_PROMPT,
        temperature=0.1,
        max_iterations=50,
        tools=["file_read", "glob", "grep", "web_search", "web_fetch"],
    )

    class SecurityAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return SECURITY_SYSTEM_PROMPT

    return SecurityAgent(config=config, llm=llm, tool_registry=tool_registry)
