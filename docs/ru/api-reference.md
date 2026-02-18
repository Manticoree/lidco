# Справочник API

Базовый URL: `http://127.0.0.1:8321`

Все тела запросов и ответов в формате JSON. Для POST-запросов указывайте заголовок `Content-Type: application/json`.

---

## GET /health

Проверка работоспособности. Всегда без аутентификации.

**Ответ:**
```json
{"status": "ok"}
```

---

## GET /api/status

Статус сервера и метаданные.

**Ответ:**
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

Список доступных агентов с описаниями.

**Ответ:**
```json
[
  {"name": "coder", "description": "General-purpose coding agent"},
  {"name": "reviewer", "description": "Code review specialist"},
  {"name": "planner", "description": "Task breakdown and planning"}
]
```

---

## POST /api/chat

Отправить сообщение и получить полный (не потоковый) ответ.

**Запрос:**
```json
{
  "message": "отрефактори эту функцию на async/await",
  "agent": "coder",
  "context_files": ["src/main.py", "src/utils.py"]
}
```

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `message` | string | да | Сообщение пользователя (1–100 000 символов) |
| `agent` | string | нет | Имя целевого агента. `null` = автоматическая маршрутизация |
| `context_files` | string[] | нет | Пути к файлам проекта для включения в контекст |

**Ответ:**
```json
{
  "content": "Вот отрефакторенная версия...",
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

То же, что `/api/chat`, но возвращает SSE-поток.

**Запрос:** Аналогичен `/api/chat`.

**Ответ:** `text/event-stream` с событиями:

```
event: start
data: {"agent": "coder"}

event: token
data: {"text": "Вот "}

event: token
data: {"text": "отрефакторенная версия..."}

event: tool_call
data: {"tool": "file_read", "args": {"path": "src/main.py"}}

event: done
data: {"agent": "coder", "model_used": "gpt-4o", "iterations": 3, "tool_calls_count": 1}
```

---

## POST /api/complete

Инлайн-дополнение кода. Возвращает только текст дополнения (без объяснений).

**Запрос:**
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

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `file_path` | string | да | Путь к редактируемому файлу |
| `content` | string | да | Полное содержимое файла |
| `cursor_line` | int | да | Номер строки курсора (с 0) |
| `cursor_column` | int | да | Номер столбца курсора (с 0) |
| `language` | string | нет | Язык программирования |
| `max_tokens` | int | нет | Максимальная длина дополнения (1–2048, по умолчанию 256) |

**Ответ:**
```json
{
  "completion": "total += item.price * item.quantity",
  "model_used": "gpt-4o-mini"
}
```

---

## POST /api/review

Отправить код на ревью.

**Запрос:**
```json
{
  "code": "def foo(x):\n    eval(x)\n    return x",
  "file_path": "src/danger.py",
  "language": "python",
  "instructions": "обрати внимание на безопасность"
}
```

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `code` | string | да | Код для ревью |
| `file_path` | string | нет | Путь к исходному файлу (для контекста) |
| `language` | string | нет | Язык программирования |
| `instructions` | string | нет | Дополнительные инструкции для ревью |

**Ответ:**
```json
{
  "review": "**Критично:** `eval(x)` — серьёзная уязвимость безопасности...",
  "agent": "reviewer",
  "model_used": "gpt-4o"
}
```

---

## POST /api/explain

Получить объяснение кода.

**Запрос:**
```json
{
  "code": "xs = [x**2 for x in range(10) if x % 2 == 0]",
  "file_path": "example.py",
  "language": "python"
}
```

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `code` | string | да | Код для объяснения |
| `file_path` | string | нет | Путь к исходному файлу |
| `language` | string | нет | Язык программирования |

**Ответ:**
```json
{
  "explanation": "Это list comprehension создаёт список квадратов чётных чисел от 0 до 9...",
  "agent": "coder",
  "model_used": "gpt-4o"
}
```

---

## GET /api/memory

Список всех записей памяти.

**Ответ:**
```json
{
  "entries": [
    {
      "key": "prefer_async",
      "content": "Всегда использовать async/await вместо колбэков",
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

Добавить запись в память.

**Запрос:**
```json
{
  "key": "db_pattern",
  "content": "Использовать паттерн Repository для всего доступа к БД",
  "category": "pattern",
  "tags": ["architecture", "database"]
}
```

**Ответ:** Созданный объект `MemoryEntry`.

---

## POST /api/memory/search

Поиск по памяти.

**Запрос:**
```json
{
  "query": "database",
  "category": "pattern",
  "limit": 10
}
```

**Ответ:** Тот же формат, что и `GET /api/memory`.

---

## DELETE /api/memory/{key}

Удалить запись памяти по ключу.

```bash
curl -X DELETE http://127.0.0.1:8321/api/memory/db_pattern
```

**Ответ:**
```json
{"deleted": true}
```

Возвращает 404, если ключ не найден.

---

## GET /api/context

Получить текущий контекст проекта (информация о проекте + память).

**Ответ:**
```json
{
  "context": "## Project: myproject\nLanguage: Python\n...",
  "project_dir": "/home/user/myproject"
}
```

---

## Ответы с ошибками

Все ошибки следуют формату:

```json
{
  "detail": "An internal error occurred. Set LIDCO_DEBUG=1 for details."
}
```

| Статус | Значение |
|--------|----------|
| 401 | Отсутствует заголовок `Authorization` (когда установлен `LIDCO_API_TOKEN`) |
| 403 | Неверный токен |
| 404 | Ресурс не найден |
| 422 | Ошибка валидации (невалидное тело запроса) |
| 500 | Внутренняя ошибка сервера |
