# LLM Providers & Per-Role Models

LIDCO lets you connect any number of LLM providers and assign different models to different agent roles. A reviewer can use Claude while a coder uses GPT-4o, completions can use a fast cheap model, and your custom security agent can use Opus — all in the same session.

## Configuration File

`llm_providers.yaml` — separate from the main `config.yaml`.

Location precedence (later overrides earlier):

| Priority | Path |
|----------|------|
| 1 | `configs/llm_providers.yaml` (shipped defaults) |
| 2 | `~/.lidco/llm_providers.yaml` (global user) |
| 3 | `.lidco/llm_providers.yaml` (project-level) |

The file has two sections: `providers` and `role_models`.

## Section 1: Providers

Define custom LLM endpoints. Cloud providers (OpenAI, Anthropic, Groq) work out of the box via litellm — you only need to add entries for self-hosted or OpenAI-compatible endpoints.

```yaml
providers:
  # Cloud providers — just list models, no api_base needed
  openai:
    api_key: "${OPENAI_API_KEY}"
    models:
      - gpt-4o
      - gpt-4o-mini

  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    models:
      - claude-sonnet-4-5-20250514
      - claude-opus-4-20250514

  # Local Ollama
  ollama:
    api_base: "http://localhost:11434"
    models:
      - ollama/llama3.1
      - ollama/codellama
      - ollama/deepseek-coder-v2

  # LM Studio on a custom port
  lmstudio:
    api_base: "http://localhost:1234/v1"
    api_key: "lm-studio"
    models:
      - lmstudio/deepseek-coder-33b

  # vLLM on a GPU server
  vllm:
    api_base: "http://gpu-server:8000/v1"
    api_key: "${VLLM_API_KEY}"
    models:
      - vllm/codellama-70b

  # Azure OpenAI
  azure:
    api_base: "https://your-resource.openai.azure.com"
    api_key: "${AZURE_API_KEY}"
    api_type: "azure"
    api_version: "2024-06-01"
    models:
      - azure/gpt-4o-deployment
```

### Provider Fields

| Field | Required | Description |
|-------|----------|-------------|
| `api_base` | no | Base URL. Omit for native litellm providers (OpenAI, Anthropic, Groq) |
| `api_key` | no | API key. Use `${ENV_VAR}` to reference environment variables |
| `api_type` | no | `"openai"` (default), `"azure"`, `"cohere"`, etc. |
| `api_version` | no | API version (Azure) |
| `models` | yes | List of model IDs available on this endpoint |
| `default_model` | no | Default model for this provider |

### Environment Variable References

Use `${VAR_NAME}` syntax in `api_key` fields. They are resolved at config load time:

```yaml
api_key: "${MY_CUSTOM_API_KEY}"   # reads os.environ["MY_CUSTOM_API_KEY"]
```

## Section 2: Per-Role Model Assignments

Map each agent role to a specific model with its own temperature and token limits.

```yaml
role_models:
  # Fallback for any role not listed below
  default:
    model: "gpt-4o-mini"
    fallback: "groq/llama-3.1-8b-instant"
    temperature: 0.1

  # Special roles
  routing:       # Orchestrator picks the right agent
    model: "gpt-4o-mini"
    temperature: 0.0
    max_tokens: 50

  completion:    # Inline code completion (must be fast)
    model: "gpt-4o-mini"
    temperature: 0.0
    max_tokens: 256

  # Per-agent overrides
  coder:
    model: "gpt-4o"
    fallback: "claude-sonnet-4-5-20250514"
    temperature: 0.1
    max_tokens: 4096

  reviewer:
    model: "claude-sonnet-4-5-20250514"
    fallback: "gpt-4o"
    temperature: 0.0

  planner:
    model: "claude-sonnet-4-5-20250514"
    fallback: "gpt-4o"

  architect:
    model: "claude-sonnet-4-5-20250514"

  debugger:
    model: "gpt-4o"
    temperature: 0.0

  tester:
    model: "gpt-4o-mini"

  docs:
    model: "gpt-4o-mini"
    temperature: 0.3
```

### Role Model Fields

| Field | Required | Description |
|-------|----------|-------------|
| `model` | yes | Primary model for this role |
| `fallback` | no | Fallback model if primary fails |
| `temperature` | no | Override temperature (otherwise uses agent default) |
| `max_tokens` | no | Override max tokens |

### Special Roles

| Role | Used by | Purpose |
|------|---------|---------|
| `default` | Any agent without explicit mapping | Global fallback |
| `routing` | Orchestrator | Picks which agent handles a message |
| `completion` | `/api/complete` endpoint | Inline code completion |

### Resolution Order

When an agent makes an LLM call, the model is resolved as follows:

```
1. Agent's explicit model override (AgentConfig.model) — highest priority
2. Role-based model from role_models[agent_name]
3. role_models["default"]
4. LLMConfig.default_model from config.yaml
```

For fallbacks:

```
1. Role-specific fallback from role_models[agent_name].fallback
2. role_models["default"].fallback
3. LLMConfig.fallback_models from config.yaml
```

## Examples

### Economy Setup: Use Free Local Models

```yaml
# .lidco/llm_providers.yaml
providers:
  ollama:
    api_base: "http://localhost:11434"
    models:
      - ollama/llama3.1
      - ollama/codellama
      - ollama/deepseek-coder-v2

role_models:
  default:
    model: "ollama/llama3.1"
  completion:
    model: "ollama/codellama"
    temperature: 0.0
  coder:
    model: "ollama/deepseek-coder-v2"
  reviewer:
    model: "ollama/llama3.1"
```

### Hybrid: Cloud for Complex, Local for Simple

```yaml
role_models:
  default:
    model: "ollama/llama3.1"

  # Powerful models for complex tasks
  coder:
    model: "gpt-4o"
    fallback: "ollama/deepseek-coder-v2"
  planner:
    model: "claude-sonnet-4-5-20250514"
    fallback: "ollama/llama3.1"
  reviewer:
    model: "claude-sonnet-4-5-20250514"
    fallback: "ollama/llama3.1"

  # Cheap/fast for simple tasks
  routing:
    model: "ollama/llama3.1"
  completion:
    model: "ollama/codellama"
  docs:
    model: "gpt-4o-mini"
  tester:
    model: "gpt-4o-mini"
```

### Maximum Power: Best Model for Each Role

```yaml
role_models:
  default:
    model: "gpt-4o"
    fallback: "claude-sonnet-4-5-20250514"
  coder:
    model: "claude-opus-4-20250514"
    fallback: "gpt-4o"
  reviewer:
    model: "claude-opus-4-20250514"
    temperature: 0.0
  planner:
    model: "claude-opus-4-20250514"
  architect:
    model: "claude-opus-4-20250514"
  completion:
    model: "gpt-4o-mini"
    temperature: 0.0
```

### Custom Agent with Its Own Model

If you have a custom YAML agent `~/.lidco/agents/security.yaml`:

```yaml
# In llm_providers.yaml
role_models:
  security:
    model: "claude-opus-4-20250514"
    temperature: 0.0
    max_tokens: 8192
```

## Verifying Configuration

Check which model each agent uses via the CLI:

```
/agents
```

Or via the API:

```bash
curl http://127.0.0.1:8321/api/status
```

To test a specific agent's model:

```
@reviewer hello
```

The response metadata includes `model_used` showing which model actually handled the request.
