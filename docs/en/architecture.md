# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interfaces                             │
│                                                                     │
│   ┌───────────┐    ┌──────────────────┐    ┌────────────────────┐  │
│   │  CLI REPL  │    │  HTTP Server     │    │  (Future: VSCode,  │  │
│   │  (Rich)    │    │  (FastAPI)       │    │   Neovim, etc.)    │  │
│   └─────┬─────┘    └────────┬─────────┘    └────────────────────┘  │
│         │                   │                                       │
│         └─────────┬─────────┘                                       │
│                   │                                                  │
│         ┌─────────▼──────────┐                                      │
│         │     Session         │  ← Central wiring point              │
│         │  (config, LLM,     │                                      │
│         │   tools, agents,   │                                      │
│         │   memory, context) │                                      │
│         └─────────┬──────────┘                                      │
│                   │                                                  │
│    ┌──────────────┼──────────────┐                                  │
│    │              │              │                                   │
│    ▼              ▼              ▼                                   │
│ ┌──────┐  ┌────────────┐  ┌─────────┐                              │
│ │ LLM  │  │ Orchestrator│  │ Memory  │                              │
│ │Router │  │  (routing   │  │ Store   │                              │
│ │      │  │   + history)│  │         │                              │
│ └──┬───┘  └──────┬─────┘  └─────────┘                              │
│    │             │                                                   │
│    ▼             ▼                                                   │
│ ┌──────┐  ┌──────────┐                                              │
│ │LiteLLM│  │  Agents   │                                             │
│ │      │  │ (ReAct    │                                              │
│ │100+  │  │  loop)    │                                              │
│ │models│  └─────┬────┘                                              │
│ └──────┘        │                                                    │
│                 ▼                                                     │
│          ┌───────────┐                                               │
│          │   Tools    │                                               │
│          │ file_read  │                                               │
│          │ file_write │                                               │
│          │ file_edit  │                                               │
│          │ bash       │                                               │
│          │ git        │                                               │
│          │ glob       │                                               │
│          │ grep       │                                               │
│          └───────────┘                                               │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### Session (`src/lidco/core/session.py`)

The central coordinator. Created once per CLI run or server instance.

Responsibilities:
- Load configuration (YAML + env vars)
- Initialize LLM provider and model router
- Create tool registry with all available tools
- Register built-in and custom agents
- Create orchestrator (LangGraph or simple fallback)
- Manage persistent memory
- Build project context

### Orchestrator (`src/lidco/agents/orchestrator.py`)

Routes user messages to the appropriate agent.

Flow:
1. If agent explicitly specified → use it directly
2. Otherwise, call LLM with agent descriptions → LLM picks the best agent
3. Forward message to selected agent with conversation history + context
4. Store exchange in history for multi-turn conversations

Two implementations:
- `Orchestrator` — simple routing with conversation history
- `GraphOrchestrator` — LangGraph-based with state machine (if langgraph available)

### Agents (`src/lidco/agents/`)

Each agent is a `BaseAgent` subclass implementing the ReAct loop:

```
System Prompt + Context + User Message
         │
         ▼
    ┌─── LLM Call ───┐
    │                 │
    │  Tool calls?    │
    │   YES ──────────┼──► Execute tools ──► Append results ──► Loop
    │   NO  ──────────┼──► Return text response
    │                 │
    └─────────────────┘
```

Built-in agents are defined in `src/lidco/agents/builtin/`. Custom agents are loaded from YAML files in `~/.lidco/agents/` and `.lidco/agents/`.

### LLM Layer (`src/lidco/llm/`)

- `BaseLLMProvider` — abstract interface for LLM calls
- `LiteLLMProvider` — implementation using litellm (supports 100+ models)
- `ModelRouter` — handles model selection, fallback chains, and retries

### Tools (`src/lidco/tools/`)

Each tool extends `BaseTool` with:
- `name` — unique identifier
- `description` — for LLM function calling
- `parameters` — JSON Schema for arguments
- `execute(**args)` — async execution returning `ToolResult`

### Memory (`src/lidco/core/memory.py`)

