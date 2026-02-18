# LIDCO — Быстрый запуск

## 1. Установка

```bash
git clone https://github.com/lidco/lidco.git
cd lidco
pip install -e ".[dev]"
```

## 2. API-ключи

```bash
cp .env.example .env
```

Откройте `.env` и впишите хотя бы один ключ:

```env
OPENAI_API_KEY=sk-...
# или
ANTHROPIC_API_KEY=sk-ant-...
# или Ollama (ключ не нужен, просто запустите ollama serve)
```

## 3. Запуск CLI

```bash
lidco
```

Примеры ввода:

```
напиши функцию сортировки на Python
@reviewer проверь этот код на баги
/model gpt-4o
/agents
/help
/exit
```

## 4. Запуск HTTP-сервера (для IDE)

```bash
lidco serve
```

Проверка:

```bash
curl http://127.0.0.1:8321/api/status
```

Кастомный порт:

```bash
lidco serve --port 9000
```

## 5. Плагин Android Studio

```bash
cd ide/android-studio-plugin
./gradlew buildPlugin
```

Установка: **Settings → Plugins → шестерёнка → Install Plugin from Disk** → выберите `build/distributions/lidco-intellij-plugin-0.1.0.zip` → перезапустите IDE.

Настройка: **Settings → Tools → LIDCO** → Server URL: `http://127.0.0.1:8321`

## 6. Назначение моделей по ролям

Создайте `~/.lidco/llm_providers.yaml`:

```yaml
role_models:
  default:
    model: "gpt-4o-mini"
  coder:
    model: "gpt-4o"
  reviewer:
    model: "claude-sonnet-4-5-20250514"
  completion:
    model: "gpt-4o-mini"
    temperature: 0.0
```

Каждый агент будет использовать свою модель.

## 7. Локальные модели (Ollama)

```bash
# Установите Ollama: https://ollama.com
ollama pull llama3.1
ollama pull codellama
```

В `~/.lidco/llm_providers.yaml`:

```yaml
providers:
  ollama:
    api_base: "http://localhost:11434"
    models:
      - ollama/llama3.1
      - ollama/codellama

role_models:
  default:
    model: "ollama/llama3.1"
  completion:
    model: "ollama/codellama"
```

## Структура команд

| Команда | Что делает |
|---------|-----------|
| `lidco` | Интерактивный CLI |
| `lidco serve` | HTTP-сервер на порту 8321 |
| `lidco serve --port 9000` | Сервер на порту 9000 |
| `lidco serve --host 0.0.0.0` | Доступ по сети |

## Полезные ссылки

- [Документация (RU)](docs/ru/README.md)
- [Справочник API](docs/ru/api-reference.md)
- [Настройка моделей](docs/ru/llm-providers.md)
- [Плагин Android Studio](docs/ru/android-studio-plugin.md)
- [Решение проблем](docs/ru/troubleshooting.md)
