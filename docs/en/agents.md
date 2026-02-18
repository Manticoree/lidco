# Agents

LIDCO uses a multi-agent architecture where specialized agents handle different types of tasks. An orchestrator routes messages to the most appropriate agent.

## Built-in Agents

| Agent | Name | Description |
|-------|------|-------------|
| Architect | `architect` | System design, architecture decisions, tech stack evaluation |
| Coder | `coder` | General-purpose coding: write, modify, implement features |
| Debugger | `debugger` | Debug errors, fix bugs, analyze tracebacks |
| Docs | `docs` | Documentation writing, README generation, docstrings |
| Planner | `planner` | Break down tasks, create implementation plans, design steps |
| Refactor | `refactor` | Code refactoring, optimization, cleanup |
| Reviewer | `reviewer` | Code review: security, quality, best practices |
| Tester | `tester` | Write tests, improve test coverage, TDD guidance |

## Targeting Agents

### CLI

```
@reviewer check this function for security issues
@planner break down the authentication feature
@debugger I'm getting a NullPointerError on line 42
```

### HTTP API

```json
{
  "message": "check this function for security issues",
  "agent": "reviewer"
}
```

### Auto-Routing

If no agent is specified, the orchestrator routes automatically based on keywords:

| Keywords | Routed to |
|----------|-----------|
| plan, break down, design, architect | `planner` |
| review, check, audit | `reviewer` |
| debug, fix, error, bug, traceback | `debugger` |
| everything else | `coder` |

## Agent Architecture

Each agent follows the ReAct (Reason + Act) pattern:

```
1. Receive message + context
2. Build system prompt (agent-specific)
3. Call LLM
4. If LLM wants to use tools → execute tools → loop back to step 3
5. If LLM returns text → return as final response
```

Agents have a configurable iteration limit (default: 20) to prevent infinite loops.

## Agent Configuration

Each agent has these properties:

| Property | Type | Description |
|----------|------|-------------|
| `name` | string | Unique agent identifier |
| `description` | string | What the agent does (shown to users and orchestrator) |
| `system_prompt` | string | Injected as the system message for LLM calls |
| `model` | string? | Override model (null = use default) |
| `temperature` | float | LLM temperature (0.0–2.0) |
| `max_tokens` | int | Max response tokens |
| `tools` | string[] | Allowed tool names (empty = all tools) |
| `max_iterations` | int | Max ReAct loop iterations |

## Custom Agents (YAML)

Create custom agents by adding YAML files to:
- `~/.lidco/agents/` (global)
- `.lidco/agents/` (project-level)

### Example: `~/.lidco/agents/security.yaml`

```yaml
name: security
description: "Security-focused code auditor"
system_prompt: |
  You are a security expert. Analyze code for vulnerabilities including:
  - SQL injection
  - XSS
  - CSRF
  - Authentication/authorization flaws
  - Hardcoded secrets
  - Input validation issues

  Rate each finding as CRITICAL, HIGH, MEDIUM, or LOW.
  Provide specific fix recommendations with code examples.

model: null          # Use default model
temperature: 0.0     # Deterministic for consistent audits
max_tokens: 4096
tools:
  - file_read
  - glob
  - grep
max_iterations: 10
```

### Example: `~/.lidco/agents/translator.yaml`

```yaml
name: translator
description: "Translates code between programming languages"
system_prompt: |
  You translate code between programming languages.
  Preserve the original logic, naming conventions, and structure.
  Use idiomatic patterns in the target language.
  Include comments explaining non-obvious translations.

temperature: 0.1
max_tokens: 8192
tools: []            # No tools needed
max_iterations: 1    # Single-pass translation
```

Usage:

```
@security audit the authentication module
@translator convert this Python to Rust
```

## Available Tools

Agents can use these tools:

| Tool | Description |
|------|-------------|
| `file_read` | Read file contents |
| `file_write` | Create/overwrite files |
| `file_edit` | Edit parts of a file |
| `bash` | Execute shell commands |
| `git` | Git operations |
| `glob` | Find files by pattern |
| `grep` | Search file contents |