File-based persistent storage:
- JSON files organized by category
- Global (`~/.lidco/memory/`) and project-level (`.lidco/memory/`)
- Injected into agent prompts as context
- Supports CRUD + text search

### HTTP Server (`src/lidco/server/`)

FastAPI application wrapping the Session:

```
Request → Middleware (CORS, Auth, Logging) → Endpoint → Session/Orchestrator → Response
```

- `app.py` — routes and endpoint handlers
- `models.py` — Pydantic request/response schemas
- `sse.py` — Server-Sent Events for streaming
- `middleware.py` — CORS, bearer token auth, request logging

## Data Flow: Chat Request

```
1. IDE sends POST /api/chat {"message": "fix the bug", "agent": null}
2. FastAPI validates request body (Pydantic)
3. Middleware checks auth token
4. Endpoint gets Session singleton
5. Session.get_full_context() builds project context + memory
6. Orchestrator.handle() routes to best agent
7. Agent.run() enters ReAct loop:
   a. Builds system prompt + context
   b. Calls LLM
   c. LLM returns tool calls → execute tools → loop
   d. LLM returns text → exit loop
8. AgentResponse returned with content, tool calls, metadata
9. Endpoint serializes to ChatResponse JSON
10. IDE displays the response
```

## Data Flow: SSE Streaming

```
1. IDE sends POST /api/chat/stream
2. Server returns EventSourceResponse
3. stream_chat_response() runs the agent
4. Events emitted:
   - start: agent selected
   - tool_call: each tool invocation
   - token: response text in 80-char chunks
   - done: metadata
5. IDE processes events incrementally
```

## Plugin Architecture (IntelliJ)

```
┌─────────────────────────────────────────┐
│           Android Studio / IntelliJ      │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │        LidcoClient (OkHttp)        │  │
│  │  HTTP calls to localhost:8321      │  │
│  └──────────────┬─────────────────────┘  │
│                 │                         │
│    ┌────────────┼────────────┐           │
│    │            │            │           │
│    ▼            ▼            ▼           │
│ ┌──────┐  ┌─────────┐  ┌──────────┐    │
│ │ Chat │  │ Actions  │  │Completion│    │
│ │Window│  │ (Review, │  │(Alt+L,   │    │
│ │      │  │  Explain,│  │ popup)   │    │
│ │      │  │  Refactor│  │          │    │
│ │      │  │  SendTo) │  │          │    │
│ └──────┘  └─────────┘  └──────────┘    │
│                                          │
│ ┌────────────────┐  ┌───────────────┐   │
│ │ Settings Page   │  │ Status Widget  │   │
│ │ (URL, token,    │  │ (connection,   │   │
│ │  agent, stream) │  │  model name)   │   │
│ └────────────────┘  └───────────────┘   │
└─────────────────────────────────────────┘
```

## Directory Structure

```
lidco/
├── src/lidco/
│   ├── __init__.py          # Package, version
│   ├── __main__.py          # CLI + serve entry point
│   ├── agents/              # Agent system
│   │   ├── base.py          # BaseAgent, AgentConfig, AgentResponse
│   │   ├── registry.py      # AgentRegistry
│   │   ├── orchestrator.py  # Message routing
│   │   ├── graph.py         # LangGraph orchestrator
│   │   ├── loader.py        # YAML agent discovery
│   │   └── builtin/         # 8 built-in agents
│   ├── cli/                 # Interactive CLI
│   ├── core/                # Session, config, context, memory
│   ├── llm/                 # LLM providers and routing
│   ├── tools/               # Tool implementations
│   ├── plugins/             # Plugin/hook system
│   ├── rag/                 # RAG (experimental)
│   └── server/              # HTTP API (FastAPI)
│       ├── app.py           # Routes and endpoints
│       ├── models.py        # Pydantic models
│       ├── sse.py           # SSE streaming
│       └── middleware.py    # CORS, auth, logging
├── ide/android-studio-plugin/  # IntelliJ plugin (Kotlin)
├── configs/                 # Default YAML configs
├── tests/                   # Test suite
└── docs/                    # Documentation
```
