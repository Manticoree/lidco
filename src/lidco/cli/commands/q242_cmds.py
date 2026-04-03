"""Q242 CLI commands: /branch-tree, /branch-nav, /branch-compare, /branch-prune."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q242 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /branch-tree
    # ------------------------------------------------------------------

    async def branch_tree_handler(args: str) -> str:
        from lidco.conversation.branch_tree import BranchTree

        tree = BranchTree()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            parent = rest if rest else None
            branch_id = tree.add_branch(parent, [{"role": "user", "content": "new branch"}])
            return f"Created branch {branch_id}"

        if sub == "list":
            branches = tree.all_branches()
            if not branches:
                return "No branches."
            lines = [f"  {b.id} (depth={tree.depth(b.id)}, msgs={len(b.messages)})" for b in branches]
            return "Branches:\n" + "\n".join(lines)

        if sub == "show":
            if not rest:
                data = tree.to_dict()
                return f"Tree: {len(data.get('nodes', {}))} node(s)"
            node = tree.get_branch(rest)
            if node is None:
                return f"Branch '{rest}' not found."
            return (
                f"Branch {node.id}\n"
                f"  parent: {node.parent_id}\n"
                f"  messages: {len(node.messages)}\n"
                f"  created: {node.created_at}\n"
                f"  metadata: {node.metadata}"
            )

        return (
            "Usage: /branch-tree <subcommand>\n"
            "  show [id]     -- show tree or branch details\n"
            "  add [parent]  -- add a new branch\n"
            "  list          -- list all branches"
        )

    # ------------------------------------------------------------------
    # /branch-nav
    # ------------------------------------------------------------------

    async def branch_nav_handler(args: str) -> str:
        from lidco.conversation.branch_navigator import BranchNavigator
        from lidco.conversation.branch_tree import BranchTree

        tree = BranchTree()
        nav = BranchNavigator(tree)
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "jump":
            if not rest:
                return "Usage: /branch-nav jump <id>"
            ok = nav.jump(rest)
            return f"Jumped to {rest}" if ok else f"Branch '{rest}' not found."

        if sub == "back":
            ok = nav.back()
            current = nav.current
            if ok and current:
                return f"Moved back to {current.id}"
            return "Cannot move back (at root or no current branch)."

        if sub == "forward":
            idx = int(rest) if rest.isdigit() else 0
            ok = nav.forward(idx)
            current = nav.current
            if ok and current:
                return f"Moved forward to {current.id}"
            return "Cannot move forward (no children)."

        if sub == "breadcrumb":
            crumbs = nav.breadcrumb()
            if not crumbs:
                return "No breadcrumb (no current branch)."
            return " > ".join(crumbs)

        return (
            "Usage: /branch-nav <subcommand>\n"
            "  jump <id>        -- jump to branch\n"
            "  back             -- go to parent\n"
            "  forward [index]  -- go to child\n"
            "  breadcrumb       -- show path from root"
        )

    # ------------------------------------------------------------------
    # /branch-compare
    # ------------------------------------------------------------------

    async def branch_compare_handler(args: str) -> str:
        from lidco.conversation.branch_comparator import BranchComparator
        from lidco.conversation.branch_tree import BranchTree

        tree = BranchTree()
        comp = BranchComparator(tree)
        parts = args.strip().split()

        if len(parts) < 2:
            return "Usage: /branch-compare <id_a> <id_b>"

        id_a, id_b = parts[0], parts[1]
        node_a = tree.get_branch(id_a)
        node_b = tree.get_branch(id_b)
        if node_a is None or node_b is None:
            missing = id_a if node_a is None else id_b
            return f"Branch '{missing}' not found."

        result = comp.diff(id_a, id_b)
        cost = comp.cost_comparison(id_a, id_b)
        sim = comp.similarity(id_a, id_b)

        lines = [
            f"Comparing {id_a} vs {id_b}",
            f"  Divergence point: {result.divergence_point or 'none'}",
            f"  Common messages:  {len(result.common)}",
            f"  Unique to {id_a}: {len(result.unique_a)}",
            f"  Unique to {id_b}: {len(result.unique_b)}",
            f"  Msgs: {cost['message_count_a']} vs {cost['message_count_b']}",
            f"  Length: {cost['content_length_a']} vs {cost['content_length_b']}",
            f"  Similarity: {sim:.1%}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /branch-prune
    # ------------------------------------------------------------------

    async def branch_prune_handler(args: str) -> str:
        from lidco.conversation.branch_pruner import BranchPruner
        from lidco.conversation.branch_tree import BranchTree

        tree = BranchTree()
        pruner = BranchPruner(tree)
        parts = args.strip().split()
        sub = parts[0] if parts else ""

        if sub == "--dead":
            min_msgs = int(parts[1]) if len(parts) > 1 else 0
            result = pruner.prune_dead(min_msgs)
            return f"Pruned {result.removed_count} dead branch(es): {result.removed_ids}"

        if sub:
            branch_id = sub
            node = tree.get_branch(branch_id)
            if node is None:
                return f"Branch '{branch_id}' not found."
            savings = pruner.space_savings(branch_id)
            archive = pruner.archive(branch_id)
            result = pruner.prune(branch_id)
            return (
                f"Pruned {result.removed_count} branch(es): {result.removed_ids}\n"
                f"  Estimated savings: {savings} bytes\n"
                f"  Archived {len(archive.get('nodes', {}))} node(s)"
            )

        return (
            "Usage: /branch-prune <subcommand>\n"
            "  <id>          -- prune branch and descendants\n"
            "  --dead [min]  -- prune dead branches"
        )

    registry.register(SlashCommand("branch-tree", "Manage conversation branch tree", branch_tree_handler))
    registry.register(SlashCommand("branch-nav", "Navigate conversation branches", branch_nav_handler))
    registry.register(SlashCommand("branch-compare", "Compare two conversation branches", branch_compare_handler))
    registry.register(SlashCommand("branch-prune", "Prune conversation branches", branch_prune_handler))
