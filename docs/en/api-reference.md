# API Reference

Base URL: `http://127.0.0.1:8321`

All request/response bodies are JSON. Include `Content-Type: application/json` for POST requests.

---

## GET /health

Health check. Always unauthenticated.

**Response:**
```json
{"status": "ok"}
```

---

## GET /api/status

Server status and metadata.

**Response:**
```json
{
  "version": "0.1.0",
  "status": "running",
  "model": "gpt-4o-mini",
  "agents": ["architect", "coder", "debugger", "docs", "planner", "refactor", "reviewer", "tester"],
  "memory_entries": 5,
  "project_dir": "/home/user/myproject"
}
```

---

## GET /api/agents

List available agents with descriptions.

**Response:**
```json
[
  {"name": "coder", "description": "General-purpose coding agent"},
  {"name": "reviewer", "description": "Code review specialist"},
  {"name": "planner", "description": "Task breakdown and planning"}
]
```

---

## POST /api/chat

Send a message and get a full (non-streaming) response.

**Request:**
```json
{
  "message": "refactor this function to use async/await",
  "agent": "coder",
  "context_files": ["src/main.py", "src/utils.py"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | yes | User message (1–100,000 chars) |
| `agent` | string | no | Target agent name. `null` = auto-route |
| `context_files` | string[] | no | Project file paths to include as context |

**Response:**
```json
{
  "content": "Here's the refactored version...",
  "agent": "coder",
  "model_used": "gpt-4o",
  "iterations": 3,
  "tool_calls": [
    {"tool": "file_read", "args": {"path": "src/main.py"}}
  ]
}
```

---

## POST /api/chat/stream

Same as `/api/chat` but returns an SSE stream.

**Request:** Same as `/api/chat`.

**Response:** `text/event-stream` with events:

```
event: start
data: {"agent": "coder"}

event: token
data: {"text": "Here's the "}

event: token
data: {"text": "refactored version..."}

event: tool_call
data: {"tool": "file_read", "args": {"path": "src/main.py"}}

event: done
data: {"agent": "coder", "model_used": "gpt-4o", "iterations": 3, "tool_calls_count": 1}
```

---

## POST /api/complete

Inline code completion. Returns only the completion text (no explanation).

**Request:**
```json
{
  "file_path": "src/app.py",
  "content": "def calculate_total(items):\n    total = 0\n    for item in items:\n        ",
  "cursor_line": 3,
  "cursor_column": 8,
  "language": "python",
  "max_tokens": 256
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | string | yes | Path of the file being edited |
| `content` | string | yes | Full file content |
| `cursor_line` | int | yes | 0-indexed line number of cursor |
| `cursor_column` | int | yes | 0-indexed column of cursor |
| `language` | string | no | Programming language |
| `max_tokens` | int | no | Max completion length (1–2048, default 256) |

**Response:**
```json
{
  "completion": "total += item.price * item.quantity",
  "model_used": "gpt-4o-mini"
}
```

---

## POST /api/review

Send code for AI review.

**Request:**
```json
{
  "code": "def foo(x):\n    eval(x)\n    return x",
  "file_path": "src/danger.py",
  "language": "python",
  "instructions": "focus on security issues"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | yes | Code to review |
| `file_path` | string | no | Source file path (for context) |
| `language` | string | no | Programming language |
| `instructions` | string | no | Additional review instructions |

**Response:**
```json
{
  "review": "**Critical:** `eval(x)` is a severe security vulnerability...",
  "agent": "reviewer",
  "model_used": "gpt-4o"
}
```

---

## POST /api/explain

Get an explanation of code.

**Request:**
```json
{
  "code": "xs = [x**2 for x in range(10) if x % 2 == 0]",
  "file_path": "example.py",
  "language": "python"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | yes | Code to explain |
| `file_path` | string | no | Source file path |
| `language` | string | no | Programming language |

**Response:**
```json
{
  "explanation": "This list comprehension creates a list of squared even numbers from 0 to 9...",
  "agent": "coder",
  "model_used": "gpt-4o"
}
```

---

## GET /api/memory

List all memory entries.

**Response:**
```json
{
  "entries": [
    {
      "key": "prefer_async",
      "content": "Always use async/await over callbacks",
      "category": "preference",
      "tags": ["style"],
      "created_at": "2025-01-15T10:30:00Z",
      "source": "/home/user/project"
    }
  ],
  "total": 1
}
```

---

## POST /api/memory

Add a memory entry.

**Request:**
```json
{
  "key": "db_pattern",
  "content": "Use repository pattern for all database access",
  "category": "pattern",
  "tags": ["architecture", "database"]
}
```

**Response:** The created `MemoryEntry` object.

---

## POST /api/memory/search

Search memories by content.

**Request:**
```json
{
  "query": "database",
  "category": "pattern",
  "limit": 10
}
```

**Response:** Same format as `GET /api/memory`.

---

## DELETE /api/memory/{key}

Delete a memory entry by key.

```bash
curl -X DELETE http://127.0.0.1:8321/api/memory/db_pattern
```

**Response:**
```json
{"deleted": true}
```

Returns 404 if key not found.

---

## GET /api/context

Get the current project context (project info + memory).

**Response:**
```json
{
  "context": "## Project: myproject\nLanguage: Python\n...",
  "project_dir": "/home/user/myproject"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "An internal error occurred. Set LIDCO_DEBUG=1 for details."
}
```

| Status | Meaning |
|--------|---------|
| 401 | Missing `Authorization` header (when `LIDCO_API_TOKEN` is set) |
| 403 | Invalid token |
| 404 | Resource not found |
| 422 | Validation error (invalid request body) |
| 500 | Internal server error |
