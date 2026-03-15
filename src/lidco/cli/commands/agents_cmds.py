"""Commands: agent and TDD."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def register(registry: Any) -> None:
    """Register agent and TDD commands."""
    from lidco.cli.commands.registry import SlashCommand


    # ── Q42 — TDD Pipeline & Batch (Tasks 286–292) ───────────────────────

    # Task 287: /spec — generate a specification
    async def spec_handler(arg: str = "", **_: Any) -> str:
        """/spec <task> | list | load <name> — generate or view specifications."""
        session = registry._session
        parts = arg.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "list":
            from lidco.tdd.spec_writer import SpecWriter
            writer = SpecWriter(session)
            specs = writer.list_specs()
            if not specs:
                return "No specs saved yet. Use `/spec <task>` to generate one."
            lines = ["**Saved specifications:**\n"]
            for s in specs:
                lines.append(f"  · `{s['name']}` — {s['goal'][:60]}")
            return "\n".join(lines)

        if sub == "load":
            if not rest:
                return "Usage: `/spec load <name>`"
            from lidco.tdd.spec_writer import SpecWriter
            writer = SpecWriter(session)
            spec = writer.load(rest)
            if spec is None:
                return f"Spec `{rest}` not found."
            return f"**Spec: {spec.goal}**\n\n{spec.content[:2000]}"

        # Generate new spec
        task = arg.strip() if not sub else arg.strip()
        if not task:
            return (
                "**Usage:** `/spec <task description>`\n\n"
                "- `/spec add JWT authentication` — generate a spec\n"
                "- `/spec list` — list saved specs\n"
                "- `/spec load <name>` — view a saved spec"
            )
        from lidco.tdd.spec_writer import SpecWriter
        writer = SpecWriter(session)
        spec = await writer.generate(task)
        path = writer.save(spec)
        return f"**Specification generated** → saved to `{path}`\n\n{spec.content[:3000]}"

    registry.register(SlashCommand("spec", "Generate a structured feature specification", spec_handler))

    # Task 286: /tdd — run TDD pipeline
    async def tdd_handler(arg: str = "", **_: Any) -> str:
        """/tdd <task> [--test <file>] [--impl <file>] [--cycles N] — run TDD pipeline."""
        import re as _re
        session = registry._session
        if not arg.strip():
            return (
                "**Usage:** `/tdd <task> [--test <file>] [--impl <file>] [--cycles N]`\n\n"
                "Runs the full TDD pipeline: spec → RED tests → GREEN implementation → review.\n"
                "Example: `/tdd add binary search to utils.py`"
            )
        # Parse flags
        test_file = None
        impl_file = None
        max_cycles = 3
        task_text = arg

        m = _re.search(r"--test\s+(\S+)", arg)
        if m:
            test_file = m.group(1)
            task_text = task_text.replace(m.group(0), "").strip()

        m = _re.search(r"--impl\s+(\S+)", arg)
        if m:
            impl_file = m.group(1)
            task_text = task_text.replace(m.group(0), "").strip()

        m = _re.search(r"--cycles\s+(\d+)", arg)
        if m:
            max_cycles = int(m.group(1))
            task_text = task_text.replace(m.group(0), "").strip()

        from lidco.tdd.pipeline import TDDPipeline
        pipeline = TDDPipeline(
            session,
            test_file=test_file,
            impl_file=impl_file,
            max_cycles=max_cycles,
        )
        result = await pipeline.run(task_text)
        return result.summary()

    registry.register(SlashCommand("tdd", "Run the TDD pipeline (spec→RED→GREEN→verify)", tdd_handler))

    # Task 288: /batch — parallel task decomposition
    async def batch_handler(arg: str = "", **_: Any) -> str:
        """/batch <task> [--n N] [--agent name] — decompose and run in parallel."""
        import re as _re
        session = registry._session
        if not arg.strip():
            return (
                "**Usage:** `/batch <task> [--n N] [--agent name]`\n\n"
                "Decomposes a large task into N independent units and runs them in parallel.\n"
                "Example: `/batch add docstrings to all public functions in src/ --n 8`"
            )
        n = 5
        agent_name = None
        task_text = arg

        m = _re.search(r"--n\s+(\d+)", arg)
        if m:
            n = max(2, min(int(m.group(1)), 20))
            task_text = task_text.replace(m.group(0), "").strip()

        m = _re.search(r"--agent\s+(\S+)", arg)
        if m:
            agent_name = m.group(1)
            task_text = task_text.replace(m.group(0), "").strip()

        from lidco.tdd.batch import BatchProcessor
        processor = BatchProcessor(session, n_units=n)
        job = await processor.run(task_text, agent_name=agent_name)
        return job.summary()

    registry.register(SlashCommand("batch", "Decompose and run tasks in parallel", batch_handler))

    # Task 289: /simplify — parallel code review
    async def simplify_handler(arg: str = "", **_: Any) -> str:
        """/simplify [file] — run 3 parallel reviewers and merge findings."""
        session = registry._session
        if not arg.strip():
            return (
                "**Usage:** `/simplify <file_or_task>`\n\n"
                "Runs 3 parallel reviewers and merges their findings.\n"
                "Example: `/simplify src/auth.py`"
            )
        from lidco.tdd.batch import BatchProcessor
        target = arg.strip()
        # Three parallel review perspectives
        sub_tasks = [
            f"Review `{target}` for correctness and logic bugs",
            f"Review `{target}` for code quality, readability, and style",
            f"Review `{target}` for security vulnerabilities and edge cases",
        ]
        processor = BatchProcessor(session, max_concurrent=3, n_units=3)
        # Run all 3 reviewers in parallel using decomposed tasks directly
        import asyncio as _asyncio
        from lidco.tdd.batch import BatchJob, BatchUnit
        job = BatchJob(original_task=f"Review: {target}")
        for i, t in enumerate(sub_tasks, 1):
            job.units.append(BatchUnit(index=i, task=t))

        semaphore = _asyncio.Semaphore(3)
        async def _run_unit(unit: "BatchUnit") -> None:
            async with semaphore:
                unit.status = "running"
                try:
                    response = await session.orchestrator.handle(
                        unit.task, agent_name="reviewer"
                    )
                    unit.result = response.content if hasattr(response, "content") else str(response)
                    unit.status = "done"
                except Exception as exc:
                    unit.status = "failed"
                    unit.error = str(exc)

        await _asyncio.gather(*[_run_unit(u) for u in job.units])

        lines = [f"**Parallel Review: {target}**\n"]
        labels = ["Correctness", "Code Quality", "Security"]
        for unit, label in zip(job.units, labels):
            if unit.status == "done":
                lines.append(f"### {label}\n{unit.result[:600]}\n")
            else:
                lines.append(f"### {label}\nFailed: {unit.error[:100]}\n")
        return "\n".join(lines)

    registry.register(SlashCommand("simplify", "Run parallel code review and merge findings", simplify_handler))

    # Task 290: /best-of — best-of-N code generation
    async def bestof_handler(arg: str = "", **_: Any) -> str:
        """/best-of <N> <task> [--test <file>] [--impl <file>] — best-of-N generation."""
        import re as _re
        session = registry._session
        if not arg.strip():
            return (
                "**Usage:** `/best-of <N> <task> [--test <file>] [--impl <file>]`\n\n"
                "Generates N code variants and picks the best by test results.\n"
                "Example: `/best-of 3 implement quicksort --test tests/test_sort.py`"
            )
        # Parse N
        m = _re.match(r"^(\d+)\s+", arg.strip())
        n = int(m.group(1)) if m else 3
        task_text = arg.strip()[len(m.group(0)):] if m else arg.strip()

        test_file = None
        impl_file = None
        tm = _re.search(r"--test\s+(\S+)", task_text)
        if tm:
            test_file = tm.group(1)
            task_text = task_text.replace(tm.group(0), "").strip()
        im = _re.search(r"--impl\s+(\S+)", task_text)
        if im:
            impl_file = im.group(1)
            task_text = task_text.replace(im.group(0), "").strip()

        from lidco.tdd.best_of_n import BestOfN
        selector = BestOfN(session, n=n)
        result = await selector.run(task_text, test_file=test_file, impl_file=impl_file)
        return result.summary()

    registry.register(SlashCommand("best-of", "Best-of-N code generation via parallel attempts", bestof_handler))

    # Task 291: /tdd-mode — test-first enforcement
    registry._test_first_mode: str = "off"  # off | warn | block

    async def tddmode_handler(arg: str = "", **_: Any) -> str:
        """/tdd-mode [off|warn|block] — control test-first enforcement."""
        mode = arg.strip().lower()
        if mode not in ("", "off", "warn", "block"):
            return "Usage: `/tdd-mode [off|warn|block]`"

        if not mode:
            enforcer = getattr(registry, "_test_first_enforcer", None)
            current = registry._test_first_mode
            return (
                f"**Test-first mode:** `{current}`\n\n"
                "- `off` — no enforcement\n"
                "- `warn` — warn when impl written before tests\n"
                "- `block` — block impl writes until tests exist"
            )

        registry._test_first_mode = mode
        enforcer = getattr(registry, "_test_first_enforcer", None)
        if enforcer is not None:
            if mode == "off":
                enforcer.set_enabled(False)
            else:
                enforcer.set_enabled(True)
                enforcer.set_mode(mode)
        return f"Test-first enforcement set to `{mode}`."

    registry.register(SlashCommand("tdd-mode", "Control test-first write enforcement", tddmode_handler))

    # ── Q43 — Skills & Plugin System (Tasks 293–299) ─────────────────────

    # Lazy-loaded skill registry (Tasks 293, 294, 297)
    registry._skill_registry: Any = None

    def _get_skill_registry() -> Any:
        from lidco.skills.registry import SkillRegistry
        if registry._skill_registry is None:
            reg = SkillRegistry()
            reg.load()
            registry._skill_registry = reg
        return registry._skill_registry

    # Task 298: /skills — list/describe/run/edit/reload skills
    async def skills_handler(arg: str = "", **_: Any) -> str:
        """/skills [list|describe <name>|run <name> [args]|reload|validate] — manage skills."""
        session = registry._session
        skill_reg = _get_skill_registry()
        parts = arg.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1] if len(parts) > 1 else ""
        extra = parts[2] if len(parts) > 2 else ""

        if sub in ("list", ""):
            skills = skill_reg.list_skills()
            if not skills:
                return (
                    "No skills found.\n\n"
                    "Create a skill file in `.lidco/skills/` or `~/.lidco/skills/`:\n"
                    "```yaml\n---\nname: review\ndescription: Review code\n---\nReview: {args}\n```"
                )
            lines = [f"**Skills ({len(skills)} loaded):**\n"]
            for s in skills:
                ver = f" v{s.version}" if s.version != "1.0" else ""
                req = f" [requires: {', '.join(s.requires)}]" if s.requires else ""
                lines.append(f"  · `/{s.name}`{ver} — {s.description}{req}")
            lines.append("\nUse `/skills describe <name>` for details, `/skills run <name> [args]` to execute.")
            return "\n".join(lines)

        if sub == "describe":
            if not rest:
                return "Usage: `/skills describe <name>`"
            skill = skill_reg.get(rest)
            if skill is None:
                return f"Skill `{rest}` not found. Use `/skills list` to see available skills."
            lines = [
                f"**Skill: {skill.name}** (v{skill.version})",
                f"*{skill.description}*" if skill.description else "",
                f"**File:** `{skill.path}`",
            ]
            if skill.requires:
                lines.append(f"**Requires:** {', '.join(skill.requires)}")
            if skill.context:
                lines.append(f"**Context:** `{skill.context}`")
            if skill.scripts:
                for hook, cmd in skill.scripts.items():
                    lines.append(f"**Script ({hook}):** `{cmd}`")
            lines.append(f"\n**Prompt template:**\n```\n{skill.prompt[:800]}\n```")
            return "\n".join(l for l in lines if l)

        if sub == "run":
            if not rest:
                return "Usage: `/skills run <name> [args]`"
            # Support pipe syntax: /skills run skill1 | skill2
            full_expr = f"{rest} {extra}".strip() if extra else rest
            if "|" in full_expr:
                from lidco.skills.chain import SkillChain
                chain = SkillChain(skill_reg, session)
                result = await chain.run(full_expr)
                return result.summary()

            skill = skill_reg.get(rest)
            if skill is None:
                return f"Skill `{rest}` not found."
            missing = skill.check_requirements()
            if missing:
                return f"⚠️ Missing required tools: {', '.join(missing)}"
            skill.run_script("pre")
            prompt = skill.render(extra)
            try:
                context = ""
                if skill.context:
                    from pathlib import Path as _P
                    cp = _P(skill.context)
                    if cp.is_file():
                        context = cp.read_text(encoding="utf-8", errors="replace")[:3000]
                response = await session.orchestrator.handle(prompt, context=context or None)
                output = response.content if hasattr(response, "content") else str(response)
                skill.run_script("post")
                return output
            except Exception as exc:
                return f"Skill `{rest}` failed: {exc}"

        if sub == "reload":
            skill_reg.reload()
            n = len(skill_reg.list_skills())
            return f"Skills reloaded — {n} skill(s) available."

        if sub == "validate":
            from lidco.skills.validator import SkillValidator
            validator = SkillValidator()
            skills = skill_reg.list_skills()
            if not skills:
                return "No skills to validate."
            lines = [f"**Skill validation ({len(skills)} skills):**\n"]
            all_ok = True
            for s in skills:
                result = validator.validate(s)
                if result.valid:
                    lines.append(f"  ✅ `{s.name}`")
                else:
                    all_ok = False
                    lines.append(f"  ❌ `{s.name}`:")
                    for issue in result.issues:
                        lines.append(f"     · {issue}")
            if all_ok:
                lines.append("\nAll skills are valid.")
            return "\n".join(lines)

        return (
            "**Usage:** `/skills [list|describe <name>|run <name> [args]|reload|validate]`\n\n"
            "- `/skills` — list all skills\n"
            "- `/skills describe <name>` — show skill details\n"
            "- `/skills run <name> [args]` — execute a skill\n"
            "- `/skills run skill1 | skill2` — chain skills\n"
            "- `/skills reload` — rescan skill directories\n"
            "- `/skills validate` — check all skills for issues"
        )

    registry.register(SlashCommand("skills", "List, run, and manage reusable skills", skills_handler))

    # ── Q56 Task 375: /conflict — AI conflict resolver ─────────────────────

    async def conflict_handler(arg: str = "", **_: Any) -> str:
        """/conflict [file] — resolve git merge conflicts interactively."""
        import asyncio as _asyncio
        import subprocess as _subprocess

        from lidco.tools.conflict_resolver import (
            ConflictBlock as _CB,
            find_conflicted_files,
            parse_conflict_blocks,
            apply_resolution,
        )

        target_file = arg.strip()

        # Find conflicted files
        if target_file:
            candidates = [target_file]
        else:
            candidates = find_conflicted_files()

        if not candidates:
            return "No conflicted files found. Run `git merge` or `git rebase` first."

        lines: list[str] = []
        for fpath in candidates:
            blocks = parse_conflict_blocks(fpath)
            if not blocks:
                lines.append(f"No conflict markers in `{fpath}`.")
                continue

            lines.append(f"## Conflicts in `{fpath}` ({len(blocks)} block{'s' if len(blocks) != 1 else ''})\n")
            resolutions: list[str] = []

            for idx, block in enumerate(blocks, 1):
                lines.append(f"### Block {idx} (line {block.start_line})")
                lines.append("**Ours:**")
                lines.append(f"```\n{block.ours}\n```")
                lines.append("**Theirs:**")
                lines.append(f"```\n{block.theirs}\n```")
                lines.append("")

                # Auto-resolution: provide structured info for AI analysis
                if registry._session:
                    try:
                        from lidco.llm.base import Message as _LLMMsg
                        prompt = (
                            "You are resolving a git merge conflict. Choose the best resolution.\n\n"
                            f"File: {block.file}\n"
                        )
                        if block.context_before:
                            prompt += f"Context before:\n```\n{block.context_before}\n```\n\n"
                        prompt += (
                            f"<<<<<<< ours\n{block.ours}\n=======\n{block.theirs}\n>>>>>>> theirs\n\n"
                        )
                        if block.context_after:
                            prompt += f"Context after:\n```\n{block.context_after}\n```\n\n"
                        prompt += (
                            "Output ONLY the resolved code that should replace the conflict block. "
                            "No explanation, no markers."
                        )
                        resp = await registry._session.llm.complete(
                            [_LLMMsg(role="user", content=prompt)],
                            temperature=0.1,
                            max_tokens=512,
                        )
                        ai_resolution = (resp.content or "").strip()
                        resolutions.append(ai_resolution)
                        lines.append(f"**AI suggestion:**")
                        lines.append(f"```\n{ai_resolution}\n```")
                    except Exception as exc:
                        resolutions.append(block.ours)
                        lines.append(f"*(AI unavailable: {exc} — defaulting to ours)*")
                else:
                    resolutions.append(block.ours)

            lines.append("")

        return "\n".join(lines)

    registry.register(SlashCommand("conflict", "Resolve git merge conflicts with AI assistance", conflict_handler))
