# LIDCO - LLM-Integrated Development COmpanion

## Vision

Модульная CLI-система для помощи в кодинге, аналог Claude Code, с поддержкой любых LLM и расширяемой архитектурой агентов.

---

## Tech Stack

| Категория | Технология | Назначение |
|-----------|-----------|------------|
| Язык | Python 3.12+ | Основной язык |
| LLM Framework | LangChain + LangGraph | Оркестрация агентов, chains, tool calling |
| LLM Providers | litellm | Единый интерфейс к 100+ LLM (OpenAI, Anthropic, Ollama, Groq, etc.) |
| CLI | Rich + Prompt Toolkit | Терминальный интерфейс, подсветка, автодополнение |
| Конфиг | Pydantic Settings + YAML | Валидация конфигов, настройки агентов |
| Файловая система | watchdog | Наблюдение за изменениями файлов |
| AST/Code | tree-sitter | Парсинг кода на 40+ языках |
| Embeddings | chromadb | Локальная векторная БД для контекста кодовой базы |
| Тесты | pytest + pytest-asyncio | Тестирование |
| Пакетирование | uv / pip | Управление зависимостями |
| Логирование | structlog | Структурированные логи |
| Плагины | pluggy | Система плагинов для расширения |

---

## Архитектура

```
┌─────────────────────────────────────────────────┐
│                   CLI Interface                  │
│              (Rich + Prompt Toolkit)             │
├─────────────────────────────────────────────────┤
│                 Session Manager                  │
│         (история, контекст, состояние)           │
├─────────────────────────────────────────────────┤
│               Agent Orchestrator                 │
│            (LangGraph State Machine)             │
├──────────┬──────────┬──────────┬────────────────┤
│ Coder    │ Reviewer │ Planner  │ Custom Agents  │
│ Agent    │ Agent    │ Agent    │ (YAML-defined) │
├──────────┴──────────┴──────────┴────────────────┤
│                  Tool Registry                   │
│   (File R/W, Bash, Grep, Git, Search, etc.)     │
├─────────────────────────────────────────────────┤
│               LLM Provider Layer                 │
│          (litellm - unified interface)           │
├──────────┬──────────┬──────────┬────────────────┤
│ OpenAI   │Anthropic │ Ollama   │ Any LLM...     │
└──────────┴──────────┴──────────┴────────────────┘
```

---

## Фазы разработки

### ФАЗА 1: Ядро системы (Foundation)

#### 1.1 Инициализация проекта
- [x]Создать структуру директорий
- [x]Настроить pyproject.toml с зависимостями
- [x]Настроить uv/pip окружение
- [x]Создать базовый .gitignore
- [x]Инициализировать git репозиторий

#### 1.2 LLM Provider Layer
- [x]Создать абстрактный интерфейс `BaseLLMProvider`
- [x]Реализовать `LiteLLMProvider` (обертка над litellm)
- [x]Конфиг моделей через YAML (`models.yaml`)
- [x]Поддержка streaming ответов
- [x]Fallback между провайдерами (если один недоступен)
- [x]Кеширование ответов (опционально)
- [x]Тесты для LLM layer

#### 1.3 Система инструментов (Tools)
- [x]Создать базовый класс `BaseTool` с интерфейсом
- [x]Реализовать `ToolRegistry` (регистрация/поиск инструментов)
- [x]Инструмент: `ReadFileTool` - чтение файлов
- [x]Инструмент: `WriteFileTool` - запись файлов
- [x]Инструмент: `EditFileTool` - редактирование (find & replace)
- [x]Инструмент: `BashTool` - выполнение команд (с sandbox)
- [x]Инструмент: `GlobTool` - поиск файлов по паттернам
- [x]Инструмент: `GrepTool` - поиск по содержимому
- [x]Инструмент: `GitTool` - операции с git
- [x]Система подтверждений (permissions) для опасных операций
- [x]Тесты для каждого инструмента

#### 1.4 Конфигурация
- [x]Pydantic-модели для конфигов
- [x]Глобальный конфиг (`~/.lidco/config.yaml`)
- [x]Конфиг проекта (`.lidco/config.yaml` в корне проекта)
- [x]Переменные окружения (`.env` поддержка)
- [x]CLI-аргументы (переопределяют конфиг)
- [x]Тесты для конфигурации

---

### ФАЗА 2: Агентная система

#### 2.1 Базовая архитектура агентов
- [x]Создать `BaseAgent` абстрактный класс
- [x]Определить `AgentConfig` (Pydantic модель)
- [x]Реализовать `AgentRegistry` (регистрация/поиск агентов)
- [x]Система ролей и system prompts для агентов
- [x]Контекстное окно и управление памятью агента
- [x]Тесты для базовой архитектуры

#### 2.2 Встроенные агенты
- [x]`CoderAgent` - основной агент для написания кода
- [x]`PlannerAgent` - планирование задач, декомпозиция
- [x]`ReviewerAgent` - ревью кода, поиск проблем
- [x]`DebuggerAgent` - отладка, анализ ошибок
- [x]`ArchitectAgent` - архитектурные решения
- [x]`TestAgent` - генерация и запуск тестов
- [x]`RefactorAgent` - рефакторинг кода
- [x]`DocAgent` - генерация документации
- [x]Тесты для каждого агента

