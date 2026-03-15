"""Commands: utility commands."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def register(registry: Any) -> None:
    """Register utility commands commands."""
    from lidco.cli.commands.registry import SlashCommand


    # ── Task 221: /pypi ───────────────────────────────────────────────────

    async def pypi_handler(arg: str = "", **_) -> str:
        import json as _json
        import asyncio as _asyncio

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/pypi <пакет> [--versions]`\n\n"
                "Информация о Python-пакете из PyPI.\n\n"
                "  `/pypi rich` — последняя версия, описание, ссылки\n"
                "  `/pypi pydantic --versions` — список версий"
            )

        show_versions = "--versions" in text
        if show_versions:
            text = text.replace("--versions", "").strip()

        package = text.lower().strip()

        # Use pip index info if available, else try PyPI JSON API
        async def _fetch_pypi(pkg: str) -> dict | None:
            try:
                proc = await _asyncio.create_subprocess_exec(
                    "python", "-m", "pip", "index", "versions", pkg,
                    "--no-color",
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.PIPE,
                )
                out, err = await _asyncio.wait_for(proc.communicate(), timeout=15)
                return {"pip_output": out.decode("utf-8", errors="replace").strip()}
            except Exception:
                return None

        # Try pip show first (for installed packages)
        async def _pip_show(pkg: str) -> str:
            try:
                proc = await _asyncio.create_subprocess_exec(
                    "python", "-m", "pip", "show", pkg,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.PIPE,
                )
                out, _ = await _asyncio.wait_for(proc.communicate(), timeout=10)
                return out.decode("utf-8", errors="replace").strip()
            except Exception:
                return ""

        pip_info = await _pip_show(package)

        lines = [f"**PyPI: `{package}`**", ""]

        if pip_info:
            # Parse pip show output
            info: dict[str, str] = {}
            for line in pip_info.splitlines():
                if ": " in line:
                    key, _, val = line.partition(": ")
                    info[key.strip()] = val.strip()

            if "Name" in info:
                lines.append(f"**Название:** `{info.get('Name', package)}`")
            if "Version" in info:
                lines.append(f"**Версия:** `{info.get('Version', '?')}`")
            if "Summary" in info:
                lines.append(f"**Описание:** {info.get('Summary', '')}")
            if "Author" in info:
                lines.append(f"**Автор:** {info.get('Author', '')}")
            if "License" in info:
                lines.append(f"**Лицензия:** `{info.get('License', '')}`")
            if "Location" in info:
                lines.append(f"**Путь:** `{info.get('Location', '')}`")
            if "Requires" in info and info["Requires"]:
                requires = info["Requires"]
                lines.append(f"**Зависимости:** `{requires}`")
            if "Home-page" in info:
                lines.append(f"**Сайт:** {info.get('Home-page', '')}")
            lines.append("")
            lines.append("✅ *Пакет установлен в текущем окружении*")
        else:
            lines.append(f"⚠️ Пакет `{package}` не установлен локально.")
            lines.append(f"Установить: `pip install {package}`")

        if show_versions:
            versions_data = await _fetch_pypi(package)
            if versions_data and versions_data.get("pip_output"):
                lines.append("")
                lines.append("**Доступные версии:**")
                lines.append(f"```\n{versions_data['pip_output'][:1000]}\n```")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "pypi",
        "Информация о Python-пакете: /pypi <пакет> [--versions]",
        pypi_handler,
    ))

    # ── Task 222: /head ───────────────────────────────────────────────────

    async def head_handler(arg: str = "", **_) -> str:
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return "**Использование:** `/head <файл> [N=10]`\n\nПоказывает первые N строк файла."

        tokens = text.rsplit(None, 1)
        n = 10
        if len(tokens) == 2 and tokens[1].isdigit():
            n = min(int(tokens[1]), 500)
            text = tokens[0].strip()

        p = _Path(text)
        if not p.exists():
            return f"Файл не найден: `{text}`"
        if not p.is_file():
            return f"`{text}` — не файл."

        try:
            raw = p.read_bytes()
            if b"\x00" in raw[:8192]:
                return f"`{p.name}` — бинарный файл."
            lines = raw.decode("utf-8", errors="replace").splitlines()
        except Exception as exc:
            return f"Ошибка чтения: {exc}"

        selected = lines[:n]
        total = len(lines)

        from pathlib import Path as _P
        _LANG_MAP = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".sh": "bash", ".json": "json", ".yaml": "yaml",
            ".toml": "toml", ".md": "markdown", ".sql": "sql",
        }
        lang = _LANG_MAP.get(p.suffix.lower(), "")

        header = f"**`{p.name}`** (первые {len(selected)} из {total} строк)"
        body = "\n".join(selected)
        result = f"{header}\n\n```{lang}\n{body}\n```"
        if total > n:
            result += f"\n*…ещё {total - n} строк. Используйте `/cat {p.name} {n+1}-{min(n*2, total)}`*"
        return result

    registry.register(SlashCommand(
        "head",
        "Первые N строк файла: /head <файл> [N=10]",
        head_handler,
    ))

    # ── Task 223: /tail ───────────────────────────────────────────────────

    async def tail_handler(arg: str = "", **_) -> str:
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return "**Использование:** `/tail <файл> [N=10]`\n\nПоказывает последние N строк файла."

        tokens = text.rsplit(None, 1)
        n = 10
        if len(tokens) == 2 and tokens[1].isdigit():
            n = min(int(tokens[1]), 500)
            text = tokens[0].strip()

        p = _Path(text)
        if not p.exists():
            return f"Файл не найден: `{text}`"
        if not p.is_file():
            return f"`{text}` — не файл."

        try:
            raw = p.read_bytes()
            if b"\x00" in raw[:8192]:
                return f"`{p.name}` — бинарный файл."
            lines = raw.decode("utf-8", errors="replace").splitlines()
        except Exception as exc:
            return f"Ошибка чтения: {exc}"

        total = len(lines)
        selected = lines[-n:] if n <= total else lines
        start_line = max(1, total - n + 1)

        _LANG_MAP = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".sh": "bash", ".json": "json", ".yaml": "yaml",
            ".toml": "toml", ".md": "markdown", ".sql": "sql",
        }
        lang = _LANG_MAP.get(p.suffix.lower(), "")

        header = f"**`{p.name}`** (строки {start_line}–{total} из {total})"
        body = "\n".join(selected)
        result = f"{header}\n\n```{lang}\n{body}\n```"
        if total > n:
            result += f"\n*Используйте `/cat {p.name}` для полного просмотра*"
        return result

    registry.register(SlashCommand(
        "tail",
        "Последние N строк файла: /tail <файл> [N=10]",
        tail_handler,
    ))

    # ── Task 224: /cd and /ls ─────────────────────────────────────────────

    async def cd_handler(arg: str = "", **_) -> str:
        import os as _os
        from pathlib import Path as _Path

        text = arg.strip()
        if not text or text == "~":
            target = _Path.home()
        elif text == "-":
            # Go to previous dir (store in registry attr)
            prev = getattr(registry, "_prev_dir", None)
            if prev is None:
                return "Предыдущая директория неизвестна."
            target = _Path(prev)
        elif text == "..":
            target = _Path.cwd().parent
        else:
            target = _Path(text).expanduser()

        if not target.exists():
            return f"Директория не найдена: `{text}`"
        if not target.is_dir():
            return f"`{text}` — не директория."

        prev = str(_Path.cwd())
        try:
            _os.chdir(target)
            registry._prev_dir = prev
            cwd = _Path.cwd()
            # Count files/dirs for context
            try:
                entries = list(cwd.iterdir())
                nfiles = sum(1 for e in entries if e.is_file())
                ndirs = sum(1 for e in entries if e.is_dir())
                hint = f"*{nfiles} файлов, {ndirs} директорий*"
            except Exception:
                hint = ""
            return f"✓ `{cwd}`\n{hint}"
        except PermissionError:
            return f"Нет прав для перехода в `{target}`."

    registry.register(SlashCommand(
        "cd",
        "Смена рабочей директории: /cd <путь> | .. | ~ | -",
        cd_handler,
    ))

    async def ls_handler(arg: str = "", **_) -> str:
        from pathlib import Path as _Path

        text = arg.strip()
        long_mode = "--l" in text or "-l" in text
        show_all = "--all" in text or "-a" in text
        for flag in ("--l", "-l", "--all", "-a"):
            text = text.replace(flag, "").strip()

        target = _Path(text) if text else _Path.cwd()
        if not target.exists():
            return f"Не найдено: `{text}`"
        if not target.is_dir():
            return f"`{text}` — не директория."

        _SKIP = {"__pycache__", ".mypy_cache", ".pytest_cache"}

        try:
            entries = sorted(target.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except PermissionError:
            return f"Нет прав для чтения `{target}`."

        if not show_all:
            entries = [e for e in entries if not e.name.startswith(".") and e.name not in _SKIP]

        if not entries:
            return f"`{target}` — пусто."

        lines = [f"**`{target}/`** ({len(entries)} элементов)", ""]

        if long_mode:
            from datetime import datetime as _dt
            for e in entries:
                try:
                    st = e.stat()
                    size = st.st_size
                    mtime = _dt.fromtimestamp(st.st_mtime).strftime("%m-%d %H:%M")
                    icon = "📁" if e.is_dir() else "📄"
                    if size < 1024:
                        size_str = f"{size}Б"
                    elif size < 1_048_576:
                        size_str = f"{size//1024}КБ"
                    else:
                        size_str = f"{size//1_048_576}МБ"
                    lines.append(f"{icon} `{e.name:<30}` {size_str:>8}  {mtime}")
                except Exception:
                    lines.append(f"  `{e.name}`")
        else:
            # Compact grid: dirs first, then files
            dirs = [e for e in entries if e.is_dir()]
            files = [e for e in entries if e.is_file()]
            if dirs:
                lines.append("**Директории:**  " + "  ".join(f"`{d.name}/`" for d in dirs))
            if files:
                # Group by extension
                from collections import defaultdict as _dd
                by_ext: dict = _dd(list)
                for f in files:
                    by_ext[f.suffix or "(без расш.)"].append(f.name)
                for ext, names in sorted(by_ext.items()):
                    lines.append(f"**{ext}:**  " + "  ".join(f"`{n}`" for n in names[:20]))

        lines.append(f"\n*`{target}`*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "ls",
        "Список файлов: /ls [путь] [--l] [--all]",
        ls_handler,
    ))

    # ── Task 225: /macro ──────────────────────────────────────────────────
    # Record and replay sequences of slash commands

    registry._macros: dict[str, list[str]] = {}
    registry._macro_recording: str | None = None
    registry._macro_buffer: list[str] = []

    async def macro_handler(arg: str = "", **_) -> str:
        text = arg.strip()

        if not text or text == "list":
            if not registry._macros:
                return "Макросов нет. Создайте: `/macro record <имя>`"
            lines = [f"**Макросы** ({len(registry._macros)} шт.)", ""]
            for name, cmds in registry._macros.items():
                lines.append(f"  **{name}** — {len(cmds)} команд: {', '.join(f'`{c}`' for c in cmds[:3])}" +
                             ("…" if len(cmds) > 3 else ""))
            return "\n".join(lines)

        parts = text.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "record":
            if not rest:
                return "Укажите имя макроса: `/macro record <имя>`"
            if registry._macro_recording:
                return (f"Уже записывается макрос `{registry._macro_recording}`. "
                        "Завершите: `/macro stop`")
            registry._macro_recording = rest
            registry._macro_buffer = []
            return f"⏺ Запись макроса `{rest}` начата. Вводите команды, затем `/macro stop`."

        if subcmd == "stop":
            if not registry._macro_recording:
                return "Нет активной записи."
            name = registry._macro_recording
            registry._macros[name] = list(registry._macro_buffer)
            count = len(registry._macro_buffer)
            registry._macro_recording = None
            registry._macro_buffer = []
            return f"⏹ Макрос `{name}` сохранён ({count} команд)."

        if subcmd == "add":
            if not registry._macro_recording:
                return "Запись не активна. Начните: `/macro record <имя>`"
            if not rest:
                return "Укажите команду: `/macro add <команда>`"
            registry._macro_buffer.append(rest)
            return f"✓ Добавлено в `{registry._macro_recording}` [#{len(registry._macro_buffer)}]: `{rest}`"

        if subcmd == "play":
            if not rest:
                return "Укажите имя макроса: `/macro play <имя>`"
            if rest not in registry._macros:
                available = ", ".join(registry._macros.keys()) or "нет"
                return f"Макрос `{rest}` не найден. Доступные: {available}"
            cmds = registry._macros[rest]
            lines = [f"**Воспроизведение макроса `{rest}`** ({len(cmds)} команд)", ""]
            for i, cmd in enumerate(cmds, 1):
                lines.append(f"  {i}. `{cmd}`")
            lines.append(
                f"\n*Для выполнения команд используйте их напрямую "
                f"или `/run` для shell-команд.*"
            )
            return "\n".join(lines)

        if subcmd == "del" or subcmd == "delete":
            if not rest:
                return "Укажите имя: `/macro del <имя>`"
            if rest not in registry._macros:
                return f"Макрос `{rest}` не найден."
            del registry._macros[rest]
            return f"Макрос `{rest}` удалён."

        if subcmd == "show":
            if not rest:
                return "Укажите имя: `/macro show <имя>`"
            if rest not in registry._macros:
                return f"Макрос `{rest}` не найден."
            cmds = registry._macros[rest]
            lines = [f"**Макрос `{rest}`** ({len(cmds)} команд)", ""]
            for i, cmd in enumerate(cmds, 1):
                lines.append(f"  {i}. `/{cmd}`")
            return "\n".join(lines)

        if subcmd == "clear":
            count = len(registry._macros)
            registry._macros.clear()
            return f"Удалено {count} макросов."

        return (
            "**Использование:** `/macro <подкоманда>`\n\n"
            "  `record <имя>` — начать запись\n"
            "  `add <команда>` — добавить команду в запись\n"
            "  `stop` — завершить запись\n"
            "  `play <имя>` — показать шаги макроса\n"
            "  `show <имя>` — просмотр команд\n"
            "  `del <имя>` — удалить макрос\n"
            "  `list` — все макросы\n"
            "  `clear` — удалить все"
        )

    registry.register(SlashCommand(
        "macro",
        "Макросы команд: /macro record|stop|add|play|show|del|list|clear",
        macro_handler,
    ))

    # ── Task 226: /coverage ───────────────────────────────────────────────

    async def coverage_handler(arg: str = "", **_) -> str:
        import asyncio as _asyncio
        import json as _json
        from pathlib import Path as _Path

        text = arg.strip()
        show_missing = "--missing" in text or "--m" in text
        for flag in ("--missing", "--m"):
            text = text.replace(flag, "").strip()

        target = text or "."

        # Try reading existing .coverage / coverage.json first
        cov_json = _Path(".coverage.json")
        cov_xml = _Path("coverage.xml")

        # Run pytest --cov if no existing report
        async def _run_coverage(path: str) -> tuple[int, str]:
            try:
                proc = await _asyncio.create_subprocess_exec(
                    "python", "-m", "pytest", path,
                    "--cov=" + path,
                    "--cov-report=term-missing",
                    "--cov-report=json:.coverage.json",
                    "-q", "--no-header", "--tb=no",
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                )
                out, _ = await _asyncio.wait_for(proc.communicate(), timeout=60)
                return proc.returncode or 0, out.decode("utf-8", errors="replace")
            except _asyncio.TimeoutError:
                return 1, "Timeout (60s)"
            except FileNotFoundError:
                return 1, "pytest не найден."
            except Exception as exc:
                return 1, str(exc)

        lines = [f"**Coverage** `{target}`", ""]

        # Try reading existing JSON report
        if cov_json.exists():
            try:
                data = _json.loads(cov_json.read_text())
                totals = data.get("totals", {})
                pct = totals.get("percent_covered", 0)
                covered = totals.get("covered_lines", 0)
                missing = totals.get("missing_lines", 0)
                total_stmts = totals.get("num_statements", 0)

                # Bar
                bar_w = 25
                filled = int(bar_w * pct / 100)
                color_char = "█" if pct >= 80 else ("▓" if pct >= 60 else "░")
                bar = color_char * filled + "░" * (bar_w - filled)

                lines.append(f"[{bar}] **{pct:.1f}%**")
                lines.append("")
                lines.append(f"Покрыто:  `{covered}` / `{total_stmts}` строк")
                lines.append(f"Пропущено: `{missing}` строк")
                lines.append("")

                # Per-file breakdown
                files_data = data.get("files", {})
                if files_data:
                    lines.append("**По файлам:**")
                    sorted_files = sorted(
                        files_data.items(),
                        key=lambda x: x[1].get("summary", {}).get("percent_covered", 100),
                    )
                    for fname, fdata in sorted_files[:20]:
                        summary = fdata.get("summary", {})
                        fpct = summary.get("percent_covered", 0)
                        fmissing = summary.get("missing_lines", 0)
                        icon = "✅" if fpct >= 80 else ("⚠️" if fpct >= 60 else "❌")
                        short = _Path(fname).name
                        miss_str = f" (пропущено: {fdata.get('missing_lines', [][:5])})" if show_missing and fmissing else ""
                        lines.append(f"  {icon} `{short:<30}` {fpct:>5.1f}%{miss_str}")

                lines.append(f"\n*Из кэша `.coverage.json`. Запустите тесты для обновления.*")
                return "\n".join(lines)
            except Exception:
                pass

        # No existing report — run coverage
        lines.append("Запускаю тесты с coverage…")
        rc, output = await _run_coverage(target)

        # Try to parse JSON after run
        if cov_json.exists():
            try:
                data = _json.loads(cov_json.read_text())
                totals = data.get("totals", {})
                pct = totals.get("percent_covered", 0)
                lines = [f"**Coverage** `{target}`", "", f"**Итого: {pct:.1f}%**", ""]
                lines.append("```")
                for line in output.splitlines()[-30:]:
                    lines.append(line)
                lines.append("```")
                return "\n".join(lines)
            except Exception:
                pass

        # Fallback: show raw output
        out_lines = output.splitlines()[-40:]
        lines.extend(["```"] + out_lines + ["```"])
        if rc != 0:
            lines.append(f"\n*Exit code: {rc}*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "coverage",
        "Отчёт покрытия тестами: /coverage [путь] [--missing]",
        coverage_handler,
    ))

    # ── Task 227: /complexity ─────────────────────────────────────────────

    async def complexity_handler(arg: str = "", **_) -> str:
        import ast as _ast
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/complexity <файл.py> [--top N]`\n\n"
                "Цикломатическая сложность функций файла.\n\n"
                "  `/complexity src/utils.py` — все функции\n"
                "  `/complexity module.py --top 5` — топ-5 сложных"
            )

        top_n = 0
        if "--top" in text:
            parts = text.split("--top", 1)
            text = parts[0].strip()
            tok = parts[1].strip().split()[0]
            if tok.isdigit():
                top_n = int(tok)

        p = _Path(text)
        if not p.exists():
            return f"Файл не найден: `{text}`"
        if not p.is_file():
            return f"`{text}` — не файл."

        try:
            source = p.read_text(encoding="utf-8", errors="replace")
            tree = _ast.parse(source, filename=str(p))
        except SyntaxError as exc:
            return f"Синтаксическая ошибка: {exc}"
        except Exception as exc:
            return f"Ошибка чтения: {exc}"

        def _cyclomatic(node) -> int:
            """Count decision points: if/elif/for/while/except/with/assert/bool ops."""
            count = 1  # base complexity
            for child in _ast.walk(node):
                if isinstance(child, (
                    _ast.If, _ast.For, _ast.While, _ast.ExceptHandler,
                    _ast.With, _ast.Assert, _ast.comprehension,
                )):
                    count += 1
                elif isinstance(child, _ast.BoolOp):
                    count += len(child.values) - 1
            return count

        results: list[tuple[int, str, int, str]] = []  # (complexity, name, lineno, kind)

        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                cc = _cyclomatic(node)
                kind = "async def" if isinstance(node, _ast.AsyncFunctionDef) else "def"
                results.append((cc, node.name, node.lineno, kind))
            elif isinstance(node, _ast.ClassDef):
                # Count class-level complexity (methods)
                class_methods = [
                    n for n in _ast.walk(node)
                    if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
                ]
                if not class_methods:
                    results.append((1, node.name, node.lineno, "class"))

        if not results:
            return f"`{p.name}` — нет функций или классов для анализа."

        results.sort(key=lambda x: -x[0])
        if top_n:
            results = results[:top_n]

        total = len(results)
        avg = sum(r[0] for r in results) / total if total else 0
        max_cc = results[0][0] if results else 0

        def _label(cc: int) -> str:
            if cc <= 5:
                return "✅ просто"
            elif cc <= 10:
                return "⚠️ умеренно"
            elif cc <= 20:
                return "🔶 сложно"
            else:
                return "❌ очень сложно"

        lines = [
            f"**Цикломатическая сложность: `{p.name}`**",
            "",
            f"Функций: {total} · Средняя: {avg:.1f} · Максимум: {max_cc}",
            "",
            f"{'Сложность':>10}  {'Функция':<30}  {'Строка':>6}  Оценка",
            "─" * 65,
        ]

        for cc, name, lineno, kind in results:
            label = _label(cc)
            lines.append(f"{cc:>10}  `{kind} {name}`{'':.<{max(0, 28-len(name)-len(kind)-1)}}  L{lineno:<5}  {label}")

        lines.append("")
        lines.append(f"*Рекомендуется: CC ≤ 10. Рефакторинг при CC > 10.*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "complexity",
        "Цикломатическая сложность: /complexity <файл.py> [--top N]",
        complexity_handler,
    ))

    # ── Task 228: /docstring ──────────────────────────────────────────────

    async def docstring_handler(arg: str = "", **_) -> str:
        import ast as _ast
        from pathlib import Path as _Path

        text = arg.strip()

        if not registry._session:
            return "Сессия не инициализирована."

        if not text:
            return (
                "**Использование:** `/docstring <файл.py> [<функция>]`\n\n"
                "AI-генерация docstrings для функций и классов.\n\n"
                "  `/docstring utils.py` — для всех публичных функций\n"
                "  `/docstring utils.py parse_config` — для конкретной функции"
            )

        # Split file from optional function name
        tokens = text.split()
        file_path_str = tokens[0]
        target_fn = tokens[1] if len(tokens) > 1 else None

        p = _Path(file_path_str)
        if not p.exists():
            return f"Файл не найден: `{file_path_str}`"
        if not p.is_file():
            return f"`{file_path_str}` — не файл."
        if p.suffix.lower() != ".py":
            return f"Только Python-файлы (.py), получен `{p.suffix}`."

        try:
            source = p.read_text(encoding="utf-8", errors="replace")
            tree = _ast.parse(source)
        except SyntaxError as exc:
            return f"Синтаксическая ошибка: {exc}"

        source_lines = source.splitlines()

        def _get_snippet(node) -> str:
            start = node.lineno - 1
            end = min(start + 30, len(source_lines))
            return "\n".join(source_lines[start:end])

        # Find functions/classes to document
        targets: list[tuple[str, str, int]] = []  # (name, snippet, lineno)
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                if node.name.startswith("_"):
                    continue
                if target_fn and node.name != target_fn:
                    continue
                # Check if already has docstring
                has_doc = (
                    isinstance(node.body[0], _ast.Expr)
                    and isinstance(node.body[0].value, _ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ) if node.body else False
                if not has_doc:
                    targets.append((node.name, _get_snippet(node), node.lineno))

        if not targets:
            if target_fn:
                return f"Функция `{target_fn}` не найдена или уже имеет docstring."
            return f"✅ Все публичные функции в `{p.name}` уже имеют docstrings."

        # Limit to 5 at a time
        cap = targets[:5]
        if len(targets) > 5:
            note = f"\n*Показаны первые 5 из {len(targets)} функций без docstring.*"
        else:
            note = ""

        snippets = "\n\n".join(
            f"### `{name}` (строка {lineno})\n```python\n{snippet}\n```"
            for name, snippet, lineno in cap
        )

        prompt = (
            f"Сгенерируй docstrings в Google-стиле для следующих Python функций из `{p.name}`.\n\n"
            "Формат для каждой:\n"
            "```\n"
            "Функция: <имя>\n"
            '"""\n'
            "Краткое описание.\n\n"
            "Args:\n"
            "    param: описание\n\n"
            "Returns:\n"
            "    описание возвращаемого значения\n\n"
            "Raises:\n"
            "    ExceptionType: когда возникает\n"
            '"""\n'
            "```\n\n"
            f"{snippets}"
        )

        try:
            resp = await registry._session.llm.complete(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            docstrings = resp.content
        except Exception as exc:
            return f"Ошибка LLM: {exc}"

        header = (
            f"**Docstrings для `{p.name}`**"
            + (f" → `{target_fn}`" if target_fn else f" ({len(cap)} функций)")
        )
        return f"{header}\n\n{docstrings}{note}"

    registry.register(SlashCommand(
        "docstring",
        "AI-генерация docstrings: /docstring <файл.py> [функция]",
        docstring_handler,
    ))

    # ── Task 229: /security-scan ──────────────────────────────────────────

    async def security_scan_handler(arg: str = "", **_) -> str:
        import re as _re
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/security-scan <файл.py или директория>`\n\n"
                "Сканирует Python-код на типичные уязвимости:\n"
                "  · Захардкоженные секреты (пароли, API-ключи, токены)\n"
                "  · SQL-инъекции (f-строки в SQL-запросах)\n"
                "  · Использование `eval`, `exec`, `pickle`\n"
                "  · `subprocess` с `shell=True`\n"
                "  · Небезопасная десериализация\n"
                "  · Отладочные маркеры в production-коде"
            )

        # Security patterns: (regex, severity, description)
        _PATTERNS: list[tuple[str, str, str]] = [
            # Hardcoded secrets
            (r'(?i)(password|passwd|pwd|secret|api_key|apikey|token|auth)\s*=\s*["\'][^"\']{4,}["\']',
             "HIGH", "Захардкоженный секрет"),
            (r'(?i)(aws_access_key|aws_secret|private_key)\s*=\s*["\'][^"\']+["\']',
             "CRITICAL", "Захардкоженный AWS/cloud ключ"),
            # SQL injection
            (r'(?i)(execute|cursor\.execute|query)\s*\(\s*f["\'].*\{',
             "HIGH", "Потенциальная SQL-инъекция (f-строка в запросе)"),
            (r'(?i)(execute|cursor\.execute)\s*\(\s*["\'].*%s.*["\']\s*%\s*',
             "MEDIUM", "SQL-запрос с %-форматированием"),
            # Dangerous builtins
            (r'\beval\s*\(', "HIGH", "Использование eval()"),
            (r'\bexec\s*\(', "HIGH", "Использование exec()"),
            # Subprocess with shell
            (r'subprocess\.(run|Popen|call|check_output).*shell\s*=\s*True',
             "HIGH", "subprocess с shell=True (риск инъекции)"),
            # Unsafe deserialization
            (r'\bpickle\.loads?\s*\(', "HIGH", "Небезопасная десериализация (pickle)"),
            (r'\byaml\.load\s*\([^)]*\)', "MEDIUM", "yaml.load() без Loader (используйте safe_load)"),
            (r'\bmarshal\.loads?\s*\(', "HIGH", "Небезопасная десериализация (marshal)"),
            # Weak crypto
            (r'(?i)hashlib\.(md5|sha1)\s*\(', "LOW", "Слабый алгоритм хеширования"),
            (r'(?i)Crypto\.Cipher\.DES\b', "MEDIUM", "Слабый шифр DES"),
            # Debug markers
            (r'\bpdb\.set_trace\s*\(\)', "LOW", "Отладочный breakpoint (pdb)"),
            (r'\bbreakpoint\s*\(\)', "LOW", "Отладочный breakpoint()"),
            (r'(?i)TODO.*(security|auth|password|token|secret)',
             "LOW", "TODO с упоминанием безопасности"),
            # Temp files
            (r'(?i)(tempfile\.mktemp|/tmp/["\'])', "LOW", "Небезопасное использование /tmp"),
            # HTTP without verification
            (r'verify\s*=\s*False', "MEDIUM", "SSL-верификация отключена"),
            (r'ssl\._create_unverified_context', "HIGH", "Небезопасный SSL-контекст"),
        ]

        p = _Path(text)
        if not p.exists():
            return f"Путь не найден: `{text}`"

        # Collect Python files
        py_files: list[_Path] = []
        if p.is_file():
            if p.suffix == ".py":
                py_files = [p]
            else:
                return f"Только .py файлы. Получен: `{p.suffix}`"
        else:
            _SKIP = {".git", "__pycache__", ".venv", "venv", "node_modules"}
            for f in p.rglob("*.py"):
                if not any(s in f.parts for s in _SKIP):
                    py_files.append(f)
            py_files = py_files[:50]  # cap

        if not py_files:
            return f"Python-файлов не найдено в `{text}`."

        findings: list[tuple[str, int, str, str, str]] = []
        # (file, line, severity, description, snippet)

        for pyf in py_files:
            try:
                lines = pyf.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for lineno, line in enumerate(lines, 1):
                for pattern, severity, desc in _PATTERNS:
                    if _re.search(pattern, line):
                        snippet = line.strip()[:80]
                        findings.append((str(pyf), lineno, severity, desc, snippet))

        if not findings:
            return (
                f"✅ **Уязвимостей не обнаружено** в `{text}`\n\n"
                f"*Проверено {len(py_files)} файлов, {len(_PATTERNS)} паттернов.*"
            )

        # Sort by severity
        _ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        findings.sort(key=lambda x: (_ORDER.get(x[2], 9), x[0], x[1]))

        _ICONS = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}

        counts = {s: sum(1 for f in findings if f[2] == s) for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
        summary_parts = [f"{_ICONS[s]} {s}: {c}" for s, c in counts.items() if c > 0]

        lines_out = [
            f"**Security Scan: `{text}`**",
            f"Файлов: {len(py_files)} · Находок: {len(findings)}",
            "  ".join(summary_parts),
            "",
        ]

        shown = findings[:30]
        for fpath, lineno, severity, desc, snippet in shown:
            rel = _Path(fpath).name
            icon = _ICONS.get(severity, "⚪")
            lines_out.append(f"{icon} **[{severity}]** `{rel}:{lineno}` — {desc}")
            lines_out.append(f"   `{snippet}`")

        if len(findings) > 30:
            lines_out.append(f"\n*…ещё {len(findings) - 30} находок (показаны первые 30)*")

        lines_out.append(f"\n*Статический анализ, возможны ложные срабатывания.*")
        return "\n".join(lines_out)

    registry.register(SlashCommand(
        "security-scan",
        "Сканирование уязвимостей: /security-scan <файл.py|директория>",
        security_scan_handler,
    ))

    # ── Task 230: /size-report ────────────────────────────────────────────

    async def size_report_handler(arg: str = "", **_) -> str:
        from pathlib import Path as _Path
        from collections import defaultdict as _dd

        text = arg.strip()
        root = _Path(text) if text else _Path(".")

        if not root.exists():
            return f"Путь не найден: `{text}`"

        _SKIP = {".git", "__pycache__", ".venv", "venv", "node_modules",
                 ".mypy_cache", ".pytest_cache", "dist", "build", ".eggs"}

        # Gather stats
        ext_stats: dict[str, dict] = _dd(lambda: {"files": 0, "lines": 0, "bytes": 0})
        dir_stats: dict[str, dict] = _dd(lambda: {"files": 0, "lines": 0, "bytes": 0})
        total_files = 0
        total_lines = 0
        total_bytes = 0
        largest: list[tuple[int, str]] = []  # (lines, path)

        def _walk(d: _Path) -> None:
            nonlocal total_files, total_lines, total_bytes
            try:
                entries = list(d.iterdir())
            except PermissionError:
                return
            for e in entries:
                if e.name in _SKIP or e.name.startswith("."):
                    continue
                if e.is_dir():
                    _walk(e)
                elif e.is_file():
                    try:
                        raw = e.read_bytes()
                        size = len(raw)
                        total_files += 1
                        total_bytes += size
                        ext = e.suffix.lower() or "(без расш.)"
                        ext_stats[ext]["files"] += 1
                        ext_stats[ext]["bytes"] += size

                        # Line count for text files
                        if size < 500_000 and b"\x00" not in raw[:512]:
                            try:
                                nlines = raw.decode("utf-8", errors="replace").count("\n")
                                ext_stats[ext]["lines"] += nlines
                                total_lines += nlines

                                # Track for dir stats
                                rel_dir = str(e.parent.relative_to(root))
                                top_dir = rel_dir.split("/")[0].split("\\")[0] if rel_dir != "." else "."
                                dir_stats[top_dir]["files"] += 1
                                dir_stats[top_dir]["lines"] += nlines
                                dir_stats[top_dir]["bytes"] += size

                                largest.append((nlines, str(e.relative_to(root))))
                            except Exception:
                                pass
                    except Exception:
                        pass

        _walk(root)

        if total_files == 0:
            return f"Файлов не найдено в `{root}`."

        def _fmt(n: int) -> str:
            if n < 1024:
                return f"{n} Б"
            elif n < 1_048_576:
                return f"{n/1024:.1f} КБ"
            else:
                return f"{n/1_048_576:.1f} МБ"

        lines_out = [
            f"**Аналитика размера: `{root.resolve().name or '.'}`**",
            "",
            f"Файлов: **{total_files:,}** · "
            f"Строк: **{total_lines:,}** · "
            f"Размер: **{_fmt(total_bytes)}**",
            "",
        ]

        # By extension
        lines_out.append("**По типу файлов:**")
        sorted_ext = sorted(ext_stats.items(), key=lambda x: -x[1]["lines"])
        for ext, s in sorted_ext[:12]:
            bar = "█" * min(20, s["lines"] // max(1, total_lines // 20))
            lines_out.append(
                f"  `{ext:<10}` {s['files']:>4} файл(а)  "
                f"{s['lines']:>6} строк  {_fmt(s['bytes']):>10}  {bar}"
            )

        # By top-level directory
        if len(dir_stats) > 1:
            lines_out.append("")
            lines_out.append("**По директориям (верхний уровень):**")
            sorted_dirs = sorted(dir_stats.items(), key=lambda x: -x[1]["lines"])
            for dname, s in sorted_dirs[:10]:
                pct = (s["lines"] / total_lines * 100) if total_lines else 0
                lines_out.append(
                    f"  `{dname:<20}` {s['lines']:>6} строк ({pct:.0f}%)  {_fmt(s['bytes'])}"
                )

        # Largest files
        largest.sort(reverse=True)
        if largest:
            lines_out.append("")
            lines_out.append("**Самые большие файлы (по строкам):**")
            for nlines, fpath in largest[:8]:
                lines_out.append(f"  `{fpath}` — {nlines:,} строк")

        return "\n".join(lines_out)

    registry.register(SlashCommand(
        "size-report",
        "Аналитика размера кодовой базы: /size-report [путь]",
        size_report_handler,
    ))

    # ── Task 231: /journal ────────────────────────────────────────────────

    async def journal_handler(arg: str = "", **_) -> str:
        import json as _json
        from pathlib import Path as _Path
        from datetime import datetime as _dt, date as _date

        journal_path = _Path(".lidco") / "journal.json"

        def _load() -> list:
            if journal_path.exists():
                try:
                    return _json.loads(journal_path.read_text(encoding="utf-8"))
                except Exception:
                    return []
            return []

        def _save(entries: list) -> None:
            journal_path.parent.mkdir(parents=True, exist_ok=True)
            journal_path.write_text(
                _json.dumps(entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        text = arg.strip()

        # today — show today's entries
        if not text or text == "today":
            entries = _load()
            today_str = _date.today().isoformat()
            today_entries = [e for e in entries if e.get("date") == today_str]
            if not today_entries:
                return (
                    f"**Журнал за {today_str}** — записей нет.\n\n"
                    "Добавьте: `/journal <текст>` или `/journal add <текст>`"
                )
            lines = [f"**Журнал за {today_str}** ({len(today_entries)} записей)", ""]
            for e in today_entries:
                time_str = e.get("time", "")
                tag = f" `[{e['tag']}]`" if e.get("tag") else ""
                lines.append(f"**{time_str}**{tag} {e['text']}")
            return "\n".join(lines)

        # list [N] — show last N days
        if text.startswith("list") or text.startswith("all"):
            parts = text.split()
            n_days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 7
            entries = _load()
            if not entries:
                return "Журнал пуст."
            # Group by date
            by_date: dict[str, list] = {}
            for e in entries:
                d = e.get("date", "")
                by_date.setdefault(d, []).append(e)
            # Last N days
            sorted_dates = sorted(by_date.keys(), reverse=True)[:n_days]
            lines = [f"**Журнал** (последние {n_days} дн., {len(entries)} записей)", ""]
            for d in sorted_dates:
                lines.append(f"**{d}:**")
                for e in by_date[d]:
                    time_str = e.get("time", "")
                    tag = f" `[{e['tag']}]`" if e.get("tag") else ""
                    lines.append(f"  {time_str}{tag} {e['text']}")
            return "\n".join(lines)

        # search <query>
        if text.startswith("search ") or text.startswith("find "):
            query = text.split(None, 1)[1].strip().lower()
            entries = _load()
            matches = [e for e in entries if query in e.get("text", "").lower()]
            if not matches:
                return f"По запросу «{query}» ничего не найдено."
            lines = [f"**Найдено:** {len(matches)} записей", ""]
            for e in matches[-20:]:
                lines.append(f"**{e.get('date')} {e.get('time','')}** {e['text']}")
            return "\n".join(lines)

        # stats
        if text == "stats":
            entries = _load()
            if not entries:
                return "Журнал пуст."
            dates = {e.get("date") for e in entries}
            tags = {}
            for e in entries:
                if e.get("tag"):
                    tags[e["tag"]] = tags.get(e["tag"], 0) + 1
            lines = [
                f"**Статистика журнала**", "",
                f"Записей: {len(entries)}",
                f"Дней: {len(dates)}",
                f"Среднее в день: {len(entries)/max(1,len(dates)):.1f}",
            ]
            if tags:
                lines.append("\n**Теги:**")
                for tag, cnt in sorted(tags.items(), key=lambda x: -x[1])[:10]:
                    lines.append(f"  `#{tag}`: {cnt}")
            return "\n".join(lines)

        # del N
        if text.startswith("del ") or text.startswith("delete "):
            idx_str = text.split(None, 1)[1].strip()
            if not idx_str.isdigit():
                return "Укажите номер записи: `/journal del <N>`"
            entries = _load()
            idx = int(idx_str) - 1
            if idx < 0 or idx >= len(entries):
                return f"Запись #{idx_str} не найдена."
            removed = entries.pop(idx)
            _save(entries)
            return f"Удалена запись: *{removed['text'][:60]}*"

        # clear
        if text == "clear":
            entries = _load()
            _save([])
            return f"Журнал очищен ({len(entries)} записей удалено)."

        # add <text> — strip "add " prefix if present
        if text.startswith("add "):
            text = text[4:].strip()

        # Parse optional #tag
        tag = ""
        if text.startswith("#"):
            parts = text.split(None, 1)
            tag = parts[0][1:]
            text = parts[1].strip() if len(parts) > 1 else ""
            if not text:
                return "Укажите текст записи: `/journal #tag текст`"

        now = _dt.now()
        entries = _load()
        entries.append({
            "text": text,
            "tag": tag,
            "date": now.date().isoformat(),
            "time": now.strftime("%H:%M"),
        })
        _save(entries)
        tag_str = f" `[{tag}]`" if tag else ""
        return f"✓ Запись #{len(entries)} добавлена{tag_str}: *{text[:80]}*"

    registry.register(SlashCommand(
        "journal",
        "Dev-журнал: /journal [add|today|list|search|stats|del|clear]",
        journal_handler,
    ))

    # ── Task 232: /table ──────────────────────────────────────────────────

    async def table_handler(arg: str = "", **_) -> str:
        import csv as _csv
        import io as _io
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/table <csv_файл или данные> [--sep ,] [--no-header]`\n\n"
                "Рендеринг CSV как таблицы.\n\n"
                "  `/table data.csv` — из файла\n"
                "  `/table \"name,age\\nAlice,30\\nBob,25\"` — из текста\n"
                "  `/table data.csv --sep ;` — с разделителем `;`"
            )

        sep = ","
        has_header = True
        if "--sep" in text:
            parts = text.split("--sep", 1)
            text = parts[0].strip()
            sep_tok = parts[1].strip().split()[0]
            sep = sep_tok if sep_tok else ","
        if "--no-header" in text:
            has_header = False
            text = text.replace("--no-header", "").strip()

        # Try as file first
        source_label = "inline"
        raw_csv = text
        p = _Path(text)
        if p.exists() and p.is_file():
            try:
                raw_csv = p.read_text(encoding="utf-8", errors="replace")
                source_label = p.name
            except Exception as exc:
                return f"Ошибка чтения файла: {exc}"
        else:
            # Allow \n escape in inline data
            raw_csv = raw_csv.replace("\\n", "\n")

        try:
            reader = _csv.reader(_io.StringIO(raw_csv), delimiter=sep)
            rows = list(reader)
        except Exception as exc:
            return f"Ошибка парсинга CSV: {exc}"

        if not rows:
            return "CSV пуст."

        # Cap rows
        max_rows = 50
        truncated = len(rows) > max_rows + (1 if has_header else 0)

        if has_header:
            headers = rows[0]
            data_rows = rows[1:max_rows + 1]
        else:
            headers = [f"Col{i+1}" for i in range(len(rows[0]))]
            data_rows = rows[:max_rows]

        if not headers:
            return "CSV не содержит столбцов."

        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in data_rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], min(len(cell), 30))

        def _fmt_row(cells: list[str]) -> str:
            parts = []
            for i, w in enumerate(col_widths):
                cell = cells[i] if i < len(cells) else ""
                cell = cell[:30]  # truncate long cells
                parts.append(cell.ljust(w))
            return "│ " + " │ ".join(parts) + " │"

        sep_line = "├─" + "─┼─".join("─" * w for w in col_widths) + "─┤"
        top_line = "┌─" + "─┬─".join("─" * w for w in col_widths) + "─┐"
        bot_line = "└─" + "─┴─".join("─" * w for w in col_widths) + "─┘"

        lines = [
            f"**Таблица: `{source_label}`** "
            f"({len(data_rows)} строк × {len(headers)} столбцов)",
            "",
            "```",
            top_line,
            _fmt_row(headers),
            sep_line,
        ]
        for row in data_rows:
            lines.append(_fmt_row(row))
        lines.append(bot_line)
        lines.append("```")

        if truncated:
            total = len(rows) - (1 if has_header else 0)
            lines.append(f"\n*Показано {len(data_rows)} из {total} строк.*")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "table",
        "Рендер CSV как таблицы: /table <файл.csv|данные> [--sep ,] [--no-header]",
        table_handler,
    ))

    # ── Task 233: /api ────────────────────────────────────────────────────

    async def api_handler(arg: str = "", **_) -> str:
        import asyncio as _asyncio
        import json as _json

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/api <url> [метод] [тело] [--header K:V]`\n\n"
                "HTTP-клиент прямо в REPL.\n\n"
                "  `/api https://httpbin.org/get` — GET запрос\n"
                "  `/api https://httpbin.org/post POST '{\"key\":\"val\"}'`\n"
                "  `/api https://api.example.com DELETE --header Authorization:Bearer_token`"
            )

        # Parse method
        _METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        parts = text.split(None, 2)
        url = parts[0]
        method = "GET"
        body = ""
        headers: dict[str, str] = {"User-Agent": "LIDCO/1.0"}

        rest = " ".join(parts[1:]) if len(parts) > 1 else ""

        # Extract --header flags
        import re as _re
        header_matches = _re.findall(r'--header\s+(\S+):(\S+)', rest)
        for k, v in header_matches:
            headers[k] = v.replace("_", " ")
        rest = _re.sub(r'--header\s+\S+:\S+', "", rest).strip()

        rest_parts = rest.split(None, 1)
        if rest_parts and rest_parts[0].upper() in _METHODS:
            method = rest_parts[0].upper()
            body = rest_parts[1].strip() if len(rest_parts) > 1 else ""
        elif rest_parts:
            body = rest.strip()

        # Validate URL
        if not url.startswith(("http://", "https://")):
            return f"URL должен начинаться с http:// или https://. Получено: `{url}`"

        # Execute via urllib (no external deps)
        import urllib.request as _urllib
        import urllib.error as _urlerr

        try:
            req_body = body.encode("utf-8") if body else None
            if req_body and "Content-Type" not in headers:
                try:
                    _json.loads(body)
                    headers["Content-Type"] = "application/json"
                except Exception:
                    headers["Content-Type"] = "text/plain"

            req = _urllib.Request(url, data=req_body, headers=headers, method=method)

            import asyncio as _aio
            loop = _aio.get_event_loop()

            def _do_request():
                with _urllib.urlopen(req, timeout=10) as resp:
                    status = resp.status
                    resp_headers = dict(resp.headers)
                    resp_body = resp.read().decode("utf-8", errors="replace")
                    return status, resp_headers, resp_body

            status, resp_headers, resp_body = await loop.run_in_executor(None, _do_request)

        except _urlerr.HTTPError as exc:
            status = exc.code
            resp_headers = {}
            try:
                resp_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                resp_body = str(exc)
        except Exception as exc:
            return f"Ошибка запроса: {exc}"

        # Format response
        status_icon = "✅" if 200 <= status < 300 else ("⚠️" if 200 <= status < 400 else "❌")
        lines = [
            f"**{method} {url}**",
            "",
            f"{status_icon} **Статус:** `{status}`",
        ]

        # Content-type
        ct = resp_headers.get("Content-Type", resp_headers.get("content-type", ""))
        if ct:
            lines.append(f"**Content-Type:** `{ct}`")

        lines.append("")

        # Body
        body_display = resp_body[:3000]
        if resp_body.strip().startswith("{") or resp_body.strip().startswith("["):
            try:
                parsed = _json.loads(resp_body)
                body_display = _json.dumps(parsed, indent=2, ensure_ascii=False)[:3000]
                lang = "json"
            except Exception:
                lang = ""
        else:
            lang = ""

        lines.append(f"```{lang}")
        lines.append(body_display)
        lines.append("```")

        if len(resp_body) > 3000:
            lines.append(f"\n*…обрезано ({len(resp_body):,} символов всего)*")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "api",
        "HTTP-клиент: /api <url> [GET|POST|...] [тело] [--header K:V]",
        api_handler,
    ))

    # ── Task 234: /lint-fix ───────────────────────────────────────────────

    async def lint_fix_handler(arg: str = "", **_) -> str:
        import asyncio as _asyncio
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/lint-fix <файл.py или директория> [--check]`\n\n"
                "Автоматическое исправление lint-ошибок через ruff.\n\n"
                "  `/lint-fix src/utils.py` — исправить файл\n"
                "  `/lint-fix src/ --check` — показать что будет исправлено\n"
                "  `/lint-fix .` — исправить всё в текущей директории"
            )

        check_only = "--check" in text
        if check_only:
            text = text.replace("--check", "").strip()

        p = _Path(text)
        if not p.exists():
            return f"Путь не найден: `{text}`"

        async def _ruff(*args, timeout=30) -> tuple[int, str]:
            try:
                proc = await _asyncio.create_subprocess_exec(
                    "ruff", *args,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                )
                out, _ = await _asyncio.wait_for(proc.communicate(), timeout=timeout)
                return proc.returncode or 0, out.decode("utf-8", errors="replace").strip()
            except FileNotFoundError:
                return 1, "ruff не найден. Установите: `pip install ruff`"
            except _asyncio.TimeoutError:
                return 1, "Timeout (30s)"
            except Exception as exc:
                return 1, str(exc)

        # First: check what would be fixed
        rc_check, check_out = await _ruff("check", str(p), "--no-fix")

        if check_only:
            if rc_check == 0:
                return f"✅ `{p}` — lint-ошибок нет."
            lines = [
                f"**ruff check** `{p}` (режим --check)",
                "",
                "```",
            ]
            for line in check_out.splitlines()[:40]:
                lines.append(line)
            lines.append("```")
            count = sum(1 for l in check_out.splitlines() if ".py:" in l)
            if count:
                lines.append(f"\n*{count} проблем будет исправлено командой `/lint-fix {text}`*")
            return "\n".join(lines)

        if rc_check == 0:
            return f"✅ `{p}` — lint-ошибок нет, исправление не требуется."

        # Count before
        before_count = sum(1 for l in check_out.splitlines() if ".py:" in l)

        # Apply fixes
        rc_fix, fix_out = await _ruff("check", str(p), "--fix")

        # Count after
        rc_after, after_out = await _ruff("check", str(p), "--no-fix")
        after_count = sum(1 for l in after_out.splitlines() if ".py:" in l) if rc_after != 0 else 0

        fixed = before_count - after_count

        lines = [f"**ruff --fix** `{p}`", ""]

        if fixed > 0:
            lines.append(f"✅ Исправлено: **{fixed}** проблем")
        if after_count > 0:
            lines.append(f"⚠️  Осталось: **{after_count}** (требуют ручного исправления)")

        if fix_out:
            lines.append("")
            lines.append("```")
            for line in fix_out.splitlines()[:20]:
                lines.append(line)
            lines.append("```")

        if after_count > 0 and after_out:
            lines.append("\n**Оставшиеся проблемы:**")
            lines.append("```")
            for line in after_out.splitlines()[:20]:
                lines.append(line)
            lines.append("```")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "lint-fix",
        "Автоисправление lint: /lint-fix <файл|директория> [--check]",
        lint_fix_handler,
    ))

    # ── Task 235: /refactor ───────────────────────────────────────────────

    async def refactor_handler(arg: str = "", **_) -> str:
        if not arg.strip():
            return (
                "**Использование:** `/refactor <файл> [инструкция]`\n\n"
                "Примеры:\n"
                "- `/refactor utils.py` — общий рефакторинг\n"
                "- `/refactor auth.py извлеки функции` — по инструкции\n"
                "- `/refactor module.py --dry` — только показать предложения"
            )
        if registry._session is None:
            return "❌ Сессия не инициализирована. Начните сессию перед использованием `/refactor`."

        parts = arg.strip().split(None, 1)
        file_part = parts[0]
        instruction = parts[1] if len(parts) > 1 else ""

        # Handle --dry flag
        dry_run = False
        if "--dry" in instruction:
            dry_run = True
            instruction = instruction.replace("--dry", "").strip()
        elif file_part == "--dry":
            return "**Использование:** `/refactor <файл> [--dry]`"

        p = Path(file_part)
        if not p.exists():
            return f"❌ Файл не найден: `{file_part}`"
        if not p.is_file():
            return f"❌ `{file_part}` — не файл."
        if p.suffix != ".py":
            return f"❌ Поддерживаются только `.py` файлы (получен `{p.suffix}`)."

        try:
            source = p.read_text(encoding="utf-8")
        except Exception as e:
            return f"❌ Ошибка чтения файла: {e}"

        loc = len(source.splitlines())
        if loc > 1000:
            return (
                f"⚠️ Файл слишком большой ({loc} строк). "
                "Используйте `/refactor <файл> <функция>` для рефакторинга конкретной части."
            )

        model = registry._session.config.llm.default_model
        hint = f"\n\nИнструкция: {instruction}" if instruction else ""
        prompt = (
            f"Проанализируй следующий Python-файл и предложи рефакторинг.{hint}\n"
            "Верни улучшенный код ЦЕЛИКОМ, обёрнутый в ```python ... ```.\n"
            "После кода добавь секцию ## Изменения с кратким списком того, что было изменено.\n\n"
            f"Файл: {p.name}\n\n```python\n{source}\n```"
        )

        try:
            resp = await registry._session.llm.complete(
                [{"role": "user", "content": prompt}],
                model=model,
                max_tokens=4096,
            )
            content = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:
            return f"❌ Ошибка LLM: {e}"

        if dry_run:
            return f"**Предложения по рефакторингу** `{p.name}` (режим --dry, файл не изменён)\n\n{content}"

        # Extract code block
        import re as _re
        code_match = _re.search(r"```python\n(.*?)```", content, _re.DOTALL)
        if not code_match:
            return f"**Предложения по рефакторингу** `{p.name}`\n\n{content}"

        new_source = code_match.group(1)
        if new_source.strip() == source.strip():
            return f"✅ `{p.name}` — рефакторинг не требуется, код уже оптимален.\n\n{content}"

        try:
            p.write_text(new_source, encoding="utf-8")
        except Exception as e:
            return f"❌ Ошибка записи файла: {e}"

        # Extract changes section
        changes_match = _re.search(r"## Изменения(.*?)(?:##|$)", content, _re.DOTALL)
        changes = changes_match.group(1).strip() if changes_match else ""

        lines = [f"✅ **Рефакторинг** `{p.name}` — файл обновлён"]
        if changes:
            lines.append(f"\n**Изменения:**\n{changes}")
        lines.append(f"\n*Применено к {p}*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "refactor",
        "AI-рефакторинг: /refactor <файл> [инструкция|--dry]",
        refactor_handler,
    ))

    # ── Task 236: /chart ──────────────────────────────────────────────────

    async def chart_handler(arg: str = "", **_) -> str:
        if not arg.strip():
            return (
                "**Использование:** `/chart <данные> [--type bar|line|pie] [--title Заголовок]`\n\n"
                "Форматы данных:\n"
                "- `10,20,30,40` — список чисел\n"
                "- `Jan:10,Feb:20,Mar:30` — метки:значения\n"
                "- `10 20 30 40` — пробелами\n\n"
                "Примеры:\n"
                "- `/chart 10,25,15,40 --type bar`\n"
                "- `/chart Jan:10,Feb:20,Mar:5 --type line`\n"
                "- `/chart Python:40,JS:30,Rust:20,Other:10 --type pie`"
            )

        import re as _re

        raw = arg.strip()

        # Extract flags
        chart_type = "bar"
        m_type = _re.search(r"--type\s+(bar|line|pie)", raw)
        if m_type:
            chart_type = m_type.group(1)
            raw = raw[:m_type.start()].strip() + raw[m_type.end():].strip()

        title = ""
        m_title = _re.search(r"--title\s+(.+?)(?:\s+--|$)", raw)
        if m_title:
            title = m_title.group(1).strip()
            raw = raw[:m_title.start()].strip() + raw[m_title.end():].strip()

        raw = raw.strip()

        # Parse data: label:value,label:value OR value,value OR value value
        labels: list[str] = []
        values: list[float] = []

        try:
            if ":" in raw:
                for item in raw.replace(";", ",").split(","):
                    item = item.strip()
                    if not item:
                        continue
                    if ":" in item:
                        lbl, val = item.rsplit(":", 1)
                        labels.append(lbl.strip())
                        values.append(float(val.strip()))
                    else:
                        labels.append(f"#{len(values)+1}")
                        values.append(float(item))
            else:
                sep = "," if "," in raw else None
                parts_v = raw.split(sep) if sep else raw.split()
                for i, v in enumerate(parts_v):
                    v = v.strip()
                    if v:
                        labels.append(f"#{i+1}")
                        values.append(float(v))
        except ValueError as e:
            return f"❌ Ошибка парсинга данных: {e}\n\nОжидается формат: `10,20,30` или `A:10,B:20`"

        if not values:
            return "❌ Нет данных для построения графика."

        if len(values) > 30:
            return f"❌ Слишком много точек ({len(values)}). Максимум 30."

        max_val = max(values)
        min_val = min(values)
        total = sum(values)

        header = f"**{title}**\n" if title else ""
        type_label = {"bar": "Столбчатая", "line": "Линейная", "pie": "Круговая"}[chart_type]
        header += f"*{type_label} диаграмма — {len(values)} точек*\n\n"

        if chart_type in ("bar", "line"):
            # ASCII bar / line chart
            W = 40
            rows = []

            if chart_type == "bar":
                max_lbl = max(len(l) for l in labels)
                for lbl, val in zip(labels, values):
                    bar_len = int(round((val / max_val) * W)) if max_val > 0 else 0
                    bar = "█" * bar_len
                    rows.append(f"{lbl:>{max_lbl}} │{bar:<{W}} {val:g}")
            else:
                # Line chart: plot on a 2D grid
                H = min(10, len(values))
                grid = [[" "] * len(values) for _ in range(H)]
                rng = max_val - min_val if max_val != min_val else 1
                for i, val in enumerate(values):
                    row = int(round((H - 1) * (1 - (val - min_val) / rng)))
                    row = max(0, min(H - 1, row))
                    grid[row][i] = "●"
                for row_idx, row in enumerate(grid):
                    y_val = max_val - (max_val - min_val) * row_idx / max(H - 1, 1)
                    rows.append(f"{y_val:>7.1f} │{''.join(row)}")
                rows.append(" " * 8 + "└" + "─" * len(values))
                max_lbl = max(len(l) for l in labels)
                rows.append(" " * 9 + "  ".join(f"{l:>{max_lbl}}" for l in labels)[:80])

            output = header + "```\n" + "\n".join(rows) + "\n```"

        else:
            # Pie chart: ASCII representation
            rows = []
            chars = "▓░▒▪▫◆◇●○■□"
            for i, (lbl, val) in enumerate(zip(labels, values)):
                pct = (val / total * 100) if total > 0 else 0
                bar_len = int(round(pct / 100 * 30))
                ch = chars[i % len(chars)]
                rows.append(f"{ch * bar_len:<30} {lbl}: {val:g} ({pct:.1f}%)")
            output = header + "```\n" + "\n".join(rows) + "\n```"

        # Stats footer
        stats = (
            f"\n*Мин: {min_val:g}  Макс: {max_val:g}  "
            f"Сумма: {total:g}  Среднее: {total/len(values):.2f}*"
        )
        return output + stats

    registry.register(SlashCommand(
        "chart",
        "ASCII-диаграмма: /chart <данные> [--type bar|line|pie] [--title ...]",
        chart_handler,
    ))

    # ── Task 237: /perf ───────────────────────────────────────────────────

    async def perf_handler(arg: str = "", **_) -> str:
        if not arg.strip():
            return (
                "**Использование:** `/perf <файл.py> [функция] [--top N] [--calls]`\n\n"
                "Примеры:\n"
                "- `/perf script.py` — профилировать весь файл\n"
                "- `/perf script.py main` — профилировать функцию main\n"
                "- `/perf script.py --top 20` — показать top-20 функций\n"
                "- `/perf script.py --calls` — включить дерево вызовов"
            )

        import re as _re
        import sys

        raw = arg.strip()

        # Extract flags
        top_n = 10
        m_top = _re.search(r"--top\s+(\d+)", raw)
        if m_top:
            top_n = int(m_top.group(1))
            raw = raw[:m_top.start()].strip() + raw[m_top.end():].strip()

        show_calls = "--calls" in raw
        if show_calls:
            raw = raw.replace("--calls", "").strip()

        parts = raw.split(None, 1)
        file_part = parts[0]
        func_name = parts[1].strip() if len(parts) > 1 else ""

        p = Path(file_part)
        if not p.exists():
            return f"❌ Файл не найден: `{file_part}`"
        if not p.is_file():
            return f"❌ `{file_part}` — не файл."
        if p.suffix != ".py":
            return f"❌ Поддерживаются только `.py` файлы."

        # Build a profiling script that runs the target and dumps stats
        import asyncio
        import tempfile, json as _json

        prof_script = f"""\
import cProfile
import pstats
import io
import sys
import json

sys.path.insert(0, r"{p.parent}")

pr = cProfile.Profile()
pr.enable()

try:
    import runpy
    runpy.run_path(r"{p}", run_name="__main__")
except SystemExit:
    pass
except Exception as exc:
    pass
finally:
    pr.disable()

s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats({top_n})
stats_text = s.getvalue()
print(stats_text)
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(prof_script)
            tf_name = tf.name

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, tf_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            except asyncio.TimeoutError:
                proc.kill()
                return f"❌ Профилирование прервано: превышен лимит 30 секунд."
        finally:
            import os as _os
            try:
                _os.unlink(tf_name)
            except Exception:
                pass

        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")

        if not out.strip() and err.strip():
            err_lines = err.splitlines()[:10]
            return f"❌ Ошибка выполнения:\n```\n" + "\n".join(err_lines) + "\n```"

        # Parse pstats output into a table
        lines_out = out.splitlines()
        # Find the header line
        table_start = None
        for i, ln in enumerate(lines_out):
            if "ncalls" in ln and "tottime" in ln:
                table_start = i
                break

        result_lines = [
            f"**Профиль** `{p.name}`  (top {top_n} по cumtime)",
            "",
        ]

        if table_start is not None:
            # Header
            result_lines.append("```")
            header_line = lines_out[table_start]
            result_lines.append(header_line)
            result_lines.append("-" * min(len(header_line), 80))

            data_rows = []
            for ln in lines_out[table_start + 1:]:
                if not ln.strip():
                    continue
                data_rows.append(ln)
                if len(data_rows) >= top_n:
                    break

            result_lines.extend(data_rows)
            result_lines.append("```")
        else:
            # Fallback: show raw output
            result_lines.append("```")
            for ln in lines_out[:min(len(lines_out), top_n + 10)]:
                result_lines.append(ln)
            result_lines.append("```")

        # Summary: total time from "function calls in X seconds"
        for ln in lines_out:
            if "function calls" in ln and "seconds" in ln:
                result_lines.append(f"\n*{ln.strip()}*")
                break

        # Call tree hint
        if show_calls:
            result_lines.append("\n**Совет:** Для дерева вызовов используйте `snakeviz` или `py-spy`.")

        # Hotspot hint
        if data_rows if table_start is not None else False:
            first_row = data_rows[0] if data_rows else ""
            result_lines.append(
                f"\n💡 Самая медленная функция: `{first_row.rsplit(None, 1)[-1] if first_row else '?'}`"
            )

        return "\n".join(result_lines)

    registry.register(SlashCommand(
        "perf",
        "Профилирование Python: /perf <файл.py> [--top N] [--calls]",
        perf_handler,
    ))

    # ── Task 238: /env ────────────────────────────────────────────────────

    async def env_handler(arg: str = "", **_) -> str:
        import os as _os
        import re as _re

        raw = arg.strip()

        # /env --export
        if raw == "--export":
            lines = ["**Export:**", "```bash"]
            for k, v in sorted(_os.environ.items()):
                lines.append(f"export {k}={v!r}")
            lines.append("```")
            return "\n".join(lines)

        # /env unset VAR
        if raw == "unset" or raw.startswith("unset "):
            key = raw[6:].strip() if raw.startswith("unset ") else ""
            if not key:
                return "❌ Укажите имя переменной: `/env unset VAR`"
            if key in _os.environ:
                del _os.environ[key]
                return f"✓ Переменная `{key}` удалена из окружения."
            return f"⚠️ `{key}` не установлена."

        # /env --filter PATTERN
        m_filter = _re.match(r"--filter\s+(.+)", raw)
        if m_filter:
            pat = m_filter.group(1).strip().lower()
            matches = {k: v for k, v in _os.environ.items() if pat in k.lower() or pat in v.lower()}
            if not matches:
                return f"*Нет переменных, содержащих `{pat}`.*"
            lines = [f"**Переменные окружения** (фильтр: `{pat}`):\n"]
            for k in sorted(matches):
                v = matches[k]
                display = v if len(v) <= 60 else v[:60] + "…"
                lines.append(f"- `{k}` = `{display}`")
            return "\n".join(lines)

        # /env VAR=value — set
        if "=" in raw and not raw.startswith("-"):
            key, _, val = raw.partition("=")
            key = key.strip()
            val = val.strip()
            if not key or not _re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                return f"❌ Некорректное имя переменной: `{key}`"
            _os.environ[key] = val
            return f"✓ `{key}` = `{val}`"

        # /env VAR — show one
        if raw and not raw.startswith("-"):
            val = _os.environ.get(raw)
            if val is None:
                return f"⚠️ Переменная `{raw}` не установлена."
            return f"**{raw}** = `{val}`"

        # /env — list all (grouped by prefix)
        env = _os.environ
        total = len(env)
        MAX = 50
        lines = [f"**Переменные окружения** ({total} всего):\n"]
        for k in sorted(env)[:MAX]:
            v = env[k]
            display = v if len(v) <= 60 else v[:60] + "…"
            lines.append(f"- `{k}` = `{display}`")
        if total > MAX:
            lines.append(f"\n*…и ещё {total - MAX}. Используйте `/env --filter pat` для поиска.*")
        lines.append(
            "\n**Команды:** `/env VAR` • `/env VAR=val` • `/env unset VAR` • "
            "`/env --filter pat` • `/env --export`"
        )
        return "\n".join(lines)

    registry.register(SlashCommand(
        "envvars",
        "Переменные окружения ОС: /envvars [VAR] [VAR=val] [unset VAR] [--filter pat] [--export]",
        env_handler,
    ))

    # ── Task 239: /template ───────────────────────────────────────────────

    _TEMPLATES: dict[str, tuple[str, str]] = {
        "class": ("MyClass.py", '''\
    class {Name}:
    """Docstring for {Name}."""

    def __init__(self) -> None:
    pass

    def __repr__(self) -> str:
    return f"{self.__class__.__name__}()"
    '''),
        "function": ("func.py", '''\
    from typing import Any


    def {name}(*args: Any, **kwargs: Any) -> None:
    """Docstring for {name}."""
    raise NotImplementedError
    '''),
        "dataclass": ("model.py", '''\
    from dataclasses import dataclass, field
    from typing import Any


    @dataclass
    class {Name}:
    """Data model for {Name}."""

    id: int = 0
    name: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
    return {"id": self.id, "name": self.name, "tags": self.tags}
    '''),
        "test": ("test_module.py", '''\
    """Tests for {name}."""
    from __future__ import annotations

    import pytest


    class Test{Name}:
    def test_basic(self) -> None:
    assert True

    def test_raises(self) -> None:
    with pytest.raises(NotImplementedError):
        raise NotImplementedError
    '''),
        "cli": ("cli.py", '''\
    """CLI entry point."""
    from __future__ import annotations

    import argparse
    import sys


    def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="{name}")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


    def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return 0


    if __name__ == "__main__":
    sys.exit(main())
    '''),
        "fastapi": ("app.py", '''\
    """FastAPI application."""
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    app = FastAPI(title="{name}")


    class Item(BaseModel):
    id: int
    name: str


    @app.get("/")
    async def root() -> dict[str, str]:
    return {{"message": "Hello from {name}"}}


    @app.get("/items/{{item_id}}")
    async def get_item(item_id: int) -> Item:
    return Item(id=item_id, name="example")
    '''),
        "decorator": ("decorators.py", '''\
    """Custom decorators."""
    from __future__ import annotations

    import functools
    import logging
    from typing import Any, Callable, TypeVar

    F = TypeVar("F", bound=Callable[..., Any])
    log = logging.getLogger(__name__)


    def {name}(func: F) -> F:
    """Decorator: {name}."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
    log.debug("Calling %s", func.__name__)
    result = func(*args, **kwargs)
    log.debug("Done %s", func.__name__)
    return result
    return wrapper  # type: ignore[return-value]
    '''),
        "context": ("context.py", '''\
    """Context manager."""
    from __future__ import annotations

    from contextlib import contextmanager
    from typing import Generator


    @contextmanager
    def {name}() -> Generator[None, None, None]:
    """Context manager: {name}."""
    # setup
    try:
    yield
    finally:
    # teardown
    pass
    '''),
    }

    async def template_handler(arg: str = "", **_) -> str:
        import re as _re

        raw = arg.strip()

        # /template — list all
        if not raw or raw == "list":
            names = sorted(_TEMPLATES)
            lines = [f"**Доступные шаблоны** ({len(names)}):\n"]
            for name in names:
                default_file, content = _TEMPLATES[name]
                loc = len(content.splitlines())
                lines.append(f"- `{name}` — `{default_file}` ({loc} строк)")
            lines.append(
                "\n**Использование:**\n"
                "- `/template <имя>` — показать шаблон\n"
                "- `/template <имя> <файл.py>` — создать файл\n"
                "- `/template <имя> <файл.py> Name=MyClass` — с заменой"
            )
            return "\n".join(lines)

        parts = raw.split(None)
        tmpl_name = parts[0].lower()

        if tmpl_name not in _TEMPLATES:
            close = [k for k in _TEMPLATES if k.startswith(tmpl_name[:2])]
            hint = f" Возможно: {', '.join(close)}" if close else ""
            return f"❌ Шаблон `{tmpl_name}` не найден.{hint}\n\nДоступные: {', '.join(sorted(_TEMPLATES))}"

        default_file, template_content = _TEMPLATES[tmpl_name]

        # Collect substitutions: Name=Foo or name=foo from remaining parts
        output_path: str | None = None
        subs: dict[str, str] = {}
        for part in parts[1:]:
            if "=" in part and not part.startswith("/"):
                k, _, v = part.partition("=")
                subs[k.strip()] = v.strip()
            elif not output_path:
                output_path = part

        # Apply substitutions to template
        content = template_content
        for k, v in subs.items():
            content = content.replace("{" + k + "}", v)

        # /template name — just show
        if output_path is None:
            return (
                f"**Шаблон:** `{tmpl_name}` (→ `{default_file}`)\n\n"
                f"```python\n{content}```\n\n"
                f"*Создать файл: `/template {tmpl_name} <путь.py>`*"
            )

        p = Path(output_path)
        if p.exists():
            return f"❌ Файл уже существует: `{output_path}`. Удалите или выберите другое имя."

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        except Exception as e:
            return f"❌ Ошибка записи: {e}"

        loc = len(content.splitlines())
        return (
            f"✅ **Создан** `{output_path}` из шаблона `{tmpl_name}` ({loc} строк)\n\n"
            f"```python\n{content[:400]}{'…' if len(content) > 400 else ''}```"
        )

    registry.register(SlashCommand(
        "scaffold",
        "Scaffolding шаблонов: /scaffold [имя] [файл] [Key=Value]",
        template_handler,
    ))

    # ── Task 240: /alias ──────────────────────────────────────────────────

    # Aliases are stored in .lidco/aliases.json as {name: command_string}
    # They are also cached in-memory on the registry for fast lookup.
    if not hasattr(registry, "_aliases"):
        registry._aliases: dict[str, str] = {}

    def _aliases_file() -> Path:
        return Path(".lidco") / "aliases.json"

    def _load_aliases() -> dict[str, str]:
        import json as _json
        f = _aliases_file()
        if f.exists():
            try:
                return _json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_aliases(data: dict[str, str]) -> None:
        import json as _json
        f = _aliases_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def alias_handler(arg: str = "", **_) -> str:
        import re as _re

        raw = arg.strip()

        def _define(name: str, cmd: str) -> str:
            if not name or not _re.match(r"^[A-Za-z0-9_-]+$", name):
                return f"❌ Некорректное имя псевдонима: `{name}`."
            if not cmd:
                return "❌ Команда не может быть пустой."
            # Auto-prefix with / if missing
            if not cmd.startswith("/"):
                cmd = "/" + cmd
            registry._aliases[name] = cmd
            _save_aliases(registry._aliases)
            return f"✓ Псевдоним `{name}` → `{cmd}` создан."

        # /alias — list
        if not raw or raw == "list":
            if not registry._aliases:
                return (
                    "Псевдонимы не определены.\n\n"
                    "**Создать:** `/alias <имя> <команда>` или `/alias <имя>=<команда>`\n"
                    "**Удалить:** `/alias del <имя>`"
                )
            lines = [f"**Псевдонимы** ({len(registry._aliases)}):\n"]
            for name in sorted(registry._aliases):
                lines.append(f"- `{name}` → `{registry._aliases[name]}`")
            lines.append("\n**Выполнить:** `/alias run <имя>` | **Удалить:** `/alias del <имя>`")
            return "\n".join(lines)

        # /alias del name
        if raw.startswith("del "):
            name = raw[4:].strip()
            if not name:
                return "❌ Укажите имя псевдонима: `/alias del <имя>`"
            if name not in registry._aliases:
                return f"⚠️ Псевдоним `{name}` не найден."
            del registry._aliases[name]
            _save_aliases(registry._aliases)
            return f"✓ Псевдоним `{name}` удалён."

        # /alias run name
        if raw.startswith("run "):
            name = raw[4:].strip()
            if not name:
                return "❌ Укажите имя псевдонима: `/alias run <имя>`"
            if name not in registry._aliases:
                return f"⚠️ Псевдоним `{name}` не найден."
            cmd = registry._aliases[name]
            return f"**Псевдоним** `{name}` → `{cmd}`\n\n*Скопируйте команду в строку ввода для выполнения.*"

        # /alias show name  (single-word lookup — old behavior)
        if raw.startswith("show "):
            name = raw[5:].strip()
            if not name:
                return "❌ Укажите имя: `/alias show <имя>`"
            if name not in registry._aliases:
                return f"⚠️ Псевдоним `{name}` не найден."
            return f"**{name}** = `{registry._aliases[name]}`"

        # /alias clear
        if raw == "clear":
            registry._aliases.clear()
            _save_aliases(registry._aliases)
            return "✓ Все псевдонимы удалены."

        # /alias name=/command ... — create/update (new = syntax)
        if "=" in raw and " " not in raw.split("=")[0]:
            name, _, cmd = raw.partition("=")
            return _define(name.strip(), cmd.strip())

        # /alias name command ... — create/update (old space syntax)
        parts = raw.split(None, 1)
        if len(parts) == 2:
            name, cmd = parts
            return _define(name.strip(), cmd.strip())

        # /alias name — show single alias (old behavior)
        if len(parts) == 1:
            name = parts[0]
            if name in registry._aliases:
                return f"`{name}` → `{registry._aliases[name]}`"
            return f"⚠️ Псевдоним `{name}` не найден."

        return (
            "**Использование:**\n"
            "- `/alias` — список псевдонимов\n"
            "- `/alias <имя> <команда>` — создать\n"
            "- `/alias <имя>=<команда>` — создать (альтернативный синтаксис)\n"
            "- `/alias run <имя>` — показать для выполнения\n"
            "- `/alias del <имя>` — удалить\n"
            "- `/alias clear` — удалить все"
        )

    registry.register(SlashCommand(
        "alias",
        "Псевдонимы команд: /alias [имя=команда] [run|del|list|clear]",
        alias_handler,
    ))

    # ── Task 241: /snippet ────────────────────────────────────────────────
    # Snippets stored in .lidco/snippets.json as:
    # {name: {code, lang, desc, created}}

    def _snippets_file() -> Path:
        return Path(".lidco") / "snippets.json"

    def _load_snippets() -> dict:
        import json as _json
        f = _snippets_file()
        if f.exists():
            try:
                return _json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_snippets(data: dict) -> None:
        import json as _json
        f = _snippets_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def snippet_handler(arg: str = "", **_) -> str:
        import re as _re
        from datetime import datetime as _dt

        raw = arg.strip()
        db = _load_snippets()

        # /snippet — list all
        if not raw or raw == "list":
            if not db:
                return (
                    "*Сниппетов нет.*\n\n"
                    "**Сохранить:** `/snippet save <имя> [--lang py] [--desc Описание]`\n"
                    "**Из файла:** `/snippet save <имя> <файл.py>`\n"
                    "**Показать:** `/snippet show <имя>`"
                )
            lines = [f"**Сниппеты** ({len(db)}):\n"]
            for name in sorted(db):
                s = db[name]
                lang = s.get("lang", "")
                desc = s.get("desc", "")
                loc = len(s.get("code", "").splitlines())
                tag = f"  *{desc}*" if desc else ""
                lines.append(f"- `{name}` ({lang}, {loc} строк){tag}")
            return "\n".join(lines)

        # /snippet show <name>
        if raw.startswith("show "):
            name = raw[5:].strip()
            if name not in db:
                return f"❌ Сниппет `{name}` не найден."
            s = db[name]
            lang = s.get("lang", "")
            desc = s.get("desc", "")
            code = s.get("code", "")
            header = f"**{name}**"
            if desc:
                header += f"  *{desc}*"
            return f"{header}\n\n```{lang}\n{code}\n```"

        # /snippet del <name>
        if raw.startswith("del "):
            name = raw[4:].strip()
            if not name:
                return "❌ Укажите имя: `/snippet del <имя>`"
            if name not in db:
                return f"⚠️ Сниппет `{name}` не найден."
            del db[name]
            _save_snippets(db)
            return f"✓ Сниппет `{name}` удалён."

        # /snippet clear
        if raw == "clear":
            _save_snippets({})
            return "✓ Все сниппеты удалены."

        # /snippet export <name> <file>
        if raw.startswith("export "):
            parts = raw[7:].strip().split(None, 1)
            if len(parts) < 2:
                return "❌ Использование: `/snippet export <имя> <файл>`"
            name, fpath = parts[0], parts[1]
            if name not in db:
                return f"❌ Сниппет `{name}` не найден."
            p = Path(fpath)
            if p.exists():
                return f"❌ Файл уже существует: `{fpath}`"
            p.write_text(db[name]["code"], encoding="utf-8")
            return f"✅ Сниппет `{name}` экспортирован в `{fpath}`"

        # /snippet save <name> [<file>] [--lang X] [--desc Y]
        if raw.startswith("save "):
            rest = raw[5:].strip()

            # Extract --lang
            lang = "py"
            m_lang = _re.search(r"--lang\s+(\S+)", rest)
            if m_lang:
                lang = m_lang.group(1)
                rest = rest[:m_lang.start()].strip() + " " + rest[m_lang.end():].strip()

            # Extract --desc
            desc = ""
            m_desc = _re.search(r"--desc\s+(.+?)(?:\s+--|$)", rest)
            if m_desc:
                desc = m_desc.group(1).strip()
                rest = rest[:m_desc.start()].strip() + " " + rest[m_desc.end():].strip()

            rest = rest.strip()
            parts = rest.split(None, 1)
            if not parts:
                return "❌ Укажите имя сниппета: `/snippet save <имя>`"

            name = parts[0]
            if not _re.match(r"^[A-Za-z0-9_.-]+$", name):
                return f"❌ Некорректное имя: `{name}`"

            code = ""
            if len(parts) > 1:
                fpath = parts[1].strip()
                fp = Path(fpath)
                if fp.exists() and fp.is_file():
                    try:
                        code = fp.read_text(encoding="utf-8")
                        lang = fp.suffix.lstrip(".") or lang
                    except Exception as e:
                        return f"❌ Ошибка чтения файла: {e}"
                else:
                    # Treat as inline code
                    code = fpath

            if not code.strip():
                return (
                    "❌ Нет кода для сохранения.\n"
                    "Использование: `/snippet save <имя> <файл>` или передайте код"
                )

            db[name] = {
                "code": code,
                "lang": lang,
                "desc": desc,
                "created": _dt.now().isoformat(timespec="seconds"),
            }
            _save_snippets(db)
            loc = len(code.splitlines())
            return f"✅ Сниппет `{name}` сохранён ({loc} строк, {lang})"

        return (
            "**Использование:**\n"
            "- `/snippet` — список сниппетов\n"
            "- `/snippet save <имя> <файл|код> [--lang py] [--desc ...]` — сохранить\n"
            "- `/snippet show <имя>` — показать\n"
            "- `/snippet del <имя>` — удалить\n"
            "- `/snippet export <имя> <файл>` — экспортировать\n"
            "- `/snippet clear` — удалить все"
        )

    registry.register(SlashCommand(
        "snippet",
        "Сниппеты кода: /snippet [save|show|del|export|clear|list]",
        snippet_handler,
    ))

    # ── Task 242: /todo ───────────────────────────────────────────────────
    # Todos stored in .lidco/todos.json as list of:
    # {id, text, done, priority, created}

    def _todos_file() -> Path:
        return Path(".lidco") / "todos.json"

    def _load_todos() -> list:
        import json as _json
        f = _todos_file()
        if f.exists():
            try:
                return _json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _save_todos(data: list) -> None:
        import json as _json
        f = _todos_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def todo_handler(arg: str = "", **_) -> str:
        import re as _re
        from datetime import datetime as _dt

        raw = arg.strip()
        todos = _load_todos()

        def _next_id() -> int:
            return max((t["id"] for t in todos), default=0) + 1

        def _render(todo_list: list, title: str = "TODO") -> str:
            if not todo_list:
                return f"*{title}: нет задач.*"
            lines = [f"**{title}** ({len(todo_list)} задач):\n"]
            for t in todo_list:
                check = "✅" if t.get("done") else "☐"
                pri = t.get("priority", "")
                pri_tag = f" [{pri}]" if pri else ""
                lines.append(f"{check} **#{t['id']}** {t['text']}{pri_tag}")
            return "\n".join(lines)

        # /todo — list pending
        if not raw or raw == "list":
            pending = [t for t in todos if not t.get("done")]
            done_count = len(todos) - len(pending)
            result = _render(pending, "TODO")
            if done_count:
                result += f"\n\n*+ {done_count} выполнено. Используйте `/todo all` для просмотра.*"
            if not pending and not todos:
                result = (
                    "*Список задач пуст.*\n\n"
                    "**Добавить:** `/todo Описание задачи`\n"
                    "**Приоритет:** `/todo !high Срочная задача`"
                )
            return result

        # /todo all
        if raw == "all":
            return _render(todos, "Все задачи")

        # /todo done <id>
        if raw.startswith("done "):
            try:
                tid = int(raw[5:].strip())
            except ValueError:
                return "❌ Укажите номер задачи: `/todo done <номер>`"
            for t in todos:
                if t["id"] == tid:
                    t["done"] = True
                    _save_todos(todos)
                    return f"✅ Задача **#{tid}** выполнена: *{t['text']}*"
            return f"⚠️ Задача **#{tid}** не найдена."

        # /todo del <id>
        if raw.startswith("del "):
            try:
                tid = int(raw[4:].strip())
            except ValueError:
                return "❌ Укажите номер задачи: `/todo del <номер>`"
            before = len(todos)
            todos = [t for t in todos if t["id"] != tid]
            if len(todos) == before:
                return f"⚠️ Задача **#{tid}** не найдена."
            _save_todos(todos)
            return f"✓ Задача **#{tid}** удалена."

        # /todo clear
        if raw == "clear":
            _save_todos([])
            return "✓ Список задач очищен."

        # /todo undone <id>
        if raw.startswith("undone "):
            try:
                tid = int(raw[7:].strip())
            except ValueError:
                return "❌ Укажите номер задачи: `/todo undone <номер>`"
            for t in todos:
                if t["id"] == tid:
                    t["done"] = False
                    _save_todos(todos)
                    return f"↩️ Задача **#{tid}** возвращена в список."
            return f"⚠️ Задача **#{tid}** не найдена."

        # /todo stats
        if raw == "stats":
            total = len(todos)
            done = sum(1 for t in todos if t.get("done"))
            pending = total - done
            pct = int(done / total * 100) if total else 0
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            return (
                f"**TODO статистика**\n\n"
                f"Всего: {total} | Выполнено: {done} | Ожидает: {pending}\n"
                f"Прогресс: [{bar}] {pct}%"
            )

        # /todo search <query>
        if raw.startswith("search "):
            q = raw[7:].strip().lower()
            matches = [t for t in todos if q in t["text"].lower()]
            return _render(matches, f"Поиск: {q}")

        # /todo <text> — add new
        # Priority prefix: !high !med !low
        priority = ""
        text = raw
        m_pri = _re.match(r"^!(high|med|low)\s+(.+)", raw, _re.IGNORECASE)
        if m_pri:
            priority = m_pri.group(1).upper()
            text = m_pri.group(2).strip()

        if not text:
            return "❌ Укажите текст задачи."

        new_todo = {
            "id": _next_id(),
            "text": text,
            "done": False,
            "priority": priority,
            "created": _dt.now().isoformat(timespec="seconds"),
        }
        todos.append(new_todo)
        _save_todos(todos)
        pri_tag = f" [{priority}]" if priority else ""
        return f"✓ Задача **#{new_todo['id']}** добавлена: *{text}*{pri_tag}"

    registry.register(SlashCommand(
        "todo",
        "Список задач: /todo [текст] [done|del|undone|stats|search|clear|all]",
        todo_handler,
    ))

    # ── Task 243: /timer ──────────────────────────────────────────────────
    # In-memory session timers: {name: start_ts}
    if not hasattr(registry, "_timers"):
        registry._timers: dict[str, float] = {}

    async def timer_handler(arg: str = "", **_) -> str:
        import time as _time
        import re as _re

        raw = arg.strip()

        def _fmt_elapsed(seconds: float) -> str:
            s = int(seconds)
            h, rem = divmod(s, 3600)
            m, sc = divmod(rem, 60)
            if h:
                return f"{h}ч {m:02d}м {sc:02d}с"
            if m:
                return f"{m}м {sc:02d}с"
            return f"{sc}с"

        # /timer — list active timers
        if not raw or raw == "list":
            if not registry._timers:
                return (
                    "*Нет активных таймеров.*\n\n"
                    "**Запустить:** `/timer start [имя]`\n"
                    "**Остановить:** `/timer stop [имя]`\n"
                    "**Статус:** `/timer status [имя]`"
                )
            now = _time.monotonic()
            lines = [f"**Активные таймеры** ({len(registry._timers)}):\n"]
            for name, start in sorted(registry._timers.items()):
                elapsed = now - start
                lines.append(f"- `{name}` — {_fmt_elapsed(elapsed)}")
            return "\n".join(lines)

        # /timer start [name]
        if raw == "start" or raw.startswith("start "):
            name = raw[6:].strip() if raw.startswith("start ") else "default"
            if not name:
                name = "default"
            if name in registry._timers:
                elapsed = _time.monotonic() - registry._timers[name]
                return f"⚠️ Таймер `{name}` уже запущен ({_fmt_elapsed(elapsed)} назад)."
            registry._timers[name] = _time.monotonic()
            return f"▶️ Таймер `{name}` запущен."

        # /timer stop [name]
        if raw == "stop" or raw.startswith("stop "):
            name = raw[5:].strip() if raw.startswith("stop ") else "default"
            if not name:
                name = "default"
            if name not in registry._timers:
                return f"⚠️ Таймер `{name}` не найден."
            elapsed = _time.monotonic() - registry._timers.pop(name)
            return f"⏹️ Таймер `{name}` остановлен. Прошло: **{_fmt_elapsed(elapsed)}**"

        # /timer status [name]
        if raw == "status" or raw.startswith("status "):
            name = raw[7:].strip() if raw.startswith("status ") else "default"
            if not name:
                name = "default"
            if name not in registry._timers:
                return f"⚠️ Таймер `{name}` не найден."
            elapsed = _time.monotonic() - registry._timers[name]
            return f"⏱️ Таймер `{name}`: **{_fmt_elapsed(elapsed)}**"

        # /timer reset [name]
        if raw == "reset" or raw.startswith("reset "):
            name = raw[6:].strip() if raw.startswith("reset ") else "default"
            if not name:
                name = "default"
            registry._timers[name] = _time.monotonic()
            return f"🔄 Таймер `{name}` перезапущен."

        # /timer clear
        if raw == "clear":
            count = len(registry._timers)
            registry._timers.clear()
            return f"✓ Удалено {count} таймер(ов)."

        # /timer lap [name] — show elapsed without stopping
        if raw == "lap" or raw.startswith("lap "):
            name = raw[4:].strip() if raw.startswith("lap ") else "default"
            if not name:
                name = "default"
            if name not in registry._timers:
                return f"⚠️ Таймер `{name}` не найден."
            elapsed = _time.monotonic() - registry._timers[name]
            return f"⏱️ Lap `{name}`: {_fmt_elapsed(elapsed)}"

        return (
            "**Использование `/timer`:**\n"
            "- `/timer start [имя]` — запустить таймер\n"
            "- `/timer stop [имя]` — остановить и показать время\n"
            "- `/timer status [имя]` — текущее время\n"
            "- `/timer lap [имя]` — промежуточный результат\n"
            "- `/timer reset [имя]` — перезапустить\n"
            "- `/timer list` — все активные таймеры\n"
            "- `/timer clear` — удалить все"
        )

    registry.register(SlashCommand(
        "timer",
        "Таймер рабочей сессии: /timer [start|stop|status|lap|reset|list|clear] [имя]",
        timer_handler,
    ))

    # ── Q38: /mcp ─────────────────────────────────────────────────────────

    async def mcp_handler(arg: str = "", **_: Any) -> str:
        """Manage MCP server connections.

        Subcommands:
          /mcp                 — list all configured servers and their status
          /mcp status          — same as /mcp
          /mcp status <name>   — status for one server
          /mcp reconnect <name>— force-reconnect a server
          /mcp tools [name]    — list available MCP tools
        """
        if not registry._session:
            return "Session not initialized."

        manager = getattr(registry._session, "mcp_manager", None)
        if manager is None:
            return (
                "MCP integration is not active.\n\n"
                "Add servers to `.lidco/mcp.json` to get started:\n"
                "```json\n"
                '{"servers": [{"name": "myserver", "command": ["npx", "my-mcp-server"]}]}\n'
                "```"
            )

        raw = (arg or "").strip()
        parts = raw.split(maxsplit=1) if raw else []
        sub = parts[0].lower() if parts else "status"
        rest = parts[1] if len(parts) > 1 else ""

        # ── /mcp status [name] ────────────────────────────────────────────
        if sub in ("status", ""):
            statuses = manager.get_status(rest.strip() or None)
            if not statuses:
                return "No MCP servers configured." if not rest else f"Server `{rest}` not found."

            lines = ["**MCP Servers**\n"]
            for name, st in statuses.items():
                icon = "✓" if st.connected else "✗"
                connected_str = (
                    f"connected at {st.connected_at.strftime('%H:%M:%S')}"
                    if st.connected and st.connected_at
                    else "not connected"
                )
                lines.append(
                    f"- **{name}** [{st.transport}] {icon} {connected_str}"
                    + (f" — {st.tool_count} tool(s)" if st.connected else "")
                    + (f"\n  Error: {st.last_error}" if st.last_error else "")
                )
            return "\n".join(lines)

        # ── /mcp tools [name] ─────────────────────────────────────────────
        if sub == "tools":
            all_schemas = manager.all_tool_schemas()
            if rest:
                schemas = all_schemas.get(rest, [])
                if not schemas:
                    return f"No tools found for server `{rest}`."
                lines = [f"**MCP tools from `{rest}`**\n"]
                for s in schemas:
                    lines.append(f"- `{s.name}` — {s.description or '(no description)'}")
                return "\n".join(lines)

            if not all_schemas:
                return "No MCP tools available (no servers connected)."
            lines = ["**MCP Tools**\n"]
            for server_name, schemas in all_schemas.items():
                lines.append(f"**{server_name}** ({len(schemas)} tool(s))")
                for s in schemas[:5]:
                    lines.append(f"  - `mcp__{server_name}__{s.name}` — {s.description or ''}")
                if len(schemas) > 5:
                    lines.append(f"  … and {len(schemas) - 5} more")
            return "\n".join(lines)

        # ── /mcp reconnect <name> ─────────────────────────────────────────
        if sub == "reconnect":
            if not rest:
                return "**Usage:** `/mcp reconnect <server-name>`"
            mcp_config = getattr(registry._session, "mcp_config", None)
            if mcp_config is None:
                return "MCP config not available."
            entry = mcp_config.get_server(rest)
            if entry is None:
                return f"Server `{rest}` not found in config."
            # Run reconnect in background to avoid blocking the REPL
            import asyncio
            asyncio.ensure_future(manager.reconnect(rest, entry))
            return f"Reconnecting to `{rest}`…"

        return (
            "**Usage:** `/mcp [status|tools|reconnect] [name]`\n\n"
            "- `/mcp` — list all MCP servers\n"
            "- `/mcp status <name>` — status for one server\n"
            "- `/mcp tools [name]` — list MCP tools\n"
            "- `/mcp reconnect <name>` — force-reconnect a server"
        )

    registry.register(SlashCommand("mcp", "Manage MCP server connections", mcp_handler))
