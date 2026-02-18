# Getting Started

## Prerequisites

- Python 3.12+
- API key for at least one LLM provider (OpenAI, Anthropic, Groq, or local Ollama)

## Installation

```bash
# Clone the repository
git clone https://github.com/lidco/lidco.git
cd lidco

# Install in development mode
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

## Configure API Keys

Edit `.env` and add your keys:

```env
# Pick one or more providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...

# Or use Ollama (no key needed)
# OLLAMA_BASE_URL=http://localhost:11434

# Default model
LIDCO_DEFAULT_MODEL=gpt-4o-mini
```

## First Run (CLI Mode)

```bash
lidco
```

You'll see the LIDCO banner and a prompt:

```
 ██╗     ██╗██████╗  ██████╗ ██████╗
 ██║     ██║██╔══██╗██╔════╝██╔═══██╗
 ██║     ██║██║  ██║██║     ██║   ██║
 ██║     ██║██║  ██║██║     ██║   ██║
 ███████╗██║██████╔╝╚██████╗╚██████╔╝
 ╚══════╝╚═╝╚═════╝  ╚═════╝ ╚═════╝

You >
```

### Basic Commands

| Input | What it does |
|-------|-------------|
| `hello, help me refactor this file` | Chat with the default agent (coder) |
| `@reviewer check this function` | Target a specific agent |
| `/help` | Show available slash commands |
| `/agents` | List available agents |
| `/model claude-sonnet-4-5-20250514` | Switch LLM model |
| `/memory list` | Show saved memories |
| `/exit` | Quit |

### Multiline Input

Press **Alt+Enter** to insert a newline. Press **Enter** to send.

## First Run (Server Mode)

To use LIDCO with Android Studio or other IDEs, start the HTTP server:

```bash
lidco serve
```

The server starts on `http://127.0.0.1:8321`. Verify:

```bash
curl http://127.0.0.1:8321/api/status
```

Response:

```json
{
  "version": "0.1.0",
  "status": "running",
  "model": "gpt-4o-mini",
  "agents": ["architect", "coder", "debugger", "docs", "planner", "refactor", "reviewer", "tester"],
  "memory_entries": 0,
  "project_dir": "/path/to/your/project"
}
```

## Next Steps

- [HTTP Server Guide](./server.md) — server configuration and startup options
- [Android Studio Plugin](./android-studio-plugin.md) — install the IDE plugin
- [Configuration](./configuration.md) — customize models, agents, permissions
- [Agents](./agents.md) — create custom agents with YAML
