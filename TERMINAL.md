# Запуск LIDCO из терминала

Пошаговая инструкция для запуска всех компонентов системы из командной строки.

---

## Требования

| Компонент | Версия |
|-----------|--------|
| Python | 3.12+ |
| pip | 23+ |
| Git | любая |

Проверка:

```bash
python --version    # Python 3.12.x
pip --version       # pip 23.x+
git --version       # git 2.x
```

> **Windows:** используйте `python` вместо `python3`.
> **Linux / macOS:** может потребоваться `python3` и `pip3`.

---

## Шаг 1. Клонирование проекта

```bash
git clone https://github.com/lidco/lidco.git
cd lidco
```

---

## Шаг 2. Создание виртуального окружения (рекомендуется)

### Windows (CMD)

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> Если PowerShell выдаёт ошибку политики выполнения:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

После активации в терминале появится префикс `(.venv)`.

---

## Шаг 3. Установка зависимостей

```bash
pip install -e ".[dev]"
```

Эта команда:
- Установит все зависимости (FastAPI, LiteLLM, LangChain, ChromaDB и др.)
- Зарегистрирует команду `lidco` в PATH
- Режим `-e` (editable) — изменения в коде применяются без переустановки

Проверка установки:

```bash
lidco --help
```

Или напрямую:

```bash
python -m lidco --help
```

---

## Шаг 4. Настройка API-ключей

### Вариант A: Файл `.env`

```bash
cp .env.example .env
```

Откройте `.env` в любом редакторе и впишите ключи:

```env
# OpenAI (для gpt-4o, gpt-4o-mini)
OPENAI_API_KEY=sk-proj-...

# Anthropic (для claude-sonnet, claude-opus)
ANTHROPIC_API_KEY=sk-ant-...

# Groq (для быстрого inference)
GROQ_API_KEY=gsk_...
```

Достаточно **одного** ключа. Если используете Ollama — ключи не нужны.

### Вариант B: Переменные окружения

**Windows (CMD):**
```cmd
set OPENAI_API_KEY=sk-proj-...
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY = "sk-proj-..."
```

**Linux / macOS:**
```bash
export OPENAI_API_KEY=sk-proj-...
```

### Вариант C: Ollama (локальные модели, без ключей)

```bash
# Установите Ollama: https://ollama.com/download
ollama pull llama3.1
ollama serve
```

Затем в `~/.lidco/llm_providers.yaml`:

```yaml
providers:
  ollama:
    api_base: "http://localhost:11434"
    models:
      - ollama/llama3.1

role_models:
  default:
    model: "ollama/llama3.1"
```

---

## Шаг 5. Запуск CLI (интерактивный режим)

```bash
lidco
```

Вы увидите приглашение LIDCO. Доступные команды:

| Ввод | Действие |
|------|----------|
| `любой текст` | Отправить сообщение AI |
| `@coder напиши ...` | Обратиться к конкретному агенту |
| `@reviewer проверь ...` | Ревью кода через агент reviewer |
| `/model gpt-4o` | Сменить модель |
| `/agents` | Список доступных агентов |
| `/help` | Справка |
| `/exit` | Выход |

Пример сессии:

```
(.venv) > lidco

╭─────────────────────────────────╮
│  LIDCO v0.1.0                   │
│  Model: gpt-4o-mini             │
│  Type /help for commands        │
╰─────────────────────────────────╯

You: напиши функцию Фибоначчи на Python

LIDCO [coder]: Вот функция вычисления числа Фибоначчи:
...

You: @reviewer проверь этот код

LIDCO [reviewer]: Ревью кода:
...

You: /exit
```

---

## Шаг 6. Запуск HTTP-сервера (для IDE-плагина)

HTTP-сервер нужен для работы плагина Android Studio и других интеграций.

### Базовый запуск

```bash
lidco serve
```

Сервер запустится на `http://127.0.0.1:8321`.

### С параметрами

```bash
# Кастомный порт
lidco serve --port 9000

# Доступ по локальной сети
lidco serve --host 0.0.0.0

# Указать директорию проекта
lidco serve --project-dir /path/to/my/project

# Все параметры вместе
lidco serve --host 0.0.0.0 --port 9000 --project-dir ./my-project
```

### Проверка работы сервера

Откройте **другой** терминал и выполните:

```bash
curl http://127.0.0.1:8321/api/status
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "model": "gpt-4o-mini",
  "agents": ["coder", "reviewer", "architect", ...],
  "memory_entries": 0
}
```

