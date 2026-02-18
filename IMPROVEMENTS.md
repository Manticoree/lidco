# LIDCO — 100 Improvements Roadmap

Дорожная карта улучшений. Приоритеты: **P0** (критично), **P1** (важно), **P2** (желательно), **P3** (nice-to-have).
Статус: `[ ]` — не начато, `[~]` — в работе, `[x]` — готово.

---

## A. Тестирование и качество кода (1–12)

1. `[ ]` **P0** — E2E тесты с Playwright для CLI (директория `tests/e2e/` пустая)
2. `[ ]` **P0** — Поднять покрытие unit-тестами до 90%+ (сейчас нет отчёта coverage)
3. `[ ]` **P0** — GitHub Actions CI: линтинг, тесты, coverage на каждый PR
4. `[ ]` **P1** — Интеграционные тесты для HTTP-сервера (`src/lidco/server/`)
5. `[ ]` **P1** — Мутационное тестирование (mutmut / cosmic-ray) для выявления слабых тестов
6. `[ ]` **P1** — Property-based тесты (hypothesis) для парсеров, конфигов, memory store
7. `[ ]` **P1** — Benchmark-тесты: время отклика агентов, потребление памяти, throughput сервера
8. `[ ]` **P2** — Snapshot-тесты для CLI-вывода (Rich-рендеринг)
9. `[ ]` **P2** — Тесты на совместимость Windows / Linux / macOS (matrix CI)
10. `[ ]` **P2** — Контракт-тесты для API сервера (OpenAPI schema validation)
11. `[ ]` **P2** — Load-тесты для HTTP-сервера (locust / k6)
12. `[ ]` **P3** — Fuzz-тесты для парсеров HTML (_strip_html), YAML-агентов, конфигов

---

## B. Дистрибуция и DevOps (13–22)

13. `[ ]` **P0** — Публикация на PyPI (`pip install lidco`)
14. `[ ]` **P0** — Docker-образ (multi-stage, slim-python)
15. `[ ]` **P1** — docker-compose.yml с сервером + ChromaDB + опциональным Ollama
16. `[ ]` **P1** — Pre-commit хуки: ruff, mypy, pytest (конфиг `.pre-commit-config.yaml`)
17. `[ ]` **P1** — Changelog автогенерация (conventional commits → CHANGELOG.md)
18. `[ ]` **P2** — GitHub Releases с автоматическими бинарниками (pyinstaller / nuitka)
19. `[ ]` **P2** — Homebrew formula для macOS
20. `[ ]` **P2** — Scoop/Chocolatey манифест для Windows
21. `[ ]` **P3** — Nix flake для NixOS
22. `[ ]` **P3** — Snap / Flatpak пакет для Linux

---

## C. LLM и модели (23–35)

23. `[ ]` **P0** — Retry с exponential backoff при ошибках LLM (429, 500, timeout)
24. `[ ]` **P1** — Circuit breaker для LLM-провайдеров (предотвращение каскадных отказов)
25. `[ ]` **P1** — Кеширование LLM-ответов (SQLite / Redis) для повторяющихся запросов
26. `[ ]` **P1** — Стоимость сессии: отслеживание $ за модель/агент/сессию в реальном времени
27. `[ ]` **P1** — Автовыбор модели по сложности задачи (простые → flash, сложные → pro)
28. `[ ]` **P2** — Speculative decoding: параллельный вызов fast + smart модели
29. `[ ]` **P2** — Streaming token counter в status bar (токены/сек, задержка первого токена)
30. `[ ]` **P2** — Поддержка vision-моделей (анализ скриншотов, UI-mockups)
31. `[ ]` **P2** — Prompt caching для провайдеров, которые это поддерживают (Anthropic, OpenAI)
32. `[ ]` **P2** — Model A/B testing: сравнение качества ответов разных моделей на одном запросе
33. `[ ]` **P3** — Ensemble: объединение ответов нескольких моделей
34. `[ ]` **P3** — Fine-tuning pipeline: дообучение на проектных данных
35. `[ ]` **P3** — Оценка качества ответов (LLM-as-judge) для автоподбора моделей

