"""Commands: session."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def register(registry: Any) -> None:
    """Register session commands."""
    from lidco.cli.commands.registry import SlashCommand


    # ── Q32: /websearch, /webfetch ────────────────────────────────────────

    async def websearch_handler(arg: str = "", **_: Any) -> str:
        """Search the web via DuckDuckGo and return formatted results."""
        query = arg.strip()
        if not query:
            return (
                "**Usage:** `/websearch <query>`\n\n"
                "Searches DuckDuckGo and returns titles, URLs, and snippets.\n\n"
                "**Example:** `/websearch python asyncio timeout`\n\n"
                "Use `/webfetch <url>` to fetch the full text of any result URL."
            )

        from lidco.tools.web_search import WebSearchTool
        tool = WebSearchTool()
        result = await tool._run(query=query, max_results=8)

        if not result.success:
            return f"Search failed: {result.error}"

        output = result.output

        # Append /webfetch hint if any URLs were returned
        if "https://" in output or "http://" in output:
            output += (
                "\n\n---\n"
                "_Tip: Use `/webfetch <url>` to fetch the full text of any URL above._"
            )

        return output

    async def webfetch_handler(arg: str = "", **_: Any) -> str:
        """Fetch a web page and return its text content."""
        url = arg.strip()
        if not url:
            return (
                "**Usage:** `/webfetch <url>`\n\n"
                "Fetches a web page and returns its plain-text content.\n\n"
                "**Example:** `/webfetch https://docs.python.org/3/library/asyncio.html`"
            )

        from lidco.tools.web_fetch import WebFetchTool
        tool = WebFetchTool()
        result = await tool._run(url=url)

        if not result.success:
            return f"Fetch failed: {result.error}"

        return result.output

    registry.register(SlashCommand("websearch", "Search the web via DuckDuckGo", websearch_handler))
    registry.register(SlashCommand("webfetch", "Fetch a web page as plain text", webfetch_handler))

    # ── Task 152: agent switching ─────────────────────────────────────────

    async def as_handler(arg: str = "", **_: Any) -> str:
        """/as <agent> <message> — одноразовый запрос к конкретному агенту."""
        parts = arg.strip().split(maxsplit=1)
        if len(parts) < 2:
            agents = (
                registry._session.agent_registry.list_names()
                if registry._session
                else []
            )
            available = ", ".join(f"`{a}`" for a in agents) if agents else "—"
            return (
                "**Использование:** `/as <агент> <сообщение>`\n\n"
                f"**Доступные агенты:** {available}\n\n"
                "**Пример:** `/as coder исправь баг в auth.py`"
            )
        agent_name, message = parts[0], parts[1]
        if registry._session:
            available = registry._session.agent_registry.list_names()
            if agent_name not in available:
                return (
                    f"Агент **{agent_name}** не найден.\n"
                    f"Доступные: {', '.join(f'`{a}`' for a in available)}"
                )
        # Reuse the @agent routing in the REPL via the __RETRY__ mechanism
        return f"__RETRY__:@{agent_name} {message}"

    async def lock_handler(arg: str = "", **_: Any) -> str:
        """/lock [<agent>|off] — закрепить агента для всей сессии."""
        arg = arg.strip()

        if not arg:
            if registry.locked_agent:
                return (
                    f"Агент **{registry.locked_agent}** закреплён.\n"
                    "Используйте `/lock off` или `/unlock` для снятия блокировки."
                )
            return (
                "Агент не закреплён — используется авторотация.\n"
                "**Использование:** `/lock <агент>` или `/lock off`"
            )

        if arg in ("off", "clear", "none", "auto"):
            registry.locked_agent = None
            return "Блокировка агента снята — вернулась авторотация."

        if registry._session:
            available = registry._session.agent_registry.list_names()
            if arg not in available:
                return (
                    f"Агент **{arg}** не найден.\n"
                    f"Доступные: {', '.join(f'`{a}`' for a in available)}"
                )
        registry.locked_agent = arg
        return (
            f"Агент **{arg}** закреплён для всей сессии.\n"
            "Каждый запрос теперь идёт к нему. `/unlock` — снять блокировку."
        )

    async def unlock_handler(**_: Any) -> str:
        """/unlock — снять блокировку агента."""
        if registry.locked_agent is None:
            return "Агент не был закреплён."
        prev = registry.locked_agent
        registry.locked_agent = None
        return f"Блокировка агента **{prev}** снята — вернулась авторотация."

    registry.register(SlashCommand("as", "Одноразовый запрос к конкретному агенту: /as <агент> <сообщение>", as_handler))
    registry.register(SlashCommand("lock", "Закрепить агента для сессии: /lock <агент> | /lock off", lock_handler))
    registry.register(SlashCommand("unlock", "Снять блокировку агента", unlock_handler))

    # ── Task 159: /shortcuts ───────────────────────────────────────────────

    async def shortcuts_handler(**_: Any) -> str:
        """/shortcuts — список горячих клавиш."""
        rows = [
            ("Ctrl+L", "/clear — очистить историю (всегда)"),
            ("Ctrl+R", "/retry — повторить последний запрос (если буфер пуст)"),
            ("Ctrl+E", "/export — экспортировать диалог (если буфер пуст)"),
            ("Ctrl+P", "/status — показать дашборд (если буфер пуст)"),
            ("Ctrl+J", "Отправить сообщение (альтернатива Enter)"),
            ("Esc+Enter", "Новая строка (мультилайн режим)"),
        ]
        lines = ["## Горячие клавиши", ""]
        for key, desc in rows:
            lines.append(f"  `{key}` — {desc}")
        lines.append("")
        lines.append("*Подсказка:* начните вводить `/`, затем нажмите Tab для автодополнения команд.")
        return "\n".join(lines)

    registry.register(SlashCommand("shortcuts", "Показать горячие клавиши", shortcuts_handler))

    # ── Task 160: /whois <agent> ───────────────────────────────────────────

    async def whois_handler(arg: str = "", **_: Any) -> str:
        """/whois <agent> — подробная карточка агента."""
        agent_name = arg.strip().lstrip("@")
        if not agent_name:
            agents = (
                registry._session.agent_registry.list_names()
                if registry._session else []
            )
            available = ", ".join(f"`{a}`" for a in agents) if agents else "—"
            return (
                "**Использование:** `/whois <агент>`\n\n"
                f"**Доступные агенты:** {available}\n\n"
                "**Пример:** `/whois coder`"
            )
        if not registry._session:
            return "Сессия не инициализирована."
        known = registry._session.agent_registry.list_names()
        if agent_name not in known:
            available = ", ".join(f"`{n}`" for n in known)
            return (
                f"Агент **{agent_name}** не найден.\n\n"
                f"Доступные: {available}"
            )
        try:
            agent = registry._session.agent_registry.get(agent_name)
        except Exception:
            return f"Ошибка при получении агента **{agent_name}**."
        name = str(agent.name)
        desc = str(agent.description)
        lines = [f"## {name}", "", desc, ""]
        # Show tools if agent exposes them
        try:
            tool_names = list(agent.tools.keys()) if hasattr(agent, "tools") else []
            if tool_names:
                lines.append("**Инструменты:**")
                for t in sorted(tool_names):
                    lines.append(f"  · `{t}`")
                lines.append("")
        except Exception:
            pass
        lines.append(f"*Обратиться: `@{name} <сообщение>` или `/as {name} <сообщение>`*")
        return "\n".join(lines)

    registry.register(SlashCommand("whois", "Карточка агента: описание и инструменты", whois_handler))

    # ── Task 161: /compact ─────────────────────────────────────────────────

    _COMPACT_DEFAULT_KEEP = 6  # keep last 6 messages (3 turns) by default

    async def compact_handler(arg: str = "", **_: Any) -> str:
        """/compact [N] — оставить последние N сообщений, остальное удалить."""
        if not registry._session:
            return "Сессия не инициализирована."
        try:
            keep = int(arg.strip()) if arg.strip() else _COMPACT_DEFAULT_KEEP
            if keep < 2:
                keep = 2
        except ValueError:
            return f"Неверный аргумент: `{arg}`. Использование: `/compact [N]` (N — количество сообщений)."

        orch = registry._session.orchestrator
        history = list(getattr(orch, "_conversation_history", []))
        total = len(history)
        if total <= keep:
            return (
                f"История уже короткая ({total} сообщений). "
                f"Нечего сжимать. Минимум для сжатия: {keep + 1}."
            )
        compacted = history[-keep:]
        orch.restore_history(compacted)
        removed = total - keep
        return (
            f"Контекст сжат: удалено **{removed}** сообщений, "
            f"оставлено последних **{keep}** (из {total})."
        )

    registry.register(SlashCommand(
        "compact",
        "Сжать историю диалога, оставив последние N сообщений [N=6]",
        compact_handler,
    ))

    # ── Task 164: /history ─────────────────────────────────────────────────

    _HISTORY_DEFAULT_TURNS = 5

    async def history_handler(arg: str = "", **_: Any) -> str:
        """/history [N] — показать последние N ходов диалога."""
        if not registry._session:
            return "Сессия не инициализирована."
        try:
            n = int(arg.strip()) if arg.strip() else _HISTORY_DEFAULT_TURNS
            if n < 1:
                n = 1
        except ValueError:
            return f"Неверный аргумент: `{arg}`. Использование: `/history [N]`"

        orch = registry._session.orchestrator
        raw = list(getattr(orch, "_conversation_history", []))
        if not raw:
            return "История диалога пуста."

        # Group into user+assistant pairs (turns)
        turns: list[tuple[str, str]] = []
        i = 0
        while i < len(raw):
            msg = raw[i]
            role = msg.get("role", "")
            content = str(msg.get("content", ""))
            if role == "user":
                assistant_content = ""
                if i + 1 < len(raw) and raw[i + 1].get("role") == "assistant":
                    assistant_content = str(raw[i + 1].get("content", ""))
                    i += 1
                turns.append((content, assistant_content))
            i += 1

        recent = turns[-n:]
        if not recent:
            return "История диалога пуста."

        lines = [f"## История диалога (последние {len(recent)} из {len(turns)} ходов)", ""]
        for idx, (user_msg, asst_msg) in enumerate(recent, start=len(turns) - len(recent) + 1):
            user_preview = user_msg[:120].replace("\n", " ")
            if len(user_msg) > 120:
                user_preview += "…"
            lines.append(f"**Ход {idx}** — Вы: {user_preview}")
            if asst_msg:
                asst_preview = asst_msg[:120].replace("\n", " ")
                if len(asst_msg) > 120:
                    asst_preview += "…"
                lines.append(f"  → Ответ: {asst_preview}")
            lines.append("")
        lines.append(f"*Всего сообщений в истории: {len(raw)}. `/compact` — сжать.*")
        return "\n".join(lines)

    registry.register(SlashCommand("history", "Показать последние N ходов диалога [N=5]", history_handler))

    # ── Task 165: /budget ──────────────────────────────────────────────────

    async def budget_handler(arg: str = "", **_: Any) -> str:
        """/budget [set N] — показать бюджет токенов или установить лимит."""
        if not registry._session:
            return "Сессия не инициализирована."
        tb = registry._session.token_budget

        # /budget set N
        parts = arg.strip().split()
        if parts and parts[0].lower() == "set":
            if len(parts) < 2:
                return "**Использование:** `/budget set <N>` (N — лимит токенов, 0 = без лимита)"
            try:
                limit = int(parts[1].replace("k", "000").replace("K", "000"))
            except ValueError:
                return f"Неверное значение: `{parts[1]}`. Ожидается целое число."
            tb.session_limit = limit
            if limit == 0:
                return "Лимит токенов снят (без ограничений)."
            return f"Лимит токенов установлен: **{limit:,}** токенов."

        # /budget — show status
        total = tb.total_tokens
        limit = tb.session_limit
        cost = getattr(tb, "_total_cost_usd", 0.0)

        def _k(n: int) -> str:
            return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

        lines = ["## Бюджет токенов", ""]
        lines.append(f"**Использовано:** {_k(total)} токенов")
        if cost > 0:
            cost_fmt = f"${cost:.4f}".rstrip("0").rstrip(".")
            lines.append(f"**Стоимость:** {cost_fmt}")
        if limit > 0:
            remaining = max(0, limit - total)
            pct = int(total / limit * 100)
            bar_filled = pct // 5
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            lines.append(f"**Лимит:** {_k(limit)} токенов")
            lines.append(f"**Остаток:** {_k(remaining)} токенов ({100 - pct}%)")
            lines.append(f"`[{bar}]` {pct}%")
        else:
            lines.append("**Лимит:** без ограничений")

        by_role = getattr(tb, "_by_role", {})
        if by_role:
            lines.append("")
            lines.append("**По агентам:**")
            for role, tok in sorted(by_role.items(), key=lambda x: -x[1]):
                lines.append(f"  · {role}: {_k(tok)}")

        lines.append("")
        lines.append("*`/budget set 100000` — установить лимит · `/budget set 0` — снять*")
        return "\n".join(lines)

    registry.register(SlashCommand("budget", "Показать/установить бюджет токенов", budget_handler))

    # ── Task 167: /note ────────────────────────────────────────────────────

    async def note_handler(arg: str = "", **_: Any) -> str:
        """/note [text|clear] — показать/установить/очистить заметку сессии."""
        text = arg.strip()
        if text.lower() == "clear":
            registry.session_note = ""
            return "Заметка сессии очищена."
        if text:
            registry.session_note = text
            return f"Заметка сессии установлена:\n\n> {text}"
        # No arg — show current note
        if registry.session_note:
            return f"**Текущая заметка сессии:**\n\n> {registry.session_note}\n\n*`/note clear` — очистить*"
        return "Заметка сессии не установлена.\n\n*Использование: `/note <текст>` — установить заметку для всех агентов.*"

    registry.register(SlashCommand(
        "note",
        "Установить заметку сессии, добавляемую в контекст агентов",
        note_handler,
    ))

    # ── Task 169: /alias ───────────────────────────────────────────────────

    async def alias_handler(arg: str = "", **_: Any) -> str:
        """/alias [name [command]] — управление псевдонимами команд."""
        parts = arg.strip().split(maxsplit=1)

        if not parts:
            # List all aliases
            if not registry._aliases:
                return "Псевдонимы не определены.\n\n*`/alias <имя> <команда>` — создать псевдоним.*"
            lines = ["## Псевдонимы команд", ""]
            for name, cmd in sorted(registry._aliases.items()):
                lines.append(f"  `/{name}` → `{cmd}`")
            return "\n".join(lines)

        name = parts[0].lstrip("/")
        if len(parts) == 1:
            # Show or delete alias
            if name == "clear":
                registry._aliases.clear()
                return "Все псевдонимы удалены."
            if name in registry._aliases:
                return f"`/{name}` → `{registry._aliases[name]}`"
            return f"Псевдоним `/{name}` не найден."

        # Define alias: /alias name command
        cmd_str = parts[1].strip()
        if not cmd_str.startswith("/"):
            cmd_str = "/" + cmd_str
        registry._aliases[name] = cmd_str
        return f"Псевдоним создан: `/{name}` → `{cmd_str}`"

    registry.register(SlashCommand(
        "alias",
        "Управление псевдонимами команд: /alias <имя> <команда>",
        alias_handler,
    ))

    # ── Task 171: /recent ──────────────────────────────────────────────────

    async def recent_handler(arg: str = "", **_: Any) -> str:
        """/recent [N] — файлы, изменённые в этой сессии."""
        try:
            n = int(arg.strip()) if arg.strip() else 10
            if n < 1:
                n = 1
        except ValueError:
            n = 10

        files = list(dict.fromkeys(registry._edited_files))  # dedupe, preserve order
        if not files:
            return "В этой сессии файлы не изменялись."
        recent = files[-n:]
        lines = [f"## Изменённые файлы (последние {len(recent)} из {len(files)})", ""]
        for i, f in enumerate(recent, 1):
            lines.append(f"  {i}. `{f}`")
        lines.append(f"\n*`/undo` — откатить · `/diff` — просмотреть изменения*")
        return "\n".join(lines)

    registry.register(SlashCommand("recent", "Файлы, изменённые в текущей сессии", recent_handler))

    # ── Task 172: /focus ───────────────────────────────────────────────────

    async def focus_handler(arg: str = "", **_: Any) -> str:
        """/focus [file|clear] — закрепить файл в контексте агентов."""
        text = arg.strip()
        if text.lower() == "clear":
            registry.focus_file = ""
            return "Фокус снят."
        if not text:
            if registry.focus_file:
                return (
                    f"**Текущий фокус:** `{registry.focus_file}`\n\n"
                    f"*`/focus clear` — снять фокус*"
                )
            return (
                "Фокус не установлен.\n\n"
                "*Использование: `/focus <путь_к_файлу>` — "
                "содержимое файла будет добавлено в контекст каждого агента.*"
            )
        from pathlib import Path as _Path
        p = _Path(text)
        if not p.exists():
            return f"Файл не найден: `{text}`"
        if not p.is_file():
            return f"Это не файл: `{text}`"
        registry.focus_file = str(p)
        size = p.stat().st_size
        return (
            f"Фокус установлен: `{p}` ({size} байт)\n\n"
            f"*Содержимое файла будет добавляться в контекст каждого хода.*"
        )

    registry.register(SlashCommand(
        "focus",
        "Закрепить файл в контексте агентов: /focus <файл> | /focus clear",
        focus_handler,
    ))

    # ── Task 173: /pin ─────────────────────────────────────────────────────

    async def pin_handler(arg: str = "", **_: Any) -> str:
        """/pin [add <text> | del <N> | clear | list] — закреплённые заметки."""
        text = arg.strip()
        if not text or text == "list":
            if not registry._pins:
                return (
                    "Нет закреплённых заметок.\n\n"
                    "*`/pin add <текст>` — добавить закреплённую заметку.*"
                )
            lines = ["## Закреплённые заметки", ""]
            for i, pin in enumerate(registry._pins, 1):
                preview = pin[:100].replace("\n", " ")
                if len(pin) > 100:
                    preview += "…"
                lines.append(f"  **{i}.** {preview}")
            lines.append("")
            lines.append("*`/pin del <N>` — удалить · `/pin clear` — очистить все*")
            return "\n".join(lines)

        if text == "clear":
            count = len(registry._pins)
            registry._pins.clear()
            return f"Удалено {count} закреплённых заметок."

        if text.startswith("del "):
            num_str = text[4:].strip()
            try:
                idx = int(num_str) - 1
            except ValueError:
                return f"Неверный номер: `{num_str}`. Использование: `/pin del <N>`"
            if idx < 0 or idx >= len(registry._pins):
                return f"Заметка #{num_str} не существует (всего {len(registry._pins)})."
            removed = registry._pins.pop(idx)
            preview = removed[:60].replace("\n", " ")
            return f"Заметка #{num_str} удалена: «{preview}»"

        if text == "add":
            return "Текст заметки не может быть пустым. Использование: `/pin add <текст>`"

        if text.startswith("add "):
            content = text[4:].strip()
            if not content:
                return "Текст заметки не может быть пустым."
            registry._pins.append(content)
            n = len(registry._pins)
            preview = content[:60].replace("\n", " ")
            return f"Заметка #{n} закреплена: «{preview}»"

        # No subcommand — treat whole arg as text to add
        registry._pins.append(text)
        n = len(registry._pins)
        preview = text[:60].replace("\n", " ")
        return f"Заметка #{n} закреплена: «{preview}»"

    registry.register(SlashCommand(
        "pin",
        "Закреплённые заметки, добавляемые в контекст: /pin add <текст> | /pin del <N> | /pin clear",
        pin_handler,
    ))

    # ── Task 174: /vars ────────────────────────────────────────────────────

    async def vars_handler(arg: str = "", **_: Any) -> str:
        """/vars [set NAME value | del NAME | clear | list] — шаблонные переменные."""
        text = arg.strip()

        if not text or text == "list":
            if not registry._vars:
                return (
                    "Переменные сессии не определены.\n\n"
                    "*`/vars set NAME значение` — задать переменную.*\n"
                    "*В сообщениях используйте `{{NAME}}` для подстановки.*"
                )
            lines = ["## Переменные сессии", ""]
            for name, val in sorted(registry._vars.items()):
                preview = str(val)[:80].replace("\n", "↵")
                lines.append(f"  `{{{{` **{name}** `}}}}` = `{preview}`")
            lines.append("")
            lines.append("*`{{NAME}}` в сообщении будет заменено на значение переменной.*")
            return "\n".join(lines)

        if text == "clear":
            count = len(registry._vars)
            registry._vars.clear()
            return f"Удалено {count} переменных."

        if text.startswith("del "):
            name = text[4:].strip()
            if not name:
                return "Укажите имя переменной: `/vars del NAME`"
            if name not in registry._vars:
                return f"Переменная `{name}` не найдена."
            del registry._vars[name]
            return f"Переменная `{name}` удалена."

        if text.startswith("set "):
            rest = text[4:].strip()
            parts = rest.split(maxsplit=1)
            if len(parts) < 2:
                return "**Использование:** `/vars set NAME значение`"
            name, value = parts[0].upper(), parts[1]
            if not name.replace("_", "").isalnum():
                return f"Имя переменной `{name}` содержит недопустимые символы (только буквы, цифры, _)."
            registry._vars[name] = value
            return f"Переменная `{name}` = `{value}`"

        return (
            "**Команды /vars:**\n\n"
            "- `/vars` — список переменных\n"
            "- `/vars set NAME значение` — задать переменную\n"
            "- `/vars del NAME` — удалить переменную\n"
            "- `/vars clear` — очистить все переменные\n\n"
            "*В сообщениях `{{NAME}}` заменяется на значение переменной.*"
        )

    registry.register(SlashCommand(
        "vars",
        "Переменные сессии для шаблонной подстановки {{VAR}} в сообщениях",
        vars_handler,
    ))

    # ── Task 175: /timing ──────────────────────────────────────────────────

    async def timing_handler(arg: str = "", **_: Any) -> str:
        """/timing — статистика времени выполнения ходов."""
        times = registry._turn_times
        if not times:
            return (
                "Данных о времени ходов ещё нет.\n\n"
                "*Статистика появится после завершения первого хода.*"
            )

        arg = arg.strip().lower()
        n = len(times)
        total = sum(times)
        avg = total / n
        mn = min(times)
        mx = max(times)

        lines = ["## Время выполнения ходов", ""]
        lines.append(f"**Ходов:** {n}")
        lines.append(f"**Среднее:** {avg:.1f}с")
        lines.append(f"**Мин / Макс:** {mn:.1f}с / {mx:.1f}с")
        lines.append(f"**Итого:** {total:.1f}с")

        # Show individual turns if asked or few enough
        if arg == "all" or n <= 10:
            lines.append("")
            lines.append("**По ходам:**")
            for i, t in enumerate(times, 1):
                bar_len = min(20, int(t / mx * 20)) if mx > 0 else 0
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(f"  Ход {i:>3}: {t:5.1f}с  [{bar}]")
        elif n > 10:
            lines.append("")
            lines.append(f"*Показаны сводные данные. `/timing all` — все {n} ходов.*")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "timing",
        "Статистика времени выполнения ходов",
        timing_handler,
    ))

    # ── Task 176: /diff ────────────────────────────────────────────────────

    async def diff_handler(arg: str = "", **_: Any) -> str:
        """/diff [file] — показать git diff для файла или всех изменений."""
        import asyncio as _asyncio

        path_arg = arg.strip()

        async def _run_git(*cmd: str) -> tuple[str, int]:
            try:
                p = await _asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.PIPE,
                )
                stdout, _ = await _asyncio.wait_for(p.communicate(), timeout=10)
                return stdout.decode("utf-8", errors="replace"), p.returncode or 0
            except _asyncio.TimeoutError:
                return "", -1
            except FileNotFoundError:
                return "", -2

        if path_arg:
            out, rc = await _run_git("git", "diff", "HEAD", "--", path_arg)
            if rc == -2:
                return "Git not found."
            if not out.strip():
                # Try staged
                out, rc = await _run_git("git", "diff", "--cached", "--", path_arg)
            if not out.strip():
                return f"Нет изменений для `{path_arg}`."
        else:
            out, rc = await _run_git("git", "diff", "HEAD")
            if rc == -2:
                return "Git not found."
            if not out.strip():
                out, rc = await _run_git("git", "diff", "--cached")
            if not out.strip():
                if registry._edited_files:
                    files_hint = ", ".join(f"`{f}`" for f in list(dict.fromkeys(registry._edited_files))[:5])
                    return (
                        f"Нет незафиксированных изменений.\n\n"
                        f"Изменённые в сессии файлы: {files_hint}\n\n"
                        "*Возможно, изменения уже зафиксированы (`/commit`).*"
                    )
                return "Нет незафиксированных изменений."

        # Limit output
        _MAX_DIFF_LINES = 300
        lines = out.splitlines()
        truncated = len(lines) > _MAX_DIFF_LINES
        display = "\n".join(lines[:_MAX_DIFF_LINES])
        if truncated:
            display += f"\n... ({len(lines) - _MAX_DIFF_LINES} строк скрыто)"

        title = f"git diff — {path_arg}" if path_arg else "git diff HEAD"
        return f"```diff\n{display}\n```\n\n*{title}*"

    registry.register(SlashCommand(
        "diff",
        "Показать git diff для файла или всех изменений: /diff [файл]",
        diff_handler,
    ))

    # ── Task 177: /snapshot ────────────────────────────────────────────────

    async def snapshot_handler(arg: str = "", **_: Any) -> str:
        """/snapshot [save <name> | load <name> | list | del <name>] — снэпшоты истории."""
        text = arg.strip()

        if not text or text == "list":
            if not registry._snapshots:
                return (
                    "Снэпшоты не сохранены.\n\n"
                    "*`/snapshot save <имя>` — сохранить текущую историю диалога.*"
                )
            lines = ["## Снэпшоты сессии", ""]
            for name, data in sorted(registry._snapshots.items()):
                msg_count = len(data)
                lines.append(f"  · **{name}** ({msg_count} сообщений)")
            lines.append("")
            lines.append("*`/snapshot load <имя>` — восстановить · `/snapshot del <имя>` — удалить*")
            return "\n".join(lines)

        if text.startswith("save "):
            name = text[5:].strip()
            if not name:
                return "Укажите имя снэпшота: `/snapshot save <имя>`"
            if not registry._session:
                # Allow saving empty snapshot for testing
                registry._snapshots[name] = []
                return f"Снэпшот **{name}** сохранён (0 сообщений)."
            orch = registry._session.orchestrator
            history = list(getattr(orch, "_conversation_history", []))
            registry._snapshots[name] = history
            return f"Снэпшот **{name}** сохранён ({len(history)} сообщений)."

        if text.startswith("load "):
            name = text[5:].strip()
            if not name:
                return "Укажите имя снэпшота: `/snapshot load <имя>`"
            if name not in registry._snapshots:
                available = ", ".join(f"`{n}`" for n in sorted(registry._snapshots))
                hint = f"\n\nДоступные: {available}" if available else ""
                return f"Снэпшот `{name}` не найден.{hint}"
            if not registry._session:
                return f"Сессия не инициализирована. Не могу загрузить снэпшот `{name}`."
            history = registry._snapshots[name]
            registry._session.orchestrator.restore_history(list(history))
            return f"Снэпшот **{name}** восстановлен ({len(history)} сообщений)."

        if text.startswith("del "):
            name = text[4:].strip()
            if not name:
                return "Укажите имя снэпшота: `/snapshot del <имя>`"
            if name not in registry._snapshots:
                return f"Снэпшот `{name}` не найден."
            del registry._snapshots[name]
            return f"Снэпшот `{name}` удалён."

        if text == "clear":
            count = len(registry._snapshots)
            registry._snapshots.clear()
            return f"Удалено {count} снэпшотов."

        return (
            "**Команды /snapshot:**\n\n"
            "- `/snapshot save <имя>` — сохранить текущую историю диалога\n"
            "- `/snapshot load <имя>` — восстановить историю из снэпшота\n"
            "- `/snapshot del <имя>` — удалить снэпшот\n"
            "- `/snapshot list` — список сохранённых снэпшотов\n"
            "- `/snapshot clear` — удалить все снэпшоты"
        )

    registry.register(SlashCommand(
        "snapshot",
        "Снэпшоты истории диалога: /snapshot save|load|del|list",
        snapshot_handler,
    ))

    # ── Task 178: /grep ────────────────────────────────────────────────────

    async def grep_handler(arg: str = "", **_: Any) -> str:
        """/grep <pattern> [path] — поиск паттерна в исходном коде."""
        import asyncio as _asyncio
        import re as _re

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/grep <паттерн> [путь]`\n\n"
                "Ищет паттерн (regex) в исходном коде проекта.\n\n"
                "**Примеры:**\n"
                "  `/grep def authenticate`\n"
                "  `/grep TODO src/lidco/core/`\n"
                "  `/grep 'class.*Error' src/`"
            )

        # Split off optional path (last token if it looks like a path)
        parts = text.split()
        search_path = "."
        pattern = text
        if len(parts) >= 2:
            last = parts[-1]
            # Treat as path if it has / or \ or . in it (not a regex special)
            if ("/" in last or "\\" in last or last.endswith(".py")):
                search_path = last
                pattern = " ".join(parts[:-1])

        from pathlib import Path as _Path

        root = _Path(search_path)
        if not root.exists():
            return f"Путь не найден: `{search_path}`"

        try:
            pat_re = _re.compile(pattern)
        except _re.error as exc:
            return f"Неверный regex: `{pattern}` — {exc}"

        if root.is_file():
            py_files = [root]
        else:
            py_files = sorted(root.rglob("*.py"))

        _MAX_RESULTS = 50
        results: list[tuple[str, int, str]] = []
        for pyf in py_files:
            if len(results) >= _MAX_RESULTS:
                break
            # Skip common non-project dirs
            parts_path = pyf.parts
            if any(p in parts_path for p in (".git", "__pycache__", ".venv", "venv", "node_modules")):
                continue
            try:
                for lineno, line in enumerate(
                    pyf.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                ):
                    if pat_re.search(line):
                        rel = str(pyf)
                        results.append((rel, lineno, line.rstrip()))
                        if len(results) >= _MAX_RESULTS:
                            break
            except OSError:
                pass

        if not results:
            return f"Паттерн `{pattern}` не найден в `{search_path}`."

        lines = [f"## Grep: `{pattern}` ({len(results)} совпадений)", ""]
        current_file = ""
        for file_path, lineno, line_content in results:
            if file_path != current_file:
                current_file = file_path
                lines.append(f"**{file_path}**")
            preview = line_content.strip()[:120]
            lines.append(f"  `{lineno}:` {preview}")

        if len(results) >= _MAX_RESULTS:
            lines.append(f"\n*Показано {_MAX_RESULTS} совпадений. Уточните паттерн или путь для сужения поиска.*")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "grep",
        "Поиск паттерна (regex) в исходном коде: /grep <паттерн> [путь]",
        grep_handler,
    ))

    # ── Task 179: /watch ───────────────────────────────────────────────────

    async def watch_handler(arg: str = "", **_: Any) -> str:
        """/watch [add <path> | remove <path> | list | clear | status] — отслеживать изменения файлов."""
        from pathlib import Path as _Path
        import os as _os

        text = arg.strip()

        def _snapshot(paths: list[str]) -> dict[str, float]:
            """Return mtime mapping for all watched paths."""
            result: dict[str, float] = {}
            for p in paths:
                try:
                    result[p] = _os.path.getmtime(p)
                except OSError:
                    result[p] = -1.0
            return result

        if not text or text == "list" or text == "status":
            watched = registry._watched_files
            if not watched:
                return (
                    "Нет отслеживаемых файлов.\n\n"
                    "*`/watch add <путь>` — начать отслеживание файла.*"
                )
            lines = ["## Отслеживаемые файлы", ""]
            snap = registry._watch_snapshot
            for p in watched:
                mtime = snap.get(p, -1.0)
                try:
                    current = _os.path.getmtime(p)
                    changed = current != mtime and mtime >= 0
                    status = " ⚡ изменён" if changed else " ✓"
                except OSError:
                    status = " ✗ не найден"
                lines.append(f"  · `{p}`{status}")
            lines.append("")
            lines.append("*`/watch remove <путь>` — убрать · `/watch clear` — убрать все · `/watch check` — проверить изменения*")
            return "\n".join(lines)

        if text.startswith("add "):
            path_str = text[4:].strip()
            if not path_str:
                return "Укажите путь: `/watch add <путь>`"
            p = _Path(path_str)
            if not p.exists():
                return f"Путь не найден: `{path_str}`"
            path_str_resolved = str(p)
            if path_str_resolved in registry._watched_files:
                return f"Файл `{path_str_resolved}` уже отслеживается."
            registry._watched_files.append(path_str_resolved)
            try:
                registry._watch_snapshot[path_str_resolved] = _os.path.getmtime(path_str_resolved)
            except OSError:
                registry._watch_snapshot[path_str_resolved] = -1.0
            return f"Отслеживание начато: `{path_str_resolved}`"

        if text.startswith("remove ") or text.startswith("rm "):
            sep = "remove " if text.startswith("remove ") else "rm "
            path_str = text[len(sep):].strip()
            if path_str in registry._watched_files:
                registry._watched_files.remove(path_str)
                registry._watch_snapshot.pop(path_str, None)
                return f"Отслеживание остановлено: `{path_str}`"
            return f"Файл `{path_str}` не отслеживается."

        if text == "clear":
            count = len(registry._watched_files)
            registry._watched_files.clear()
            registry._watch_snapshot.clear()
            return f"Убрано {count} отслеживаемых файлов."

        if text == "check":
            watched = registry._watched_files
            if not watched:
                return "Нет отслеживаемых файлов."
            changed: list[str] = []
            for p in watched:
                try:
                    current = _os.path.getmtime(p)
                    prev = registry._watch_snapshot.get(p, -1.0)
                    if current != prev:
                        changed.append(p)
                        registry._watch_snapshot[p] = current
                except OSError:
                    pass
            if not changed:
                return f"Изменений нет (проверено {len(watched)} файлов)."
            lines = [f"**Изменено {len(changed)} файлов:**", ""]
            for p in changed:
                lines.append(f"  · `{p}`")
            lines.append("\n*Используйте `/diff <файл>` для просмотра изменений.*")
            return "\n".join(lines)

        return (
            "**Команды /watch:**\n\n"
            "- `/watch add <путь>` — начать отслеживание\n"
            "- `/watch remove <путь>` — остановить отслеживание\n"
            "- `/watch list` — список отслеживаемых файлов\n"
            "- `/watch check` — проверить изменения\n"
            "- `/watch clear` — убрать все\n"
        )

    registry.register(SlashCommand(
        "watch",
        "Отслеживать изменения файлов: /watch add|remove|list|check|clear",
        watch_handler,
    ))

    # ── Task 180: /tag ─────────────────────────────────────────────────────

    async def tag_handler(arg: str = "", **_: Any) -> str:
        """/tag [add <label> | list | del <label> | jump <label>] — теги для ходов диалога."""
        text = arg.strip()

        if not text or text == "list":
            if not registry._tags:
                return (
                    "Нет тегов.\n\n"
                    "*`/tag add <метка>` — пометить текущий ход тегом.*"
                )
            lines = ["## Теги диалога", ""]
            for label, turn_idx in sorted(registry._tags.items()):
                lines.append(f"  · **#{label}** → ход {turn_idx}")
            lines.append("")
            lines.append("*`/tag del <метка>` — удалить тег*")
            return "\n".join(lines)

        if text.startswith("add "):
            label = text[4:].strip()
            if not label:
                return "Укажите метку: `/tag add <метка>`"
            if not label.replace("-", "").replace("_", "").isalnum():
                return f"Метка `{label}` содержит недопустимые символы (только буквы, цифры, -, _)."
            # Use current history length as the turn marker
            turn_idx = 0
            if registry._session:
                orch = registry._session.orchestrator
                turn_idx = len(getattr(orch, "_conversation_history", []))
            else:
                turn_idx = len(registry._turn_times)
            registry._tags[label] = turn_idx
            return f"Тег **#{label}** установлен на ход {turn_idx}."

        if text.startswith("del "):
            label = text[4:].strip()
            if label not in registry._tags:
                return f"Тег `#{label}` не найден."
            del registry._tags[label]
            return f"Тег **#{label}** удалён."

        if text == "clear":
            count = len(registry._tags)
            registry._tags.clear()
            return f"Удалено {count} тегов."

        if text.startswith("jump "):
            label = text[5:].strip()
            if label not in registry._tags:
                available = ", ".join(f"`#{k}`" for k in sorted(registry._tags))
                hint = f"\n\nДоступные: {available}" if available else ""
                return f"Тег `#{label}` не найден.{hint}"
            turn_idx = registry._tags[label]
            if not registry._session:
                return f"Сессия не инициализирована. Тег **#{label}** указывает на ход {turn_idx}."
            orch = registry._session.orchestrator
            history = list(getattr(orch, "_conversation_history", []))
            if turn_idx > len(history):
                return f"Тег **#{label}** указывает на ход {turn_idx}, но история содержит только {len(history)} сообщений."
            orch.restore_history(history[:turn_idx])
            return f"История восстановлена до тега **#{label}** (ход {turn_idx}, {turn_idx} сообщений)."

        # Bare word — treat as shortcut for add
        label = text
        if not label.replace("-", "").replace("_", "").isalnum():
            return f"Метка `{label}` содержит недопустимые символы. Использование: `/tag add <метка>`"
        turn_idx = len(registry._turn_times)
        registry._tags[label] = turn_idx
        return f"Тег **#{label}** установлен на ход {turn_idx}."

    registry.register(SlashCommand(
        "tag",
        "Теги для ходов диалога: /tag add <метка> | /tag jump <метка> | /tag list",
        tag_handler,
    ))

    # ── Task 181: /summary ─────────────────────────────────────────────────

    async def summary_handler(arg: str = "", **_: Any) -> str:
        """/summary — краткое резюме текущего диалога."""
        if not registry._session:
            return "Сессия не инициализирована."

        orch = registry._session.orchestrator
        history = list(getattr(orch, "_conversation_history", []))

        if not history:
            return "История диалога пуста."

        # Build a condensed transcript (user messages only, or last N pairs)
        _MAX_CHARS = 6000
        pairs: list[str] = []
        total_chars = 0
        for msg in reversed(history):
            role = msg.get("role", "")
            content = str(msg.get("content", ""))[:400]
            if role in ("user", "assistant"):
                entry = f"{role.upper()}: {content}"
                total_chars += len(entry)
                pairs.insert(0, entry)
                if total_chars >= _MAX_CHARS:
                    break

        transcript = "\n\n".join(pairs)

        from lidco.llm.base import Message as LLMMessage
        try:
            resp = await registry._session.llm.complete(
                [LLMMessage(role="user", content=(
                    "Summarize this conversation in 3-5 bullet points in Russian. "
                    "Focus on what was accomplished, what was decided, and what's pending.\n\n"
                    f"CONVERSATION:\n{transcript}\n\n"
                    "Output ONLY the bullet points, no preamble."
                ))],
                temperature=0.3,
                max_tokens=300,
            )
            summary_text = (resp.content or "").strip()
        except Exception as exc:
            return f"Не удалось сгенерировать резюме: {exc}"

        turn_count = sum(1 for m in history if m.get("role") == "user")
        return (
            f"## Резюме диалога ({turn_count} ходов)\n\n"
            f"{summary_text}\n\n"
            f"*`/history` — полная история · `/compact` — сжать контекст*"
        )

    registry.register(SlashCommand(
        "summary",
        "Краткое AI-резюме текущего диалога",
        summary_handler,
    ))

    # ── Task 182: /profile ─────────────────────────────────────────────────

    async def profile_handler(arg: str = "", **_: Any) -> str:
        """/profile — статистика производительности по агентам."""
        if not registry._agent_stats:
            return (
                "Статистика агентов пока недоступна.\n\n"
                "*Данные появятся после первого обращения к агенту.*"
            )

        arg = arg.strip().lower()

        # /profile reset
        if arg == "reset":
            registry._agent_stats.clear()
            return "Статистика агентов сброшена."

        # /profile <agent> — single agent details
        if arg and arg != "all":
            stats = registry._agent_stats.get(arg)
            if not stats:
                available = ", ".join(f"`{k}`" for k in sorted(registry._agent_stats))
                return (
                    f"Агент `{arg}` не найден в статистике.\n\n"
                    f"Доступные: {available}"
                )
            calls = stats.get("calls", 0)
            tokens = stats.get("tokens", 0)
            elapsed = stats.get("elapsed", 0.0)
            avg_t = elapsed / calls if calls else 0.0
            avg_tok = tokens // calls if calls else 0
            lines = [
                f"## Профиль: {arg}", "",
                f"**Вызовов:** {calls}",
                f"**Токенов:** {tokens:,}",
                f"**Время:** {elapsed:.1f}с итого · {avg_t:.1f}с среднее",
                f"**Токенов/вызов:** {avg_tok:,}",
            ]
            return "\n".join(lines)

        # /profile — full table
        def _k(n: int) -> str:
            return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

        lines = ["## Профиль агентов", ""]
        sorted_agents = sorted(
            registry._agent_stats.items(),
            key=lambda x: -x[1].get("tokens", 0),
        )
        for agent_name, stats in sorted_agents:
            calls = stats.get("calls", 0)
            tokens = stats.get("tokens", 0)
            elapsed = stats.get("elapsed", 0.0)
            avg_t = elapsed / calls if calls else 0.0
            lines.append(
                f"  **{agent_name}** — {calls} вызовов · "
                f"{_k(tokens)} токенов · {elapsed:.1f}с итого · {avg_t:.1f}с avg"
            )

        lines.append("")
        lines.append("*`/profile <агент>` — детали · `/profile reset` — сбросить*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "profile",
        "Статистика производительности по агентам",
        profile_handler,
    ))

    # ── Task 183: /template ────────────────────────────────────────────────

    async def template_handler(arg: str = "", **_: Any) -> str:
        """/template [save <name> <text> | use <name> [vars] | list | del <name>] — шаблоны сообщений."""
        import re as _re
        text = arg.strip()

        if not text or text == "list":
            if not registry._templates:
                return (
                    "Шаблоны не определены.\n\n"
                    "*`/template save <имя> <текст>` — сохранить шаблон.*\n"
                    "*Используйте `{{PLACEHOLDER}}` для переменных.*"
                )
            lines = ["## Шаблоны сообщений", ""]
            for name, tmpl in sorted(registry._templates.items()):
                preview = tmpl[:80].replace("\n", " ")
                if len(tmpl) > 80:
                    preview += "…"
                # Find placeholders
                placeholders = _re.findall(r"\{\{([A-Z0-9_]+)\}\}", tmpl)
                ph_hint = f" [{', '.join(placeholders)}]" if placeholders else ""
                lines.append(f"  · **{name}**{ph_hint}: `{preview}`")
            lines.append("")
            lines.append("*`/template use <имя>` — применить · `/template del <имя>` — удалить*")
            return "\n".join(lines)

        if text.startswith("save "):
            rest = text[5:].strip()
            parts = rest.split(maxsplit=1)
            if len(parts) < 2:
                return "**Использование:** `/template save <имя> <текст шаблона>`"
            name, tmpl_text = parts[0], parts[1]
            if not name.replace("-", "").replace("_", "").isalnum():
                return f"Имя шаблона `{name}` содержит недопустимые символы."
            registry._templates[name] = tmpl_text
            placeholders = _re.findall(r"\{\{([A-Z0-9_]+)\}\}", tmpl_text)
            ph_note = f"\n\nПеременные: {', '.join(f'`{{{{{p}}}}}`' for p in placeholders)}" if placeholders else ""
            return f"Шаблон **{name}** сохранён.{ph_note}"

        if text.startswith("use "):
            rest = text[4:].strip()
            parts = rest.split(maxsplit=1)
            if not parts:
                return "Укажите имя шаблона: `/template use <имя> [KEY=value ...]`"
            name = parts[0]
            if name not in registry._templates:
                available = ", ".join(f"`{n}`" for n in sorted(registry._templates))
                hint = f"\n\nДоступные: {available}" if available else ""
                return f"Шаблон `{name}` не найден.{hint}"
            tmpl_text = registry._templates[name]
            # Parse KEY=value pairs from remainder
            overrides: dict[str, str] = {}
            if len(parts) > 1:
                for kv in parts[1].split():
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        overrides[k.upper()] = v
            # Apply: first /vars, then overrides
            merged = {**registry._vars, **overrides}
            result_text = _re.sub(
                r"\{\{([A-Z0-9_]+)\}\}",
                lambda m: merged.get(m.group(1), m.group(0)),
                tmpl_text,
            )
            # Check for unfilled placeholders
            remaining = _re.findall(r"\{\{([A-Z0-9_]+)\}\}", result_text)
            if remaining:
                return (
                    f"Шаблон **{name}** содержит незаполненные переменные: "
                    f"{', '.join(f'`{{{{{p}}}}}`' for p in remaining)}\n\n"
                    f"Используйте `/template use {name} KEY=value ...` для подстановки.\n\n"
                    f"Текущий результат:\n\n> {result_text}"
                )
            return f"__RETRY__:{result_text}"

        if text.startswith("del "):
            name = text[4:].strip()
            if name not in registry._templates:
                return f"Шаблон `{name}` не найден."
            del registry._templates[name]
            return f"Шаблон **{name}** удалён."

        if text.startswith("show "):
            name = text[5:].strip()
            if name not in registry._templates:
                return f"Шаблон `{name}` не найден."
            return f"**{name}:**\n\n```\n{registry._templates[name]}\n```"

        if text == "clear":
            count = len(registry._templates)
            registry._templates.clear()
            return f"Удалено {count} шаблонов."

        return (
            "**Команды /template:**\n\n"
            "- `/template save <имя> <текст>` — сохранить шаблон\n"
            "- `/template use <имя> [KEY=value ...]` — применить шаблон\n"
            "- `/template show <имя>` — показать шаблон\n"
            "- `/template del <имя>` — удалить\n"
            "- `/template list` — список всех шаблонов\n"
            "- `/template clear` — удалить все\n\n"
            "*Переменные в тексте: `{{PLACEHOLDER}}`.*"
        )

    registry.register(SlashCommand(
        "template",
        "Шаблоны сообщений с переменными: /template save|use|list|del",
        template_handler,
    ))

    # ── Task 184: /pipe ────────────────────────────────────────────────────

    async def pipe_handler(arg: str = "", **_: Any) -> str:
        """/pipe <agent1> | <agent2> [| ...] <message> — передать ответ через цепочку агентов."""
        if not arg.strip():
            return (
                "**Использование:** `/pipe <агент1> | <агент2> <сообщение>`\n\n"
                "Передаёт ответ первого агента на вход следующему.\n\n"
                "**Пример:** `/pipe coder | tester напиши функцию сортировки`\n\n"
                "*Первый агент получает оригинальное сообщение, каждый следующий — ответ предыдущего.*"
            )

        if not registry._session:
            return "Сессия не инициализирована."

        # Parse: split by " | " but keep last segment as message for first agent
        # Format: "agent1 | agent2 | agent3 message"
        # or:    "agent1 | agent2 message" where message goes to agent1
        raw = arg.strip()
        segments = [s.strip() for s in raw.split("|")]

        if len(segments) < 2:
            return (
                "Укажите хотя бы двух агентов через `|`.\n\n"
                "**Пример:** `/pipe coder | tester напиши функцию`"
            )

        # Last segment may contain "agentN message" or just "agentN"
        # First segment: "agent1 message" (message sent to first agent)
        first_parts = segments[0].split(maxsplit=1)
        first_agent = first_parts[0]
        message = first_parts[1] if len(first_parts) > 1 else ""

        # Middle agents: pure agent names
        middle_agents = []
        for seg in segments[1:-1]:
            middle_agents.append(seg.strip().split()[0])

        # Last agent: may have trailing message appended
        last_parts = segments[-1].split(maxsplit=1)
        last_agent = last_parts[0]
        if not message and len(last_parts) > 1:
            message = last_parts[1]

        agents = [first_agent] + middle_agents + [last_agent]

        if not message:
            return "Укажите сообщение для первого агента."

        # Validate all agents exist
        available = registry._session.agent_registry.list_names()
        for a in agents:
            if a not in available:
                return (
                    f"Агент **{a}** не найден.\n"
                    f"Доступные: {', '.join(f'`{n}`' for n in available)}"
                )

        # Execute pipeline
        current_message = message
        results: list[tuple[str, str]] = []
        for i, agent_name in enumerate(agents):
            try:
                response = await registry._session.orchestrator.handle(
                    current_message,
                    agent_name=agent_name,
                )
                current_message = response.content or ""
                results.append((agent_name, current_message))
            except Exception as exc:
                results.append((agent_name, f"[Ошибка: {exc}]"))
                break

        # Format output
        lines = [f"## Pipe: {' → '.join(agents)}", ""]
        for step, (agent_name, output) in enumerate(results, 1):
            preview = output[:300]
            if len(output) > 300:
                preview += "…"
            lines.append(f"**Шаг {step} ({agent_name}):**")
            lines.append(preview)
            if step < len(results):
                lines.append("")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "pipe",
        "Цепочка агентов: /pipe агент1 | агент2 сообщение",
        pipe_handler,
    ))

    # ── Task 185: /mode ────────────────────────────────────────────────────

    _MODES: dict[str, dict] = {
        "focus": {
            "desc": "Минимальный вывод, только суть ответа. Без подсказок и предложений.",
            "no_suggestions": True,
            "no_tool_display": True,
        },
        "normal": {
            "desc": "Стандартный режим (по умолчанию).",
            "no_suggestions": False,
            "no_tool_display": False,
        },
        "verbose": {
            "desc": "Подробный вывод: все инструменты, токены, подсказки.",
            "no_suggestions": False,
            "no_tool_display": False,
            "show_tokens": True,
        },
        "quiet": {
            "desc": "Тихий режим: вывод только финального ответа, без технических деталей.",
            "no_suggestions": True,
            "no_tool_display": True,
        },
    }

    async def mode_handler(arg: str = "", **_: Any) -> str:
        """/mode [focus|normal|verbose|quiet] — переключить режим взаимодействия."""
        text = arg.strip().lower()

        if not text:
            current = registry.session_mode
            mode_info = _MODES.get(current, {})
            lines = [f"**Режим:** `{current}`", "", mode_info.get("desc", ""), ""]
            lines.append("**Доступные режимы:**")
            for name, info in _MODES.items():
                marker = " ← текущий" if name == current else ""
                lines.append(f"  · `{name}`{marker} — {info['desc']}")
            lines.append("\n*`/mode <название>` — переключить режим*")
            return "\n".join(lines)

        if text not in _MODES:
            names = ", ".join(f"`{n}`" for n in _MODES)
            return f"Неизвестный режим `{text}`.\n\nДоступные: {names}"

        registry.session_mode = text
        info = _MODES[text]
        return f"Режим переключён на **{text}**.\n\n{info['desc']}"

    registry.register(SlashCommand(
        "mode",
        "Режим взаимодействия: /mode focus|normal|verbose|quiet",
        mode_handler,
    ))

    # ── Task 186: /autosave ────────────────────────────────────────────────

    async def autosave_handler(arg: str = "", **_: Any) -> str:
        """/autosave [on|off|N|status] — автоэкспорт сессии каждые N ходов."""
        text = arg.strip().lower()

        if not text or text == "status":
            interval = registry._autosave_interval
            count = registry._autosave_turn_count
            if interval == 0:
                return (
                    "Автосохранение **отключено**.\n\n"
                    "*`/autosave on` — включить (каждые 10 ходов) · "
                    "`/autosave <N>` — задать интервал*"
                )
            next_in = interval - (count % interval)
            return (
                f"Автосохранение **включено** (каждые {interval} ходов).\n"
                f"Ходов до следующего сохранения: {next_in}\n\n"
                f"*`/autosave off` — отключить · `/autosave <N>` — изменить интервал*"
            )

        if text in ("off", "disable", "0"):
            registry._autosave_interval = 0
            return "Автосохранение **отключено**."

        if text in ("on", "enable"):
            registry._autosave_interval = 10
            return "Автосохранение **включено** (каждые 10 ходов)."

        try:
            n = int(text)
            if n < 1:
                return "Интервал должен быть ≥ 1."
            registry._autosave_interval = n
            return f"Автосохранение **включено** (каждые {n} ходов)."
        except ValueError:
            return (
                f"Неверный аргумент `{arg}`.\n\n"
                "**Использование:** `/autosave on|off|<N>`"
            )

    registry.register(SlashCommand(
        "autosave",
        "Автоэкспорт сессии каждые N ходов: /autosave on|off|N",
        autosave_handler,
    ))

    # ── Task 187: /remind ──────────────────────────────────────────────────

    async def remind_handler(arg: str = "", **_: Any) -> str:
        """/remind [in <N> <text> | list | del <N> | clear] — напоминания по ходам."""
        text = arg.strip()

        if not text or text == "list":
            if not registry._reminders:
                return (
                    "Нет активных напоминаний.\n\n"
                    "*`/remind in <N> <текст>` — напомнить через N ходов.*"
                )
            lines = ["## Напоминания", ""]
            current_turn = len(registry._turn_times)
            for i, rem in enumerate(registry._reminders, 1):
                fire_at = rem["fire_at"]
                turns_left = max(0, fire_at - current_turn)
                lines.append(
                    f"  **{i}.** (через {turns_left} ходов): {rem['text']}"
                )
            lines.append("")
            lines.append("*`/remind del <N>` — удалить · `/remind clear` — удалить все*")
            return "\n".join(lines)

        if text.startswith("in "):
            rest = text[3:].strip()
            parts = rest.split(maxsplit=1)
            if len(parts) < 2:
                return "**Использование:** `/remind in <N> <текст напоминания>`"
            try:
                n = int(parts[0])
                if n < 1:
                    return "Количество ходов должно быть ≥ 1."
            except ValueError:
                return f"Неверное количество ходов: `{parts[0]}`"
            reminder_text = parts[1].strip()
            if not reminder_text:
                return "Текст напоминания не может быть пустым."
            fire_at = len(registry._turn_times) + n
            registry._reminders.append({"fire_at": fire_at, "text": reminder_text})
            return f"Напоминание установлено через {n} ходов: «{reminder_text}»"

        if text.startswith("del "):
            num_str = text[4:].strip()
            try:
                idx = int(num_str) - 1
            except ValueError:
                return f"Неверный номер: `{num_str}`"
            if idx < 0 or idx >= len(registry._reminders):
                return f"Напоминание #{num_str} не существует (всего {len(registry._reminders)})."
            removed = registry._reminders.pop(idx)
            return f"Напоминание #{num_str} удалено: «{removed['text']}»"

        if text == "clear":
            count = len(registry._reminders)
            registry._reminders.clear()
            return f"Удалено {count} напоминаний."

        return (
            "**Команды /remind:**\n\n"
            "- `/remind in <N> <текст>` — напомнить через N ходов\n"
            "- `/remind list` — список напоминаний\n"
            "- `/remind del <N>` — удалить напоминание\n"
            "- `/remind clear` — удалить все напоминания"
        )

    registry.register(SlashCommand(
        "remind",
        "Напоминания по ходам: /remind in <N> <текст> | /remind list",
        remind_handler,
    ))

    # ── Task 188: /bookmark ────────────────────────────────────────────────

    async def bookmark_handler(arg: str = "", **_: Any) -> str:
        """/bookmark [add <name> <file>[:<line>] | list | del <name> | go <name>] — закладки файлов."""
        from pathlib import Path as _Path
        text = arg.strip()

        if not text or text == "list":
            if not registry._bookmarks:
                return (
                    "Нет закладок.\n\n"
                    "*`/bookmark add <имя> <файл>[:<строка>]` — добавить закладку.*"
                )
            lines = ["## Закладки", ""]
            for name, bm in sorted(registry._bookmarks.items()):
                loc = bm["file"]
                if bm.get("line"):
                    loc += f":{bm['line']}"
                lines.append(f"  · **{name}** → `{loc}`")
            lines.append("")
            lines.append("*`/bookmark go <имя>` — перейти (показать содержимое) · `/bookmark del <имя>` — удалить*")
            return "\n".join(lines)

        if text.startswith("add "):
            rest = text[4:].strip()
            parts = rest.split(maxsplit=1)
            if len(parts) < 2:
                return "**Использование:** `/bookmark add <имя> <файл>[:<строка>]`"
            name = parts[0]
            location = parts[1].strip()
            # Parse file:line
            line_num: int | None = None
            if ":" in location:
                file_part, line_part = location.rsplit(":", 1)
                try:
                    line_num = int(line_part)
                    location = file_part
                except ValueError:
                    pass  # treat whole thing as filename
            p = _Path(location)
            if not p.exists():
                return f"Файл не найден: `{location}`"
            if not p.is_file():
                return f"Это не файл: `{location}`"
            registry._bookmarks[name] = {"file": str(p), "line": line_num}
            loc_str = f"{p}:{line_num}" if line_num else str(p)
            return f"Закладка **{name}** → `{loc_str}`"

        if text.startswith("del "):
            name = text[4:].strip()
            if name not in registry._bookmarks:
                return f"Закладка `{name}` не найдена."
            del registry._bookmarks[name]
            return f"Закладка **{name}** удалена."

        if text == "clear":
            count = len(registry._bookmarks)
            registry._bookmarks.clear()
            return f"Удалено {count} закладок."

        if text.startswith("go "):
            name = text[3:].strip()
            if name not in registry._bookmarks:
                available = ", ".join(f"`{n}`" for n in sorted(registry._bookmarks))
                hint = f"\n\nДоступные: {available}" if available else ""
                return f"Закладка `{name}` не найдена.{hint}"
            bm = registry._bookmarks[name]
            file_path = bm["file"]
            line_num = bm.get("line")
            try:
                content = _Path(file_path).read_text(encoding="utf-8", errors="replace")
                lines_list = content.splitlines()
                total = len(lines_list)
                if line_num and 1 <= line_num <= total:
                    # Show ±5 lines around target
                    start = max(0, line_num - 6)
                    end = min(total, line_num + 5)
                    excerpt = "\n".join(
                        f"{'→' if i + 1 == line_num else ' '} {i + start + 1:4}: {lines_list[i + start]}"
                        for i in range(end - start)
                    )
                    return f"**{file_path}:{line_num}** ({total} строк)\n\n```python\n{excerpt}\n```"
                else:
                    # Show first 30 lines
                    preview = "\n".join(f"  {i:4}: {l}" for i, l in enumerate(lines_list[:30], 1))
                    suffix = f"\n  ... ({total - 30} строк скрыто)" if total > 30 else ""
                    return f"**{file_path}** ({total} строк)\n\n```python\n{preview}{suffix}\n```"
            except OSError as exc:
                return f"Не удалось прочитать `{file_path}`: {exc}"

        return (
            "**Команды /bookmark:**\n\n"
            "- `/bookmark add <имя> <файл>[:<строка>]` — добавить закладку\n"
            "- `/bookmark go <имя>` — показать содержимое файла у закладки\n"
            "- `/bookmark del <имя>` — удалить\n"
            "- `/bookmark list` — список закладок\n"
            "- `/bookmark clear` — удалить все"
        )

    registry.register(SlashCommand(
        "bookmark",
        "Закладки файлов: /bookmark add|go|del|list",
        bookmark_handler,
    ))

    # ── Task 189: /fmt ─────────────────────────────────────────────────────

    async def fmt_handler(arg: str = "", **_: Any) -> str:
        """/fmt [file|--check] — форматировать Python файл через ruff format."""
        import asyncio as _asyncio
        from pathlib import Path as _Path

        text = arg.strip()
        check_only = False

        if text.endswith("--check"):
            check_only = True
            text = text[: -len("--check")].strip()

        if not text:
            return (
                "**Использование:** `/fmt <файл.py> [--check]`\n\n"
                "Форматирует Python файл с помощью `ruff format`.\n\n"
                "**Примеры:**\n"
                "  `/fmt src/lidco/core/session.py`\n"
                "  `/fmt src/lidco/ --check` — проверить без изменений"
            )

        p = _Path(text)
        if not p.exists():
            return f"Путь не найден: `{text}`"

        cmd = ["python", "-m", "ruff", "format"]
        if check_only:
            cmd.append("--check")
        cmd.append(str(p))

        try:
            proc = await _asyncio.create_subprocess_exec(
                *cmd,
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE,
            )
            stdout, stderr = await _asyncio.wait_for(proc.communicate(), timeout=30)
            rc = proc.returncode or 0
        except _asyncio.TimeoutError:
            return "Форматирование превысило лимит времени (30с)."
        except FileNotFoundError:
            return "ruff не найден. Установите: `pip install ruff`"

        out = (stdout + stderr).decode("utf-8", errors="replace").strip()

        if check_only:
            if rc == 0:
                return f"`{text}` — форматирование не требуется ✓"
            return f"`{text}` — требуется форматирование ✗\n\n```\n{out}\n```" if out else f"`{text}` — требуется форматирование ✗"

        if rc == 0:
            note = f"\n\n```\n{out}\n```" if out else ""
            return f"`{text}` — отформатировано ✓{note}"
        return f"Ошибка форматирования:\n\n```\n{out}\n```"

    registry.register(SlashCommand(
        "fmt",
        "Форматировать Python файл: /fmt <файл> [--check]",
        fmt_handler,
    ))

    # ── Task 190: /cost ────────────────────────────────────────────────────

    async def cost_handler(arg: str = "", **_: Any) -> str:
        """/cost — подробная разбивка стоимости сессии."""
        if not registry._session:
            return "Сессия не инициализирована."

        tb = registry._session.token_budget
        total_tokens = getattr(tb, "_total_tokens", 0)
        prompt_tokens = getattr(tb, "_total_prompt_tokens", 0)
        completion_tokens = getattr(tb, "_total_completion_tokens", 0)
        total_cost = getattr(tb, "_total_cost_usd", 0.0)
        by_role: dict = getattr(tb, "_by_role", {}) or {}
        model = registry._session.config.llm.default_model

        def _k(n: int) -> str:
            return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

        def _fmt_cost(usd: float) -> str:
            if usd == 0.0:
                return "$0.000000"
            return f"${usd:.6f}".rstrip("0").rstrip(".")

        lines = ["## Стоимость сессии", ""]
        lines.append(f"**Модель:** `{model}`")
        lines.append("")
        lines.append(f"**Токены ввода:**    {_k(prompt_tokens)}")
        lines.append(f"**Токены вывода:**   {_k(completion_tokens)}")
        lines.append(f"**Итого токенов:**   {_k(total_tokens)}")
        lines.append("")
        lines.append(f"**Стоимость:**       {_fmt_cost(total_cost)}")

        # Per-agent cost estimates (proportional to token usage)
        if by_role and total_tokens > 0:
            lines.append("")
            lines.append("**По агентам:**")
            for role, toks in sorted(by_role.items(), key=lambda x: -x[1]):
                pct = int(toks / total_tokens * 100)
                agent_cost = total_cost * toks / total_tokens if total_cost > 0 else 0.0
                cost_str = f" · {_fmt_cost(agent_cost)}" if total_cost > 0 else ""
                lines.append(f"  · **{role}**: {_k(toks)} токенов ({pct}%){cost_str}")

        # Session timing summary
        turn_times = registry._turn_times
        if turn_times:
            total_time = sum(turn_times)
            avg_time = total_time / len(turn_times)
            lines.append("")
            lines.append(f"**Ходов:**          {len(turn_times)}")
            lines.append(f"**Время сессии:**   {total_time:.1f}с итого · {avg_time:.1f}с avg")
            if total_cost > 0 and total_time > 0:
                cost_per_min = total_cost / (total_time / 60)
                lines.append(f"**$/мин:**          {_fmt_cost(cost_per_min)}")

        lines.append("")
        lines.append("*`/budget` — лимит токенов · `/profile` — по агентам · `/timing` — время*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "cost",
        "Подробная разбивка стоимости сессии",
        cost_handler,
    ))

    # ── Task 191: /reload ──────────────────────────────────────────────────

    async def reload_handler(arg: str = "", **_: Any) -> str:
        """/reload [config|agents|tools] — перезагрузить конфигурацию без перезапуска."""
        if not registry._session:
            return "Сессия не инициализирована."

        target = arg.strip().lower() or "config"
        session = registry._session

        results: list[str] = []

        if target in ("config", "all"):
            try:
                reloader = getattr(session, "_config_reloader", None)
                if reloader and hasattr(reloader, "_reload_once"):
                    reloader._reload_once()
                    results.append("✓ Конфигурация перезагружена")
                elif hasattr(session, "config"):
                    # Re-read config from disk if possible
                    from lidco.core.config import load_config
                    new_cfg = load_config()
                    session.config = new_cfg
                    results.append("✓ Конфигурация перезагружена")
                else:
                    results.append("⚠ Перезагрузка конфига недоступна (нет reloader)")
            except Exception as exc:
                results.append(f"✗ Ошибка перезагрузки конфига: {exc}")

        if target in ("agents", "all"):
            try:
                agent_reg = getattr(session, "agent_registry", None)
                if agent_reg and hasattr(agent_reg, "reload"):
                    agent_reg.reload()
                    n = len(agent_reg.list_names())
                    results.append(f"✓ Агенты перезагружены ({n} агентов)")
                else:
                    names = agent_reg.list_names() if agent_reg else []
                    results.append(f"✓ Агенты активны ({len(names)} агентов, горячая перезагрузка недоступна)")
            except Exception as exc:
                results.append(f"✗ Ошибка перезагрузки агентов: {exc}")

        if target in ("tools", "all"):
            try:
                tool_reg = getattr(session, "tool_registry", None)
                if tool_reg and hasattr(tool_reg, "list_tools"):
                    n = len(tool_reg.list_tools())
                    results.append(f"✓ Инструменты активны ({n} инструментов)")
                else:
                    results.append("⚠ Реестр инструментов недоступен")
            except Exception as exc:
                results.append(f"✗ Ошибка: {exc}")

        if not results:
            return (
                f"Неизвестная цель: `{target}`.\n\n"
                "**Использование:** `/reload [config|agents|tools|all]`"
            )

        model = session.config.llm.default_model
        lines = ["## Перезагрузка", ""]
        lines.extend(results)
        lines.append("")
        lines.append(f"*Модель: `{model}`*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "reload",
        "Перезагрузить конфигурацию: /reload [config|agents|tools|all]",
        reload_handler,
    ))

    # ── Q66 Task 444: /sessions — list saved sessions ─────────────────────

    async def sessions_handler(arg: str = "", **_: Any) -> str:
        """List saved sessions from the SessionStore."""
        from lidco.cli.session_store import SessionStore

        store = getattr(registry, "_session_store", None)
        if store is None:
            store = SessionStore()

        sessions = store.list_sessions()
        if not sessions:
            return "No saved sessions."

        lines = ["## Saved Sessions", ""]
        for s in sessions[:20]:
            sid = s.get("session_id", "?")[:8]
            name = s.get("metadata", {}).get("name") or "unnamed"
            msg_count = s.get("message_count", 0)
            saved_at = s.get("saved_at", "")[:19]
            lines.append(f"  {sid}  {name}  ({msg_count} msgs)  {saved_at}")
        if len(sessions) > 20:
            lines.append(f"  ... and {len(sessions) - 20} more")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "sessions",
        "List saved sessions",
        sessions_handler,
    ))

    # ── Q67 Task 452: /memory — persistent agent memory ──────────────────

    memory_handler = _memory_handler_factory()
    registry.register(SlashCommand(
        "memory",
        "Manage persistent agent memories across sessions",
        memory_handler,
    ))


def _memory_handler_factory(db_path: Path | str | None = None):
    """Create a /memory handler, optionally with a custom db_path (for testing)."""

    async def memory_handler(args: str = "", **_: Any) -> str:
        from lidco.memory.agent_memory import AgentMemoryStore

        store = AgentMemoryStore(db_path=db_path)
        parts = args.strip().split(None, 1)
        subcmd = parts[0].lower() if parts else "list"
        rest = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            memories = store.list(20)
            if not memories:
                return "No memories stored."
            lines = [
                f"  {m.id}  {m.content[:60]}{'...' if len(m.content) > 60 else ''}"
                for m in memories
            ]
            return f"Memories ({len(memories)}):\n" + "\n".join(lines)
        elif subcmd == "add":
            if not rest.strip():
                return "Usage: /memory add <text>"
            m = store.add(rest.strip())
            return f"Memory saved: [{m.id}] {m.content[:60]}"
        elif subcmd == "delete":
            if not rest.strip():
                return "Usage: /memory delete <id>"
            ok = store.delete(rest.strip())
            return "Deleted." if ok else f"Memory '{rest.strip()}' not found."
        elif subcmd == "search":
            if not rest.strip():
                return "Usage: /memory search <query>"
            results = store.search(rest.strip(), limit=10)
            if not results:
                return "No memories match."
            lines = [f"  {m.id}  {m.content[:60]}" for m in results]
            return "\n".join(lines)
        elif subcmd == "clear":
            n = store.clear()
            return f"Cleared {n} memories."
        else:
            return "Usage: /memory [list|add <text>|delete <id>|search <query>|clear]"

    return memory_handler
