"""Q334 CLI commands — /analyze-writing, /improve-writing, /writing-template, /glossary

Registered via register_q334_commands(registry).
"""

from __future__ import annotations

import json
import shlex


def register_q334_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q334 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /analyze-writing — Analyze technical writing quality
    # ------------------------------------------------------------------
    async def analyze_writing_handler(args: str) -> str:
        """
        Usage: /analyze-writing <text>
               /analyze-writing readability <text>
               /analyze-writing jargon <text>
               /analyze-writing tone <text>
               /analyze-writing consistency <text>
        """
        from lidco.writing.analyzer import WritingAnalyzer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /analyze-writing <subcommand> <text>\n"
                "  <text>                    full analysis\n"
                "  readability <text>        readability score\n"
                "  jargon <text>             detect jargon\n"
                "  tone <text>               analyze tone\n"
                "  consistency <text>        check consistency"
            )

        analyzer = WritingAnalyzer()
        subcmd = parts[0].lower()

        if subcmd == "readability":
            text = args.strip()[len("readability"):].strip()
            if not text:
                return "Usage: /analyze-writing readability <text>"
            score = analyzer.readability(text)
            return (
                f"Readability: {score.label}\n"
                f"Grade level: {score.grade_level}\n"
                f"Reading ease: {score.reading_ease}\n"
                f"Avg sentence length: {score.avg_sentence_length} words\n"
                f"Avg syllables/word: {score.avg_syllables_per_word}"
            )

        if subcmd == "jargon":
            text = args.strip()[len("jargon"):].strip()
            if not text:
                return "Usage: /analyze-writing jargon <text>"
            matches = analyzer.detect_jargon(text)
            if not matches:
                return "No jargon detected."
            lines = [f"Jargon detected ({len(matches)}):"]
            for m in matches:
                lines.append(f"  L{m.line}: '{m.term}' -> '{m.suggestion}'")
            return "\n".join(lines)

        if subcmd == "tone":
            text = args.strip()[len("tone"):].strip()
            if not text:
                return "Usage: /analyze-writing tone <text>"
            tone = analyzer.analyze_tone(text)
            return (
                f"Tone: {tone.label}\n"
                f"Formality: {tone.formality}\n"
                f"Confidence: {tone.confidence}"
            )

        if subcmd == "consistency":
            text = args.strip()[len("consistency"):].strip()
            if not text:
                return "Usage: /analyze-writing consistency <text>"
            issues = analyzer.check_consistency(text)
            if not issues:
                return "No consistency issues found."
            lines = [f"Consistency issues ({len(issues)}):"]
            for iss in issues:
                lines.append(
                    f"  '{iss.variant}' used {iss.occurrences}x, "
                    f"prefer '{iss.preferred}'"
                )
            return "\n".join(lines)

        # Default: full analysis
        text = args.strip()
        result = analyzer.analyze(text)
        lines = [
            f"Words: {result.word_count}, Sentences: {result.sentence_count}",
            f"Readability: {result.readability.label} (ease={result.readability.reading_ease})",
            f"Tone: {result.tone.label} (formality={result.tone.formality})",
            f"Jargon hits: {len(result.jargon)}",
            f"Consistency issues: {len(result.consistency_issues)}",
        ]
        return "\n".join(lines)

    registry.register_async("analyze-writing", "Analyze technical writing quality", analyze_writing_handler)

    # ------------------------------------------------------------------
    # /improve-writing — Suggest writing improvements
    # ------------------------------------------------------------------
    async def improve_writing_handler(args: str) -> str:
        """
        Usage: /improve-writing <text>
               /improve-writing simplify <text>
               /improve-writing grammar <text>
               /improve-writing structure <text>
               /improve-writing examples <text>
        """
        from lidco.writing.improver import WritingImprover

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /improve-writing <subcommand> <text>\n"
                "  <text>                    full improvement\n"
                "  simplify <text>           simplify verbose phrases\n"
                "  grammar <text>            fix grammar/spelling\n"
                "  structure <text>          check structure\n"
                "  examples <text>           suggest examples"
            )

        improver = WritingImprover()
        subcmd = parts[0].lower()

        if subcmd == "simplify":
            text = args.strip()[len("simplify"):].strip()
            if not text:
                return "Usage: /improve-writing simplify <text>"
            suggestions = improver.simplify(text)
            if not suggestions:
                return "No simplification suggestions."
            lines = [f"Simplifications ({len(suggestions)}):"]
            for s in suggestions:
                lines.append(f"  L{s.line}: '{s.original}' -> '{s.replacement}'")
            return "\n".join(lines)

        if subcmd == "grammar":
            text = args.strip()[len("grammar"):].strip()
            if not text:
                return "Usage: /improve-writing grammar <text>"
            suggestions = improver.fix_grammar(text)
            if not suggestions:
                return "No grammar issues found."
            lines = [f"Grammar issues ({len(suggestions)}):"]
            for s in suggestions:
                lines.append(f"  L{s.line}: '{s.original}' -> '{s.replacement}'")
            return "\n".join(lines)

        if subcmd == "structure":
            text = args.strip()[len("structure"):].strip()
            if not text:
                return "Usage: /improve-writing structure <text>"
            suggestions = improver.check_structure(text)
            if not suggestions:
                return "Structure looks good."
            lines = [f"Structure issues ({len(suggestions)}):"]
            for s in suggestions:
                lines.append(f"  L{s.line}: {s.reason}")
            return "\n".join(lines)

        if subcmd == "examples":
            text = args.strip()[len("examples"):].strip()
            if not text:
                return "Usage: /improve-writing examples <text>"
            suggestions = improver.suggest_examples(text)
            if not suggestions:
                return "No example suggestions."
            lines = [f"Example suggestions ({len(suggestions)}):"]
            for s in suggestions:
                lines.append(f"  L{s.line}: {s.reason}")
            return "\n".join(lines)

        # Default: full improvement
        text = args.strip()
        result = improver.improve(text)
        lines = [
            f"Suggestions: {result.suggestion_count}",
            f"Original words: {result.original_word_count}",
            f"Simplified words: {result.simplified_word_count}",
        ]
        if result.suggestions:
            lines.append("Top suggestions:")
            for s in result.suggestions[:5]:
                lines.append(f"  [{s.category}] L{s.line}: '{s.original}' -> '{s.replacement}'")
        return "\n".join(lines)

    registry.register_async("improve-writing", "Suggest writing improvements", improve_writing_handler)

    # ------------------------------------------------------------------
    # /writing-template — Writing templates
    # ------------------------------------------------------------------
    async def writing_template_handler(args: str) -> str:
        """
        Usage: /writing-template list
               /writing-template show <name>
               /writing-template render <name> [key=value ...]
        """
        from lidco.writing.templates import TemplateLibrary

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /writing-template <subcommand>\n"
                "  list                       list all templates\n"
                "  show <name>                show template details\n"
                "  render <name> [k=v ...]    render a template"
            )

        lib = TemplateLibrary()
        subcmd = parts[0].lower()

        if subcmd == "list":
            templates = lib.list_templates()
            lines = [f"Templates ({len(templates)}):"]
            for tpl in templates:
                lines.append(f"  {tpl.name}: {tpl.description}")
            return "\n".join(lines)

        if subcmd == "show":
            if len(parts) < 2:
                return "Usage: /writing-template show <name>"
            name = parts[1]
            tpl = lib.get(name)
            if tpl is None:
                return f"Template '{name}' not found."
            lines = [f"Template: {tpl.name}", f"Description: {tpl.description}", "Sections:"]
            for sec in tpl.sections:
                req = " (required)" if sec.required else " (optional)"
                lines.append(f"  - {sec.title}{req}")
            if tpl.variables:
                lines.append(f"Variables: {', '.join(tpl.variables)}")
            return "\n".join(lines)

        if subcmd == "render":
            if len(parts) < 2:
                return "Usage: /writing-template render <name> [key=value ...]"
            name = parts[1]
            values: dict[str, str] = {}
            for kv in parts[2:]:
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    values[k] = v
            rendered = lib.render(name, values)
            if rendered is None:
                return f"Template '{name}' not found."
            return rendered

        return f"Unknown subcommand '{subcmd}'. Use list/show/render."

    registry.register_async("writing-template", "Writing templates (RFC, design doc, etc.)", writing_template_handler)

    # ------------------------------------------------------------------
    # /glossary — Project glossary management
    # ------------------------------------------------------------------
    async def glossary_handler(args: str) -> str:
        """
        Usage: /glossary list
               /glossary add <term> <definition>
               /glossary remove <term>
               /glossary search <query>
               /glossary scan <text>
               /glossary export
               /glossary import <json>
        """
        from lidco.writing.glossary import GlossaryEntry, GlossaryManager

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /glossary <subcommand>\n"
                "  list                       list all terms\n"
                "  add <term> <definition>    add a term\n"
                "  remove <term>              remove a term\n"
                "  search <query>             search glossary\n"
                "  scan <text>                scan text for terms\n"
                "  export                     export as JSON\n"
                "  import <json>              import from JSON"
            )

        mgr = GlossaryManager()
        subcmd = parts[0].lower()

        if subcmd == "list":
            entries = mgr.list_entries()
            if not entries:
                return "Glossary is empty."
            lines = [f"Glossary ({len(entries)} terms):"]
            for e in entries:
                lines.append(f"  {e.term}: {e.definition}")
            return "\n".join(lines)

        if subcmd == "add":
            if len(parts) < 3:
                return "Usage: /glossary add <term> <definition>"
            term = parts[1]
            definition = " ".join(parts[2:])
            mgr.add(GlossaryEntry(term=term, definition=definition))
            return f"Added '{term}' to glossary."

        if subcmd == "remove":
            if len(parts) < 2:
                return "Usage: /glossary remove <term>"
            term = parts[1]
            if mgr.remove(term):
                return f"Removed '{term}' from glossary."
            return f"Term '{term}' not found."

        if subcmd == "search":
            if len(parts) < 2:
                return "Usage: /glossary search <query>"
            query = " ".join(parts[1:])
            results = mgr.search(query)
            if not results:
                return f"No results for '{query}'."
            lines = [f"Results ({len(results)}):"]
            for e in results:
                lines.append(f"  {e.term}: {e.definition}")
            return "\n".join(lines)

        if subcmd == "scan":
            text = args.strip()[len("scan"):].strip()
            if not text:
                return "Usage: /glossary scan <text>"
            report = mgr.scan(text)
            lines = [
                f"Defined terms found: {len(report.defined_terms_found)}",
                f"Undefined terms: {len(report.undefined_terms)}",
                f"Consistency violations: {len(report.consistency_violations)}",
            ]
            return "\n".join(lines)

        if subcmd == "export":
            return mgr.export_json()

        if subcmd == "import":
            raw = args.strip()[len("import"):].strip()
            if not raw:
                return "Usage: /glossary import <json>"
            try:
                count = mgr.import_json(raw)
                return f"Imported {count} entries."
            except (json.JSONDecodeError, KeyError) as exc:
                return f"Error: {exc}"

        return f"Unknown subcommand '{subcmd}'. Use list/add/remove/search/scan/export/import."

    registry.register_async("glossary", "Project glossary management", glossary_handler)
