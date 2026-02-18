# Конфигурация

LIDCO использует многоуровневую систему конфигурации. Более поздние уровни перезаписывают более ранние.

## Приоритет конфигурации

| Приоритет | Источник | Путь |
|-----------|----------|------|
| 1 (низший) | Встроенные значения | Значения по умолчанию Pydantic |
| 2 | Конфигурация пакета | `configs/default.yaml` |
| 3 | Глобальная пользовательская | `~/.lidco/config.yaml` |
| 4 | Проектная | `.lidco/config.yaml` (в корне проекта) |
| 5 (высший) | Переменные окружения | `LIDCO_*` |

## Полный справочник конфигурации

### `configs/default.yaml`

```yaml
llm:
  default_model: "gpt-4o-mini"      # Любая модель, поддерживаемая litellm
  temperature: 0.1                    # 0.0–2.0
  max_tokens: 4096                    # Максимум токенов в ответе
  streaming: true                     # Включить стриминг (CLI)
  fallback_models:                    # Резервные модели при ошибке основной
    - "claude-sonnet-4-5-20250514"
    - "gpt-4o-mini"

cli:
  theme: "monokai"                    # Тема синтаксиса Rich
  show_tool_calls: true               # Показывать вызовы инструментов
  show_thinking: false                # Показывать ход мыслей агента
  max_history: 1000                   # Количество записей в истории

permissions:
  auto_allow:                         # Без подтверждения
    - file_read
    - glob
    - grep
  ask:                                # Спрашивать перед выполнением
    - file_write
    - file_edit
    - bash
    - git
  deny: []                            # Всегда запрещено

agents:
  default: "coder"                    # Агент по умолчанию для маршрутизации
  auto_review: true                   # Авто-ревью после изменений кода
  parallel_execution: true            # Запускать агентов параллельно

memory:
  enabled: true                       # Система постоянной памяти
  auto_save: true                     # Автосохранение сводок вызовов инструментов
  max_entries: 500                    # Максимум записей на файл категории

rag:
  enabled: false                      # RAG/векторный поиск (экспериментальный)
  chunk_size: 1000
  chunk_overlap: 200
  max_results: 10
```

## Переменные окружения

### API-ключи LLM

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
OLLAMA_BASE_URL=http://localhost:11434
```

### Настройки LIDCO

| Переменная | Описание |
|------------|----------|
| `LIDCO_DEFAULT_MODEL` | Переопределение модели по умолчанию |
| `LIDCO_LOG_LEVEL` | Уровень логирования: DEBUG, INFO, WARNING, ERROR |

### Переменные только для сервера

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `LIDCO_API_TOKEN` | _(пусто)_ | Bearer-токен для аутентификации API |
| `LIDCO_ALLOWED_ORIGINS` | `http://localhost:*,http://127.0.0.1:*` | CORS-источники |
| `LIDCO_DEBUG` | `false` | Подробные сообщения об ошибках |

## Конфигурация на уровне проекта

Создайте `.lidco/config.yaml` в корне вашего проекта для переопределения настроек:

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

## Строки моделей

LIDCO использует [litellm](https://docs.litellm.ai/docs/providers) для маршрутизации моделей. Примеры:

| Провайдер | Строка модели |
|-----------|--------------|
| OpenAI | `gpt-4o`, `gpt-4o-mini`, `o1-preview` |
| Anthropic | `claude-sonnet-4-5-20250514`, `claude-opus-4-20250514` |
| Groq | `groq/llama-3.1-70b-versatile` |
| Ollama | `ollama/llama3.1`, `ollama/codellama` |
| Together AI | `together_ai/meta-llama/Llama-3-70b` |
| AWS Bedrock | `bedrock/anthropic.claude-v2` |

Смена модели в рантайме:
- **CLI:** `/model claude-sonnet-4-5-20250514`
- **Сервер:** Измените конфигурацию и перезапустите, или попросите агента через чат

## Директории памяти

| Расположение | Область | Назначение |
|-------------|---------|-----------|
| `~/.lidco/memory/` | Глобальная | Межпроектные воспоминания |
| `.lidco/memory/` | Проект | Воспоминания конкретного проекта |
| `~/.lidco/memory/MEMORY.md` | Глобальная | Markdown-память (внедряется в промпты) |

Воспоминания хранятся в JSON-файлах, организованных по категориям (`general.json`, `pattern.json` и т.д.).
