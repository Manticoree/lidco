"""Commands: git and multi-agent."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def register(registry: Any) -> None:
    """Register git and multi-agent commands."""
    from lidco.cli.commands.registry import SlashCommand


    # ── Q56 Task 376: /bisect — git bisect integration ─────────────────────

    async def bisect_handler(arg: str = "", **_: Any) -> str:
        """/bisect <start <test>|run|stop> — git bisect integration."""
        import asyncio as _asyncio
        import subprocess as _subprocess

        parts = arg.strip().split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _git(*cmd: str, timeout: int = 30) -> tuple[str, str, int]:
            try:
                r = _subprocess.run(
                    ["git"] + list(cmd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
                return r.stdout.strip(), r.stderr.strip(), r.returncode
            except FileNotFoundError:
                return "", "git not found", -1
            except _subprocess.TimeoutExpired:
                return "", "timeout", -2

        if sub == "stop":
            out, err, rc = _git("bisect", "reset")
            if rc != 0:
                return f"bisect reset failed: {err}"
            return f"Git bisect stopped.\n```\n{out}\n```"

        if sub == "start":
            if not rest.strip():
                return "Usage: `/bisect start <test-expression>`\n\nExample: `/bisect start pytest tests/test_foo.py -k test_bar`"

            test_expr = rest.strip()
            # Start bisect
            out1, err1, rc1 = _git("bisect", "start")
            if rc1 != 0:
                return f"Failed to start bisect: {err1}"

            # Mark HEAD as bad
            out2, err2, rc2 = _git("bisect", "bad")
            if rc2 != 0:
                return f"Failed to mark HEAD bad: {err2}"

            # Find last 10 commits to pick a "good" baseline
            log_out, _, _ = _git("log", "--oneline", "-20")
            commit_lines = [ln for ln in log_out.splitlines() if ln.strip()]
            commits_list = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(commit_lines))

            result_lines = [
                "## Git Bisect Started",
                "",
                f"Test expression: `{test_expr}`",
                "",
                "HEAD marked as **bad**. Recent commits:",
                f"```\n{commits_list}\n```",
                "",
                "Mark the last known good commit with:",
                f"`git bisect good <hash>`",
                "",
                "Then run `/bisect run` to automate the search.",
            ]
            return "\n".join(result_lines)

        if sub == "run":
            # Run a bisect iteration: test current commit
            test_expr = rest.strip()
            if not test_expr:
                return "Usage: `/bisect run <test-expression>`"

            try:
                proc = _subprocess.run(
                    test_expr.split(),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
                test_passed = proc.returncode == 0
            except (FileNotFoundError, _subprocess.TimeoutExpired) as e:
                return f"Failed to run test: {e}"

            mark = "good" if test_passed else "bad"
            bisect_out, bisect_err, bisect_rc = _git("bisect", mark)
            full_out = bisect_out or bisect_err

            result_lines = [
                f"## Bisect Step: marked **{mark}**",
                "",
                f"Test `{test_expr}` {'passed' if test_passed else 'failed'}.",
                "",
                f"```\n{full_out}\n```",
            ]

            # Check if bisect found the culprit
            if "is the first bad commit" in full_out or "bisect found" in full_out.lower():
                # Extract commit hash
                culprit_hash = ""
                for ln in full_out.splitlines():
                    if ln and not ln.startswith("[") and len(ln.split()) >= 1:
                        culprit_hash = ln.split()[0]
                        break

                result_lines.append("")
                result_lines.append("**Culprit commit found!**")

                if culprit_hash and registry._session:
                    try:
                        show_out, _, _ = _git("show", "--stat", culprit_hash, timeout=10)
                        from lidco.llm.base import Message as _LLMMsg
                        explain_resp = await registry._session.llm.complete(
                            [_LLMMsg(role="user", content=(
                                f"Explain this git commit and why it might have introduced a bug:\n\n"
                                f"```\n{show_out[:2000]}\n```\n\n"
                                "Be concise (2-3 sentences)."
                            ))],
                            temperature=0.2,
                            max_tokens=150,
                        )
                        result_lines.append("")
                        result_lines.append(f"**AI explanation:** {(explain_resp.content or '').strip()}")
                    except Exception:
                        pass

            return "\n".join(result_lines)

        return (
            "**Usage:** `/bisect <subcommand>`\n\n"
            "- `/bisect start <test-expr>` — start bisect, mark HEAD as bad\n"
            "- `/bisect run <test-expr>` — run test on current commit, auto-mark\n"
            "- `/bisect stop` — abort bisect session\n\n"
            "**Example:** `/bisect start pytest tests/ -k test_login`"
        )

    registry.register(SlashCommand("bisect", "Git bisect integration for finding regressions", bisect_handler))

    # ── Q56 Task 377: /branch, /checkout, /stash ──────────────────────────

    async def branch_handler(arg: str = "", **_: Any) -> str:
        """/branch [list|create <name>|delete <name>|rename <old> <new>]."""
        import subprocess as _subprocess

        def _git(*cmd: str) -> tuple[str, str, int]:
            try:
                r = _subprocess.run(
                    ["git"] + list(cmd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
                return r.stdout.strip(), r.stderr.strip(), r.returncode
            except FileNotFoundError:
                return "", "git not found", -1
            except _subprocess.TimeoutExpired:
                return "", "timeout", -2

        parts = arg.strip().split()
        sub = parts[0].lower() if parts else "list"

        if sub == "list" or sub == "" or not parts:
            out, err, rc = _git("branch", "-a", "--color=never")
            if rc != 0:
                return f"Error listing branches: {err}"
            if not out:
                return "No branches found."
            branch_lines = []
            for ln in out.splitlines():
                marker = "**" if ln.startswith("*") else ""
                branch_lines.append(f"  {marker}{ln.strip()}{marker}")
            return "## Branches\n\n" + "\n".join(branch_lines)

        if sub == "create" and len(parts) >= 2:
            name = parts[1]
            out, err, rc = _git("branch", name)
            if rc != 0:
                return f"Failed to create branch `{name}`: {err}"
            return f"Branch `{name}` created."

        if sub == "delete" and len(parts) >= 2:
            name = parts[1]
            out, err, rc = _git("branch", "-d", name)
            if rc != 0:
                # Try force delete
                out2, err2, rc2 = _git("branch", "-D", name)
                if rc2 != 0:
                    return f"Failed to delete branch `{name}`: {err}"
                return f"Branch `{name}` force-deleted."
            return f"Branch `{name}` deleted."

        if sub == "rename" and len(parts) >= 3:
            old, new = parts[1], parts[2]
            out, err, rc = _git("branch", "-m", old, new)
            if rc != 0:
                return f"Failed to rename `{old}` to `{new}`: {err}"
            return f"Branch renamed: `{old}` → `{new}`."

        return (
            "**Usage:** `/branch [list|create <name>|delete <name>|rename <old> <new>]`\n\n"
            "- `/branch` — list all branches\n"
            "- `/branch create feature/my-work` — create a new branch\n"
            "- `/branch delete old-branch` — delete a branch\n"
            "- `/branch rename old-name new-name` — rename a branch"
        )

    registry.register(SlashCommand("branch", "Manage git branches", branch_handler))

    async def checkout_handler(arg: str = "", **_: Any) -> str:
        """/checkout <branch-or-file> — switch branches or restore files."""
        import subprocess as _subprocess

        target = arg.strip()
        if not target:
            return "**Usage:** `/checkout <branch-or-file>`"

        try:
            r = _subprocess.run(
                ["git", "checkout", target],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if r.returncode != 0:
                return f"Checkout failed:\n```\n{r.stderr.strip()}\n```"
            out = (r.stdout + r.stderr).strip()
            return f"Checked out `{target}`." + (f"\n```\n{out}\n```" if out else "")
        except FileNotFoundError:
            return "Git not found."
        except _subprocess.TimeoutExpired:
            return "Checkout timed out."

    registry.register(SlashCommand("checkout", "Checkout a branch or restore a file", checkout_handler))

    async def stash_handler(arg: str = "", **_: Any) -> str:
        """/stash [list|push [message]|pop [index]|drop [index]]."""
        import subprocess as _subprocess

        def _git(*cmd: str) -> tuple[str, str, int]:
            try:
                r = _subprocess.run(
                    ["git"] + list(cmd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
                return r.stdout.strip(), r.stderr.strip(), r.returncode
            except FileNotFoundError:
                return "", "git not found", -1
            except _subprocess.TimeoutExpired:
                return "", "timeout", -2

        parts = arg.strip().split(None, 1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "list" or not parts:
            out, err, rc = _git("stash", "list")
            if rc != 0:
                return f"Error: {err}"
            if not out:
                return "No stashes found."
            return "## Stash List\n\n```\n" + out + "\n```"

        if sub == "push":
            cmd_args = ["stash", "push"]
            if rest.strip():
                cmd_args += ["-m", rest.strip()]
            out, err, rc = _git(*cmd_args)
            if rc != 0:
                return f"Stash push failed: {err}"
            return f"Stashed changes." + (f"\n```\n{out}\n```" if out else "")

        if sub == "pop":
            cmd_args = ["stash", "pop"]
            if rest.strip():
                cmd_args += [f"stash@{{{rest.strip()}}}"]
            out, err, rc = _git(*cmd_args)
            if rc != 0:
                return f"Stash pop failed: {err}"
            return f"Popped stash." + (f"\n```\n{out}\n```" if out else "")

        if sub == "drop":
            cmd_args = ["stash", "drop"]
            if rest.strip():
                cmd_args += [f"stash@{{{rest.strip()}}}"]
            out, err, rc = _git(*cmd_args)
            if rc != 0:
                return f"Stash drop failed: {err}"
            return f"Dropped stash." + (f"\n```\n{out}\n```" if out else "")

        return (
            "**Usage:** `/stash [list|push [message]|pop [index]|drop [index]]`\n\n"
            "- `/stash` — list stashes\n"
            "- `/stash push Work in progress` — stash with message\n"
            "- `/stash pop` — apply latest stash\n"
            "- `/stash pop 1` — apply stash@{1}\n"
            "- `/stash drop 0` — drop stash@{0}"
        )

    registry.register(SlashCommand("stash", "Manage git stashes", stash_handler))

    # ── Q56 Task 378: /pr create — AI-generated PR creation ───────────────
    # NOTE: Extends existing /pr (which handles load/context). We register
    # a new 'pr-create' command AND patch pr_handler to support 'create'.

    async def pr_create_handler(arg: str = "", **_: Any) -> str:
        """/pr-create [--draft] [--base <branch>] — create a PR with AI-generated title/body."""
        import subprocess as _subprocess

        # Parse flags
        draft = False
        base_branch = ""
        tokens = arg.strip().split()
        i = 0
        while i < len(tokens):
            if tokens[i] == "--draft":
                draft = True
                i += 1
            elif tokens[i] == "--base" and i + 1 < len(tokens):
                base_branch = tokens[i + 1]
                i += 2
            else:
                i += 1

        def _run(*cmd: str, timeout: int = 30) -> tuple[str, str, int]:
            try:
                r = _subprocess.run(
                    list(cmd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
                return r.stdout.strip(), r.stderr.strip(), r.returncode
            except FileNotFoundError:
                return "", f"{cmd[0]} not found", -1
            except _subprocess.TimeoutExpired:
                return "", "timeout", -2

        # Gather git context
        log_out, _, _ = _run("git", "log", "origin/HEAD..HEAD", "--oneline", timeout=15)
        if not log_out:
            log_out, _, _ = _run("git", "log", "-10", "--oneline", timeout=15)

        stat_out, _, _ = _run("git", "diff", "--stat", "origin/HEAD..HEAD", timeout=15)
        if not stat_out:
            stat_out, _, _ = _run("git", "diff", "--stat", "HEAD~1..HEAD", timeout=15)

        current_branch, _, _ = _run("git", "rev-parse", "--abbrev-ref", "HEAD")

        if not registry._session:
            return "Session not initialized. Cannot generate PR title/body."

        try:
            from lidco.llm.base import Message as _LLMMsg
            prompt = (
                "Generate a GitHub pull request title and body for these changes.\n\n"
                f"Branch: {current_branch}\n\n"
                f"Commits:\n```\n{log_out[:1500]}\n```\n\n"
                f"Diff stat:\n```\n{stat_out[:800]}\n```\n\n"
                "Format your response exactly as:\n"
                "TITLE: <one-line title under 70 chars>\n"
                "BODY:\n<markdown body with Summary section and bullet points>\n"
            )
            resp = await registry._session.llm.complete(
                [_LLMMsg(role="user", content=prompt)],
                temperature=0.2,
                max_tokens=500,
            )
            content = (resp.content or "").strip()
        except Exception as e:
            return f"Failed to generate PR content: {e}"

        # Parse generated title/body
        title = ""
        body = ""
        if "TITLE:" in content:
            lines_content = content.splitlines()
            for i2, ln in enumerate(lines_content):
                if ln.startswith("TITLE:"):
                    title = ln[6:].strip()
                elif ln.startswith("BODY:"):
                    body = "\n".join(lines_content[i2 + 1:]).strip()
                    break
        else:
            lines_content = content.splitlines()
            title = lines_content[0].strip() if lines_content else "Update"
            body = "\n".join(lines_content[1:]).strip()

        if not title:
            title = f"Update from {current_branch}"

        # Build gh command
        gh_cmd = ["gh", "pr", "create", "--title", title, "--body", body]
        if draft:
            gh_cmd.append("--draft")
        if base_branch:
            gh_cmd += ["--base", base_branch]

        preview_lines = [
            "## PR Preview",
            "",
            f"**Title:** {title}",
            "",
            f"**Body:**\n{body[:600]}{'...' if len(body) > 600 else ''}",
            "",
            f"**Command:** `{' '.join(gh_cmd[:6])} ...`",
            "",
            "_Run `gh pr create` manually or confirm with this command._",
        ]

        # Try to actually create
        out, err, rc = _run(*gh_cmd, timeout=30)
        if rc == 0:
            preview_lines.append("")
            preview_lines.append(f"PR created: {out}")
        else:
            preview_lines.append("")
            preview_lines.append(f"**Note:** `gh pr create` returned error: {err or out}")
            preview_lines.append("_You may need to push your branch first: `git push -u origin HEAD`_")

        return "\n".join(preview_lines)

    registry.register(SlashCommand("pr-create", "Create a PR with AI-generated title and body", pr_create_handler))

    # ── Q56 Task 379: /pr-review <number> ─────────────────────────────────

    async def pr_review_handler(arg: str = "", **_: Any) -> str:
        """/pr-review <number> — AI-powered PR review with security+code analysis."""
        import subprocess as _subprocess

        pr_number = arg.strip()
        if not pr_number:
            return "**Usage:** `/pr-review <number>`\n\nExample: `/pr-review 123`"

        def _run(*cmd: str, timeout: int = 30) -> tuple[str, str, int]:
            try:
                r = _subprocess.run(
                    list(cmd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
                return r.stdout.strip(), r.stderr.strip(), r.returncode
            except FileNotFoundError:
                return "", f"{cmd[0]} not found", -1
            except _subprocess.TimeoutExpired:
                return "", "timeout", -2

        diff_out, diff_err, diff_rc = _run("gh", "pr", "diff", pr_number, timeout=30)
        if diff_rc != 0:
            return f"Failed to fetch PR #{pr_number} diff: {diff_err or diff_out}"

        if not diff_out:
            return f"PR #{pr_number} has no diff or is empty."

        if not registry._session:
            return "Session not initialized."

        # Truncate large diffs
        diff_excerpt = diff_out[:6000]
        if len(diff_out) > 6000:
            diff_excerpt += f"\n... ({len(diff_out) - 6000} chars truncated)"

        try:
            from lidco.llm.base import Message as _LLMMsg
            prompt = (
                f"Review this GitHub PR diff (PR #{pr_number}) as both a security expert "
                "and a senior engineer.\n\n"
                "Provide:\n"
                "1. **Security issues** (if any) — list as inline comments with file:line\n"
                "2. **Code quality issues** — style, logic, complexity\n"
                "3. **Suggestions** — improvements, missing tests, etc.\n"
                "4. **Overall verdict** — APPROVE / REQUEST_CHANGES / COMMENT\n\n"
                f"```diff\n{diff_excerpt}\n```"
            )
            resp = await registry._session.llm.complete(
                [_LLMMsg(role="user", content=prompt)],
                temperature=0.2,
                max_tokens=800,
            )
            review_content = (resp.content or "").strip()
        except Exception as e:
            return f"Failed to generate review: {e}"

        return f"## PR #{pr_number} Review\n\n{review_content}"

    registry.register(SlashCommand("pr-review", "AI-powered review of a GitHub PR", pr_review_handler))

    # ── Q56 Task 381: enhance /commit with template support ───────────────
    # We replace the commit_handler registered earlier by re-registering
    # a new one that loads .lidco/commit-template.md if present.

    async def commit_with_template_handler(arg: str = "", **_: Any) -> str:
        """Enhanced /commit — generates commit message, optionally using .lidco/commit-template.md."""
        import asyncio as _asyncio
        import subprocess as _subprocess
        from pathlib import Path as _Path

        if not registry._session:
            return "Session not initialized."

        def _get_diff() -> tuple[str, str]:
            try:
                r = _subprocess.run(
                    ["git", "diff", "--cached"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                )
                if r.stdout.strip():
                    return r.stdout.strip(), "staged"
                r = _subprocess.run(
                    ["git", "diff", "HEAD"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                )
                if r.stdout.strip():
                    return r.stdout.strip(), "working tree"
                return "", "none"
            except FileNotFoundError:
                return "", "error:git not found"
            except Exception as e:
                return "", f"error:{e}"

        def _load_template() -> str:
            """Load .lidco/commit-template.md if it exists."""
            for candidate in [
                _Path(".lidco") / "commit-template.md",
                _Path(".lidco") / "commit-template.txt",
            ]:
                if candidate.exists():
                    try:
                        return candidate.read_text(encoding="utf-8", errors="replace").strip()
                    except OSError:
                        pass
            return ""

        loop = _asyncio.get_event_loop()
        diff, source = await loop.run_in_executor(None, _get_diff)

        if source.startswith("error:"):
            return f"Git error: {source[6:]}"
        if not diff:
            return "No changes found. Stage files with `git add` first."

        if arg.strip():
            commit_msg = arg.strip()
        else:
            diff_excerpt = diff[:4000]
            template = await loop.run_in_executor(None, _load_template)

            template_section = ""
            if template:
                template_section = (
                    f"\n\nCommit message template to follow:\n```\n{template}\n```\n"
                    "Use the template format above for the commit message."
                )

            from lidco.llm.base import Message as _LLMMsg2
            try:
                resp = await registry._session.llm.complete(
                    [_LLMMsg2(role="user", content=(
                        "Write a git commit message for these changes.\n"
                        "Rules: one line, max 72 chars, format '<type>: <description>'\n"
                        "Types: feat, fix, refactor, docs, test, chore, perf\n"
                        f"{template_section}\n"
                        f"\n```diff\n{diff_excerpt}\n```\n\n"
                        "Output ONLY the commit message, nothing else."
                    ))],
                    temperature=0.1,
                    max_tokens=80,
                )
                commit_msg = (resp.content or "").strip().strip('"').strip("'")
            except Exception as e:
                return f"Failed to generate commit message: {e}"

        def _confirm_and_commit(msg: str, diff_source: str) -> str:
            from rich.console import Console as _RC2
            from rich.panel import Panel as _Panel2
            from rich.prompt import Prompt as _Prompt2

            c = _RC2()
            c.print()
            c.print(_Panel2(
                f"[bold cyan]{msg}[/bold cyan]\n\n[dim]Changes: {diff_source}[/dim]",
                title="Proposed Commit",
                border_style="cyan",
            ))
            answer = _Prompt2.ask(
                "Commit? [[green]y[/green]/[yellow]e[/yellow]dit/[red]n[/red]]",
                default="y",
            )
            if answer.lower() in ("n", "no", "q", "cancel"):
                return "__CANCEL__"
            if answer.lower() in ("e", "edit"):
                msg = _Prompt2.ask("New message", default=msg)

            staged_check = _subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                capture_output=True, timeout=5,
            )
            if staged_check.returncode == 0:
                add_result = _subprocess.run(
                    ["git", "add", "-u"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=10,
                )
                if add_result.returncode != 0:
                    return f"__ERROR__:Failed to stage changes: {add_result.stderr.strip()}"

            result = _subprocess.run(
                ["git", "commit", "-m", msg],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            if result.returncode != 0:
                return f"__ERROR__:{result.stderr.strip()}"
            return f"__OK__:{result.stdout.strip()}"

        outcome = await loop.run_in_executor(
            None, lambda: _confirm_and_commit(commit_msg, source)
        )

        if outcome == "__CANCEL__":
            return "Commit cancelled."
        if outcome.startswith("__ERROR__:"):
            return f"Commit failed:\n\n```\n{outcome[10:]}\n```"
        return f"Committed successfully:\n\n```\n{outcome[6:]}\n```"

    # Override the existing /commit with template-aware version
    registry.register(SlashCommand("commit", "Generate a commit message and commit (supports .lidco/commit-template.md)", commit_with_template_handler))

    # ── Q58 Task 389: /compare ────────────────────────────────────────────────
    async def compare_handler(arg: str = "", **_: Any) -> str:
        """Compare two files (diff) or run a task on multiple agents.

        File comparison (Task 198):
          /compare <file1> <file2>

        Agent comparison (Task 389):
          /compare <task>
          /compare --agents coder,architect <task>
        """
        import difflib as _difflib

        _PLANNING_AGENTS_LIST = ["coder", "architect", "tester", "refactor", "debugger"]
        agent_names: list[str] = []
        task_text = (arg or "").strip()

        # ── File comparison mode: detect two path-like arguments ──────────
        # Only when NOT using --agents flag and NOT starting with a verb-like word
        if task_text and not task_text.startswith("--agents "):
            parts_cmp = task_text.split(None, 1)
            if len(parts_cmp) == 2:
                p1_str, p2_str = parts_cmp[0], parts_cmp[1].strip()
                # Heuristic: if both look like file paths (have extension or abs path)
                _path_like = lambda s: "/" in s or "\\" in s or "." in s.split("/")[-1]
                if _path_like(p1_str) and not p2_str.startswith("--") and not any(
                    c in p1_str for c in (" ",)
                ):
                    p1 = Path(p1_str)
                    p2 = Path(p2_str)
                    # If first token looks like a file path, treat as file diff
                    if p1.suffix or p1.is_absolute() or p2.suffix or p2.is_absolute():
                        # File diff mode
                        if not p1.exists():
                            return f"File not found: `{p1_str}`"
                        if p1.is_dir():
                            return f"`{p1_str}` is a directory, not a file."
                        if not p2.exists():
                            return f"File not found: `{p2_str}`"
                        if p2.is_dir():
                            return f"`{p2_str}` is a directory, not a file."
                        text1 = p1.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                        text2 = p2.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                        diff = list(_difflib.unified_diff(text1, text2, fromfile=p1_str, tofile=p2_str))
                        size1 = p1.stat().st_size
                        size2 = p2.stat().st_size
                        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
                        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
                        if not diff:
                            return (
                                f"**{p1_str}** and **{p2_str}** are identical.\n\n"
                                f"Size: {size1} bytes"
                            )
                        diff_text = "".join(diff)
                        _MAX_DIFF_LINES = 200
                        diff_lines = diff_text.splitlines()
                        hidden = 0
                        if len(diff_lines) > _MAX_DIFF_LINES:
                            hidden = len(diff_lines) - _MAX_DIFF_LINES
                            diff_text = "\n".join(diff_lines[:_MAX_DIFF_LINES])
                        header = (
                            f"**{p1_str}** ({size1} bytes) → **{p2_str}** ({size2} bytes)\n"
                            f"+{added} added / -{removed} removed\n\n"
                        )
                        result_str = header + f"```diff\n{diff_text}\n```"
                        if hidden:
                            result_str += f"\n\n_{hidden} lines hidden_"
                        return result_str

        # ── Agent comparison mode ─────────────────────────────────────────
        # Parse --agents flag
        if task_text.startswith("--agents "):
            rest = task_text[len("--agents "):].strip()
            if " " in rest:
                agents_str, task_text = rest.split(" ", 1)
                task_text = task_text.strip()
            else:
                agents_str, task_text = rest, ""
            agent_names = [a.strip() for a in agents_str.split(",") if a.strip()]

        if not task_text:
            return (
                "Usage:\n"
                "  `/compare <file1> <file2>` — diff two files\n"
                "  `/compare <task>` — run task on multiple agents\n"
                "  `/compare --agents coder,tester <task>` — specify agents"
            )

        if len(task_text.split()) == 1 and not agent_names:
            # Single token that didn't match two files — show better error
            return (
                f"Need two file paths or a task description.\n\n"
                "  `/compare <file1> <file2>` — diff two files\n"
                "  `/compare <task words>` — run agents on a task"
            )

        if not registry._session:
            return "Session not initialized."

        if not agent_names:
            # Use top 3 planning agents that are registered
            reg = registry._session.agent_registry
            available = {a.name for a in reg.list_agents()} if reg else set()
            agent_names = [
                n for n in _PLANNING_AGENTS_LIST if n in available
            ][:3]
            if not agent_names:
                agent_names = _PLANNING_AGENTS_LIST[:3]

        from lidco.agents.comparison import AgentComparator
        comparator = AgentComparator()
        result = await comparator.run(task_text, agent_names, registry._session)

        if not result.results:
            return "No agents available for comparison."

        lines: list[str] = [f"## Comparison: `{task_text[:60]}`\n"]
        for i, ar in enumerate(result.results):
            idx = i + 1
            if ar.success:
                preview = ar.response[:600]
                if len(ar.response) > 600:
                    preview += "\n...(truncated)"
                lines.append(
                    f"### [{idx}] {ar.agent_name} "
                    f"({ar.elapsed:.1f}s{', ' + str(ar.tokens) + ' tok' if ar.tokens else ''})"
                )
                lines.append(preview)
            else:
                lines.append(f"### [{idx}] {ar.agent_name} — FAILED: {ar.error}")
            lines.append("")

        lines.append("---")
        lines.append(
            "Select the best result by replying with its number, "
            "or continue with your next message."
        )
        return "\n".join(lines)

    registry.register(SlashCommand("compare", "Compare files (diff) or run task on multiple agents", compare_handler))

    # ── Q58 Task 390 & 393: /pipeline ─────────────────────────────────────
    # Stores paused pipeline state for /pipeline resume
    registry._pipeline_state: "dict[str, Any]" = {}  # type: ignore[assignment]

    async def pipeline_handler(arg: str = "", **_: Any) -> str:
        """Load and run a declarative YAML agent pipeline.

        /pipeline <yaml-file>         — load from file and run
        /pipeline resume              — resume paused pipeline
        /pipeline inline: <yaml>      — run inline YAML (newlines as \\n)
        """
        if not registry._session:
            return "Session not initialized."

        arg = (arg or "").strip()

        # /pipeline resume
        if arg == "resume":
            state = getattr(registry, "_pipeline_state", {})
            if not state:
                return "No paused pipeline to resume."
            yaml_str = state.get("yaml_str", "")
            task_text = state.get("task", "")
            if not yaml_str or not task_text:
                return "Paused pipeline state is incomplete."
            registry._pipeline_state = {}  # type: ignore[assignment]
            # Re-run from scratch (simplest safe approach)
            arg = ""  # fall through to re-run logic below
            from lidco.agents.pipeline import AgentPipeline
            pipeline_obj = AgentPipeline()
            try:
                pipeline_obj.load(yaml_str)
            except ValueError as exc:
                return f"Pipeline YAML error: {exc}"
            result = await pipeline_obj.run(task_text, registry._session)
            return _format_pipeline_result(result)

        if not arg:
            return (
                "Usage:\n"
                "  `/pipeline <yaml-file>` — run pipeline from YAML file\n"
                "  `/pipeline resume` — resume paused pipeline\n"
                "  `/pipeline inline: <yaml>` — run inline YAML"
            )

        from lidco.agents.pipeline import AgentPipeline

        # Parse task and yaml source
        yaml_str = ""
        task_text = ""

        if arg.startswith("inline:"):
            # /pipeline inline: steps:\n  - name: ...
            rest = arg[len("inline:"):].strip()
            # treat first line as task if it doesn't look like yaml
            lines_split = rest.split("\\n")
            yaml_str = "\n".join(lines_split)
            task_text = "Execute pipeline"
        else:
            # Treat arg as: [task ]<yaml-file>
            # If arg ends in .yaml or .yml assume it's a file
            parts = arg.split(None, 1)
            if len(parts) == 2 and (parts[1].endswith(".yaml") or parts[1].endswith(".yml")):
                task_text = parts[0]
                yaml_path_str = parts[1]
            elif arg.endswith(".yaml") or arg.endswith(".yml"):
                task_text = "Execute pipeline"
                yaml_path_str = arg
            else:
                # last token is file, rest is task
                yaml_path_str = parts[-1]
                task_text = parts[0] if len(parts) > 1 else "Execute pipeline"

            yaml_file = Path(yaml_path_str)
            if not yaml_file.exists():
                return f"YAML file not found: `{yaml_path_str}`"
            try:
                yaml_str = yaml_file.read_text(encoding="utf-8")
            except OSError as exc:
                return f"Failed to read pipeline file: {exc}"

        pipeline_obj = AgentPipeline()
        try:
            pipeline_obj.load(yaml_str)
        except ValueError as exc:
            return f"Pipeline YAML error: {exc}"

        # confirm_fn for checkpoints — auto-accept in non-interactive contexts
        async def _confirm(step_name: str, results_so_far: dict) -> bool:
            # Store paused state for /pipeline resume
            registry._pipeline_state = {"yaml_str": yaml_str, "task": task_text}  # type: ignore[assignment]
            return False  # pause; user runs /pipeline resume to continue

        result = await pipeline_obj.run(task_text, registry._session, confirm_fn=_confirm)

        if result.checkpoint and result.checkpoint.paused:
            lines_out = [_format_pipeline_result(result)]
            lines_out.append(
                f"\n**Pipeline paused at checkpoint `{result.checkpoint.step_name}`.**\n"
                "Run `/pipeline resume` to continue."
            )
            return "\n".join(lines_out)

        return _format_pipeline_result(result)

    def _format_pipeline_result(result: "Any") -> str:
        from lidco.agents.pipeline import PipelineResult
        if not isinstance(result, PipelineResult):
            return str(result)
        lines: list[str] = ["## Pipeline Result\n"]
        for sr in result.steps:
            if sr.skipped:
                lines.append(f"- **{sr.name}** — ⏭ skipped (condition)")
            elif sr.success:
                preview = sr.output[:300] + ("..." if len(sr.output) > 300 else "")
                lines.append(f"- **{sr.name}** [{sr.agent or 'checkpoint'}] ✓")
                if preview:
                    lines.append(f"  {preview}")
            else:
                lines.append(f"- **{sr.name}** [{sr.agent}] ✗ {sr.error}")
        status = "✓ Success" if result.success else "✗ Failed"
        lines.append(f"\n**{status}** ({len(result.steps)} steps)")
        return "\n".join(lines)

    registry.register(SlashCommand("pipeline", "Run a declarative YAML agent pipeline", pipeline_handler))

    # ── Q58 Task 391: /broadcast ──────────────────────────────────────────
    async def broadcast_handler(arg: str = "", **_: Any) -> str:
        """Send a message to all registered agents simultaneously.

        /broadcast <message>
        /broadcast --agents coder,tester <message>
        """
        if not registry._session:
            return "Session not initialized."

        msg = (arg or "").strip()
        agent_names: list[str] = []

        if msg.startswith("--agents "):
            rest = msg[len("--agents "):].strip()
            if " " in rest:
                agents_str, msg = rest.split(" ", 1)
                msg = msg.strip()
            else:
                agents_str, msg = rest, ""
            agent_names = [a.strip() for a in agents_str.split(",") if a.strip()]

        if not msg:
            return (
                "Usage: `/broadcast <message>` or "
                "`/broadcast --agents coder,tester <message>`"
            )

        reg = registry._session.agent_registry
        if not agent_names:
            agent_names = [a.name for a in reg.list_agents()] if reg else []

        if not agent_names:
            return "No agents registered."

        async def _run_one(name: str) -> tuple[str, str]:
            try:
                context = registry._session.get_full_context() if hasattr(registry._session, "get_full_context") else ""
                response = await registry._session.orchestrator.handle(
                    msg, agent_name=name, context=context
                )
                content = response.content if hasattr(response, "content") else str(response)
                return name, content
            except Exception as exc:
                return name, f"ERROR: {exc}"

        import asyncio as _aio
        raw_results = await _aio.gather(*(_run_one(name) for name in agent_names))

        # Deduplicate findings: extract bullet lines, drop near-duplicates (same first 40 chars)
        all_findings: list[tuple[str, str]] = []  # (agent, finding)
        for agent_name, text in raw_results:
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith(("-", "*", "•")) or stripped.startswith(tuple("123456789")):
                    all_findings.append((agent_name, stripped))

        seen_prefixes: set[str] = set()
        unique_findings: list[tuple[str, str]] = []
        for agent_name, finding in all_findings:
            prefix = finding[:40]
            if prefix not in seen_prefixes:
                seen_prefixes.add(prefix)
                unique_findings.append((agent_name, finding))

        lines: list[str] = [f"## Broadcast: `{msg[:60]}`\n"]

        if unique_findings:
            lines.append("### Aggregated Findings (deduplicated)\n")
            by_agent: dict[str, list[str]] = {}
            for a, f in unique_findings:
                by_agent.setdefault(a, []).append(f)
            for name in agent_names:
                if name in by_agent:
                    lines.append(f"**{name}:**")
                    for finding in by_agent[name]:
                        lines.append(f"  {finding}")
            lines.append("")
        else:
            # Fallback: show full responses
            for a_name, text in raw_results:
                preview = text[:400] + ("..." if len(text) > 400 else "")
                lines.append(f"**{a_name}:**\n{preview}\n")

        return "\n".join(lines)

    registry.register(SlashCommand("broadcast", "Send task to all agents simultaneously", broadcast_handler))

    # ── Q58 Task 392: extend /agents with stats subcommand ────────────────
    # We store the enhanced handler; patch the registered command after
    _orig_agents_handler = registry._commands.get("agents")

    async def agents_with_stats_handler(arg: str = "", **_: Any) -> str:
        """Extended /agents with stats subcommand.

        /agents              — list agents
        /agents stats        — performance leaderboard
        /agents stats --period 7d
        /agents bg           — background tasks
        /agents inspect <n>  — agent details
        """
        raw = (arg or "").strip()

        # /agents stats [--period Nd]
        if raw == "stats" or raw.startswith("stats"):
            stats = registry._agent_stats
            if not stats:
                return "No agent stats recorded yet."

            # Parse --period flag (approximate: all stats if not filterable)
            _period_days: int | None = None
            if "--period" in raw:
                try:
                    period_part = raw.split("--period")[1].strip().split()[0]
                    if period_part.endswith("d"):
                        _period_days = int(period_part[:-1])
                except (IndexError, ValueError):
                    pass

            rows: list[tuple[str, int, float, int, float]] = []
            for name, info in stats.items():
                call_count = int(info.get("call_count", 0))
                total_elapsed = float(info.get("total_elapsed", 0.0))
                total_tokens = int(info.get("total_tokens", 0))
                success_count = int(info.get("success_count", call_count))
                avg_elapsed = total_elapsed / call_count if call_count else 0.0
                success_rate = success_count / call_count if call_count else 1.0
                rows.append((name, call_count, avg_elapsed, total_tokens, success_rate))

            # Sort by call count desc
            rows.sort(key=lambda r: r[1], reverse=True)

            lines: list[str] = ["## Agent Performance Leaderboard\n"]
            header = f"{'Agent':<16} {'Calls':>6} {'Avg(s)':>8} {'Tokens':>8} {'Success':>8}"
            lines.append(f"```\n{header}")
            lines.append("-" * len(header))
            for name, calls, avg_s, tokens, rate in rows:
                lines.append(
                    f"{name:<16} {calls:>6} {avg_s:>8.2f} {tokens:>8} {rate:>7.0%}"
                )
            lines.append("```")
            if _period_days:
                lines.append(f"\n_Period filter: last {_period_days}d (approximate — all available data shown)_")
            return "\n".join(lines)

        # Delegate to original handler
        if _orig_agents_handler:
            return await _orig_agents_handler.handler(arg=arg)
        return "Session not initialized."

    registry.register(SlashCommand("agents", "List agents, view stats, manage background tasks", agents_with_stats_handler))


