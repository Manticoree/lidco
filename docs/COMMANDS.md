# LIDCO Slash Commands Index

Total: 88 commands

## Core

| Command | Description |
|---------|-------------|
| `/clear` | Clear conversation history |
| `/config` | Show or set runtime configuration |
| `/debug` | Toggle debug mode / run file: /debug [on|off|run <file>|kb|stats|preset] |
| `/errors` | View recent error history [N=5] |
| `/exit` | Exit LIDCO |
| `/health` | Project health: lint, tests, TODOs, coverage |
| `/help` | Show available commands |
| `/retry` | Resend last message [or new message] |
| `/run` | Execute code snippet in REPL [python|bash|js] |
| `/status` | Show session health dashboard |
| `/todos` | Find TODO/FIXME/HACK/XXX comments |
| `/undo` | Show/revert file changes via git restore [--force] |

## Session

| Command | Description |
|---------|-------------|
| `/checkpoint` | Manage pre-write file checkpoints |
| `/export` | Export session to JSON (default) or Markdown (--md) |
| `/fork` | Fork current session into a branch |
| `/import` | Restore session from a JSON export file |
| `/replay` | Replay user messages from a saved session |
| `/repos` | Manage multiple repositories |
| `/session` | Save, load, and manage conversation sessions |
| `/workprofile` | Manage workspace configuration profiles |

## Agents

| Command | Description |
|---------|-------------|
| `/agents` | List agents, view stats, manage background tasks |
| `/as` | Одноразовый запрос к конкретному агенту: /as <агент> <сообщение> |
| `/batch` | Decompose and run tasks in parallel |
| `/best-of` | Best-of-N code generation via parallel attempts |
| `/lock` | Закрепить агента для сессии: /lock <агент> | /lock off |
| `/simplify` | Run parallel code review and merge findings |
| `/spec` | Generate a structured feature specification |
| `/tdd` | Run the TDD pipeline (spec→RED→GREEN→verify) |
| `/tdd-mode` | Control test-first write enforcement |
| `/unlock` | Снять блокировку агента |

## Git

| Command | Description |
|---------|-------------|
| `/bisect` | Git bisect integration for finding regressions |
| `/branch` | Manage git branches |
| `/checkout` | Checkout a branch or restore a file |
| `/commit` | Generate a commit message and commit (supports .lidco/commit-template.md) |
| `/conflict` | Resolve git merge conflicts with AI assistance |
| `/pr` | Load GitHub PR context into agents via gh CLI |
| `/pr-create` | Create a PR with AI-generated title and body |
| `/pr-review` | AI-powered review of a GitHub PR |
| `/stash` | Manage git stashes |

## Context

| Command | Description |
|---------|-------------|
| `/add-dir` | Add an external directory to session scope |
| `/compact` | Compress conversation history (N=keep last N, text=LLM summarize) |
| `/context` | Show context window usage gauge |
| `/index` | Build/update the structural project index |
| `/index-status` | Show current index statistics |
| `/memory` | Manage persistent memory |
| `/mention` | Inject a file into the next agent turn |
| `/model` | Show or switch the current LLM model |
| `/theme` | Show or set color theme |

## Tools

| Command | Description |
|---------|-------------|
| `/recent` | Файлы, изменённые в текущей сессии |

## Analysis

| Command | Description |
|---------|-------------|
| `/arch` | Show architecture dependency diagram |
| `/bugbot` | Proactive AST-based bug detector |
| `/fix` | Auto-fix lint and import issues |
| `/lint` | Run ruff + mypy static analysis [path] |
| `/perf-hints` | Show AST-based performance hints for a Python file |
| `/plan` | Plan a task before implementation |
| `/refactor-suggest` | Code smell detection and LLM-assisted refactoring |
| `/search` | Search the codebase (symbols + semantic) |

## Skills

| Command | Description |
|---------|-------------|
| `/skills` | List, run, and manage reusable skills |
| `/snippet` | Save and recall reusable code snippets |

## Integrations

| Command | Description |
|---------|-------------|
| `/http` | Make HTTP API requests (METHOD-first format) |
| `/mcp` | Manage MCP server connections |
| `/webfetch` | Fetch a web page as plain text |
| `/websearch` | Search the web via DuckDuckGo |

## Permissions

| Command | Description |
|---------|-------------|
| `/decisions` | Manage clarification decisions |
| `/init` | Generate LIDCO.md from project analysis [--force] |
| `/permissions` | View and manage tool permission rules |
| `/rules` | Manage project rules |

## Other

| Command | Description |
|---------|-------------|
| `/broadcast` | Send task to all agents simultaneously |
| `/browser` | Open browser and take screenshot via Playwright |
| `/budget` | Показать/установить бюджет токенов |
| `/changelog` | Generate CHANGELOG from git history |
| `/ci` | Show CI/CD workflow run status for current branch |
| `/compare` | Compare files (diff) or run task on multiple agents |
| `/diff-output` | Compare command output before/after changes |
| `/history` | Показать последние N ходов диалога [N=5] |
| `/install` | Install Python package with AI guidance |
| `/issue` | GitHub Issues integration |
| `/openapi` | Generate Python API client from OpenAPI spec |
| `/pipeline` | Run a declarative YAML agent pipeline |
| `/regcheck` | Run related tests to detect regressions |
| `/secscan` | Scan for security issues (hardcoded secrets, SQL injection, eval) |
| `/shortcuts` | Показать горячие клавиши |
| `/slack` | Send Slack notification to configured webhook |
| `/suggest` | Toggle next-action suggestions after responses |
| `/test` | Run pytest from REPL: /test [path] [-k filter] [--watch] |
| `/ticket` | Linear/Jira ticket integration |
| `/venv` | Manage Python virtual environments |
| `/whois` | Карточка агента: описание и инструменты |
