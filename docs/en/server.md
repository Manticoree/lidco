# HTTP Server

The LIDCO HTTP server exposes a REST/SSE API on localhost for IDE integration. It wraps the same session, agents, and tools used by the CLI.

## Starting the Server

```bash
# Default: localhost:8321
lidco serve

# Custom port
lidco serve --port 9000

# Bind to all interfaces (for remote access — use with caution)
lidco serve --host 0.0.0.0

# Specify project directory
lidco serve --project-dir /path/to/project
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LIDCO_API_TOKEN` | _(empty)_ | Bearer token for authentication. If empty, auth is disabled (local dev mode) |
| `LIDCO_ALLOWED_ORIGINS` | `http://localhost:*,http://127.0.0.1:*` | Comma-separated CORS allowed origins |
| `LIDCO_DEBUG` | `false` | Set to `1` or `true` for verbose error messages in API responses |
| `LIDCO_DEFAULT_MODEL` | `gpt-4o-mini` | Override default LLM model |
| `LIDCO_LOG_LEVEL` | `INFO` | Logging level |

## Authentication

By default (no `LIDCO_API_TOKEN` set), all requests are allowed. This is fine for local development.

To enable authentication:

```bash
export LIDCO_API_TOKEN=my-secret-token
lidco serve
```

Then include the token in requests:

```bash
curl -H "Authorization: Bearer my-secret-token" \
     http://127.0.0.1:8321/api/status
```

The `/health` endpoint is always unauthenticated.

## Health Check

```bash
curl http://127.0.0.1:8321/health
# {"status": "ok"}
```

Use this for monitoring, load balancer probes, or IDE connectivity checks.

## Architecture

```
┌──────────────┐
│  IDE / curl   │
└──────┬───────┘
       │ HTTP (localhost:8321)
┌──────▼───────┐
│   FastAPI     │  ← CORS, Auth, Logging middleware
├──────────────┤
│   Session     │  ← Same as CLI: LLM + Tools + Agents
├──────────────┤
│  Orchestrator │  ← Routes messages to agents
├──────────────┤
│   Agents      │  ← coder, reviewer, planner, debugger, ...
├──────────────┤
│   LLM Layer   │  ← litellm (OpenAI, Anthropic, Ollama, ...)
└──────────────┘
```

The server creates a single `Session` instance on first request (lazy init). All endpoints share this session, which means conversation history persists across requests within the same server process.

## SSE Streaming

The `/api/chat/stream` endpoint uses Server-Sent Events for real-time response streaming.

Event types:

| Event | Data | Description |
|-------|------|-------------|
| `start` | `{"agent": "coder"}` | Stream started, agent selected |
| `token` | `{"text": "chunk..."}` | Response text chunk |
| `tool_call` | `{"tool": "file_read", "args": {...}}` | Agent called a tool |
| `done` | `{"agent": "coder", "model_used": "gpt-4o", "iterations": 2}` | Stream complete |
| `error` | `{"message": "..."}` | Error occurred |

Example with curl:

```bash
curl -N -X POST http://127.0.0.1:8321/api/chat/stream \
     -H "Content-Type: application/json" \
     -d '{"message": "explain what this project does"}'
```

## Stopping the Server

Press **Ctrl+C** in the terminal where `lidco serve` is running.
