# Как запустить LIDCO

## Быстрый запуск (3 команды)

Откройте **Windows Terminal** (или cmd.exe) и выполните:

```cmd
cd /d F:\projects\lidco
.venv\Scripts\activate
lidco
```

Если виртуальное окружение ещё не создано — см. раздел "Первая установка" ниже.

---

## Режимы работы

### CLI — интерактивный чат

```cmd
lidco
```

Откроется чат с AI. Примеры ввода:

```
напиши функцию сортировки на Python
@reviewer проверь этот код
@architect спроектируй REST API
/model gpt-4o
/agents
/help
/exit
```

### HTTP-сервер — для плагина Android Studio

```cmd
lidco serve
```

Сервер запустится на `http://127.0.0.1:8321`. Оставьте его работать и откройте Android Studio.

---

## Первая установка (один раз)

### Windows

```cmd
cd /d F:\projects\lidco
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

### Linux / macOS

```bash
cd /path/to/lidco
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Настройка API-ключа

Скопируйте `.env.example` в `.env` и впишите ключ:

```cmd
copy .env.example .env
```

Откройте `.env` и добавьте ключ (уже настроен для Z.AI):

```env
ZAI_API_KEY=ваш_ключ
```

---

## Частые проблемы

### `lidco: command not found` / `lidco не является командой`

Виртуальное окружение не активировано:

```cmd
.venv\Scripts\activate
```

### Кракозябры в консоли

Переключите кодировку на UTF-8:

```cmd
chcp 65001
```

### Сервер не отвечает

Убедитесь что сервер запущен в отдельном окне терминала:

```cmd
lidco serve
```

Проверка:

```cmd
curl http://127.0.0.1:8321/api/status
```
