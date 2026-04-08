"""
Q309 CLI commands — /visual-capture, /visual-diff, /visual-baseline, /visual-report

Registered via register_q309_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q309_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q309 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /visual-capture — Capture screenshots
    # ------------------------------------------------------------------
    async def visual_capture_handler(args: str) -> str:
        """
        Usage: /visual-capture <url> [--selector SEL] [--device DEV]
               /visual-capture <url> --full-page
               /visual-capture devices
        """
        from lidco.visual_test.capture import CaptureOptions, ScreenshotCapture, ViewportConfig

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /visual-capture <url> [--selector SEL] [--device DEV] [--full-page]\n"
                "       /visual-capture devices — list available device profiles"
            )

        cap = ScreenshotCapture()

        if parts[0] == "devices":
            devices = cap.list_devices()
            if not devices:
                return "No device profiles registered."
            return "Device profiles:\n" + "\n".join(f"  {d}" for d in devices)

        url = parts[0]
        selector = ""
        device_name = ""
        full_page = False

        i = 1
        while i < len(parts):
            if parts[i] == "--selector" and i + 1 < len(parts):
                selector = parts[i + 1]
                i += 2
            elif parts[i] == "--device" and i + 1 < len(parts):
                device_name = parts[i + 1]
                i += 2
            elif parts[i] == "--full-page":
                full_page = True
                i += 1
            else:
                i += 1

        device = cap.devices.get(device_name) if device_name else None
        opts = CaptureOptions(
            url=url, selector=selector, device=device, full_page=full_page,
        )
        result = cap.capture(opts)

        if not result.ok:
            return f"Capture failed: {result.error}"

        name = url.replace("://", "_").replace("/", "_")[:50]
        path = cap.save(result, name)
        return (
            f"Captured: {result.url}\n"
            f"Size: {result.width}x{result.height}\n"
            f"SHA256: {result.sha256[:16]}\n"
            f"Saved: {path}"
        )

    registry.register_async("visual-capture", "Capture screenshots for visual testing", visual_capture_handler)

    # ------------------------------------------------------------------
    # /visual-diff — Compare two images
    # ------------------------------------------------------------------
    async def visual_diff_handler(args: str) -> str:
        """
        Usage: /visual-diff <baseline_path> <current_path> [--tolerance N] [--threshold N]
        """
        from lidco.visual_test.diff import DiffOptions, VisualDiffEngine

        parts = shlex.split(args) if args.strip() else []
        if len(parts) < 2:
            return (
                "Usage: /visual-diff <baseline_path> <current_path> "
                "[--tolerance 0.0-1.0] [--threshold 0.0-1.0]"
            )

        baseline_path = parts[0]
        current_path = parts[1]

        tolerance = 0.0
        threshold = 0.01
        i = 2
        while i < len(parts):
            if parts[i] == "--tolerance" and i + 1 < len(parts):
                tolerance = float(parts[i + 1])
                i += 2
            elif parts[i] == "--threshold" and i + 1 < len(parts):
                threshold = float(parts[i + 1])
                i += 2
            else:
                i += 1

        from pathlib import Path
        bp = Path(baseline_path)
        cp = Path(current_path)
        if not bp.exists():
            return f"Baseline not found: {baseline_path}"
        if not cp.exists():
            return f"Current not found: {current_path}"

        b_data = bp.read_bytes()
        c_data = cp.read_bytes()

        engine = VisualDiffEngine()
        opts = DiffOptions(tolerance=tolerance, threshold=threshold)
        # Assume square for raw comparison; real use would parse image headers
        size = max(1, int(len(b_data) ** 0.5 // 2))
        result = engine.compare_raw(b_data, c_data, size, size, opts)

        status = "MATCH" if result.match else "DIFF"
        return (
            f"Status: {status}\n"
            f"Diff pixels: {result.diff_pixels}/{result.total_pixels}\n"
            f"Diff percentage: {result.diff_percentage}%\n"
            f"Dimensions match: {result.dimensions_match}"
        )

    registry.register_async("visual-diff", "Compare images for visual differences", visual_diff_handler)

    # ------------------------------------------------------------------
    # /visual-baseline — Manage baselines
    # ------------------------------------------------------------------
    async def visual_baseline_handler(args: str) -> str:
        """
        Usage: /visual-baseline list [branch]
               /visual-baseline store <name> <branch> <image_path>
               /visual-baseline delete <name> <branch>
               /visual-baseline pending
               /visual-baseline approve <name> <branch>
               /visual-baseline merge <source> <target>
        """
        from lidco.visual_test.baseline import BaselineManager

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /visual-baseline <subcommand>\n"
                "  list [branch]                    list baselines\n"
                "  store <name> <branch> <path>     store baseline image\n"
                "  delete <name> <branch>           delete baseline\n"
                "  pending                          show pending approvals\n"
                "  approve <name> <branch>          approve pending update\n"
                "  merge <source> <target>          merge baselines between branches"
            )

        mgr = BaselineManager()
        subcmd = parts[0].lower()

        if subcmd == "list":
            branch = parts[1] if len(parts) > 1 else None
            baselines = mgr.list_baselines(branch)
            if not baselines:
                return "No baselines found."
            lines = [f"Baselines ({len(baselines)}):"]
            for b in baselines:
                approved = "approved" if b.approved else "pending"
                lines.append(f"  {b.name} [{b.branch}] {b.sha256[:12]} ({approved})")
            return "\n".join(lines)

        if subcmd == "store":
            if len(parts) < 4:
                return "Usage: /visual-baseline store <name> <branch> <image_path>"
            name, branch, img_path = parts[1], parts[2], parts[3]
            from pathlib import Path
            p = Path(img_path)
            if not p.exists():
                return f"Image not found: {img_path}"
            data = p.read_bytes()
            entry = mgr.store(name, branch, data, width=0, height=0)
            return f"Stored baseline '{entry.name}' on branch '{entry.branch}' (sha={entry.sha256[:12]})"

        if subcmd == "delete":
            if len(parts) < 3:
                return "Usage: /visual-baseline delete <name> <branch>"
            deleted = mgr.delete(parts[1], parts[2])
            return f"Deleted: {deleted}"

        if subcmd == "pending":
            pending = mgr.pending_approvals
            if not pending:
                return "No pending approvals."
            lines = [f"Pending approvals ({len(pending)}):"]
            for r in pending:
                lines.append(f"  {r.name} [{r.branch}] diff={r.diff_percentage:.2f}%")
            return "\n".join(lines)

        if subcmd == "approve":
            if len(parts) < 3:
                return "Usage: /visual-baseline approve <name> <branch>"
            ok = mgr.approve(parts[1], parts[2])
            return f"Approved: {ok}"

        if subcmd == "merge":
            if len(parts) < 3:
                return "Usage: /visual-baseline merge <source_branch> <target_branch>"
            result = mgr.merge_baselines(parts[1], parts[2])
            return (
                f"Merged {result.merged_count} baseline(s). "
                f"Skipped: {len(result.skipped)}. Errors: {len(result.errors)}."
            )

        return f"Unknown subcommand '{subcmd}'. Use list/store/delete/pending/approve/merge."

    registry.register_async("visual-baseline", "Manage visual regression baselines", visual_baseline_handler)

    # ------------------------------------------------------------------
    # /visual-report — Generate visual test reports
    # ------------------------------------------------------------------
    async def visual_report_handler(args: str) -> str:
        """
        Usage: /visual-report generate [--title TITLE] [--ci]
               /visual-report json
               /visual-report summary
        """
        from lidco.visual_test.report import ReportConfig, ReportEntry, VisualTestReport

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /visual-report <subcommand>\n"
                "  generate [--title TITLE] [--ci]  generate HTML report\n"
                "  json                             export JSON report\n"
                "  summary                          show report summary"
            )

        # For demo, create an empty report
        title = "Visual Regression Report"
        ci_mode = False
        i = 1
        while i < len(parts):
            if parts[i] == "--title" and i + 1 < len(parts):
                title = parts[i + 1]
                i += 2
            elif parts[i] == "--ci":
                ci_mode = True
                i += 1
            else:
                i += 1

        config = ReportConfig(title=title, ci_mode=ci_mode)
        report = VisualTestReport(config)

        subcmd = parts[0].lower()

        if subcmd == "generate":
            path = report.save_html()
            exit_info = f" CI exit code: {report.ci_exit_code()}" if ci_mode else ""
            return f"Report generated: {path}{exit_info}"

        if subcmd == "json":
            path = report.save_json()
            return f"JSON report saved: {path}"

        if subcmd == "summary":
            s = report.summary()
            return (
                f"Total: {s.total}, Passed: {s.passed}, "
                f"Failed: {s.failed}, New: {s.new_baselines}, Errors: {s.errors}"
            )

        return f"Unknown subcommand '{subcmd}'. Use generate/json/summary."

    registry.register_async("visual-report", "Generate visual regression test reports", visual_report_handler)