#### 2.3 Оркестрация агентов (LangGraph)
- [x]Граф состояний для маршрутизации между агентами
- [x]`OrchestratorAgent` - главный агент-роутер
- [x]Параллельное выполнение независимых агентов
- [x]Передача контекста между агентами
- [x]Система приоритетов задач
- [x]Обработка ошибок и retry логика
- [x]Тесты для оркестрации

#### 2.4 Пользовательские агенты
- [x]YAML-спецификация для создания агентов
- [x]Парсер YAML -> AgentConfig
- [x]Горячая загрузка агентов из `~/.lidco/agents/`
- [x]Горячая загрузка из `.lidco/agents/` проекта
- [x]Валидация пользовательских агентов
- [x]CLI-команда `/create-agent` для интерактивного создания
- [x]Шаблоны агентов (templates)
- [x]Тесты для пользовательских агентов

---

### ФАЗА 3: CLI интерфейс

#### 3.1 Базовый CLI
- [x]Точка входа `lidco` (CLI command)
- [x]REPL цикл (read-eval-print loop)
- [x]Rich-форматирование ответов (markdown, код)
- [x]Подсветка синтаксиса в выводе кода
- [x]Индикаторы загрузки (spinners, progress bars)
- [x]Тесты для CLI

#### 3.2 Продвинутый CLI
- [x]Автодополнение команд и путей файлов
- [x]Slash-команды (`/help`, `/model`, `/agent`, `/clear`, `/exit`)
- [x]История команд (persistent)
- [x]Многострочный ввод
- [x]Горячие клавиши (Ctrl+C для остановки, etc.)
- [x]Цветовые темы
- [x]Тесты

#### 3.3 Система разрешений
- [x]Уровни разрешений: auto, ask, deny
- [x]Конфигурация разрешений по инструментам
- [x]Подтверждение опасных операций (удаление файлов, git push)
- [x]Логирование всех действий
- [x]Тесты

---

### ФАЗА 4: Контекст и память

#### 4.1 Контекст проекта
- [x]Автоматическое определение типа проекта (package.json, pyproject.toml, etc.)
- [x]Индексация файлов проекта
- [x]`.lidco/rules/` - пользовательские правила (аналог CLAUDE.md)
- [x]Автоматический сбор контекста (git info, structure, dependencies)
- [x]Тесты

#### 4.2 Векторное хранилище (RAG)
- [x]Интеграция chromadb для локального хранения
- [x]Индексация кодовой базы (tree-sitter для чанкинга)
- [x]Семантический поиск по коду
- [x]Автоматическое обновление индекса при изменениях (watchdog)
- [x]Ограничение контекстного окна - умный отбор релевантных чанков
- [x]Тесты

#### 4.3 Память между сессиями
- [x]Persistent memory (`~/.lidco/memory/`)
- [x]Автоматическое сохранение паттернов
- [x]Память проекта (`.lidco/memory/`)
- [x]Загрузка памяти в system prompt
- [x]Тесты

---

### ФАЗА 5: Расширения и плагины

#### 5.1 Система плагинов
- [x]Интерфейс `BasePlugin` (pluggy)
- [x]Hook-система (pre/post для каждого инструмента)
- [x]Загрузка плагинов из `~/.lidco/plugins/`
- [x]pip-installable плагины
- [x]Тесты

#### 5.2 MCP (Model Context Protocol) поддержка
- [x]MCP клиент для подключения внешних серверов
- [x]MCP сервер - экспорт инструментов LIDCO
- [x]Конфигурация MCP серверов
- [x]Тесты

#### 5.3 Интеграции
- [x]GitHub API (issues, PRs, reviews)
- [x]Jira/Linear интеграция
- [x]Slack/Discord нотификации
- [x]VS Code extension (Language Server Protocol)
- [x]Тесты

---

### ФАЗА 6: Качество и Production

#### 6.1 Тестирование
- [x]Unit тесты (>80% coverage)
- [x]Integration тесты
- [x]E2E тесты (CLI сценарии)
- [x]Benchmark тесты (скорость, потребление памяти)

#### 6.2 Документация
- [x]README.md с quick start
- [x]Документация API
- [x]Руководство по созданию агентов
- [x]Руководство по созданию плагинов
- [x]Примеры использования

#### 6.3 Распространение
- [x]PyPI пакет
- [x]Docker образ
- [x]Homebrew formula
- [x]GitHub Actions CI/CD

---

## Структура проекта

