"""Q331 CLI commands -- /skills, /learning-path, /practice, /learning-progress

Registered via register_q331_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q331_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q331 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /skills -- Manage developer skill tracking
    # ------------------------------------------------------------------
    async def skills_handler(args: str) -> str:
        """
        Usage: /skills list [category]
               /skills add <name> [category]
               /skills record <name> [xp]
               /skills top [n]
               /skills weak [threshold]
               /skills snapshot
               /skills growth <name>
        """
        from lidco.learning.skills import SkillTracker

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /skills <subcommand>\n"
                "  list [category]        list all skills\n"
                "  add <name> [category]  add a new skill\n"
                "  record <name> [xp]     record skill usage\n"
                "  top [n]                show top skills\n"
                "  weak [threshold]       show weak skills\n"
                "  snapshot               take proficiency snapshot\n"
                "  growth <name>          show growth for a skill"
            )

        tracker = SkillTracker()
        subcmd = parts[0].lower()

        if subcmd == "list":
            cat = parts[1] if len(parts) > 1 else None
            skills = tracker.list_skills(cat)
            if not skills:
                return "No skills tracked."
            return tracker.format_summary()

        if subcmd == "add":
            if len(parts) < 2:
                return "Usage: /skills add <name> [category]"
            name = parts[1]
            cat = parts[2] if len(parts) > 2 else "language"
            entry = tracker.add_skill(name, cat)
            return f"Added skill '{entry.name}' [{entry.category}]"

        if subcmd == "record":
            if len(parts) < 2:
                return "Usage: /skills record <name> [xp]"
            name = parts[1]
            xp = int(parts[2]) if len(parts) > 2 else 10
            entry = tracker.record_usage(name, xp)
            return f"Recorded {xp} xp for '{entry.name}' (total={entry.xp}, level={entry.level()})"

        if subcmd == "top":
            n = int(parts[1]) if len(parts) > 1 else 5
            top = tracker.top_skills(n)
            if not top:
                return "No skills tracked."
            lines = [f"Top {n} skills:"]
            for s in top:
                lines.append(f"  {s.name}: {s.proficiency:.0%} ({s.level()})")
            return "\n".join(lines)

        if subcmd == "weak":
            threshold = float(parts[1]) if len(parts) > 1 else 0.3
            weak = tracker.weak_skills(threshold)
            if not weak:
                return "No weak skills found."
            lines = [f"Weak skills (< {threshold:.0%}):"]
            for s in weak:
                lines.append(f"  {s.name}: {s.proficiency:.0%}")
            return "\n".join(lines)

        if subcmd == "snapshot":
            snap = tracker.snapshot()
            return f"Snapshot taken at {snap.timestamp:.0f} with {len(snap.skills)} skills."

        if subcmd == "growth":
            if len(parts) < 2:
                return "Usage: /skills growth <name>"
            growth = tracker.growth(parts[1])
            if not growth:
                return f"No growth data for '{parts[1]}'."
            lines = [f"Growth for '{parts[1]}':"]
            for g in growth:
                lines.append(f"  t={g['timestamp']:.0f} proficiency={g['proficiency']:.0%}")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use list/add/record/top/weak/snapshot/growth."

    registry.register_async("skills", "Track developer skills and proficiency", skills_handler)

    # ------------------------------------------------------------------
    # /learning-path -- Personalized learning paths
    # ------------------------------------------------------------------
    async def learning_path_handler(args: str) -> str:
        """
        Usage: /learning-path generate <skill1,skill2,...>
               /learning-path show
               /learning-path complete <step_index>
               /learning-path next
        """
        from lidco.learning.path import LearningPathGenerator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /learning-path <subcommand>\n"
                "  generate <skill1,skill2,...>  generate path for skills\n"
                "  show                          show current path\n"
                "  complete <step_index>         mark step completed\n"
                "  next                          show next step"
            )

        subcmd = parts[0].lower()
        gen = LearningPathGenerator()

        if subcmd == "generate":
            if len(parts) < 2:
                return "Usage: /learning-path generate <skill1,skill2,...>"
            skills = [s.strip() for s in parts[1].split(",") if s.strip()]
            path = gen.generate(skills)
            return gen.format_path(path)

        if subcmd == "show":
            path = gen.generate([])
            return gen.format_path(path)

        if subcmd == "complete":
            if len(parts) < 2:
                return "Usage: /learning-path complete <step_index>"
            return f"Marked step {parts[1]} as completed."

        if subcmd == "next":
            return "No active path. Use /learning-path generate <skills> first."

        return f"Unknown subcommand '{subcmd}'. Use generate/show/complete/next."

    registry.register_async("learning-path", "Personalized learning paths", learning_path_handler)

    # ------------------------------------------------------------------
    # /practice -- Coding exercises
    # ------------------------------------------------------------------
    async def practice_handler(args: str) -> str:
        """
        Usage: /practice list [skill] [difficulty]
               /practice generate <pattern> <code>
               /practice show <exercise_id>
               /practice submit <exercise_id> <code>
               /practice stats
        """
        from lidco.learning.practice import PracticeGenerator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /practice <subcommand>\n"
                "  list [skill] [difficulty]       list exercises\n"
                "  generate <pattern> <code>       generate exercise from pattern\n"
                "  show <exercise_id>              show exercise details\n"
                "  submit <exercise_id> <code>     submit solution\n"
                "  stats                           show submission stats"
            )

        subcmd = parts[0].lower()
        gen = PracticeGenerator()

        if subcmd == "list":
            skill = parts[1] if len(parts) > 1 else None
            diff = int(parts[2]) if len(parts) > 2 else None
            exercises = gen.list_exercises(skill, diff)
            if not exercises:
                return "No exercises available."
            lines = [f"Exercises ({len(exercises)}):"]
            for e in exercises:
                lines.append(f"  [{e.exercise_id}] {e.title} (difficulty={e.difficulty}, skill={e.skill})")
            return "\n".join(lines)

        if subcmd == "generate":
            if len(parts) < 3:
                return "Usage: /practice generate <pattern> <code>"
            pattern = parts[1]
            code = " ".join(parts[2:])
            exercise = gen.generate_from_pattern(pattern, code)
            return f"Generated exercise [{exercise.exercise_id}]: {exercise.title} (difficulty={exercise.difficulty})"

        if subcmd == "show":
            if len(parts) < 2:
                return "Usage: /practice show <exercise_id>"
            ex = gen.get_exercise(parts[1])
            if ex is None:
                return f"Exercise '{parts[1]}' not found."
            return (
                f"Exercise: {ex.title}\n"
                f"Difficulty: {ex.difficulty}\n"
                f"Skill: {ex.skill}\n"
                f"Description: {ex.description}\n"
                f"Template:\n{ex.template}"
            )

        if subcmd == "submit":
            if len(parts) < 3:
                return "Usage: /practice submit <exercise_id> <code>"
            eid = parts[1]
            code = " ".join(parts[2:])
            sub = gen.submit(eid, code)
            status = "PASSED" if sub.passed else "FAILED"
            return f"Submission {status} (score={sub.score:.0%}): {sub.feedback}"

        if subcmd == "stats":
            return gen.format_summary()

        return f"Unknown subcommand '{subcmd}'. Use list/generate/show/submit/stats."

    registry.register_async("practice", "Coding exercises and practice", practice_handler)

    # ------------------------------------------------------------------
    # /learning-progress -- Learning progress dashboard
    # ------------------------------------------------------------------
    async def learning_progress_handler(args: str) -> str:
        """
        Usage: /learning-progress summary
               /learning-progress day <YYYY-MM-DD> [exercises] [xp]
               /learning-progress achievements
               /learning-progress streak <date1,date2,...>
        """
        from lidco.learning.progress import ProgressDashboard

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /learning-progress <subcommand>\n"
                "  summary                            show progress summary\n"
                "  day <YYYY-MM-DD> [exercises] [xp]  record daily activity\n"
                "  achievements                       list achievements\n"
                "  streak <date1,date2,...>            calculate streak"
            )

        subcmd = parts[0].lower()
        dash = ProgressDashboard()

        if subcmd == "summary":
            return dash.format_summary()

        if subcmd == "day":
            if len(parts) < 2:
                return "Usage: /learning-progress day <YYYY-MM-DD> [exercises] [xp]"
            date = parts[1]
            exercises = int(parts[2]) if len(parts) > 2 else 0
            xp = int(parts[3]) if len(parts) > 3 else 0
            entry = dash.record_day(date, exercises, xp)
            return (
                f"Recorded {date}: exercises={entry.exercises_completed}, xp={entry.xp_earned}"
            )

        if subcmd == "achievements":
            achs = dash.list_achievements()
            if not achs:
                return "No achievements registered."
            lines = ["Achievements:"]
            for a in achs:
                status = "unlocked" if a.unlocked else "locked"
                lines.append(f"  {a.name}: {a.description} [{status}]")
            return "\n".join(lines)

        if subcmd == "streak":
            if len(parts) < 2:
                return "Usage: /learning-progress streak <date1,date2,...>"
            dates = [d.strip() for d in parts[1].split(",") if d.strip()]
            s = dash.streak(dates)
            return f"Current streak: {s} days"

        return f"Unknown subcommand '{subcmd}'. Use summary/day/achievements/streak."

    registry.register_async("learning-progress", "Learning progress dashboard", learning_progress_handler)
