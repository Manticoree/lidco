"""Commands: code analysis tools."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def register(registry: Any) -> None:
    """Register code analysis tools commands."""
    from lidco.cli.commands.registry import SlashCommand

    # ── Task 192: /inspect ─────────────────────────────────────────────────

    async def inspect_handler(arg: str = "", **_: Any) -> str:
        """/inspect <symbol> — показать исходный код, docstring и сигнатуру символа."""
        import asyncio as _asyncio
        import re as _re
        from pathlib import Path as _Path

        symbol = arg.strip()
        if not symbol:
            return (
                "**Использование:** `/inspect <символ>`\n\n"
                "Ищет определение символа в кодовой базе и показывает его.\n\n"
                "**Примеры:**\n"
                "  `/inspect CommandRegistry`\n"
                "  `/inspect process_slash_command`\n"
                "  `/inspect BaseAgent._run`"
            )

        # Grep for definition
        root = _Path(".")
        if registry._session:
            project_dir = getattr(registry._session, "project_dir", None)
            if project_dir:
                root = _Path(str(project_dir))

        # Search for def/class definition
        def_pattern = _re.compile(
            rf"^\s*(def|class|async def)\s+{_re.escape(symbol.split('.')[-1])}\b"
        )
        found: list[tuple[str, int]] = []  # (file, lineno)

        for pyf in sorted(root.rglob("*.py")):
            parts = pyf.parts
            if any(p in parts for p in (".git", "__pycache__", ".venv", "venv")):
                continue
            try:
                for lineno, line in enumerate(
                    pyf.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                ):
                    if def_pattern.search(line):
                        found.append((str(pyf), lineno))
                        if len(found) >= 5:
                            break
            except OSError:
                pass
            if len(found) >= 5:
                break

        if not found:
            return f"Символ `{symbol}` не найден в кодовой базе."

        results: list[str] = []
        for file_path, lineno in found[:3]:
            try:
                source_lines = _Path(file_path).read_text(encoding="utf-8", errors="ignore").splitlines()
                # Extract up to 40 lines from definition
                start = lineno - 1
                end = min(len(source_lines), start + 40)
                # Trim at next top-level def/class (same indent level)
                base_indent = len(source_lines[start]) - len(source_lines[start].lstrip())
                for i in range(start + 1, end):
                    line = source_lines[i]
                    if line.strip() == "":
                        continue
                    indent = len(line) - len(line.lstrip())
                    if indent <= base_indent and _re.match(r"\s*(def|class|async def)\b", line):
                        end = i
                        break
                excerpt = "\n".join(source_lines[start:end])
                results.append(
                    f"**`{file_path}:{lineno}`**\n\n```python\n{excerpt}\n```"
                )
            except OSError:
                results.append(f"**`{file_path}:{lineno}`** — не удалось прочитать файл")

        header = f"## `{symbol}` — {len(found)} определений" if len(found) > 1 else f"## `{symbol}`"
        if len(found) > 3:
            header += f" (показано 3 из {len(found)})"

        return header + "\n\n" + "\n\n---\n\n".join(results)

    registry.register(SlashCommand(
        "inspect",
        "Показать исходный код символа: /inspect <имя>",
        inspect_handler,
    ))

    # ── Task 193: /ask ─────────────────────────────────────────────────────

    async def ask_handler(arg: str = "", **_: Any) -> str:
        """/ask [--model <model>] <question> — быстрый вопрос к LLM без агентского оверхеда."""
        if not registry._session:
            return "Сессия не инициализирована."

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/ask [--model <модель>] <вопрос>`\n\n"
                "Задаёт быстрый вопрос напрямую LLM без маршрутизации через агентов.\n\n"
                "**Примеры:**\n"
                "  `/ask что такое декоратор в Python?`\n"
                "  `/ask --model openai/gpt-4o-mini explain asyncio`"
            )

        # Parse optional --model flag
        model_override: str | None = None
        _parts = text.split()
        if _parts and _parts[0] == "--model":
            if len(_parts) < 2:
                return "Укажите имя модели: `/ask --model <модель> <вопрос>`"
            model_override = _parts[1]
            text = " ".join(_parts[2:]).strip()
            if not text:
                return "Укажите вопрос после флага `--model <модель>`."

        from lidco.llm.base import Message as LLMMessage
        try:
            kwargs: dict = {"temperature": 0.3, "max_tokens": 1000}
            if model_override:
                kwargs["model"] = model_override

            resp = await registry._session.llm.complete(
                [LLMMessage(role="user", content=text)],
                **kwargs,
            )
            answer = (resp.content or "").strip()
            model_used = getattr(resp, "model", model_override or registry._session.config.llm.default_model)
            return f"{answer}\n\n*[{model_used}]*"
        except Exception as exc:
            return f"Ошибка LLM: {exc}"

    registry.register(SlashCommand(
        "ask",
        "Быстрый вопрос к LLM напрямую: /ask [--model <модель>] <вопрос>",
        ask_handler,
    ))

    # ── Task 194: /explain ─────────────────────────────────────────────────

    async def explain_handler(arg: str = "", **_: Any) -> str:
        """/explain <code or file> — объяснить код или файл через LLM."""
        if not registry._session:
            return "Сессия не инициализирована."

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/explain <код или путь к файлу>`\n\n"
                "Объясняет код или содержимое файла простым языком.\n\n"
                "**Примеры:**\n"
                "  `/explain src/lidco/core/session.py`\n"
                "  `/explain lambda x: x**2 if x > 0 else -x`"
            )

        from pathlib import Path as _Path
        from lidco.llm.base import Message as LLMMessage

        # Check if arg looks like a file path
        p = _Path(text)
        source_label = text
        if p.is_file():
            try:
                code = p.read_text(encoding="utf-8", errors="replace")
                source_label = str(p)
                # Trim very large files
                if len(code) > 8000:
                    code = code[:8000] + "\n... (обрезано)"
            except OSError as exc:
                return f"Не удалось прочитать `{text}`: {exc}"
        else:
            code = text

        prompt = (
            "Explain the following Python code clearly and concisely in Russian. "
            "Cover: what it does, key patterns used, and any non-obvious parts.\n\n"
            f"```python\n{code}\n```\n\n"
            "Keep the explanation under 300 words."
        )

        try:
            resp = await registry._session.llm.complete(
                [LLMMessage(role="user", content=prompt)],
                temperature=0.2,
                max_tokens=600,
            )
            explanation = (resp.content or "").strip()
        except Exception as exc:
            return f"Ошибка LLM: {exc}"

        return f"## Объяснение: `{source_label}`\n\n{explanation}"

    registry.register(SlashCommand(
        "explain",
        "Объяснить код или файл через LLM: /explain <код или файл>",
        explain_handler,
    ))

    # ── Task 195: /token ───────────────────────────────────────────────────

    async def token_handler(arg: str = "", **_: Any) -> str:
        """/token <text> — приблизительный подсчёт токенов для текста."""
        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/token <текст>`\n\n"
                "Показывает приблизительное количество токенов для текста.\n\n"
                "**Примеры:**\n"
                "  `/token def hello(): return 42`\n"
                "  `/token Привет, как дела?`"
            )

        # Rough tokenization heuristics (no tiktoken required)
        import re as _re

        chars = len(text)
        words = len(text.split())

        # Approximate token count:
        # - ~4 chars per token for English
        # - ~2-3 chars per token for non-ASCII (CJK/Cyrillic)
        # - code has shorter tokens on average
        non_ascii = sum(1 for c in text if ord(c) > 127)
        ascii_chars = chars - non_ascii

        # Mixed estimate
        est_tokens = (ascii_chars // 4) + (non_ascii // 2)
        est_tokens = max(1, est_tokens)

        # Word-based cross-check
        word_est = int(words * 1.3)

        # Use the higher of the two as conservative estimate
        conservative = max(est_tokens, word_est)

        # Cost estimate at common pricing tiers
        _PRICING = {
            "GPT-4o": (2.50, 10.0),       # $/1M in, $/1M out
            "GPT-4o-mini": (0.15, 0.60),
            "Claude Sonnet": (3.0, 15.0),
            "Claude Haiku": (0.25, 1.25),
        }

        lines = [
            "## Подсчёт токенов", "",
            f"**Текст:** {chars} символов · {words} слов",
            f"**Оценка токенов:** ~{conservative}",
            "",
            "**Приблизительная стоимость (per 1K токенов):**",
        ]
        for model_name, (price_in, price_out) in _PRICING.items():
            cost_in = conservative / 1_000_000 * price_in
            cost_out = conservative / 1_000_000 * price_out
            lines.append(
                f"  · {model_name}: ${cost_in:.6f} вход / ${cost_out:.6f} выход"
            )

        lines.append("")
        lines.append(
            "*Оценка приблизительная (~4 символа/токен для ASCII, "
            "~2 для кириллицы). Точный подсчёт зависит от токенизатора модели.*"
        )
        return "\n".join(lines)

    registry.register(SlashCommand(
        "token",
        "Приблизительный подсчёт токенов: /token <текст>",
        token_handler,
    ))

    # ── Task 196: /env ─────────────────────────────────────────────────────

    async def env_handler(arg: str = "", **_: Any) -> str:
        """/env — информация о Python-окружении, пакетах и системе."""
        import sys
        import os
        import platform

        text = arg.strip().lower()

        lines = ["## Окружение", ""]

        # Python
        py_ver = sys.version.split()[0]
        py_impl = platform.python_implementation()
        lines.append(f"**Python:** {py_impl} {py_ver}")
        lines.append(f"**Исполняемый:** `{sys.executable}`")

        # Virtualenv
        venv = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_DEFAULT_ENV", "")
        if venv:
            lines.append(f"**Virtualenv:** `{venv}`")
        else:
            lines.append("**Virtualenv:** не активен")

        # OS
        lines.append(f"**ОС:** {platform.system()} {platform.release()}")
        lines.append(f"**Архитектура:** {platform.machine()}")

        # CWD
        lines.append(f"**Рабочая директория:** `{os.getcwd()}`")

        # Key packages
        _KEY_PACKAGES = [
            "lidco", "rich", "prompt_toolkit", "litellm", "langchain",
            "langgraph", "pydantic", "pytest", "ruff", "mypy",
        ]
        lines.append("")
        lines.append("**Ключевые пакеты:**")

        import importlib.metadata as _meta
        for pkg in _KEY_PACKAGES:
            try:
                ver = _meta.version(pkg)
                lines.append(f"  · `{pkg}` {ver}")
            except _meta.PackageNotFoundError:
                if text == "all":
                    lines.append(f"  · `{pkg}` — не установлен")

        # Session info
        if registry._session:
            model = registry._session.config.llm.default_model
            lines.append("")
            lines.append(f"**Модель LIDCO:** `{model}`")

        lines.append("")
        lines.append("*`/env all` — показать все пакеты включая неустановленные*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "env",
        "Информация о Python-окружении и пакетах",
        env_handler,
    ))

    # ── Task 197: /bench ───────────────────────────────────────────────────

    async def bench_handler(arg: str = "", **_: Any) -> str:
        """/bench [N] — измерить задержку LLM (N запросов, по умолчанию 3)."""
        import time as _time

        if not registry._session:
            return "Сессия не инициализирована."

        text = arg.strip()
        try:
            n = int(text) if text else 3
            if n < 1:
                n = 1
            elif n > 10:
                n = 10
        except ValueError:
            return f"Неверный аргумент `{text}`. Использование: `/bench [N]` (N от 1 до 10)"

        from lidco.llm.base import Message as LLMMessage
        _PROBE = "Reply with exactly: OK"

        latencies: list[float] = []
        errors: list[str] = []
        model = registry._session.config.llm.default_model

        for i in range(n):
            t0 = _time.monotonic()
            try:
                await registry._session.llm.complete(
                    [LLMMessage(role="user", content=_PROBE)],
                    temperature=0.0,
                    max_tokens=5,
                )
                latencies.append(_time.monotonic() - t0)
            except Exception as exc:
                errors.append(f"Запрос {i + 1}: {exc}")

        if not latencies:
            err_str = "\n".join(errors)
            return f"Все запросы завершились ошибкой:\n\n{err_str}"

        avg = sum(latencies) / len(latencies)
        mn = min(latencies)
        mx = max(latencies)
        total = sum(latencies)

        lines = [f"## Benchmark: `{model}`", ""]
        lines.append(f"**Запросов:** {n} (успешных: {len(latencies)})")
        lines.append(f"**Среднее:** {avg:.2f}с")
        lines.append(f"**Мин / Макс:** {mn:.2f}с / {mx:.2f}с")
        lines.append(f"**Итого:** {total:.2f}с")
        lines.append("")
        lines.append("**По запросам:**")
        for i, lat in enumerate(latencies, 1):
            bar_len = min(20, int(lat / mx * 20)) if mx > 0 else 0
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"  #{i}: {lat:.2f}с  [{bar}]")

        if errors:
            lines.append("")
            lines.append(f"**Ошибки ({len(errors)}):**")
            for e in errors:
                lines.append(f"  · {e}")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "bench",
        "Бенчмарк LLM: измерить задержку N запросами: /bench [N]",
        bench_handler,
    ))

    # ── Task 198: /compare ─────────────────────────────────────────────────

    async def compare_handler(arg: str = "", **_: Any) -> str:
        """/compare <file1> <file2> — сравнить два файла (unified diff + статистика)."""
        import difflib as _diff
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/compare <файл1> <файл2>`\n\n"
                "Показывает unified diff и статистику между двумя файлами.\n\n"
                "**Пример:** `/compare src/v1.py src/v2.py`"
            )

        parts = text.split()
        if len(parts) < 2:
            return "Укажите два файла: `/compare <файл1> <файл2>`"

        path1, path2 = _Path(parts[0]), _Path(parts[1])

        if not path1.exists():
            return f"Файл не найден: `{parts[0]}`"
        if not path2.exists():
            return f"Файл не найден: `{parts[1]}`"
        if not path1.is_file():
            return f"Это не файл: `{parts[0]}`"
        if not path2.is_file():
            return f"Это не файл: `{parts[1]}`"

        try:
            content1 = path1.read_text(encoding="utf-8", errors="replace")
            content2 = path2.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Ошибка чтения: {exc}"

        lines1 = content1.splitlines()
        lines2 = content2.splitlines()

        diff = list(_diff.unified_diff(
            lines1, lines2,
            fromfile=str(path1),
            tofile=str(path2),
            lineterm="",
        ))

        # Stats
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        size1 = path1.stat().st_size
        size2 = path2.stat().st_size

        if not diff:
            return (
                f"**Файлы идентичны:**\n\n"
                f"- `{path1}` ({size1} байт, {len(lines1)} строк)\n"
                f"- `{path2}` ({size2} байт, {len(lines2)} строк)"
            )

        _MAX_DIFF = 200
        truncated = len(diff) > _MAX_DIFF
        diff_text = "\n".join(diff[:_MAX_DIFF])
        if truncated:
            diff_text += f"\n... ({len(diff) - _MAX_DIFF} строк скрыто)"

        stat_lines = [
            f"## Сравнение файлов", "",
            f"**{path1}** ({len(lines1)} строк, {size1} байт)",
            f"**{path2}** ({len(lines2)} строк, {size2} байт)",
            f"",
            f"**+{added}** добавлено / **−{removed}** удалено",
            "",
            f"```diff\n{diff_text}\n```",
        ]
        return "\n".join(stat_lines)

    registry.register(SlashCommand(
        "compare",
        "Сравнить два файла: /compare <файл1> <файл2>",
        compare_handler,
    ))

    # ── Task 199: /outline ─────────────────────────────────────────────────

    async def outline_handler(arg: str = "", **_: Any) -> str:
        """/outline [file] — структурный обзор Python файла (классы, функции, сигнатуры)."""
        import re as _re
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/outline <файл.py>`\n\n"
                "Показывает структуру Python-файла: классы, функции и их сигнатуры.\n\n"
                "**Пример:** `/outline src/lidco/cli/commands.py`"
            )

        p = _Path(text)
        if not p.exists():
            return f"Файл не найден: `{text}`"
        if not p.is_file():
            return f"Это не файл: `{text}`"

        try:
            source = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Не удалось прочитать: {exc}"

        source_lines = source.splitlines()
        total_lines = len(source_lines)

        # Parse structure via regex
        _DEF_RE = _re.compile(
            r"^(?P<indent>\s*)(?P<kind>async def|def|class)\s+(?P<name>\w+)"
            r"(?P<sig>\([^)]*\))?(?:\s*->.*?)?\s*:"
        )

        entries: list[dict] = []
        i = 0
        while i < len(source_lines):
            line = source_lines[i]
            m = _DEF_RE.match(line)
            if m:
                indent = len(m.group("indent"))
                kind = m.group("kind").strip()
                name = m.group("name")
                sig = m.group("sig") or "()"
                # Grab docstring if next non-empty line is a triple-quote
                docstring = ""
                j = i + 1
                while j < len(source_lines) and not source_lines[j].strip():
                    j += 1
                if j < len(source_lines):
                    ds = source_lines[j].strip()
                    if ds.startswith('"""') or ds.startswith("'''"):
                        # Single-line docstring
                        end = ds[3:]
                        if '"""' in end or "'''" in end:
                            docstring = end.split('"""')[0].split("'''")[0].strip()[:80]
                        else:
                            docstring = end.strip()[:80]
                entries.append({
                    "lineno": i + 1,
                    "indent": indent,
                    "kind": kind,
                    "name": name,
                    "sig": sig if len(sig) <= 60 else sig[:57] + "…)",
                    "docstring": docstring,
                })
            i += 1

        if not entries:
            return f"`{text}` — нет определений классов или функций ({total_lines} строк)."

        lines = [f"## Структура: `{text}` ({total_lines} строк)", ""]
        for entry in entries:
            prefix = "  " * (entry["indent"] // 4)
            kind_emoji = "🔷" if entry["kind"] == "class" else "⚡" if "async" in entry["kind"] else "🔹"
            sig_str = entry["sig"] if entry["kind"] != "class" else ""
            doc_str = f" — {entry['docstring']}" if entry["docstring"] else ""
            lines.append(
                f"{prefix}{kind_emoji} **{entry['name']}**`{sig_str}`  "
                f"`L{entry['lineno']}`{doc_str}"
            )

        lines.append("")
        lines.append(f"*{len(entries)} определений · `/inspect <имя>` — подробнее*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "outline",
        "Структурный обзор Python файла: /outline <файл>",
        outline_handler,
    ))

    # ── Task 200: /tree ────────────────────────────────────────────────────

    async def tree_handler(arg: str = "", **_: Any) -> str:
        """/tree [path] [--depth N] [--py] — показать дерево директорий."""
        from pathlib import Path as _Path
        import re as _re

        text = arg.strip()

        # Parse flags
        depth = 3
        py_only = False
        root_str = "."

        tokens = text.split()
        remaining: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok == "--depth" and i + 1 < len(tokens):
                try:
                    depth = max(1, min(10, int(tokens[i + 1])))
                    i += 2
                    continue
                except ValueError:
                    pass
            elif tok == "--py":
                py_only = True
                i += 1
                continue
            remaining.append(tok)
            i += 1

        if remaining:
            root_str = remaining[0]

        root = _Path(root_str)
        if not root.exists():
            return f"Путь не найден: `{root_str}`"

        _SKIP = frozenset({
            ".git", "__pycache__", ".venv", "venv", "node_modules",
            "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
            ".tox", "htmlcov", ".lidco",
        })

        def _render(path: _Path, prefix: str, current_depth: int) -> list[str]:
            if current_depth > depth:
                return []
            lines: list[str] = []
            try:
                children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            except PermissionError:
                return []
            # Filter
            visible = []
            for child in children:
                if child.name.startswith(".") and child.name not in (".env",):
                    continue
                if child.name in _SKIP:
                    continue
                if py_only and child.is_file() and not child.name.endswith(".py"):
                    continue
                visible.append(child)

            for idx, child in enumerate(visible):
                is_last = idx == len(visible) - 1
                connector = "└── " if is_last else "├── "
                extension = "    " if is_last else "│   "
                if child.is_dir():
                    lines.append(f"{prefix}{connector}**{child.name}/**")
                    lines.extend(_render(child, prefix + extension, current_depth + 1))
                else:
                    lines.append(f"{prefix}{connector}{child.name}")
            return lines

        header = f"**{root.resolve().name}/**"
        body = _render(root, "", 1)

        if not body:
            return f"{header}\n\n*(пусто)*"

        # Count files and dirs
        total_files = sum(1 for l in body if not l.rstrip().endswith("**"))
        total_dirs = sum(1 for l in body if l.rstrip().endswith("**") or l.rstrip().endswith("*/"))

        lines = [f"## Дерево: `{root_str}`", "", header]
        lines.extend(body)
        lines.append("")
        lines.append(f"*{total_dirs} директорий · {total_files} файлов · глубина {depth}*")
        if depth < 10:
            lines.append(f"*`/tree {root_str} --depth {depth + 2}` — показать глубже*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "tree",
        "Дерево директорий: /tree [путь] [--depth N] [--py]",
        tree_handler,
    ))

    # ── Task 201: /word ────────────────────────────────────────────────────

    async def word_handler(arg: str = "", **_: Any) -> str:
        """/word <file or text> [--top N] — частотный анализ слов."""
        import re as _re
        from pathlib import Path as _Path
        from collections import Counter

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/word <файл или текст> [--top N]`\n\n"
                "Анализирует частоту слов в файле или тексте.\n\n"
                "**Примеры:**\n"
                "  `/word src/lidco/core/session.py`\n"
                "  `/word The quick brown fox --top 5`"
            )

        # Parse --top flag
        top_n = 20
        top_match = _re.search(r"--top\s+(\d+)", text)
        if top_match:
            top_n = max(1, min(100, int(top_match.group(1))))
            text = text[:top_match.start()].strip() + text[top_match.end():].strip()
            text = text.strip()

        # Try as file path
        source_label = text
        p = _Path(text)
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                source_label = str(p)
            except OSError as exc:
                return f"Не удалось прочитать `{text}`: {exc}"
        else:
            content = text

        # Tokenize: extract words (ignore punctuation, numbers)
        words = _re.findall(r"\b[a-zA-Zа-яА-ЯёЁ]{3,}\b", content.lower())

        # Common stop words to exclude
        _STOP = frozenset({
            "and", "the", "for", "that", "this", "with", "from", "are", "was",
            "not", "but", "have", "its", "you", "your", "they", "their",
            "def", "self", "return", "import", "class", "pass", "none",
            "true", "false", "elif", "else", "while", "async", "await",
            "что", "как", "это", "для", "или", "при", "если", "то",
            "не", "да", "нет", "его", "она", "они", "все", "был",
        })
        words = [w for w in words if w not in _STOP]

        if not words:
            return f"В `{source_label}` не найдено слов для анализа."

        counter = Counter(words)
        total = len(words)
        unique = len(counter)
        top = counter.most_common(top_n)

        lines = [f"## Частотный анализ: `{source_label}`", ""]
        lines.append(f"**Слов:** {total} · **Уникальных:** {unique}")
        lines.append("")
        lines.append(f"**Топ {min(top_n, len(top))} слов:**")

        max_count = top[0][1] if top else 1
        for word, count in top:
            pct = int(count / total * 100)
            bar_len = min(15, int(count / max_count * 15))
            bar = "█" * bar_len + "░" * (15 - bar_len)
            lines.append(f"  `{word:<20}` {count:4}×  ({pct}%)  [{bar}]")

        lines.append("")
        lines.append(f"*`/word {source_label} --top 50` — показать больше слов*")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "word",
        "Частотный анализ слов в файле: /word <файл> [--top N]",
        word_handler,
    ))

    # ── Task 202: /deps ────────────────────────────────────────────────────

    async def deps_handler(arg: str = "", **_: Any) -> str:
        """/deps <file.py> — граф зависимостей Python файла (импорты)."""
        import re as _re
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/deps <файл.py>`\n\n"
                "Показывает импорты файла и их типы.\n\n"
                "**Примеры:**\n"
                "  `/deps src/lidco/core/session.py`\n"
                "  `/deps src/lidco/cli/app.py`"
            )

        p = _Path(text)
        if not p.exists():
            return f"Файл не найден: `{text}`"
        if not p.is_file():
            return f"Это не файл: `{text}`"
        if not text.endswith(".py") and not p.suffix == ".py":
            return f"Ожидается Python файл (.py): `{text}`"

        try:
            source = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Не удалось прочитать: {exc}"

        # Parse imports
        _IMPORT_RE = _re.compile(
            r"^(?:from\s+([\w.]+)\s+import\s+([\w*,\s]+)|import\s+([\w.,\s]+))",
            _re.MULTILINE,
        )

        stdlib_modules: set[str] = set()
        third_party: set[str] = set()
        local_imports: set[str] = set()

        # Known stdlib top-level names (subset)
        _STDLIB = frozenset({
            "os", "sys", "re", "io", "abc", "ast", "time", "math", "json",
            "enum", "uuid", "copy", "glob", "shutil", "string", "struct",
            "typing", "types", "functools", "itertools", "collections",
            "dataclasses", "contextlib", "threading", "asyncio", "concurrent",
            "subprocess", "pathlib", "datetime", "calendar", "hashlib",
            "base64", "urllib", "http", "email", "csv", "sqlite3",
            "logging", "warnings", "traceback", "inspect", "importlib",
            "platform", "socket", "ssl", "signal", "weakref", "gc",
            "unittest", "textwrap", "difflib", "pprint", "pickle",
            "__future__",
        })

        # Try to get actual project root
        project_root = "."
        if registry._session:
            pd = getattr(registry._session, "project_dir", None)
            if pd:
                project_root = str(pd)
        project_root_path = _Path(project_root)

        for m in _IMPORT_RE.finditer(source):
            if m.group(1):  # from X import Y
                module = m.group(1)
            else:  # import X, Y
                module = (m.group(3) or "").split(",")[0].strip().split(".")[0]

            if not module:
                continue

            top_level = module.split(".")[0]

            # Check if it's a local module
            possible_local = (
                project_root_path / module.replace(".", "/")
            ).with_suffix(".py")
            possible_local_pkg = project_root_path / module.replace(".", "/") / "__init__.py"

            if possible_local.exists() or possible_local_pkg.exists():
                local_imports.add(module)
            elif top_level in _STDLIB or top_level == "_":
                stdlib_modules.add(module)
            else:
                third_party.add(module)

        lines = [f"## Зависимости: `{text}`", ""]

        if local_imports:
            lines.append("**Локальные модули:**")
            for imp in sorted(local_imports):
                lines.append(f"  · `{imp}`")
            lines.append("")

        if third_party:
            lines.append("**Сторонние пакеты:**")
            for imp in sorted(third_party):
                lines.append(f"  · `{imp}`")
            lines.append("")

        if stdlib_modules:
            lines.append("**Стандартная библиотека:**")
            for imp in sorted(stdlib_modules):
                lines.append(f"  · `{imp}`")
            lines.append("")

        total = len(local_imports) + len(third_party) + len(stdlib_modules)
        if total == 0:
            return f"`{text}` — нет импортов."

        lines.append(
            f"*{total} импортов: {len(local_imports)} локальных · "
            f"{len(third_party)} сторонних · {len(stdlib_modules)} stdlib*"
        )
        return "\n".join(lines)

    registry.register(SlashCommand(
        "deps",
        "Граф зависимостей Python файла: /deps <файл.py>",
        deps_handler,
    ))

    # ── Task 203: /hash ───────────────────────────────────────────────────

    async def hash_handler(arg: str = "", **_) -> str:
        import hashlib

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/hash <текст или файл> [--algo <алгоритм>]`\n\n"
                "Алгоритмы: `md5`, `sha1`, `sha256` (по умолчанию), `sha512`, `sha3_256`"
            )

        algo = "sha256"
        if "--algo" in text:
            parts = text.split("--algo")
            text = parts[0].strip()
            algo = parts[1].strip().split()[0].lower()

        supported = {"md5", "sha1", "sha256", "sha512", "sha3_256"}
        if algo not in supported:
            return (
                f"Неизвестный алгоритм `{algo}`. "
                f"Доступные: {', '.join(sorted(supported))}"
            )

        from pathlib import Path as _Path

        source_label = text
        try:
            p = _Path(text)
            if p.exists() and p.is_file():
                data = p.read_bytes()
                source_label = p.name
            else:
                data = text.encode()
        except Exception:
            data = text.encode()

        h = hashlib.new(algo, data)
        digest = h.hexdigest()

        lines = [f"**Хеш файла/текста:** `{source_label}`", ""]
        lines.append(f"**Алгоритм:** `{algo}`")
        lines.append(f"**Длина дайджеста:** {len(digest)} символов ({len(digest)*4} бит)")
        lines.append("")
        lines.append(f"```\n{digest}\n```")

        # Also show all algos for text input (unless it was a file path with spaces risk)
        if len(data) < 10_000 and source_label == text:
            lines.append("\n**Все алгоритмы:**")
            for a in sorted(supported):
                lines.append(f"  `{a}`: `{hashlib.new(a, data).hexdigest()}`")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "hash",
        "Хеш строки или файла: /hash <текст|файл> [--algo sha256]",
        hash_handler,
    ))

    # ── Task 204: /base64 ─────────────────────────────────────────────────

    async def base64_handler(arg: str = "", **_) -> str:
        import base64 as _b64

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/base64 <текст> [--decode] [--file <путь>]`\n\n"
                "По умолчанию кодирует текст в Base64. "
                "С флагом `--decode` — декодирует."
            )

        decode_mode = "--decode" in text
        if decode_mode:
            text = text.replace("--decode", "").strip()

        from pathlib import Path as _Path

        source_label = text[:40] + ("…" if len(text) > 40 else "")

        # Check if it's a file path
        try:
            p = _Path(text)
            if p.exists() and p.is_file():
                raw = p.read_bytes()
                source_label = p.name
                if decode_mode:
                    return (
                        "Декодирование бинарного файла не поддерживается. "
                        "Передайте Base64-строку напрямую."
                    )
            else:
                raw = text.encode("utf-8")
        except Exception:
            raw = text.encode("utf-8")

        try:
            if decode_mode:
                # Validate input
                stripped = text.strip().replace("\n", "").replace(" ", "")
                decoded = _b64.b64decode(stripped, validate=True)
                try:
                    result_text = decoded.decode("utf-8")
                    lines = [
                        f"**Base64 → текст** (`{source_label}`)", "",
                        "```",
                        result_text,
                        "```",
                        "",
                        f"*{len(decoded)} байт → {len(result_text)} символов*",
                    ]
                except UnicodeDecodeError:
                    lines = [
                        f"**Base64 → бинарные данные** (`{source_label}`)", "",
                        f"*{len(decoded)} байт (не UTF-8, бинарный контент)*",
                        "",
                        f"Hex-preview: `{decoded[:32].hex()}`{'…' if len(decoded) > 32 else ''}",
                    ]
                return "\n".join(lines)
            else:
                encoded = _b64.b64encode(raw).decode("ascii")
                # Break into 76-char lines for readability
                chunks = [encoded[i:i+76] for i in range(0, len(encoded), 76)]
                lines = [
                    f"**Текст → Base64** (`{source_label}`)", "",
                    "```",
                    "\n".join(chunks),
                    "```",
                    "",
                    f"*{len(raw)} байт → {len(encoded)} символов Base64*",
                ]
                return "\n".join(lines)
        except Exception as exc:
            return f"Ошибка: {exc}"

    registry.register(SlashCommand(
        "base64",
        "Кодирование/декодирование Base64: /base64 <текст> [--decode]",
        base64_handler,
    ))

    # ── Task 205: /json ───────────────────────────────────────────────────

    async def json_handler(arg: str = "", **_) -> str:
        import json as _json
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/json <текст или файл> [--compact] [--keys] [--validate]`\n\n"
                "Форматирует JSON с отступами, показывает структуру. "
                "Флаги: `--compact` (минификация), `--keys` (список ключей), "
                "`--validate` (только проверка)."
            )

        compact = "--compact" in text
        show_keys = "--keys" in text
        validate_only = "--validate" in text

        for flag in ("--compact", "--keys", "--validate"):
            text = text.replace(flag, "").strip()

        source_label = text[:40] + ("…" if len(text) > 40 else "")

        # Try as file path first
        try:
            p = _Path(text)
            if p.exists() and p.is_file():
                raw = p.read_text(encoding="utf-8")
                source_label = p.name
            else:
                raw = text
        except Exception:
            raw = text

        try:
            parsed = _json.loads(raw)
        except _json.JSONDecodeError as exc:
            return (
                f"**Ошибка JSON** (`{source_label}`)\n\n"
                f"`{exc}`\n\n"
                f"*Строка {exc.lineno}, позиция {exc.colno}*"
            )

        if validate_only:
            kind = type(parsed).__name__
            size = len(raw.encode())
            return (
                f"**JSON валиден** ✓ (`{source_label}`)\n\n"
                f"Тип: `{kind}` · Размер: {size} байт"
            )

        if compact:
            result = _json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
            lines = [
                f"**JSON (компакт)** (`{source_label}`)", "",
                "```json",
                result[:4000] + ("…" if len(result) > 4000 else ""),
                "```",
                "",
                f"*{len(result)} символов*",
            ]
            return "\n".join(lines)

        formatted = _json.dumps(parsed, indent=2, ensure_ascii=False)

        if show_keys and isinstance(parsed, dict):
            keys = list(parsed.keys())
            lines = [
                f"**Ключи JSON** (`{source_label}`)", "",
                f"*{len(keys)} ключей верхнего уровня:*", "",
            ]
            for k in keys:
                v = parsed[k]
                vtype = type(v).__name__
                if isinstance(v, dict):
                    vtype = f"dict ({len(v)} ключей)"
                elif isinstance(v, list):
                    vtype = f"list ({len(v)} элементов)"
                lines.append(f"  · `{k}` — *{vtype}*")
            return "\n".join(lines)

        # Default: pretty-print with truncation
        max_lines = 100
        formatted_lines = formatted.splitlines()
        truncated = len(formatted_lines) > max_lines
        display = "\n".join(formatted_lines[:max_lines])

        lines = [
            f"**JSON** (`{source_label}`)", "",
            "```json",
            display,
            "```",
        ]
        if truncated:
            hidden = len(formatted_lines) - max_lines
            lines.append(f"\n*…скрыто {hidden} строк. Используйте `--compact` для минификации.*")

        # Stats
        depth = _json_depth(parsed)
        total_keys = _json_key_count(parsed)
        lines.append(f"\n*Глубина: {depth} · Ключей: {total_keys}*")

        return "\n".join(lines)

    def _json_depth(obj, d=0) -> int:
        if isinstance(obj, dict):
            return max((_json_depth(v, d + 1) for v in obj.values()), default=d + 1)
        if isinstance(obj, list):
            return max((_json_depth(v, d + 1) for v in obj), default=d + 1)
        return d

    def _json_key_count(obj) -> int:
        if isinstance(obj, dict):
            return len(obj) + sum(_json_key_count(v) for v in obj.values())
        if isinstance(obj, list):
            return sum(_json_key_count(v) for v in obj)
        return 0

    registry.register(SlashCommand(
        "json",
        "Форматирование и валидация JSON: /json <текст|файл> [--compact|--keys|--validate]",
        json_handler,
    ))

    # ── Task 206: /url ────────────────────────────────────────────────────

    async def url_handler(arg: str = "", **_) -> str:
        from urllib.parse import (
            urlparse, urlencode, parse_qs, quote, unquote, urlunparse,
        )

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/url <url> [--decode] [--encode] [--parse]`\n\n"
                "По умолчанию парсит URL. "
                "`--encode` — percent-encode строку, "
                "`--decode` — декодирует percent-encoded строку, "
                "`--parse` — разбивает URL на компоненты."
            )

        encode_mode = "--encode" in text
        decode_mode = "--decode" in text
        parse_mode = "--parse" in text

        for flag in ("--encode", "--decode", "--parse"):
            text = text.replace(flag, "").strip()

        if decode_mode:
            decoded = unquote(text)
            return (
                f"**URL-декодирование**\n\n"
                f"Вход: `{text}`\n"
                f"Результат: `{decoded}`"
            )

        if encode_mode:
            encoded = quote(text, safe="")
            return (
                f"**URL-кодирование**\n\n"
                f"Вход: `{text}`\n"
                f"Результат: `{encoded}`"
            )

        # Default: parse URL
        try:
            parsed = urlparse(text)
        except Exception as exc:
            return f"Ошибка разбора URL: {exc}"

        lines = [f"**Разбор URL:** `{text}`", ""]

        if parsed.scheme:
            lines.append(f"**Схема:** `{parsed.scheme}`")
        if parsed.netloc:
            lines.append(f"**Хост:** `{parsed.netloc}`")
        if parsed.path:
            lines.append(f"**Путь:** `{parsed.path}`")
        if parsed.query:
            lines.append(f"**Query-строка:** `{parsed.query}`")
            qs = parse_qs(parsed.query)
            for k, vs in qs.items():
                lines.append(f"  · `{k}` = `{', '.join(vs)}`")
        if parsed.fragment:
            lines.append(f"**Фрагмент:** `#{parsed.fragment}`")
        if parsed.username:
            lines.append(f"**Пользователь:** `{parsed.username}`")
        if parsed.port:
            lines.append(f"**Порт:** `{parsed.port}`")

        if not any([parsed.scheme, parsed.netloc, parsed.path]):
            return f"Не удалось разобрать URL: `{text}`"

        return "\n".join(lines)

    registry.register(SlashCommand(
        "url",
        "Парсинг и кодирование URL: /url <url> [--encode|--decode|--parse]",
        url_handler,
    ))

    # ── Task 207: /uuid ───────────────────────────────────────────────────

    async def uuid_handler(arg: str = "", **_) -> str:
        import uuid as _uuid

        text = arg.strip()

        # Subcommands: validate, info, or generate
        if text.startswith("validate ") or text.startswith("check "):
            raw = text.split(None, 1)[1].strip()
            try:
                u = _uuid.UUID(raw)
                ver = u.version if u.variant == _uuid.RFC_4122 else None
                lines = [
                    f"**UUID валиден** ✓",
                    "",
                    f"**Версия:** {ver if ver else 'не RFC 4122'}",
                    f"**Вариант:** `{u.variant}`",
                    f"**Hex:** `{u.hex}`",
                    f"**Int:** `{u.int}`",
                ]
                if ver == 1:
                    lines.append(f"**Время:** `{u.time}`")
                elif ver == 3 or ver == 5:
                    lines.append("*(хеш-based UUID)*")
                return "\n".join(lines)
            except ValueError:
                return f"Неверный UUID: `{raw}`"

        # Generate N UUIDs (default 1, max 20)
        count = 1
        version = 4
        if text:
            parts = text.split()
            for p in parts:
                if p.isdigit():
                    count = min(int(p), 20)
                elif p.startswith("v") and p[1:].isdigit():
                    version = int(p[1:])

        generators = {
            1: _uuid.uuid1,
            3: None,  # requires namespace+name
            4: _uuid.uuid4,
            5: None,
        }
        if version not in generators or generators[version] is None:
            version = 4

        gen = generators[version]
        uids = [str(gen()) for _ in range(count)]

        lines = [f"**UUID v{version}** ({count} шт.)", ""]
        lines.extend(f"  `{u}`" for u in uids)
        lines.append("")
        lines.append(f"*Используйте `/uuid validate <uuid>` для проверки*")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "uuid",
        "Генерация и проверка UUID: /uuid [N] [v4] | validate <uuid>",
        uuid_handler,
    ))

    # ── Task 208: /calc ───────────────────────────────────────────────────

    async def calc_handler(arg: str = "", **_) -> str:
        import math as _math
        import ast as _ast

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/calc <выражение>`\n\n"
                "Примеры: `2 + 2`, `sqrt(16)`, `2**10`, `sin(pi/2)`, `log(100, 10)`\n"
                "Поддерживаются: `+`, `-`, `*`, `/`, `**`, `%`, `//`, "
                "`sqrt`, `sin`, `cos`, `tan`, `log`, `abs`, `round`, `pi`, `e`"
            )

        # Safe evaluation: whitelist of allowed names
        _SAFE_NAMES = {
            "sqrt": _math.sqrt,
            "sin": _math.sin,
            "cos": _math.cos,
            "tan": _math.tan,
            "log": _math.log,
            "log2": _math.log2,
            "log10": _math.log10,
            "exp": _math.exp,
            "abs": abs,
            "round": round,
            "floor": _math.floor,
            "ceil": _math.ceil,
            "pow": pow,
            "pi": _math.pi,
            "e": _math.e,
            "inf": _math.inf,
            "tau": _math.tau,
        }

        # Validate AST — only allow safe node types
        _ALLOWED_NODES = (
            _ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Call,
            _ast.Constant, _ast.Name, _ast.Load,
            _ast.Add, _ast.Sub, _ast.Mult, _ast.Div, _ast.Pow,
            _ast.Mod, _ast.FloorDiv, _ast.USub, _ast.UAdd,
        )

        try:
            tree = _ast.parse(text, mode="eval")
        except SyntaxError:
            return f"Синтаксическая ошибка в выражении: `{text}`"

        for node in _ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES):
                return (
                    f"Недопустимая операция в выражении: `{type(node).__name__}`\n"
                    "Разрешены только математические операции."
                )
            if isinstance(node, _ast.Name) and node.id not in _SAFE_NAMES:
                return f"Неизвестная переменная или функция: `{node.id}`"
            if isinstance(node, _ast.Call):
                if not isinstance(node.func, _ast.Name):
                    return "Вызов функции через атрибут не поддерживается."

        try:
            result = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, _SAFE_NAMES)
        except ZeroDivisionError:
            return "Ошибка: деление на ноль."
        except OverflowError:
            return "Ошибка: результат слишком большой."
        except Exception as exc:
            return f"Ошибка вычисления: {exc}"

        # Format result
        if isinstance(result, float):
            if result == int(result) and abs(result) < 1e15:
                formatted = str(int(result))
            else:
                formatted = f"{result:.10g}"
        else:
            formatted = str(result)

        lines = [
            f"**Калькулятор**",
            "",
            f"  `{text}` = **{formatted}**",
        ]

        # Show additional info for notable results
        if isinstance(result, (int, float)) and not _math.isinf(result) and not _math.isnan(result):
            if isinstance(result, float) and result != int(result):
                lines.append(f"\n*Точное значение: {result!r}*")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "calc",
        "Математический калькулятор: /calc <выражение>",
        calc_handler,
    ))

    # ── Task 209: /note ───────────────────────────────────────────────────
    # Persistent cross-session notes stored in .lidco/notes.json

    async def note_handler(arg: str = "", **_) -> str:
        import json as _json
        from pathlib import Path as _Path
        import time as _time

        notes_path = _Path(".lidco") / "notes.json"

        def _load() -> list:
            if notes_path.exists():
                try:
                    return _json.loads(notes_path.read_text(encoding="utf-8"))
                except Exception:
                    return []
            return []

        def _save(notes: list) -> None:
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            notes_path.write_text(_json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

        text = arg.strip()

        # list (default with no arg)
        if not text or text in ("list", "ls"):
            notes = _load()
            if not notes:
                return "Заметок нет. Добавьте: `/note <текст>`"
            lines = [f"**Заметки** ({len(notes)} шт.)", ""]
            for i, n in enumerate(notes, 1):
                ts = n.get("ts", "")
                tag = f" `[{n['tag']}]`" if n.get("tag") else ""
                lines.append(f"**{i}.** {n['text']}{tag}  *{ts}*")
            return "\n".join(lines)

        # del N
        if text.startswith("del ") or text.startswith("delete ") or text.startswith("rm "):
            parts = text.split(None, 1)
            idx_str = parts[1].strip() if len(parts) > 1 else ""
            if not idx_str.isdigit():
                return "Укажите номер заметки: `/note del <N>`"
            notes = _load()
            idx = int(idx_str) - 1
            if idx < 0 or idx >= len(notes):
                return f"Заметка #{idx_str} не найдена (всего {len(notes)})."
            removed = notes.pop(idx)
            _save(notes)
            return f"Удалена заметка #{idx_str}: *{removed['text'][:60]}*"

        # clear
        if text == "clear":
            notes = _load()
            count = len(notes)
            _save([])
            return f"Удалено {count} заметок."

        # search <query>
        if text.startswith("search ") or text.startswith("find "):
            query = text.split(None, 1)[1].strip().lower()
            notes = _load()
            matches = [
                (i + 1, n) for i, n in enumerate(notes)
                if query in n["text"].lower() or query in n.get("tag", "").lower()
            ]
            if not matches:
                return f"Заметок по запросу «{query}» не найдено."
            lines = [f"**Найдено заметок:** {len(matches)}", ""]
            for num, n in matches:
                tag = f" `[{n['tag']}]`" if n.get("tag") else ""
                lines.append(f"**{num}.** {n['text']}{tag}")
            return "\n".join(lines)

        # tag: "add #bug fix auth" → tag=bug, text=fix auth
        tag = ""
        if text.startswith("#"):
            parts = text.split(None, 1)
            tag = parts[0][1:]
            text = parts[1].strip() if len(parts) > 1 else ""
            if not text:
                return "Укажите текст заметки после тега: `/note #tag текст`"

        # add <text> (default)
        notes = _load()
        from datetime import datetime as _dt
        ts = _dt.now().strftime("%Y-%m-%d %H:%M")
        notes.append({"text": text, "tag": tag, "ts": ts})
        _save(notes)
        tag_str = f" `[{tag}]`" if tag else ""
        return f"✓ Заметка #{len(notes)} сохранена{tag_str}: *{text[:80]}*"

    registry.register(SlashCommand(
        "notes",
        "Постоянные заметки: /notes <текст> | list | del N | search | clear",
        note_handler,
    ))

    # ── Task 210: /git ────────────────────────────────────────────────────
    # Git workflow: log, status, branch, blame

    async def git_handler(arg: str = "", **_) -> str:
        import asyncio as _asyncio
        from pathlib import Path as _Path

        text = arg.strip()

        async def _git(*args, cwd=None, timeout=10) -> tuple[int, str]:
            try:
                proc = await _asyncio.create_subprocess_exec(
                    "git", *args,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                    cwd=cwd,
                )
                out, _ = await _asyncio.wait_for(proc.communicate(), timeout=timeout)
                return proc.returncode or 0, out.decode("utf-8", errors="replace").strip()
            except FileNotFoundError:
                return 1, "git не найден в PATH."
            except _asyncio.TimeoutError:
                return 1, "Timeout."
            except Exception as exc:
                return 1, str(exc)

        if not text or text == "status":
            rc, out = await _git("status", "--short", "--branch")
            if rc != 0:
                return f"git status ошибка: {out}"
            lines = ["**git status**", ""]
            for line in out.splitlines():
                if line.startswith("##"):
                    branch_info = line[3:].strip()
                    lines.append(f"**Ветка:** `{branch_info}`")
                elif line.strip():
                    status_code = line[:2]
                    fname = line[3:]
                    icon = "📝" if "M" in status_code else ("➕" if "A" in status_code else ("🗑" if "D" in status_code else "❓"))
                    lines.append(f"  {icon} `{fname}` *({status_code.strip()})*")
            if len(lines) <= 2:
                lines.append("*Чисто — нет незафиксированных изменений*")
            return "\n".join(lines)

        if text.startswith("log"):
            parts = text.split()
            n = 10
            for p in parts[1:]:
                if p.isdigit():
                    n = min(int(p), 50)
            rc, out = await _git("log", f"--oneline", f"-{n}", "--no-color")
            if rc != 0:
                return f"git log ошибка: {out}"
            if not out:
                return "История коммитов пуста."
            lines = [f"**git log** (последние {n})", ""]
            for line in out.splitlines():
                sha, _, msg = line.partition(" ")
                lines.append(f"  `{sha}` {msg}")
            return "\n".join(lines)

        if text.startswith("branch"):
            rc, out = await _git("branch", "-v", "--no-color")
            if rc != 0:
                return f"git branch ошибка: {out}"
            lines = ["**git branch**", ""]
            for line in out.splitlines():
                current = line.startswith("*")
                marker = "→ " if current else "  "
                lines.append(f"{marker}`{line.strip()}`")
            return "\n".join(lines)

        if text.startswith("blame"):
            parts = text.split(None, 1)
            if len(parts) < 2:
                return "Укажите файл: `/git blame <файл> [строки N-M]`"
            rest = parts[1].strip()
            # optional line range: "file.py 10-20"
            toks = rest.rsplit(None, 1)
            file_path = rest
            line_range_args = []
            if len(toks) == 2 and "-" in toks[1] and toks[1].replace("-", "").isdigit():
                file_path = toks[0]
                start, end = toks[1].split("-")
                line_range_args = [f"-L{start},{end}"]
            rc, out = await _git("blame", "--date=short", "--no-color", *line_range_args, file_path)
            if rc != 0:
                return f"git blame ошибка: {out}"
            lines_out = out.splitlines()[:40]
            if len(out.splitlines()) > 40:
                lines_out.append(f"*…скрыто {len(out.splitlines()) - 40} строк*")
            return f"**git blame** `{file_path}`\n\n```\n" + "\n".join(lines_out) + "\n```"

        if text.startswith("diff"):
            parts = text.split(None, 1)
            extra = parts[1].strip() if len(parts) > 1 else "HEAD"
            rc, out = await _git("diff", "--no-color", "--stat", extra)
            if rc != 0:
                return f"git diff ошибка: {out}"
            if not out:
                return f"Нет изменений (`git diff {extra}`)."
            lines = [f"**git diff** `{extra}`", "", "```", out[:3000], "```"]
            return "\n".join(lines)

        if text.startswith("show"):
            parts = text.split(None, 1)
            ref = parts[1].strip() if len(parts) > 1 else "HEAD"
            rc, out = await _git("show", "--stat", "--no-color", ref)
            if rc != 0:
                return f"git show ошибка: {out}"
            lines_out = out.splitlines()[:60]
            return f"**git show** `{ref}`\n\n```\n" + "\n".join(lines_out) + "\n```"

        return (
            "**Использование:** `/git <подкоманда>`\n\n"
            "Подкоманды: `status`, `log [N]`, `branch`, `blame <файл> [N-M]`, "
            "`diff [ref]`, `show [ref]`"
        )

    registry.register(SlashCommand(
        "git",
        "Git workflow: /git status|log|branch|blame|diff|show",
        git_handler,
    ))

    # ── Task 211: /ctx ────────────────────────────────────────────────────
    # Context window usage meter

    async def ctx_handler(arg: str = "", **_) -> str:
        text = arg.strip()

        # Estimate from session history if available
        history: list = []
        model_name = "unknown"
        if registry._session:
            try:
                orch = getattr(registry._session, "_orchestrator", None)
                if orch:
                    history = getattr(orch, "_messages", []) or []
                model_name = registry._session.config.llm.default_model
            except Exception:
                pass

        # Rough token estimate: 1 token ≈ 4 chars
        total_chars = sum(len(str(m.get("content", ""))) for m in history)
        estimated_tokens = total_chars // 4

        # Context window sizes by model family
        _CONTEXT_SIZES = {
            "claude-opus-4": 200_000,
            "claude-sonnet-4": 200_000,
            "claude-haiku-4": 200_000,
            "claude-3-5": 200_000,
            "gpt-4o": 128_000,
            "gpt-4-turbo": 128_000,
            "gpt-4": 8_192,
            "gpt-3.5": 16_385,
            "gemini-1.5": 1_000_000,
            "gemini-2": 1_000_000,
        }
        ctx_limit = 200_000  # default Claude
        for key, size in _CONTEXT_SIZES.items():
            if key in model_name:
                ctx_limit = size
                break

        used_pct = min(100, (estimated_tokens / ctx_limit) * 100) if ctx_limit else 0
        remaining = max(0, ctx_limit - estimated_tokens)
        remaining_pct = 100 - used_pct

        # Bar chart
        bar_width = 30
        filled = int(bar_width * used_pct / 100)
        if used_pct < 60:
            bar_char = "█"
        elif used_pct < 80:
            bar_char = "▓"
        else:
            bar_char = "▒"
        bar = bar_char * filled + "░" * (bar_width - filled)

        msg_count = len(history)

        lines = [
            "**Контекстное окно**",
            "",
            f"Модель: `{model_name}`",
            f"Лимит: `{ctx_limit:,}` токенов",
            "",
            f"Использовано: `~{estimated_tokens:,}` токенов ({used_pct:.1f}%)",
            f"Осталось:     `~{remaining:,}` токенов ({remaining_pct:.1f}%)",
            f"Сообщений:    `{msg_count}`",
            "",
            f"[{bar}] {used_pct:.0f}%",
        ]

        # Warnings
        if used_pct >= 85:
            lines.append(
                "\n⚠️  **Контекст почти заполнен.** "
                "Рассмотрите `/export` + новую сессию или сжатие истории."
            )
        elif used_pct >= 70:
            lines.append(
                "\n⚡ Использовано >70%. "
                "Скоро может потребоваться сжатие контекста."
            )
        else:
            lines.append(
                f"\n*Оценка приблизительная (~4 символа/токен). "
                f"Осталось ~{remaining // 1000}K токенов.*"
            )

        return "\n".join(lines)

    registry.register(SlashCommand(
        "ctx",
        "Состояние контекстного окна и бюджет токенов",
        ctx_handler,
    ))

    # ── Task 212: /regex ──────────────────────────────────────────────────

    async def regex_handler(arg: str = "", **_) -> str:
        import re as _re

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/regex <паттерн> <текст>`\n\n"
                "Флаги (добавьте после паттерна):\n"
                "  `--i` — игнорировать регистр\n"
                "  `--m` — многострочный режим\n"
                "  `--s` — точка совпадает с `\\n`\n"
                "  `--all` — показать все совпадения\n\n"
                "**Примеры:**\n"
                "  `/regex \\d+ hello world 42`\n"
                "  `/regex ^def\\s+\\w+ --i --m def Foo(): pass`"
            )

        # Parse flags
        flags = 0
        show_all = False
        for flag in ("--i", "--m", "--s", "--all"):
            if flag in text:
                text = text.replace(flag, "").strip()
                if flag == "--i":
                    flags |= _re.IGNORECASE
                elif flag == "--m":
                    flags |= _re.MULTILINE
                elif flag == "--s":
                    flags |= _re.DOTALL
                elif flag == "--all":
                    show_all = True

        # Split pattern from test string: first token is pattern, rest is text
        parts = text.split(None, 1)
        if len(parts) < 2:
            return (
                "Укажите паттерн и тест-строку: `/regex <паттерн> <текст>`\n\n"
                f"Получен только: `{text}`"
            )

        pattern, test_str = parts[0], parts[1]

        # Try to compile
        try:
            compiled = _re.compile(pattern, flags)
        except _re.error as exc:
            return (
                f"**Ошибка паттерна:** `{pattern}`\n\n"
                f"`{exc}`"
            )

        lines = [f"**Regex:** `{pattern}`", f"**Текст:** `{test_str[:120]}`", ""]

        if show_all:
            matches = list(compiled.finditer(test_str))
            if not matches:
                lines.append("❌ Совпадений не найдено.")
            else:
                lines.append(f"✅ **Найдено совпадений: {len(matches)}**")
                lines.append("")
                for i, m in enumerate(matches[:20], 1):
                    lines.append(f"**#{i}** `{m.group()}` (позиция {m.start()}–{m.end()})")
                    if m.groups():
                        for j, g in enumerate(m.groups(), 1):
                            lines.append(f"  Группа {j}: `{g}`")
                if len(matches) > 20:
                    lines.append(f"\n*…ещё {len(matches) - 20} совпадений*")
        else:
            m = compiled.search(test_str)
            if not m:
                lines.append("❌ Совпадений нет.")
                # Suggest partial match
                for length in range(len(pattern), 0, -1):
                    try:
                        partial = _re.compile(pattern[:length], flags)
                        pm = partial.search(test_str)
                        if pm:
                            lines.append(f"\n*Частичное совпадение для `{pattern[:length]}`: `{pm.group()}`*")
                            break
                    except Exception:
                        break
            else:
                lines.append(f"✅ **Совпадение найдено:** `{m.group()}`")
                lines.append(f"Позиция: {m.start()}–{m.end()}")
                if m.groups():
                    lines.append("\n**Группы:**")
                    for i, g in enumerate(m.groups(), 1):
                        lines.append(f"  Группа {i}: `{g}`")
                if m.groupdict():
                    lines.append("\n**Именованные группы:**")
                    for name, val in m.groupdict().items():
                        lines.append(f"  `{name}`: `{val}`")

                # Highlight match in context
                start, end = m.start(), m.end()
                ctx_start = max(0, start - 20)
                ctx_end = min(len(test_str), end + 20)
                prefix = ("…" if ctx_start > 0 else "") + test_str[ctx_start:start]
                matched = test_str[start:end]
                suffix = test_str[end:ctx_end] + ("…" if ctx_end < len(test_str) else "")
                lines.append(f"\nКонтекст: `{prefix}**[{matched}]**{suffix}`")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "regex",
        "Тестирование регулярных выражений: /regex <паттерн> <текст> [--i --m --s --all]",
        regex_handler,
    ))

    # ── Task 213: /stat ───────────────────────────────────────────────────

    async def stat_handler(arg: str = "", **_) -> str:
        import os as _os
        import stat as _stat
        from pathlib import Path as _Path
        from datetime import datetime as _dt
        import re as _re

        text = arg.strip()
        if not text:
            return "**Использование:** `/stat <файл или директория>`"

        p = _Path(text)
        if not p.exists():
            return f"Путь не найден: `{text}`"

        st = p.stat()
        size = st.st_size
        mtime = _dt.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        ctime = _dt.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")

        def _fmt_size(n: int) -> str:
            for unit in ("Б", "КБ", "МБ", "ГБ"):
                if n < 1024:
                    return f"{n:.1f} {unit}"
                n /= 1024
            return f"{n:.1f} ТБ"

        lines = [f"**Статистика:** `{p.name}`", ""]
        lines.append(f"**Путь:**      `{p.resolve()}`")
        lines.append(f"**Тип:**       {'директория' if p.is_dir() else 'файл'}")
        lines.append(f"**Размер:**    {_fmt_size(size)} ({size:,} байт)")
        lines.append(f"**Изменён:**   {mtime}")
        lines.append(f"**Создан:**    {ctime}")

        # Permissions
        mode = st.st_mode
        perms = _stat.filemode(mode)
        lines.append(f"**Права:**     `{perms}`")

        if p.is_file():
            # Line count and language detection
            try:
                raw = p.read_bytes()
                is_binary = b"\x00" in raw[:8192]
                if not is_binary:
                    content = raw.decode("utf-8", errors="replace")
                    line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
                    word_count = len(content.split())
                    char_count = len(content)
                    lines.append(f"**Строк:**     {line_count:,}")
                    lines.append(f"**Слов:**      {word_count:,}")
                    lines.append(f"**Символов:**  {char_count:,}")

                    # Encoding detection hint
                    suffix = p.suffix.lower()
                    lang_map = {
                        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
                        ".rs": "Rust", ".go": "Go", ".java": "Java",
                        ".cpp": "C++", ".c": "C", ".rb": "Ruby",
                        ".md": "Markdown", ".json": "JSON", ".yaml": "YAML",
                        ".toml": "TOML", ".sh": "Shell", ".sql": "SQL",
                    }
                    if suffix in lang_map:
                        lines.append(f"**Язык:**      {lang_map[suffix]}")
                else:
                    lines.append("**Тип данных:** бинарный файл")
            except Exception:
                pass

        elif p.is_dir():
            try:
                entries = list(p.iterdir())
                dirs = sum(1 for e in entries if e.is_dir())
                files = sum(1 for e in entries if e.is_file())
                lines.append(f"**Содержимое:** {files} файлов, {dirs} директорий")
                total_size = sum(e.stat().st_size for e in entries if e.is_file())
                lines.append(f"**Размер содержимого:** {_fmt_size(total_size)}")
            except PermissionError:
                lines.append("*Нет прав для чтения содержимого*")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "stat",
        "Статистика файла или директории: /stat <путь>",
        stat_handler,
    ))

    # ── Task 214: /diff3 ──────────────────────────────────────────────────
    # 3-way merge diff: base, ours, theirs

    async def diff3_handler(arg: str = "", **_) -> str:
        import difflib as _difflib
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/diff3 <база> <наш> <их>`\n\n"
                "Трёхсторонний diff: находит конфликты между двумя версиями "
                "относительно общей базы.\n\n"
                "**Пример:** `/diff3 original.py our_version.py their_version.py`"
            )

        parts = text.split()
        if len(parts) < 3:
            return (
                f"Нужно три файла, получено {len(parts)}.\n"
                "**Использование:** `/diff3 <база> <наш> <их>`"
            )

        base_path, ours_path, theirs_path = (
            _Path(parts[0]), _Path(parts[1]), _Path(parts[2])
        )

        for label, p in [("база", base_path), ("наш", ours_path), ("их", theirs_path)]:
            if not p.exists():
                return f"Файл `{label}` не найден: `{p}`"
            if not p.is_file():
                return f"`{p}` не является файлом."

        base_lines = base_path.read_text(encoding="utf-8", errors="replace").splitlines()
        ours_lines = ours_path.read_text(encoding="utf-8", errors="replace").splitlines()
        theirs_lines = theirs_path.read_text(encoding="utf-8", errors="replace").splitlines()

        # Run merge3 algorithm using difflib SequenceMatcher
        def _merge3(base, ours, theirs):
            """Simple 3-way merge returning (result_lines, conflicts)."""
            result = []
            conflicts = []

            sm_ours = _difflib.SequenceMatcher(None, base, ours)
            sm_theirs = _difflib.SequenceMatcher(None, base, theirs)

            ops_ours = {
                i: (tag, j1, j2)
                for tag, i1, i2, j1, j2 in sm_ours.get_opcodes()
                for i in range(i1, i2)
                if tag != "equal"
            }
            ops_theirs = {
                i: (tag, j1, j2)
                for tag, i1, i2, j1, j2 in sm_theirs.get_opcodes()
                for i in range(i1, i2)
                if tag != "equal"
            }

            i = 0
            while i < len(base):
                in_ours = i in ops_ours
                in_theirs = i in ops_theirs
                if not in_ours and not in_theirs:
                    result.append(("equal", base[i]))
                    i += 1
                elif in_ours and not in_theirs:
                    result.append(("ours", base[i]))
                    i += 1
                elif not in_ours and in_theirs:
                    result.append(("theirs", base[i]))
                    i += 1
                else:
                    # Both changed — conflict
                    conflicts.append(i)
                    result.append(("conflict", base[i]))
                    i += 1

            return result, conflicts

        _, conflict_indices = _merge3(base_lines, ours_lines, theirs_lines)

        # Show standard unified-style 3-way diff
        merger = _difflib.Differ()
        diff_ours = list(merger.compare(base_lines, ours_lines))
        diff_theirs = list(merger.compare(base_lines, theirs_lines))

        # Summary stats
        added_ours = sum(1 for l in diff_ours if l.startswith("+ "))
        removed_ours = sum(1 for l in diff_ours if l.startswith("- "))
        added_theirs = sum(1 for l in diff_theirs if l.startswith("+ "))
        removed_theirs = sum(1 for l in diff_theirs if l.startswith("- "))

        lines = [
            "**3-way diff**",
            "",
            f"**База:**  `{base_path.name}`",
            f"**Наш:**   `{ours_path.name}` (+{added_ours} −{removed_ours})",
            f"**Их:**    `{theirs_path.name}` (+{added_theirs} −{removed_theirs})",
            "",
        ]

        if conflict_indices:
            lines.append(f"⚠️  **Конфликты:** {len(conflict_indices)} строк")
        else:
            lines.append("✅ **Конфликтов нет**")

        lines.append("")

        # Show unified diff: ours vs theirs (practical view)
        unified = list(_difflib.unified_diff(
            ours_lines, theirs_lines,
            fromfile=f"наш/{ours_path.name}",
            tofile=f"их/{theirs_path.name}",
            lineterm="",
        ))

        if not unified:
            lines.append("*Наша и их версии идентичны.*")
        else:
            cap = unified[:100]
            lines.append("```diff")
            lines.extend(cap)
            lines.append("```")
            if len(unified) > 100:
                lines.append(f"\n*…скрыто {len(unified) - 100} строк diff*")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "diff3",
        "Трёхсторонний diff: /diff3 <база> <наш> <их>",
        diff3_handler,
    ))

    # ── Task 215: /cat ────────────────────────────────────────────────────

    async def cat_handler(arg: str = "", **_) -> str:
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/cat <файл> [N] [N-M] [--num]`\n\n"
                "Показывает содержимое файла.\n"
                "  `/cat file.py` — весь файл (до 200 строк)\n"
                "  `/cat file.py 10` — первые 10 строк\n"
                "  `/cat file.py 20-40` — строки 20–40\n"
                "  `/cat file.py --num` — с номерами строк"
            )

        show_nums = "--num" in text
        if show_nums:
            text = text.replace("--num", "").strip()

        # Parse optional line range/count at end
        tokens = text.rsplit(None, 1)
        line_from = 1
        line_to: int | None = None

        if len(tokens) == 2:
            spec = tokens[1]
            if "-" in spec and all(p.isdigit() for p in spec.split("-", 1)):
                parts = spec.split("-", 1)
                line_from = max(1, int(parts[0]))
                line_to = int(parts[1])
                text = tokens[0].strip()
            elif spec.isdigit():
                line_to = int(spec)
                text = tokens[0].strip()

        p = _Path(text)
        if not p.exists():
            return f"Файл не найден: `{text}`"
        if not p.is_file():
            return f"`{text}` — не файл. Для директорий используйте `/tree` или `/ls`."

        try:
            raw = p.read_bytes()
            if b"\x00" in raw[:8192]:
                size = len(raw)
                return f"`{p.name}` — бинарный файл ({size:,} байт). Используйте `/stat` для информации."
            content = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            return f"Ошибка чтения файла: {exc}"

        all_lines = content.splitlines()
        total = len(all_lines)

        # Apply range
        lo = line_from - 1          # 0-based
        hi = line_to if line_to else min(lo + 200, total)
        hi = min(hi, total)

        selected = all_lines[lo:hi]
        truncated = hi < total and line_to is None

        # Detect language for code block
        _LANG_MAP = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".rs": "rust", ".go": "go", ".java": "java", ".cpp": "cpp",
            ".c": "c", ".rb": "ruby", ".sh": "bash", ".md": "markdown",
            ".json": "json", ".yaml": "yaml", ".toml": "toml",
            ".sql": "sql", ".html": "html", ".css": "css",
        }
        lang = _LANG_MAP.get(p.suffix.lower(), "")

        # Format lines
        if show_nums:
            width = len(str(hi))
            body = "\n".join(
                f"{lo + i + 1:>{width}} │ {line}"
                for i, line in enumerate(selected)
            )
        else:
            body = "\n".join(selected)

        range_str = f"строки {line_from}–{hi}" if line_from > 1 or line_to else f"строки 1–{hi}"
        header = f"**`{p.name}`** ({range_str} из {total})"

        lines = [header, "", f"```{lang}", body, "```"]
        if truncated:
            lines.append(
                f"\n*…показано {hi} из {total} строк. "
                f"Используйте `/cat {p.name} {hi+1}-{min(hi+200, total)}` для продолжения.*"
            )
        return "\n".join(lines)

    registry.register(SlashCommand(
        "cat",
        "Просмотр файла: /cat <файл> [N] [N-M] [--num]",
        cat_handler,
    ))

    # ── Task 216: /find ───────────────────────────────────────────────────

    async def find_handler(arg: str = "", **_) -> str:
        import fnmatch as _fnmatch
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/find <паттерн> [путь] [--type f|d] [--ext .py]`\n\n"
                "Поиск файлов по имени.\n"
                "  `/find *.py` — все .py файлы\n"
                "  `/find test_* src/` — файлы test_* в src/\n"
                "  `/find config --type f` — только файлы\n"
                "  `/find --ext .json` — все JSON файлы"
            )

        # Parse flags
        only_files = False
        only_dirs = False
        ext_filter: str | None = None

        if "--type f" in text:
            only_files = True
            text = text.replace("--type f", "").strip()
        elif "--type d" in text:
            only_dirs = True
            text = text.replace("--type d", "").strip()

        if "--ext" in text:
            parts = text.split("--ext", 1)
            text = parts[0].strip()
            ext_filter = parts[1].strip().split()[0].lower()
            if not ext_filter.startswith("."):
                ext_filter = "." + ext_filter

        # Split pattern from optional search root
        tokens = text.split()
        pattern = tokens[0] if tokens else "*"
        root_str = tokens[1] if len(tokens) > 1 else "."

        root = _Path(root_str)
        if not root.exists():
            return f"Директория не найдена: `{root_str}`"

        # Skip noise dirs
        _SKIP = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache"}

        matches: list[_Path] = []

        def _walk(d: _Path, depth: int = 0) -> None:
            if depth > 10:
                return
            try:
                entries = sorted(d.iterdir(), key=lambda e: (e.is_file(), e.name))
            except PermissionError:
                return
            for entry in entries:
                if entry.name in _SKIP:
                    continue
                if only_files and not entry.is_file():
                    pass
                elif only_dirs and not entry.is_dir():
                    pass
                else:
                    name_match = _fnmatch.fnmatch(entry.name, pattern) or pattern in entry.name
                    ext_match = (ext_filter is None) or (entry.suffix.lower() == ext_filter)
                    if name_match and ext_match:
                        if (only_files and entry.is_file()) or \
                           (only_dirs and entry.is_dir()) or \
                           (not only_files and not only_dirs):
                            matches.append(entry)
                if entry.is_dir() and entry.name not in _SKIP:
                    _walk(entry, depth + 1)
                if len(matches) >= 200:
                    return

        _walk(root)

        if not matches:
            return (
                f"Файлов по паттерну `{pattern}` не найдено"
                + (f" в `{root_str}`" if root_str != "." else "") + "."
            )

        lines = [
            f"**Найдено:** {len(matches)} {'(первые 200)' if len(matches) >= 200 else ''}",
            f"**Паттерн:** `{pattern}`"
            + (f"  **Путь:** `{root_str}`" if root_str != "." else ""),
            "",
        ]

        # Group by directory
        by_dir: dict[str, list[_Path]] = {}
        for m in matches[:200]:
            parent = str(m.parent)
            by_dir.setdefault(parent, []).append(m)

        for parent, files in list(by_dir.items())[:30]:
            lines.append(f"**{parent}/**")
            for f in files[:20]:
                icon = "📁" if f.is_dir() else "📄"
                size_hint = ""
                if f.is_file():
                    try:
                        sz = f.stat().st_size
                        size_hint = f" *({sz:,} б)*" if sz < 10_000 else f" *({sz//1024} КБ)*"
                    except Exception:
                        pass
                lines.append(f"  {icon} `{f.name}`{size_hint}")
            if len(files) > 20:
                lines.append(f"  *…ещё {len(files) - 20}*")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "find",
        "Поиск файлов по имени: /find <паттерн> [путь] [--type f|d] [--ext .py]",
        find_handler,
    ))

    # ── Task 217: /review ─────────────────────────────────────────────────

    async def review_handler(arg: str = "", **_) -> str:
        from pathlib import Path as _Path

        text = arg.strip()

        if not registry._session:
            return "Сессия не инициализирована. Запустите LIDCO обычным образом."

        if not text:
            return (
                "**Использование:** `/review <файл> [--focus <тема>]`\n\n"
                "AI-ревью кода: баги, проблемы безопасности, качество, предложения.\n\n"
                "  `/review src/auth.py` — полное ревью\n"
                "  `/review utils.py --focus security` — фокус на безопасность\n"
                "  `/review api.py --focus performance` — фокус на производительность"
            )

        focus = ""
        if "--focus" in text:
            parts = text.split("--focus", 1)
            text = parts[0].strip()
            focus = parts[1].strip().split()[0]

        p = _Path(text)
        if not p.exists():
            return f"Файл не найден: `{text}`"
        if not p.is_file():
            return f"`{text}` — не файл."

        try:
            code = p.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return f"Ошибка чтения: {exc}"

        # Truncate large files
        MAX_CHARS = 8000
        truncated = len(code) > MAX_CHARS
        code_excerpt = code[:MAX_CHARS]
        if truncated:
            code_excerpt += f"\n\n# [обрезано — показано {MAX_CHARS} из {len(code)} символов]"

        focus_instruction = ""
        if focus:
            focus_map = {
                "security": "Уделите особое внимание уязвимостям безопасности.",
                "performance": "Уделите особое внимание производительности и узким местам.",
                "style": "Уделите особое внимание читаемости и стилю кода.",
                "tests": "Оцените тестируемость кода и покрытие крайних случаев.",
                "types": "Проверьте аннотации типов и возможные ошибки типизации.",
            }
            focus_instruction = focus_map.get(focus.lower(), f"Уделите особое внимание: {focus}.")

        prompt = (
            f"Проведи код-ревью следующего файла: `{p.name}`.\n\n"
            f"{focus_instruction}\n\n"
            "Структура ответа:\n"
            "1. **Критические проблемы** (баги, уязвимости) — если есть\n"
            "2. **Предупреждения** (потенциальные проблемы, антипаттерны)\n"
            "3. **Предложения** (улучшения кода, читаемость)\n"
            "4. **Итог** (1-2 предложения общей оценки)\n\n"
            f"```python\n{code_excerpt}\n```"
        )

        try:
            resp = await registry._session.llm.complete(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            review_text = resp.content
        except Exception as exc:
            return f"Ошибка LLM при ревью: {exc}"

        header = f"**Code Review: `{p.name}`**"
        if focus:
            header += f" *(фокус: {focus})*"
        if truncated:
            header += f"\n*Файл обрезан до {MAX_CHARS} символов*"

        return f"{header}\n\n{review_text}"

    registry.register(SlashCommand(
        "review",
        "AI-ревью кода: /review <файл> [--focus security|performance|style]",
        review_handler,
    ))

    # ── Task 218: /test-gen ───────────────────────────────────────────────

    async def test_gen_handler(arg: str = "", **_) -> str:
        from pathlib import Path as _Path

        text = arg.strip()

        if not registry._session:
            return "Сессия не инициализирована."

        if not text:
            return (
                "**Использование:** `/test-gen <файл> [--framework pytest|unittest]`\n\n"
                "AI-генерация тестов для Python файла.\n\n"
                "  `/test-gen src/utils.py` — генерация pytest-тестов\n"
                "  `/test-gen auth.py --framework unittest`"
            )

        framework = "pytest"
        if "--framework" in text:
            parts = text.split("--framework", 1)
            text = parts[0].strip()
            fw_tok = parts[1].strip().split()[0].lower()
            if fw_tok in ("pytest", "unittest"):
                framework = fw_tok

        p = _Path(text)
        if not p.exists():
            return f"Файл не найден: `{text}`"
        if not p.is_file():
            return f"`{text}` — не файл."
        if p.suffix.lower() != ".py":
            return f"Поддерживаются только Python-файлы (.py), получен `{p.suffix}`."

        try:
            code = p.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return f"Ошибка чтения: {exc}"

        MAX_CHARS = 6000
        truncated = len(code) > MAX_CHARS
        code_excerpt = code[:MAX_CHARS]
        if truncated:
            code_excerpt += f"\n# [обрезано до {MAX_CHARS} символов]"

        # Determine suggested test file path
        stem = p.stem
        test_filename = f"test_{stem}.py"
        test_dir = "tests/unit/"

        prompt = (
            f"Сгенерируй тесты ({framework}) для следующего Python файла: `{p.name}`.\n\n"
            "Требования:\n"
            f"- Используй фреймворк: {framework}\n"
            "- Покрой все публичные функции и методы классов\n"
            "- Добавь тесты для крайних случаев (пустой ввод, None, граничные значения)\n"
            "- Используй моки (unittest.mock) для внешних зависимостей\n"
            "- Каждый тест должен быть независимым\n"
            "- Добавь docstring к каждому тесту\n\n"
            f"Предложи сохранить в: `{test_dir}{test_filename}`\n\n"
            f"```python\n{code_excerpt}\n```\n\n"
            "Верни только код тестов, без дополнительных объяснений."
        )

        try:
            resp = await registry._session.llm.complete(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            tests_code = resp.content
        except Exception as exc:
            return f"Ошибка LLM: {exc}"

        header_lines = [
            f"**Тесты для `{p.name}`** (фреймворк: {framework})",
            f"*Рекомендуемый путь: `{test_dir}{test_filename}`*",
        ]
        if truncated:
            header_lines.append(f"*Файл обрезан до {MAX_CHARS} символов*")

        return "\n".join(header_lines) + "\n\n" + tests_code

    registry.register(SlashCommand(
        "test-gen",
        "AI-генерация тестов: /test-gen <файл.py> [--framework pytest|unittest]",
        test_gen_handler,
    ))

    # ── Task 219: /dead ───────────────────────────────────────────────────

    async def dead_handler(arg: str = "", **_) -> str:
        import ast as _ast
        from pathlib import Path as _Path

        text = arg.strip()
        if not text:
            return (
                "**Использование:** `/dead <файл.py> [--imports] [--functions] [--all]`\n\n"
                "Детектор мёртвого кода: неиспользуемые импорты, функции, переменные.\n\n"
                "  `/dead utils.py` — все категории\n"
                "  `/dead module.py --imports` — только импорты\n"
                "  `/dead app.py --functions` — только функции"
            )

        check_imports = "--imports" in text or "--all" in text or (
            "--imports" not in text and "--functions" not in text
        )
        check_functions = "--functions" in text or "--all" in text or (
            "--imports" not in text and "--functions" not in text
        )

        for flag in ("--imports", "--functions", "--all"):
            text = text.replace(flag, "").strip()

        p = _Path(text)
        if not p.exists():
            return f"Файл не найден: `{text}`"
        if not p.is_file():
            return f"`{text}` — не файл."

        try:
            source = p.read_text(encoding="utf-8", errors="replace")
            tree = _ast.parse(source, filename=str(p))
        except SyntaxError as exc:
            return f"Синтаксическая ошибка в `{p.name}`: {exc}"
        except Exception as exc:
            return f"Ошибка чтения: {exc}"

        lines_src = source.splitlines()
        results: list[str] = []

        if check_imports:
            # Collect imported names
            imported: dict[str, int] = {}  # name → line
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Import):
                    for alias in node.names:
                        name = alias.asname if alias.asname else alias.name.split(".")[0]
                        imported[name] = node.lineno
                elif isinstance(node, _ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        name = alias.asname if alias.asname else alias.name
                        imported[name] = node.lineno

            # Collect all Name usages (excluding import statements)
            used_names: set[str] = set()
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.Import, _ast.ImportFrom)):
                    continue
                if isinstance(node, _ast.Name):
                    used_names.add(node.id)
                elif isinstance(node, _ast.Attribute):
                    if isinstance(node.value, _ast.Name):
                        used_names.add(node.value.id)

            unused_imports = {
                name: lineno
                for name, lineno in imported.items()
                if name not in used_names and name != "_"
            }

            if unused_imports:
                results.append(f"**Неиспользуемые импорты** ({len(unused_imports)}):")
                for name, lineno in sorted(unused_imports.items(), key=lambda x: x[1]):
                    results.append(f"  Строка {lineno:>3}: `{name}`")
            else:
                results.append("✅ **Неиспользуемых импортов нет**")

        if check_functions:
            # Collect defined function/method names
            defined_fns: dict[str, int] = {}
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    if not node.name.startswith("_") and node.name not in (
                        "main", "setup", "teardown", "setUp", "tearDown"
                    ):
                        defined_fns[node.name] = node.lineno

            # Collect all Call usages
            called: set[str] = set()
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Call):
                    if isinstance(node.func, _ast.Name):
                        called.add(node.func.id)
                    elif isinstance(node.func, _ast.Attribute):
                        called.add(node.func.attr)

            # Also check string references (decorators, __all__ etc.)
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Constant) and isinstance(node.value, str):
                    called.add(node.value)

            unused_fns = {
                name: lineno
                for name, lineno in defined_fns.items()
                if name not in called
            }

            if results:
                results.append("")

            if unused_fns:
                results.append(f"**Возможно неиспользуемые функции** ({len(unused_fns)}):")
                results.append("*(не вызываются внутри этого файла — могут использоваться снаружи)*")
                for name, lineno in sorted(unused_fns.items(), key=lambda x: x[1]):
                    results.append(f"  Строка {lineno:>3}: `def {name}(...)`")
            else:
                results.append("✅ **Все функции вызываются в файле**")

        header = f"**Анализ мёртвого кода: `{p.name}`**\n"
        return header + "\n".join(results)

    registry.register(SlashCommand(
        "dead",
        "Детектор мёртвого кода: /dead <файл.py> [--imports|--functions|--all]",
        dead_handler,
    ))

    # ── Task 220: /standup ────────────────────────────────────────────────

    async def standup_handler(arg: str = "", **_) -> str:
        import asyncio as _asyncio
        from datetime import datetime as _dt, timedelta as _td

        text = arg.strip()
        days = 1
        if text.isdigit():
            days = min(int(text), 30)

        since = (_dt.now() - _td(days=days)).strftime("%Y-%m-%d")

        async def _git(*args, timeout=10) -> tuple[int, str]:
            try:
                proc = await _asyncio.create_subprocess_exec(
                    "git", *args,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                )
                out, _ = await _asyncio.wait_for(proc.communicate(), timeout=timeout)
                return proc.returncode or 0, out.decode("utf-8", errors="replace").strip()
            except Exception as exc:
                return 1, str(exc)

        # Get commits since N days ago
        rc, commits = await _git(
            "log", f"--since={since}", "--oneline", "--no-color",
            "--format=%h %s"
        )
        # Get changed files
        rc2, files = await _git(
            "diff", "--name-only", f"HEAD~{max(1, days * 3)}..HEAD",
            "--diff-filter=ACMR"
        )
        # Get current branch
        rc3, branch = await _git("rev-parse", "--abbrev-ref", "HEAD")

        from datetime import date as _date
        today = _date.today().strftime("%d %B %Y")

        lines = [f"**Стендап за {today}** (последние {days} дн.)", ""]

        # Branch info
        if rc3 == 0 and branch:
            lines.append(f"**Ветка:** `{branch}`")
            lines.append("")

        # What was done
        lines.append("**Что сделано:**")
        if rc == 0 and commits:
            for line in commits.splitlines()[:15]:
                sha, _, msg = line.partition(" ")
                lines.append(f"  · {msg} `[{sha}]`")
        else:
            lines.append("  · Коммитов не найдено")

        lines.append("")

        # Changed files
        if rc2 == 0 and files:
            file_list = files.splitlines()
            lines.append(f"**Изменённые файлы** ({len(file_list)}):")
            for f in file_list[:10]:
                lines.append(f"  · `{f}`")
            if len(file_list) > 10:
                lines.append(f"  *…ещё {len(file_list) - 10}*")
        else:
            lines.append("**Изменённые файлы:** не определены")

        lines.append("")
        lines.append("**Блокеры:** —")
        lines.append("**На сегодня:** —")
        lines.append("")
        lines.append("*Заполните блокеры и планы вручную.*")

        return "\n".join(lines)

    registry.register(SlashCommand(
        "standup",
        "Авто-стендап из git: /standup [дней=1]",
        standup_handler,
    ))

    # ── Task 454: /dry-run, /apply, /discard — shadow workspace commands ──

    async def dryrun_handler(arg: str = "", **_: Any) -> str:
        """/dry-run [on|off|status] — toggle dry-run mode (shadow workspace)."""
        sw = getattr(registry, "_shadow_workspace", None)
        if sw is None:
            return "Shadow workspace not available."
        sub = arg.strip().lower()
        if sub in ("on", "enable"):
            sw.enable()
            return "[dry-run] ON -- file writes will be staged, not applied."
        elif sub in ("off", "disable"):
            sw.disable()
            return "[dry-run] OFF -- file writes applied immediately."
        else:
            state = "ON" if sw.active else "OFF"
            return f"[dry-run] {state}. {sw.summary()}"

    registry.register(SlashCommand(
        "dry-run",
        "Toggle dry-run mode: /dry-run [on|off|status]",
        dryrun_handler,
    ))

    async def apply_handler(arg: str = "", **_: Any) -> str:
        """/apply [path ...] — apply staged dry-run changes to disk."""
        sw = getattr(registry, "_shadow_workspace", None)
        if sw is None:
            return "Shadow workspace not available."
        paths = arg.strip().split() if arg.strip() else None
        if not sw.pending_paths():
            return "No pending changes to apply."
        diff_text = sw.get_diff()
        result = sw.apply(paths)
        lines = []
        if diff_text:
            lines.append("**Applied diff:**\n```diff\n" + diff_text + "\n```\n")
        if result.applied:
            lines.append(f"Applied {len(result.applied)} file(s): " + ", ".join(result.applied))
        if result.skipped:
            lines.append(f"Skipped {len(result.skipped)} file(s): " + ", ".join(result.skipped))
        if result.errors:
            for p, err in result.errors.items():
                lines.append(f"Error writing {p}: {err}")
        remaining = len(sw.pending_paths())
        if remaining:
            lines.append(f"{remaining} file(s) still pending.")
        return "\n".join(lines) if lines else "Nothing applied."

    registry.register(SlashCommand(
        "apply",
        "Apply staged dry-run changes: /apply [path ...]",
        apply_handler,
    ))

    async def discard_handler(arg: str = "", **_: Any) -> str:
        """/discard [path ...] — discard staged dry-run changes."""
        sw = getattr(registry, "_shadow_workspace", None)
        if sw is None:
            return "Shadow workspace not available."
        paths = arg.strip().split() if arg.strip() else None
        if not sw.pending_paths():
            return "No pending changes to discard."
        count = sw.discard(paths)
        remaining = len(sw.pending_paths())
        msg = f"Discarded {count} file(s)."
        if remaining:
            msg += f" {remaining} file(s) still pending."
        return msg

    registry.register(SlashCommand(
        "discard",
        "Discard staged dry-run changes: /discard [path ...]",
        discard_handler,
    ))