---

## D. Агенты (36–50)

36. `[ ]` **P1** — Agent chaining: пайплайн из нескольких агентов (planner → coder → tester → reviewer)
37. `[ ]` **P1** — Параллельный запуск агентов: несколько агентов одновременно на независимых подзадачах
38. `[ ]` **P1** — Agent confidence score: роутер показывает уверенность выбора (0–1)
39. `[ ]` **P1** — Агент `security-reviewer`: OWASP Top 10, secrets detection, dependency audit
40. `[ ]` **P2** — Агент `data-analyst`: pandas, matplotlib, Jupyter notebook генерация
41. `[ ]` **P2** — Агент `devops`: Dockerfile, CI/CD pipeline, Terraform, k8s manifests
42. `[ ]` **P2** — Агент `frontend`: React/Vue/Svelte специфика, accessibility, responsive design
43. `[ ]` **P2** — Агент `database`: SQL-миграции, query optimization, schema design
44. `[ ]` **P2** — Agent voting: запуск 3 агентов, выбор лучшего ответа по консенсусу
45. `[ ]` **P2** — Conditional agent routing: if-then-else логика в графе (LangGraph conditions)
46. `[ ]` **P2** — Agent memory isolation: каждый агент помнит свои прошлые сессии отдельно
47. `[ ]` **P3** — Агент `mobile`: iOS/Android специфика, Flutter, React Native
48. `[ ]` **P3** — Агент `performance`: профилирование, bottleneck detection, optimization
49. `[ ]` **P3** — Пользовательские Python-агенты (не только YAML, но и .py файлы в `.lidco/agents/`)
50. `[ ]` **P3** — Agent marketplace: каталог community-агентов с установкой через CLI

---

## E. Инструменты (tools) (51–62)

51. `[ ]` **P1** — `sql` tool: выполнение SQL-запросов (SQLite, PostgreSQL, MySQL)
52. `[ ]` **P1** — `http_request` tool: произвольные HTTP-запросы (REST API тестирование)
53. `[ ]` **P1** — `notebook` tool: создание и редактирование Jupyter .ipynb файлов
54. `[ ]` **P2** — `docker` tool: build, run, exec, logs для контейнеров
55. `[ ]` **P2** — `image_gen` tool: генерация диаграмм (mermaid, plantuml) в PNG/SVG
56. `[ ]` **P2** — `diff` tool: показ unified diff между файлами или версиями
57. `[ ]` **P2** — `tree` tool: вывод дерева директорий с фильтрацией
58. `[ ]` **P2** — Sandbox-режим для bash tool: выполнение в Docker-контейнере
59. `[ ]` **P3** — `clipboard` tool: чтение/запись системного буфера обмена
60. `[ ]` **P3** — `screenshot` tool: скриншот экрана/окна для vision-моделей
61. `[ ]` **P3** — `calendar` tool: интеграция с Google Calendar / Outlook
62. `[ ]` **P3** — Tool usage analytics: статистика использования инструментов

---

## F. RAG и контекст (63–72)

63. `[ ]` **P1** — Инкрементальная индексация (file watcher → автообновление индекса)
64. `[ ]` **P1** — Поддержка дополнительных языков в tree-sitter: Kotlin, Swift, Dart, Elixir, Scala
65. `[ ]` **P1** — Hybrid search: vector similarity + BM25 keyword search
66. `[ ]` **P2** — Cross-repo search: индексация нескольких проектов одновременно
67. `[ ]` **P2** — Dependency graph context: автоматический анализ import-графа
68. `[ ]` **P2** — Git blame context: кто и когда менял файл, для review-агента
69. `[ ]` **P2** — Documentation context: автоматическое подключение README, wiki, docs/
70. `[ ]` **P2** — Configurable embedding model: выбор модели эмбеддингов (local / API)
71. `[ ]` **P3** — Code knowledge graph: Neo4j-подобный граф связей в кодовой базе
72. `[ ]` **P3** — Multi-modal RAG: индексация изображений (UI mockups, диаграммы)

