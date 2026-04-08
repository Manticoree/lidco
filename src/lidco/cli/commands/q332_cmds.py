"""Q332 CLI commands — /review-patterns, /review-train, /review-style, /review-analytics

Registered via register_q332_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q332_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q332 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /review-patterns — Manage review feedback patterns
    # ------------------------------------------------------------------
    async def review_patterns_handler(args: str) -> str:
        """
        Usage: /review-patterns list [category|language|tag] [value]
               /review-patterns show <name>
               /review-patterns search <query>
               /review-patterns add <name> <description> <category> <severity>
        """
        from lidco.review_learn.patterns import (
            PatternCategory,
            PatternRegistry,
            ReviewPattern,
            Severity,
            create_default_registry,
        )

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /review-patterns <subcommand>\n"
                "  list [category|language|tag] [value]  list patterns\n"
                "  show <name>                           show pattern details\n"
                "  search <query>                        search patterns\n"
                "  add <name> <desc> <category> <sev>    add a pattern"
            )

        subcmd = parts[0].lower()
        reg = create_default_registry()

        if subcmd == "list":
            if len(parts) >= 3:
                filter_type = parts[1].lower()
                value = parts[2]
                if filter_type == "category":
                    try:
                        cat = PatternCategory(value)
                        patterns = reg.find_by_category(cat)
                    except ValueError:
                        return f"Unknown category: {value}. Valid: {', '.join(c.value for c in PatternCategory)}"
                elif filter_type == "language":
                    patterns = reg.find_by_language(value)
                elif filter_type == "tag":
                    patterns = reg.find_by_tag(value)
                else:
                    return f"Unknown filter: {filter_type}. Use category/language/tag."
            else:
                patterns = reg.list_all()

            if not patterns:
                return "No patterns found."
            lines = [f"Review Patterns ({len(patterns)}):"]
            for p in patterns:
                lines.append(f"  [{p.severity.value}] {p.name} — {p.description}")
            return "\n".join(lines)

        if subcmd == "show":
            if len(parts) < 2:
                return "Usage: /review-patterns show <name>"
            pattern = reg.get(parts[1])
            if pattern is None:
                return f"Pattern '{parts[1]}' not found."
            lines = [
                f"Pattern: {pattern.name}",
                f"Category: {pattern.category.value}",
                f"Severity: {pattern.severity.value}",
                f"Description: {pattern.description}",
            ]
            if pattern.languages:
                lines.append(f"Languages: {', '.join(pattern.languages)}")
            if pattern.example_bad:
                lines.append(f"Bad example:\n  {pattern.example_bad}")
            if pattern.example_good:
                lines.append(f"Good example:\n  {pattern.example_good}")
            if pattern.tags:
                lines.append(f"Tags: {', '.join(pattern.tags)}")
            return "\n".join(lines)

        if subcmd == "search":
            if len(parts) < 2:
                return "Usage: /review-patterns search <query>"
            query = " ".join(parts[1:])
            results = reg.search(query)
            if not results:
                return f"No patterns matching '{query}'."
            lines = [f"Search results ({len(results)}):"]
            for p in results:
                lines.append(f"  [{p.severity.value}] {p.name} — {p.description}")
            return "\n".join(lines)

        if subcmd == "add":
            if len(parts) < 5:
                return "Usage: /review-patterns add <name> <description> <category> <severity>"
            name = parts[1]
            desc = parts[2]
            try:
                cat = PatternCategory(parts[3])
                sev = Severity(parts[4])
            except ValueError as exc:
                return f"Invalid category or severity: {exc}"
            pattern = ReviewPattern(name=name, description=desc, category=cat, severity=sev)
            reg.add(pattern)
            return f"Added pattern '{name}' ({cat.value}, {sev.value})"

        return f"Unknown subcommand '{subcmd}'. Use list/show/search/add."

    registry.register_async("review-patterns", "Manage review feedback patterns", review_patterns_handler)

    # ------------------------------------------------------------------
    # /review-train — Practice code review with sample PRs
    # ------------------------------------------------------------------
    async def review_train_handler(args: str) -> str:
        """
        Usage: /review-train list [difficulty]
               /review-train start <pr-id>
               /review-train hints <pr-id>
               /review-train submit <pr-id> <issue1> [issue2] ...
               /review-train scores [pr-id]
        """
        from lidco.review_learn.trainer import Difficulty, ReviewSubmission, create_default_trainer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /review-train <subcommand>\n"
                "  list [difficulty]                    list sample PRs\n"
                "  start <pr-id>                        view a sample PR\n"
                "  hints <pr-id>                        get progressive hints\n"
                "  submit <pr-id> <issue1> [...]         submit review\n"
                "  scores [pr-id]                       view scores"
            )

        subcmd = parts[0].lower()
        trainer = create_default_trainer()

        if subcmd == "list":
            diff = None
            if len(parts) >= 2:
                try:
                    diff = Difficulty(parts[1].lower())
                except ValueError:
                    return f"Unknown difficulty: {parts[1]}. Valid: {', '.join(d.value for d in Difficulty)}"
            samples = trainer.list_samples(diff)
            if not samples:
                return "No sample PRs available."
            lines = [f"Sample PRs ({len(samples)}):"]
            for s in samples:
                lines.append(f"  {s.pr_id} [{s.difficulty.value}] {s.title} ({s.issue_count} issues)")
            return "\n".join(lines)

        if subcmd == "start":
            if len(parts) < 2:
                return "Usage: /review-train start <pr-id>"
            sample = trainer.get_sample(parts[1])
            if sample is None:
                return f"Sample PR '{parts[1]}' not found."
            lines = [
                f"PR: {sample.title}",
                f"Description: {sample.description}",
                f"Language: {sample.language}",
                f"Difficulty: {sample.difficulty.value}",
                f"Diff:\n{sample.diff}",
                f"\nFind the issues and submit with: /review-train submit {sample.pr_id} <issue1> ...",
            ]
            return "\n".join(lines)

        if subcmd == "hints":
            if len(parts) < 2:
                return "Usage: /review-train hints <pr-id>"
            hints = trainer.guided_hints(parts[1])
            if not hints:
                return f"No hints for '{parts[1]}' (sample not found or no issues)."
            lines = [f"Hints for {parts[1]}:"]
            for i, h in enumerate(hints, 1):
                lines.append(f"  {i}. {h}")
            return "\n".join(lines)

        if subcmd == "submit":
            if len(parts) < 3:
                return "Usage: /review-train submit <pr-id> <issue1> [issue2] ..."
            pr_id = parts[1]
            found = parts[2:]
            sub = ReviewSubmission(pr_id=pr_id, found_issues=found)
            try:
                score = trainer.submit_review(sub)
            except ValueError as exc:
                return f"Error: {exc}"
            return (
                f"Score: {score.score} (Grade: {score.grade})\n"
                f"Found: {score.issues_found}/{score.issues_total}\n"
                f"Precision: {score.precision}, Recall: {score.recall}\n"
                f"Feedback: {score.feedback}"
            )

        if subcmd == "scores":
            pr_id = parts[1] if len(parts) >= 2 else None
            scores = trainer.get_scores(pr_id)
            if not scores:
                return "No scores recorded yet."
            lines = [f"Training Scores ({len(scores)}):"]
            for s in scores:
                lines.append(f"  {s.pr_id}: {s.score} ({s.grade})")
            avg = trainer.average_score()
            lines.append(f"Average: {avg}")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use list/start/hints/submit/scores."

    registry.register_async("review-train", "Practice code review with sample PRs", review_train_handler)

    # ------------------------------------------------------------------
    # /review-style — Team review conventions and feedback templates
    # ------------------------------------------------------------------
    async def review_style_handler(args: str) -> str:
        """
        Usage: /review-style conventions
               /review-style templates [category]
               /review-style render <template-id> [key=value ...]
               /review-style add-convention <name> <description>
               /review-style add-template <id> <category> <tone> <template>
        """
        from lidco.review_learn.style import (
            FeedbackTemplate,
            StyleConvention,
            Tone,
            create_default_style_guide,
        )

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /review-style <subcommand>\n"
                "  conventions                          list conventions\n"
                "  templates [category]                 list templates\n"
                "  render <id> [key=value ...]           render a template\n"
                "  add-convention <name> <desc>          add convention\n"
                "  add-template <id> <cat> <tone> <tpl>  add template"
            )

        subcmd = parts[0].lower()
        guide = create_default_style_guide()

        if subcmd == "conventions":
            convs = guide.list_conventions()
            if not convs:
                return "No conventions defined."
            lines = [f"Review Conventions ({len(convs)}):"]
            for c in convs:
                lines.append(f"  [{c.priority}] {c.name} — {c.description}")
            return "\n".join(lines)

        if subcmd == "templates":
            category = parts[1] if len(parts) >= 2 else None
            templates = guide.list_templates(category=category)
            if not templates:
                return "No templates found."
            lines = [f"Feedback Templates ({len(templates)}):"]
            for t in templates:
                lines.append(f"  {t.template_id} [{t.tone.value}] ({t.category})")
            return "\n".join(lines)

        if subcmd == "render":
            if len(parts) < 2:
                return "Usage: /review-style render <template-id> [key=value ...]"
            template_id = parts[1]
            kwargs: dict[str, str] = {}
            for part in parts[2:]:
                if "=" in part:
                    k, v = part.split("=", 1)
                    kwargs[k] = v
            result = guide.render_feedback(template_id, **kwargs)
            if result is None:
                return f"Template '{template_id}' not found."
            return result

        if subcmd == "add-convention":
            if len(parts) < 3:
                return "Usage: /review-style add-convention <name> <description>"
            conv = StyleConvention(name=parts[1], description=" ".join(parts[2:]))
            guide.add_convention(conv)
            return f"Added convention '{parts[1]}'"

        if subcmd == "add-template":
            if len(parts) < 5:
                return "Usage: /review-style add-template <id> <category> <tone> <template>"
            tid = parts[1]
            cat = parts[2]
            try:
                tone = Tone(parts[3].lower())
            except ValueError:
                return f"Unknown tone: {parts[3]}. Valid: {', '.join(t.value for t in Tone)}"
            tpl = " ".join(parts[4:])
            template = FeedbackTemplate(template_id=tid, category=cat, tone=tone, template=tpl)
            guide.add_template(template)
            return f"Added template '{tid}' ({cat}, {tone.value})"

        return f"Unknown subcommand '{subcmd}'. Use conventions/templates/render/add-convention/add-template."

    registry.register_async("review-style", "Team review conventions and feedback templates", review_style_handler)

    # ------------------------------------------------------------------
    # /review-analytics — Review quality metrics and trends
    # ------------------------------------------------------------------
    async def review_analytics_handler(args: str) -> str:
        """
        Usage: /review-analytics summary
               /review-analytics reviewer <name>
               /review-analytics issues [top-n]
               /review-analytics trend [reviewer] [periods]
        """
        from lidco.review_learn.analytics import ReviewAnalytics, ReviewEvent

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /review-analytics <subcommand>\n"
                "  summary                          overall metrics\n"
                "  reviewer <name>                  reviewer stats\n"
                "  issues [top-n]                   common issues\n"
                "  trend [reviewer] [periods]       improvement trend"
            )

        subcmd = parts[0].lower()
        analytics = ReviewAnalytics()

        if subcmd == "summary":
            s = analytics.summary()
            return (
                f"Review Analytics Summary:\n"
                f"  Total reviews: {s['total_reviews']}\n"
                f"  Unique reviewers: {s['unique_reviewers']}\n"
                f"  Adoption rate: {s['adoption_rate']}\n"
                f"  Avg review time: {s['avg_review_time']}s\n"
                f"  Tracked issue types: {s['common_issues']}"
            )

        if subcmd == "reviewer":
            if len(parts) < 2:
                return "Usage: /review-analytics reviewer <name>"
            stats = analytics.reviewer_stats(parts[1])
            if stats is None:
                return f"No data for reviewer '{parts[1]}'."
            return (
                f"Reviewer: {stats.reviewer}\n"
                f"  Reviews: {stats.total_reviews}\n"
                f"  Issues found: {stats.total_issues}\n"
                f"  Issues adopted: {stats.total_adopted}\n"
                f"  Adoption rate: {stats.adoption_rate}\n"
                f"  Avg review time: {stats.avg_review_time}s"
            )

        if subcmd == "issues":
            top_n = int(parts[1]) if len(parts) >= 2 else 10
            issues = analytics.common_issues(top_n)
            if not issues:
                return "No issues tracked yet."
            lines = [f"Common Issues (top {top_n}):"]
            for iss in issues:
                lines.append(f"  {iss.issue_type}: {iss.count} occurrences (adoption: {iss.adoption_rate})")
            return "\n".join(lines)

        if subcmd == "trend":
            reviewer = parts[1] if len(parts) >= 2 else None
            periods = int(parts[2]) if len(parts) >= 3 else 5
            trend = analytics.improvement_trend(reviewer=reviewer, periods=periods)
            if not trend:
                return "No trend data available."
            lines = ["Improvement Trend:"]
            for tp in trend:
                bar = "#" * int(tp.value * 20)
                lines.append(f"  {tp.period}: {tp.value:.2%} {bar}")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use summary/reviewer/issues/trend."

    registry.register_async("review-analytics", "Review quality metrics and trends", review_analytics_handler)
