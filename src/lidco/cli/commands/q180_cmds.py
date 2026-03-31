"""CLI commands for Q180 — Code Review Intelligence."""

from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand


def register_q180_commands(registry) -> None:
    """Register /review-checklist, /style-check, /security-scan, /perf-check."""

    from lidco.review.checklist_gen import ReviewChecklistGenerator
    from lidco.review.style_checker import StyleConsistencyChecker
    from lidco.review.security_scanner import SecurityPatternScanner
    from lidco.review.perf_detector import PerfAntiPatternDetector

    async def review_checklist_handler(args: str) -> str:
        diff_text = args.strip()
        if not diff_text:
            return "Usage: /review-checklist <diff_text>"
        gen = ReviewChecklistGenerator()
        checklist = gen.generate(diff_text)
        return checklist.format()

    async def style_check_handler(args: str) -> str:
        source = args.strip()
        if not source:
            return "Usage: /style-check <source_code>"
        checker = StyleConsistencyChecker()
        report = checker.check(source)
        return report.format()

    async def security_scan_handler(args: str) -> str:
        source = args.strip()
        if not source:
            return "Usage: /security-scan <source_code>"
        scanner = SecurityPatternScanner()
        report = scanner.scan(source)
        return report.format()

    async def perf_check_handler(args: str) -> str:
        source = args.strip()
        if not source:
            return "Usage: /perf-check <source_code>"
        detector = PerfAntiPatternDetector()
        report = detector.detect(source)
        return report.format()

    registry.register(SlashCommand("review-checklist", "Generate review checklist from diff", review_checklist_handler))
    registry.register(SlashCommand("style-check", "Check code for style violations", style_check_handler))
    registry.register(SlashCommand("security-scan", "Scan code for security patterns", security_scan_handler))
    registry.register(SlashCommand("perf-check", "Detect performance anti-patterns", perf_check_handler))