---

## G. CLI и UX (73–84)

73. `[ ]` **P1** — Undo/redo: откат последних изменений агента (`/undo`, `/redo`)
74. `[ ]` **P1** — Rich diff view: подсветка изменений перед подтверждением file_edit
75. `[ ]` **P1** — Session export: сохранение переписки в Markdown (`/export`)
76. `[ ]` **P1** — Suggested follow-ups: предложения следующих вопросов после ответа агента
77. `[ ]` **P2** — TUI режим: полноэкранный интерфейс (textual / urwid) с панелями
78. `[ ]` **P2** — Themes: набор цветовых схем (dracula, solarized, monokai, nord)
79. `[ ]` **P2** — Fuzzy file picker: интерактивный выбор файлов (fzf-стиль)
80. `[ ]` **P2** — Конфигуратор-визард: интерактивная первичная настройка (`lidco init`)
81. `[ ]` **P2** — Keyboard shortcuts: кастомизируемые горячие клавиши
82. `[ ]` **P3** — Voice input: голосовой ввод через Whisper API
83. `[ ]` **P3** — Notifications: уведомления при завершении долгих задач (toast / sound)
84. `[ ]` **P3** — Progress bar для многошаговых операций (индексация, тестирование)

---

## H. Memory и персистентность (85–92)

85. `[ ]` **P1** — Vector search по памяти (семантический поиск вместо текстового)
86. `[ ]` **P1** — Memory categories UI: просмотр, фильтрация, удаление через CLI
87. `[ ]` **P2** — Memory export/import: JSON, Markdown, миграция между проектами
88. `[ ]` **P2** — Memory TTL: автоудаление устаревших записей
89. `[ ]` **P2** — Memory versioning: история изменений каждой записи
90. `[ ]` **P2** — Session replay: запись и воспроизведение сессий для демо/обучения
91. `[ ]` **P3** — Memory sync: синхронизация между устройствами (git / cloud)
92. `[ ]` **P3** — Shared team memory: общая база знаний для команды

---

## I. Интеграции и протоколы (93–100)

93. `[ ]` **P0** — MCP (Model Context Protocol): клиент для подключения внешних MCP-серверов
94. `[ ]` **P1** — MCP server mode: LIDCO как MCP-сервер для других инструментов
95. `[ ]` **P1** — GitHub API интеграция: создание PR, issues, code review comments
96. `[ ]` **P1** — VS Code extension: Language Server Protocol + Sidebar chat
97. `[ ]` **P2** — Jira / Linear интеграция: чтение задач, обновление статусов
98. `[ ]` **P2** — Slack / Discord бот: взаимодействие через мессенджеры
99. `[ ]` **P2** — Neovim плагин: Lua-based интеграция через HTTP API
100. `[ ]` **P3** — Webhook system: POST-уведомления о событиях (task done, error, review)

---

## Приоритеты — сводка

| Приоритет | Кол-во | Описание |
|-----------|--------|----------|
| **P0** | 7 | Блокеры для production-релиза |
| **P1** | 30 | Значительное улучшение качества и функциональности |
| **P2** | 40 | Желательные фичи, улучшающие опыт использования |
| **P3** | 23 | Nice-to-have, долгосрочная перспектива |

## Рекомендуемый порядок реализации

### Фаза 1 — Production Ready (P0)
> E2E тесты → CI/CD → PyPI → Docker → MCP client → Retry/circuit breaker

### Фаза 2 — Core Enhancements (P1)
> Agent chaining → Security agent → Undo/redo → Cost tracking → GitHub API → VS Code

### Фаза 3 — Power Features (P2)
> New tools → TUI → RAG improvements → New agents → Memory enhancements

### Фаза 4 — Ecosystem (P3)
> Marketplace → Voice → Team features → Fine-tuning → Knowledge graph
