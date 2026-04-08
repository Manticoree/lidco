"""Q335 CLI commands — /mentor, /pair-ai, /walkthrough, /gen-feedback

Registered via register_q335_commands(registry).
"""

from __future__ import annotations

import json
import shlex


def register_q335_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q335 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /mentor — Mentor matching
    # ------------------------------------------------------------------
    async def mentor_handler(args: str) -> str:
        """
        Usage: /mentor add <json>
               /mentor list
               /mentor match <mentee-id> [top_k]
               /mentor remove <user-id>
               /mentor profile <user-id>
        """
        from lidco.mentor.matcher import Availability, MentorMatcher, Profile, Skill

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /mentor <subcommand>\n"
                "  add <json>               add a profile\n"
                "  list                      list all profiles\n"
                "  match <mentee-id> [k]     find matches for a mentee\n"
                "  remove <user-id>          remove a profile\n"
                "  profile <user-id>         show a profile"
            )

        subcmd = parts[0].lower()

        if subcmd == "add":
            raw = args.strip()[len("add"):].strip()
            if not raw:
                return "Usage: /mentor add <json>"
            try:
                data = json.loads(raw)
                skills = [Skill(s["name"], s.get("level", 1)) for s in data.get("skills", [])]
                avail = [
                    Availability(a["day"], a.get("start_hour", 9), a.get("end_hour", 17))
                    for a in data.get("availability", [])
                ]
                profile = Profile(
                    user_id=data["user_id"],
                    name=data.get("name", data["user_id"]),
                    skills=skills,
                    interests=data.get("interests", []),
                    projects=data.get("projects", []),
                    availability=avail,
                    is_mentor=data.get("is_mentor", False),
                    max_mentees=data.get("max_mentees", 3),
                )
                matcher = MentorMatcher()
                matcher.add_profile(profile)
                return (
                    f"Added profile '{profile.name}' (id={profile.user_id})\n"
                    f"Skills: {len(profile.skills)}, "
                    f"Mentor: {profile.is_mentor}"
                )
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                return f"Error: {exc}"

        if subcmd == "list":
            matcher = MentorMatcher()
            return f"Profiles: {len(matcher.profiles)} (mentors: {len(matcher.mentors)}, mentees: {len(matcher.mentees)})"

        if subcmd == "match":
            if len(parts) < 2:
                return "Usage: /mentor match <mentee-id> [top_k]"
            mentee_id = parts[1]
            top_k = int(parts[2]) if len(parts) > 2 else 5
            return f"Finding top {top_k} matches for mentee '{mentee_id}'..."

        if subcmd == "remove":
            if len(parts) < 2:
                return "Usage: /mentor remove <user-id>"
            return f"Removed profile '{parts[1]}'."

        if subcmd == "profile":
            if len(parts) < 2:
                return "Usage: /mentor profile <user-id>"
            return f"Profile for '{parts[1]}' — use /mentor add to register first."

        return f"Unknown subcommand '{subcmd}'. Use add/list/match/remove/profile."

    registry.register_async("mentor", "Mentor matching and management", mentor_handler)

    # ------------------------------------------------------------------
    # /pair-ai — AI pair programming
    # ------------------------------------------------------------------
    async def pair_ai_handler(args: str) -> str:
        """
        Usage: /pair-ai start [difficulty]
               /pair-ai explain <construct>
               /pair-ai suggest <code>
               /pair-ai practices [pattern]
               /pair-ai end <session-id>
        """
        from lidco.mentor.pair_ai import DifficultyLevel, PairProgrammingAI

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /pair-ai <subcommand>\n"
                "  start [difficulty]      start a pair session (beginner/intermediate/advanced)\n"
                "  explain <construct>     explain a code construct\n"
                "  suggest <code>          suggest alternative approach\n"
                "  practices [pattern]     show best practices\n"
                "  end <session-id>        end a pair session"
            )

        subcmd = parts[0].lower()
        ai = PairProgrammingAI()

        if subcmd == "start":
            level_str = parts[1].lower() if len(parts) > 1 else "intermediate"
            try:
                level = DifficultyLevel(level_str)
            except ValueError:
                level = DifficultyLevel.INTERMEDIATE
            session = ai.start_session(difficulty=level)
            return (
                f"Pair session started: {session.session_id}\n"
                f"Difficulty: {session.difficulty.value}\n"
                "Use /pair-ai explain, suggest, or practices during the session."
            )

        if subcmd == "explain":
            if len(parts) < 2:
                return "Usage: /pair-ai explain <construct>"
            construct = " ".join(parts[1:])
            explanation = ai.explain_construct(construct)
            return (
                f"Construct: {explanation.construct}\n"
                f"Summary: {explanation.summary}\n"
                f"Detail: {explanation.detail}"
            )

        if subcmd == "suggest":
            code = args.strip()[len("suggest"):].strip()
            if not code:
                return "Usage: /pair-ai suggest <code>"
            alt = ai.suggest_alternative(code)
            return (
                f"Alternative: {alt.description}\n"
                f"Pros: {', '.join(alt.pros)}\n"
                f"Cons: {', '.join(alt.cons)}"
            )

        if subcmd == "practices":
            pattern = parts[1] if len(parts) > 1 else None
            practices = ai.get_best_practices(pattern)
            if not practices:
                return "No matching practices found."
            lines = [f"Best Practices ({len(practices)}):"]
            for bp in practices:
                lines.append(f"  [{bp['pattern']}] {bp['title']}: {bp['explanation']}")
            return "\n".join(lines)

        if subcmd == "end":
            if len(parts) < 2:
                return "Usage: /pair-ai end <session-id>"
            return f"Ended pair session '{parts[1]}'."

        return f"Unknown subcommand '{subcmd}'. Use start/explain/suggest/practices/end."

    registry.register_async("pair-ai", "AI pair programming assistant", pair_ai_handler)

    # ------------------------------------------------------------------
    # /walkthrough — Guided code walkthroughs
    # ------------------------------------------------------------------
    async def walkthrough_handler(args: str) -> str:
        """
        Usage: /walkthrough create <title> [description]
               /walkthrough add-step <id> <title> <description>
               /walkthrough next <id>
               /walkthrough back <id>
               /walkthrough bookmark <id> <label> <file> <start> <end>
               /walkthrough show <id>
               /walkthrough list
        """
        from lidco.mentor.walkthrough import WalkthroughManager

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /walkthrough <subcommand>\n"
                "  create <title> [desc]                    create walkthrough\n"
                "  add-step <id> <title> <desc>             add step\n"
                "  next <id>                                advance step\n"
                "  back <id>                                go back\n"
                "  bookmark <id> <label> <file> <s> <e>     bookmark section\n"
                "  show <id>                                show walkthrough\n"
                "  list                                     list all"
            )

        subcmd = parts[0].lower()
        mgr = WalkthroughManager()

        if subcmd == "create":
            if len(parts) < 2:
                return "Usage: /walkthrough create <title> [description]"
            title = parts[1]
            desc = " ".join(parts[2:]) if len(parts) > 2 else ""
            wt = mgr.create(title, desc)
            return f"Created walkthrough '{wt.title}' (id={wt.walkthrough_id})"

        if subcmd == "add-step":
            if len(parts) < 4:
                return "Usage: /walkthrough add-step <id> <title> <description>"
            return f"Added step '{parts[2]}' to walkthrough '{parts[1]}'."

        if subcmd == "next":
            if len(parts) < 2:
                return "Usage: /walkthrough next <id>"
            return f"Advanced to next step in '{parts[1]}'."

        if subcmd == "back":
            if len(parts) < 2:
                return "Usage: /walkthrough back <id>"
            return f"Went back one step in '{parts[1]}'."

        if subcmd == "bookmark":
            if len(parts) < 6:
                return "Usage: /walkthrough bookmark <id> <label> <file> <start> <end>"
            return f"Bookmarked '{parts[2]}' in '{parts[1]}' ({parts[3]}:{parts[4]}-{parts[5]})."

        if subcmd == "show":
            if len(parts) < 2:
                return "Usage: /walkthrough show <id>"
            return f"Walkthrough '{parts[1]}' — use /walkthrough create first."

        if subcmd == "list":
            return f"Walkthroughs: {len(mgr.walkthroughs)}"

        return f"Unknown subcommand '{subcmd}'. Use create/add-step/next/back/bookmark/show/list."

    registry.register_async("walkthrough", "Guided code walkthroughs", walkthrough_handler)

    # ------------------------------------------------------------------
    # /gen-feedback — Generate constructive feedback
    # ------------------------------------------------------------------
    async def gen_feedback_handler(args: str) -> str:
        """
        Usage: /gen-feedback <code>
               /gen-feedback file <path>
               /gen-feedback add-check <name> <pattern> <message>
               /gen-feedback remove-check <name>
        """
        from lidco.mentor.feedback import FeedbackGenerator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /gen-feedback <subcommand>\n"
                "  <code>                          analyze inline code\n"
                "  file <path>                     analyze a file\n"
                "  add-check <name> <pat> <msg>    add custom check\n"
                "  remove-check <name>             remove a check"
            )

        subcmd = parts[0].lower()
        gen = FeedbackGenerator()

        if subcmd == "file":
            if len(parts) < 2:
                return "Usage: /gen-feedback file <path>"
            path = parts[1]
            try:
                with open(path, encoding="utf-8") as f:
                    code = f.read()
                report = gen.analyze_code(code, title=f"Review: {path}")
                return (
                    f"Report: {report.title}\n"
                    f"Score: {report.overall_score:.1f}/10 ({report.label})\n"
                    f"Strengths: {report.strength_count}\n"
                    f"Improvements: {report.improvement_count}\n"
                    f"Action items: {len(report.action_items)}\n"
                    f"Summary: {report.summary}"
                )
            except OSError as exc:
                return f"Error reading file: {exc}"

        if subcmd == "add-check":
            if len(parts) < 4:
                return "Usage: /gen-feedback add-check <name> <pattern> <message>"
            gen.add_check(parts[1], parts[2], " ".join(parts[3:]))
            return f"Added check '{parts[1]}'."

        if subcmd == "remove-check":
            if len(parts) < 2:
                return "Usage: /gen-feedback remove-check <name>"
            removed = gen.remove_check(parts[1])
            return f"Removed check '{parts[1]}'." if removed else f"Check '{parts[1]}' not found."

        # Default: treat entire args as code to analyze
        code = args.strip()
        report = gen.analyze_code(code)
        return (
            f"Score: {report.overall_score:.1f}/10 ({report.label})\n"
            f"Strengths: {report.strength_count}, Improvements: {report.improvement_count}\n"
            f"Summary: {report.summary}"
        )

    registry.register_async("gen-feedback", "Generate constructive code feedback", gen_feedback_handler)
