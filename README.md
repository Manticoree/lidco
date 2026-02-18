# LIDCO - LLM-Integrated Development COmpanion

Multi-agent coding assistant with pluggable LLM support.

## Quick Start

```bash
pip install -e ".[dev]"
cp .env.example .env
# Add your API keys to .env
lidco
```

## Features

- Pluggable LLM backends (OpenAI, Anthropic, Ollama, Groq, 100+)
- Multi-agent architecture (Coder, Planner, Reviewer, Debugger)
- Custom agents via YAML
- Rich CLI with syntax highlighting
- Tool system (file ops, bash, git, grep, glob)