### Проверка чата через curl

```bash
curl -X POST http://127.0.0.1:8321/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"привет, что ты умеешь?\"}"
```

### Windows (CMD) — curl с двойными кавычками

```cmd
curl -X POST http://127.0.0.1:8321/api/chat -H "Content-Type: application/json" -d "{\"message\": \"hello\"}"
```

### Windows (PowerShell) — через Invoke-RestMethod

```powershell
$body = @{ message = "привет" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8321/api/status -Method Get
Invoke-RestMethod -Uri http://127.0.0.1:8321/api/chat -Method Post -Body $body -ContentType "application/json"
```

---

## Шаг 7. Одновременный запуск CLI и сервера

Для полноценной работы вам могут потребоваться оба режима. Откройте **два терминала**:

**Терминал 1 — HTTP-сервер:**

```bash
cd lidco
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS
lidco serve
```

**Терминал 2 — CLI:**

```bash
cd lidco
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS
lidco
```

---

## Шаг 8. Запуск в фоновом режиме

### Linux / macOS

```bash
# Через nohup
nohup lidco serve > lidco.log 2>&1 &

# Через tmux
tmux new-session -d -s lidco 'lidco serve'
tmux attach -t lidco    # чтобы подключиться
```

### Windows (PowerShell)

```powershell
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m", "lidco", "serve"
```

### Windows (отдельное окно)

```cmd
start "LIDCO Server" cmd /k "cd /d %CD% && .venv\Scripts\activate && lidco serve"
```

---

## Все API-эндпоинты

После запуска сервера доступны следующие эндпоинты:

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/health` | Проверка жизни сервера |
| GET | `/api/status` | Статус: модель, агенты, память |
| GET | `/api/agents` | Список доступных агентов |
| POST | `/api/chat` | Отправить сообщение (ответ целиком) |
| POST | `/api/chat/stream` | Стриминг ответа через SSE |
| POST | `/api/complete` | Инлайн-дополнение кода |
| POST | `/api/review` | Ревью кода |
| POST | `/api/explain` | Объяснение кода |
| GET | `/api/memory` | Получить все записи памяти |
| POST | `/api/memory` | Добавить запись в память |
| POST | `/api/memory/search` | Поиск по памяти |
| DELETE | `/api/memory/{key}` | Удалить запись из памяти |
| GET | `/api/context` | Контекст текущего проекта |

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `OPENAI_API_KEY` | — | Ключ OpenAI |
| `ANTHROPIC_API_KEY` | — | Ключ Anthropic |
| `GROQ_API_KEY` | — | Ключ Groq |
| `LIDCO_DEFAULT_MODEL` | `gpt-4o-mini` | Модель по умолчанию |
| `LIDCO_LOG_LEVEL` | `INFO` | Уровень логирования |
| `LIDCO_AUTH_TOKEN` | — | Токен авторизации для сервера |
| `LIDCO_ALLOWED_ORIGINS` | `localhost` | Разрешённые CORS-домены |
| `LIDCO_DEBUG` | `0` | Режим отладки (`1` = подробные ошибки) |

---

## Решение проблем

### `lidco: command not found`

Пакет не установлен или venv не активирован:

```bash
# Активируйте виртуальное окружение
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/macOS

# Или запустите напрямую
python -m lidco
python -m lidco serve
```

### `ModuleNotFoundError: No module named 'lidco'`

```bash
pip install -e ".[dev]"
```

### `Connection refused` при обращении к серверу

Сервер не запущен. Проверьте:

```bash
# Запустите сервер в отдельном терминале
lidco serve

# Проверьте, слушает ли порт
# Windows:
netstat -an | findstr 8321
# Linux/macOS:
ss -tlnp | grep 8321
```

### `OPENAI_API_KEY not set` или аналогичная ошибка

API-ключ не найден. Убедитесь, что:
1. Файл `.env` существует и содержит ключ
2. Или переменная окружения установлена в текущем терминале

```bash
# Проверка (Windows CMD):
echo %OPENAI_API_KEY%

# Проверка (PowerShell):
echo $env:OPENAI_API_KEY

# Проверка (Linux/macOS):
echo $OPENAI_API_KEY
```

### Порт 8321 уже занят

```bash
# Используйте другой порт
lidco serve --port 9000

# Или найдите процесс на порту:
# Windows:
netstat -ano | findstr 8321
taskkill /PID <PID> /F

# Linux/macOS:
lsof -i :8321
kill <PID>
```
