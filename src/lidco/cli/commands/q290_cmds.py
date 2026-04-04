"""
Q290 CLI commands — /gl-mr, /gl-issue, /gl-pipeline, /gl-wiki

Registered via register_q290_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q290_commands(registry) -> None:
    """Register Q290 GitLab slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /gl-mr — Merge request workflow
    # ------------------------------------------------------------------
    async def gl_mr_handler(args: str) -> str:
        """
        Usage: /gl-mr create <title> <source> [target]
               /gl-mr describe <diff-text>
               /gl-mr approve <mr_id>
               /gl-mr reviewers <mr_id> <user1,user2,...>
               /gl-mr discussions <mr_id>
        """
        from lidco.gitlab.mr_workflow import MRWorkflow

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /gl-mr <subcommand>\n"
                "  create <title> <source> [target]  create a merge request\n"
                "  describe <diff-text>              auto-describe from diff\n"
                "  approve <mr_id>                   approve a merge request\n"
                "  reviewers <mr_id> <users>         assign reviewers (comma-separated)\n"
                "  discussions <mr_id>               list discussions"
            )

        subcmd = parts[0].lower()
        wf = MRWorkflow()

        if subcmd == "create":
            if len(parts) < 3:
                return "Error: Usage: /gl-mr create <title> <source> [target]"
            title = parts[1]
            source = parts[2]
            target = parts[3] if len(parts) > 3 else "main"
            try:
                mr = wf.create_mr(title, "", source, target)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Created MR !{mr.id}: {mr.title} ({mr.source_branch} -> {mr.target_branch})"

        if subcmd == "describe":
            if len(parts) < 2:
                return "Error: Usage: /gl-mr describe <diff-text>"
            diff = " ".join(parts[1:])
            desc = wf.auto_describe(diff)
            return desc

        if subcmd == "approve":
            if len(parts) < 2:
                return "Error: Usage: /gl-mr approve <mr_id>"
            try:
                mr_id = int(parts[1])
            except ValueError:
                return "Error: mr_id must be an integer"
            try:
                wf.approve(mr_id)
            except (KeyError, ValueError) as exc:
                return f"Error: {exc}"
            return f"MR !{mr_id} approved."

        if subcmd == "reviewers":
            if len(parts) < 3:
                return "Error: Usage: /gl-mr reviewers <mr_id> <user1,user2,...>"
            try:
                mr_id = int(parts[1])
            except ValueError:
                return "Error: mr_id must be an integer"
            reviewers = [r.strip() for r in parts[2].split(",") if r.strip()]
            try:
                wf.assign_reviewers(mr_id, reviewers)
            except (KeyError, ValueError) as exc:
                return f"Error: {exc}"
            return f"Reviewers assigned to MR !{mr_id}."

        if subcmd == "discussions":
            if len(parts) < 2:
                return "Error: Usage: /gl-mr discussions <mr_id>"
            try:
                mr_id = int(parts[1])
            except ValueError:
                return "Error: mr_id must be an integer"
            try:
                discussions = wf.list_discussions(mr_id)
            except KeyError as exc:
                return f"Error: {exc}"
            if not discussions:
                return f"No discussions on MR !{mr_id}."
            return f"{len(discussions)} discussion(s) on MR !{mr_id}."

        return f"Unknown subcommand '{subcmd}'. Use create/describe/approve/reviewers/discussions."

    registry.register_async("gl-mr", "GitLab merge request workflow", gl_mr_handler)

    # ------------------------------------------------------------------
    # /gl-issue — GitLab issue commands (stub)
    # ------------------------------------------------------------------
    async def gl_issue_handler(args: str) -> str:
        """
        Usage: /gl-issue list [state]
               /gl-issue create <title>
               /gl-issue close <issue_id>
        """
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /gl-issue <subcommand>\n"
                "  list [state]      list issues (opened/closed/all)\n"
                "  create <title>    create an issue\n"
                "  close <issue_id>  close an issue"
            )

        subcmd = parts[0].lower()

        if subcmd == "list":
            state = parts[1] if len(parts) > 1 else "opened"
            return f"Listing GitLab issues with state={state} (simulated: 0 results)."

        if subcmd == "create":
            if len(parts) < 2:
                return "Error: Usage: /gl-issue create <title>"
            title = " ".join(parts[1:])
            return f"Created GitLab issue: {title} (simulated)."

        if subcmd == "close":
            if len(parts) < 2:
                return "Error: Usage: /gl-issue close <issue_id>"
            return f"Closed GitLab issue #{parts[1]} (simulated)."

        return f"Unknown subcommand '{subcmd}'. Use list/create/close."

    registry.register_async("gl-issue", "GitLab issue management", gl_issue_handler)

    # ------------------------------------------------------------------
    # /gl-pipeline — Pipeline monitor
    # ------------------------------------------------------------------
    async def gl_pipeline_handler(args: str) -> str:
        """
        Usage: /gl-pipeline list <project_id>
               /gl-pipeline status <pipeline_id>
               /gl-pipeline logs <job_id>
               /gl-pipeline retry <job_id>
        """
        from lidco.gitlab.pipeline import PipelineMonitor

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /gl-pipeline <subcommand>\n"
                "  list <project_id>     list pipelines for project\n"
                "  status <pipeline_id>  show pipeline status\n"
                "  logs <job_id>         show job logs\n"
                "  retry <job_id>        retry a failed job"
            )

        subcmd = parts[0].lower()
        mon = PipelineMonitor()

        if subcmd == "list":
            if len(parts) < 2:
                return "Error: Usage: /gl-pipeline list <project_id>"
            try:
                project_id = int(parts[1])
            except ValueError:
                return "Error: project_id must be an integer"
            pipelines = mon.list_pipelines(project_id)
            if not pipelines:
                return f"No pipelines found for project {project_id}."
            return f"{len(pipelines)} pipeline(s) for project {project_id}."

        if subcmd == "status":
            if len(parts) < 2:
                return "Error: Usage: /gl-pipeline status <pipeline_id>"
            try:
                pid = int(parts[1])
            except ValueError:
                return "Error: pipeline_id must be an integer"
            try:
                pipeline = mon.get_pipeline(pid)
            except KeyError as exc:
                return f"Error: {exc}"
            return f"Pipeline #{pipeline.id}: {pipeline.status} (ref={pipeline.ref})"

        if subcmd == "logs":
            if len(parts) < 2:
                return "Error: Usage: /gl-pipeline logs <job_id>"
            try:
                jid = int(parts[1])
            except ValueError:
                return "Error: job_id must be an integer"
            try:
                log = mon.job_logs(jid)
            except KeyError as exc:
                return f"Error: {exc}"
            return log if log else "(empty log)"

        if subcmd == "retry":
            if len(parts) < 2:
                return "Error: Usage: /gl-pipeline retry <job_id>"
            try:
                jid = int(parts[1])
            except ValueError:
                return "Error: job_id must be an integer"
            try:
                mon.retry_job(jid)
            except (KeyError, ValueError) as exc:
                return f"Error: {exc}"
            return f"Job {jid} retried."

        return f"Unknown subcommand '{subcmd}'. Use list/status/logs/retry."

    registry.register_async("gl-pipeline", "GitLab CI/CD pipeline monitor", gl_pipeline_handler)

    # ------------------------------------------------------------------
    # /gl-wiki — Wiki page management
    # ------------------------------------------------------------------
    async def gl_wiki_handler(args: str) -> str:
        """
        Usage: /gl-wiki list
               /gl-wiki get <slug>
               /gl-wiki create <title> <content>
               /gl-wiki update <slug> <content>
               /gl-wiki search <query>
        """
        from lidco.gitlab.wiki import GitLabWiki

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /gl-wiki <subcommand>\n"
                "  list                  list all wiki pages\n"
                "  get <slug>            get a wiki page\n"
                "  create <title> <content>  create a page\n"
                "  update <slug> <content>   update a page\n"
                "  search <query>        search wiki pages"
            )

        subcmd = parts[0].lower()
        wiki = GitLabWiki()

        if subcmd == "list":
            pages = wiki.list_pages()
            if not pages:
                return "No wiki pages."
            return "\n".join(f"  {p.slug}: {p.title}" for p in pages)

        if subcmd == "get":
            if len(parts) < 2:
                return "Error: Usage: /gl-wiki get <slug>"
            try:
                page = wiki.get_page(parts[1])
            except KeyError as exc:
                return f"Error: {exc}"
            return f"# {page.title}\n\n{page.content}"

        if subcmd == "create":
            if len(parts) < 3:
                return "Error: Usage: /gl-wiki create <title> <content>"
            title = parts[1]
            content = " ".join(parts[2:])
            try:
                page = wiki.create_page(title, content)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Created wiki page '{page.slug}'."

        if subcmd == "update":
            if len(parts) < 3:
                return "Error: Usage: /gl-wiki update <slug> <content>"
            slug = parts[1]
            content = " ".join(parts[2:])
            try:
                page = wiki.update_page(slug, content)
            except KeyError as exc:
                return f"Error: {exc}"
            return f"Updated wiki page '{page.slug}'."

        if subcmd == "search":
            if len(parts) < 2:
                return "Error: Usage: /gl-wiki search <query>"
            query = " ".join(parts[1:])
            results = wiki.search(query)
            if not results:
                return "No wiki pages matched."
            return "\n".join(f"  {p.slug}: {p.title}" for p in results)

        return f"Unknown subcommand '{subcmd}'. Use list/get/create/update/search."

    registry.register_async("gl-wiki", "GitLab wiki page management", gl_wiki_handler)
