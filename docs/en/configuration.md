# Configuration

LIDCO uses a layered configuration system. Later layers override earlier ones.

## Configuration Precedence

| Priority | Source | Path |
|----------|--------|------|
| 1 (lowest) | Built-in defaults | Pydantic model defaults |
| 2 | Package config | `configs/default.yaml` |
| 3 | Global user config | `~/.lidco/config.yaml` |
| 4 | Project config | `.lidco/config.yaml` (in project root) |
| 5 (highest) | Environment variables | `LIDCO_*` |

## Full Config Reference

### `configs/default.yaml`

```yaml
llm:
  default_model: "gpt-4o-mini"      # Any litellm-supported model
  temperature: 0.1                    # 0.0–2.0
  max_tokens: 4096                    # Max response tokens
  streaming: true                     # Enable streaming (CLI)
  fallback_models:                    # Try these if default fails
    - "claude-sonnet-4-5-20250514"
    - "gpt-4o-mini"

cli:
  theme: "monokai"                    # Rich syntax theme
  show_tool_calls: true               # Show tool invocations
  show_thinking: false                # Show agent thinking process
  max_history: 1000                   # Prompt history entries

permissions:
  auto_allow:                         # No confirmation needed
    - file_read
    - glob
    - grep
  ask:                                # Ask before executing
    - file_write
    - file_edit
    - bash
    - git
  deny: []                            # Always blocked

agents:
  default: "coder"                    # Default agent for routing
  auto_review: true                   # Auto-review after code changes
  parallel_execution: true            # Run agents in parallel

memory:
  enabled: true                       # Persistent memory system
  auto_save: true                     # Auto-save tool call summaries
  max_entries: 500                    # Max entries per category file

rag:
  enabled: false                      # RAG/vector search (experimental)
  chunk_size: 1000
  chunk_overlap: 200
  max_results: 10
```

## Environment Variables

### LLM API Keys

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
OLLAMA_BASE_URL=http://localhost:11434
```

### LIDCO Settings

| Variable | Description |
|----------|-------------|
| `LIDCO_DEFAULT_MODEL` | Override default model |
| `LIDCO_LOG_LEVEL` | Logging: DEBUG, INFO, WARNING, ERROR |

### Server-Only Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LIDCO_API_TOKEN` | _(empty)_ | Bearer token for API auth |
| `LIDCO_ALLOWED_ORIGINS` | `http://localhost:*,http://127.0.0.1:*` | CORS origins |
| `LIDCO_DEBUG` | `false` | Verbose error messages |

## Project-Level Config

Create `.lidco/config.yaml` in your project root to override settings per-project:

```yaml
# .lidco/config.yaml
llm:
  default_model: "claude-sonnet-4-5-20250514"
  temperature: 0.0

agents:
  default: "planner"

permissions:
  auto_allow:
    - file_read
    - file_write
    - glob
    - grep
```

## Model Strings

LIDCO uses [litellm](https://docs.litellm.ai/docs/providers) for model routing. Examples:

| Provider | Model String |
|----------|-------------|
| OpenAI | `gpt-4o`, `gpt-4o-mini`, `o1-preview` |
| Anthropic | `claude-sonnet-4-5-20250514`, `claude-opus-4-20250514` |
| Groq | `groq/llama-3.1-70b-versatile` |
| Ollama | `ollama/llama3.1`, `ollama/codellama` |
| Together AI | `together_ai/meta-llama/Llama-3-70b` |
| AWS Bedrock | `bedrock/anthropic.claude-v2` |

Switch models at runtime:
- **CLI:** `/model claude-sonnet-4-5-20250514`
- **Server:** Change config and restart, or use chat to ask an agent

## Memory Directories

| Location | Scope | Purpose |
|----------|-------|---------|
| `~/.lidco/memory/` | Global | Cross-project memories |
| `.lidco/memory/` | Project | Project-specific memories |
| `~/.lidco/memory/MEMORY.md` | Global | Markdown memory (injected into prompts) |

Memories are stored as JSON files organized by category (`general.json`, `pattern.json`, etc.).