```
lidco/
├── pyproject.toml
├── README.md
├── .env.example
├── src/
│   └── lidco/
│       ├── __init__.py
│       ├── __main__.py              # Entry point
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py               # Main CLI REPL
│       │   ├── commands.py          # Slash commands
│       │   ├── renderer.py          # Rich output rendering
│       │   └── permissions.py       # Permission system
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py            # Pydantic config models
│       │   ├── session.py           # Session management
│       │   ├── context.py           # Project context builder
│       │   └── memory.py            # Persistent memory
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── base.py              # BaseLLMProvider
│       │   ├── litellm_provider.py  # LiteLLM implementation
│       │   ├── router.py            # Model routing/fallback
│       │   └── cache.py             # Response caching
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── base.py              # BaseTool
│       │   ├── registry.py          # ToolRegistry
│       │   ├── file_read.py
│       │   ├── file_write.py
│       │   ├── file_edit.py
│       │   ├── bash.py
│       │   ├── glob.py
│       │   ├── grep.py
│       │   └── git.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py              # BaseAgent
│       │   ├── registry.py          # AgentRegistry
│       │   ├── orchestrator.py      # LangGraph orchestrator
│       │   ├── loader.py            # YAML agent loader
│       │   ├── builtin/
│       │   │   ├── __init__.py
│       │   │   ├── coder.py
│       │   │   ├── planner.py
│       │   │   ├── reviewer.py
│       │   │   ├── debugger.py
│       │   │   ├── architect.py
│       │   │   ├── tester.py
│       │   │   ├── refactor.py
│       │   │   └── docs.py
│       │   └── templates/           # Agent YAML templates
│       │       ├── basic.yaml
│       │       ├── reviewer.yaml
│       │       └── specialist.yaml
│       ├── rag/
│       │   ├── __init__.py
│       │   ├── indexer.py           # Code indexer (tree-sitter)
│       │   ├── store.py             # ChromaDB store
│       │   └── retriever.py         # Context retriever
│       └── plugins/
│           ├── __init__.py
│           ├── base.py              # BasePlugin
│           ├── hooks.py             # Hook system
│           └── manager.py           # Plugin manager
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_tools/
│   │   ├── test_agents/
│   │   ├── test_llm/
│   │   └── test_core/
│   ├── integration/
│   └── e2e/
├── configs/
│   ├── default.yaml                 # Default configuration
│   └── models.yaml                  # Model definitions
└── examples/
    ├── custom_agent.yaml            # Example custom agent
    └── custom_plugin.py             # Example plugin
```

---

## Формат YAML для пользовательских агентов

```yaml
# ~/.lidco/agents/security-reviewer.yaml
name: security-reviewer
description: "Analyzes code for security vulnerabilities"
version: "1.0"

model:
  preferred: "gpt-4o"          # Preferred model
  fallback: "claude-sonnet-4-5-20250514" # Fallback
  temperature: 0.1

system_prompt: |
  You are a security expert. Analyze code for:
  - OWASP Top 10 vulnerabilities
  - Hardcoded secrets
  - Injection attacks
  - Authentication flaws

tools:
  - file_read
  - grep
  - glob
  # НЕ включаем file_write, bash - только анализ

output_format:
  type: structured
  schema:
    severity: [CRITICAL, HIGH, MEDIUM, LOW]
    findings: list
    recommendations: list

triggers:
  - on: pre_commit
    condition: "files_changed > 0"
  - on: manual
    command: "/security-review"
```

---

## Порядок реализации (приоритет)

| # | Задача | Фаза | Зависимости | Сложность |
|---|--------|------|-------------|-----------|
| 1 | Инициализация проекта | 1.1 | - | Легко |
| 2 | Конфигурация (Pydantic) | 1.4 | #1 | Средне |
| 3 | LLM Provider Layer | 1.2 | #1, #2 | Средне |
| 4 | Базовые инструменты | 1.3 | #1 | Средне |
| 5 | Базовый CLI (REPL) | 3.1 | #3, #4 | Средне |
| 6 | BaseAgent + Registry | 2.1 | #3, #4 | Сложно |
| 7 | CoderAgent (MVP) | 2.2 | #6 | Средне |
| 8 | Оркестрация (LangGraph) | 2.3 | #6, #7 | Сложно |
| 9 | Остальные встроенные агенты | 2.2 | #6 | Средне |
| 10 | YAML агенты | 2.4 | #6 | Средне |
| 11 | Продвинутый CLI | 3.2 | #5 | Средне |
| 12 | Разрешения | 3.3 | #4, #5 | Средне |
| 13 | Контекст проекта | 4.1 | #4 | Средне |
| 14 | RAG (ChromaDB) | 4.2 | #13 | Сложно |
| 15 | Память | 4.3 | #2 | Легко |
| 16 | Плагины | 5.1 | #4, #6 | Сложно |
| 17 | MCP | 5.2 | #4, #16 | Сложно |
| 18 | Интеграции | 5.3 | #16 | Средне |
| 19 | Тестирование полное | 6.1 | Все | Средне |
| 20 | Документация | 6.2 | Все | Легко |
| 21 | Публикация | 6.3 | Все | Легко |

---

## MVP (Minimum Viable Product)

Для первого рабочего прототипа нужны задачи **#1-7**:

1. Проект инициализирован
2. Можно подключить любую LLM через litellm
3. Есть базовые инструменты (чтение/запись файлов, bash, grep)
4. Работает CLI с REPL
5. Один рабочий агент (CoderAgent) может помогать с кодом

**Ожидаемое время до MVP: задачи 1-7**
