# LLM-провайдеры и модели по ролям

LIDCO позволяет подключать любое количество LLM-провайдеров и назначать разные модели разным ролям агентов. Ревьюер может использовать Claude, кодер — GPT-4o, дополнения — быструю дешёвую модель, а ваш кастомный агент безопасности — Opus. Всё в одной сессии.

## Файл конфигурации

`llm_providers.yaml` — отдельный от основного `config.yaml`.

Приоритет (более поздний перезаписывает более ранний):

| Приоритет | Путь |
|-----------|------|
| 1 | `configs/llm_providers.yaml` (поставляется с пакетом) |
| 2 | `~/.lidco/llm_providers.yaml` (глобальный пользовательский) |
| 3 | `.lidco/llm_providers.yaml` (на уровне проекта) |

Файл содержит два раздела: `providers` и `role_models`.

## Раздел 1: Провайдеры

Определяют пользовательские LLM-эндпоинты. Облачные провайдеры (OpenAI, Anthropic, Groq) работают из коробки через litellm — записи нужны только для самохостинговых или OpenAI-совместимых эндпоинтов.

```yaml
providers:
  # Облачные провайдеры — указываем только модели, api_base не нужен
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

  # Локальный Ollama
  ollama:
    api_base: "http://localhost:11434"
    models:
      - ollama/llama3.1
      - ollama/codellama
      - ollama/deepseek-coder-v2

  # LM Studio на пользовательском порту
  lmstudio:
    api_base: "http://localhost:1234/v1"
    api_key: "lm-studio"
    models:
      - lmstudio/deepseek-coder-33b

  # vLLM на GPU-сервере
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

### Поля провайдера

| Поле | Обязательно | Описание |
|------|-------------|----------|
| `api_base` | нет | Базовый URL. Опустить для нативных litellm-провайдеров (OpenAI, Anthropic, Groq) |
| `api_key` | нет | API-ключ. Используйте `${ENV_VAR}` для ссылки на переменные окружения |
| `api_type` | нет | `"openai"` (по умолчанию), `"azure"`, `"cohere"` и т.д. |
| `api_version` | нет | Версия API (Azure) |
| `models` | да | Список ID моделей, доступных на этом эндпоинте |
| `default_model` | нет | Модель по умолчанию для этого провайдера |

### Ссылки на переменные окружения

Используйте синтаксис `${VAR_NAME}` в полях `api_key`. Они разрешаются при загрузке конфигурации:

```yaml
api_key: "${MY_CUSTOM_API_KEY}"   # читает os.environ["MY_CUSTOM_API_KEY"]
```

## Раздел 2: Назначение моделей по ролям

Сопоставьте каждую роль агента с конкретной моделью, с собственной температурой и лимитом токенов.

```yaml
role_models:
  # Fallback для любой роли, не указанной ниже
  default:
    model: "gpt-4o-mini"
    fallback: "groq/llama-3.1-8b-instant"
    temperature: 0.1

  # Специальные роли
  routing:       # Оркестратор выбирает нужного агента
    model: "gpt-4o-mini"
    temperature: 0.0
    max_tokens: 50

  completion:    # Инлайн-дополнение кода (должно быть быстрым)
    model: "gpt-4o-mini"
    temperature: 0.0
    max_tokens: 256

  # Переопределения по агентам
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

### Поля модели роли

| Поле | Обязательно | Описание |
|------|-------------|----------|
| `model` | да | Основная модель для этой роли |
| `fallback` | нет | Резервная модель при ошибке основной |
| `temperature` | нет | Переопределение температуры (иначе используется значение агента) |
| `max_tokens` | нет | Переопределение максимума токенов |

### Специальные роли

| Роль | Используется | Назначение |
|------|-------------|-----------|
| `default` | Любой агент без явного маппинга | Глобальный fallback |
| `routing` | Оркестратор | Выбирает, какой агент обработает сообщение |
| `completion` | Эндпоинт `/api/complete` | Инлайн-дополнение кода |

### Порядок разрешения

При вызове LLM агентом модель определяется так:

```
1. Явное переопределение модели агента (AgentConfig.model) — высший приоритет
2. Модель по роли из role_models[имя_агента]
3. role_models["default"]
4. LLMConfig.default_model из config.yaml
```

Для fallback-моделей:

```
1. Роль-специфичный fallback из role_models[имя_агента].fallback
2. role_models["default"].fallback
3. LLMConfig.fallback_models из config.yaml
```

## Примеры

### Экономный: бесплатные локальные модели

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

### Гибридный: облако для сложного, локально для простого

```yaml
role_models:
  default:
    model: "ollama/llama3.1"

  # Мощные модели для сложных задач
  coder:
    model: "gpt-4o"
    fallback: "ollama/deepseek-coder-v2"
  planner:
    model: "claude-sonnet-4-5-20250514"
    fallback: "ollama/llama3.1"
  reviewer:
    model: "claude-sonnet-4-5-20250514"
    fallback: "ollama/llama3.1"

  # Дешёвые/быстрые для простых задач
  routing:
    model: "ollama/llama3.1"
  completion:
    model: "ollama/codellama"
  docs:
    model: "gpt-4o-mini"
  tester:
    model: "gpt-4o-mini"
```

### Максимальная мощность: лучшая модель для каждой роли

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

### Кастомный агент со своей моделью

Если у вас есть кастомный YAML-агент `~/.lidco/agents/security.yaml`:

```yaml
# В llm_providers.yaml
role_models:
  security:
    model: "claude-opus-4-20250514"
    temperature: 0.0
    max_tokens: 8192
```

## Проверка конфигурации

Проверьте, какая модель у каждого агента, через CLI:

```
/agents
```

Или через API:

```bash
curl http://127.0.0.1:8321/api/status
```

Для тестирования модели конкретного агента:

```
@reviewer привет
```

Метаданные ответа содержат `model_used`, показывающий, какая модель фактически обработала запрос.
