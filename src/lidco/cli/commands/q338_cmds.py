"""Q338 CLI commands — /marketplace-v2, /theme-gallery, /share-recipe, /community

Registered via register_q338_commands(registry).
"""
from __future__ import annotations

import json
import shlex


def register_q338_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q338 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /marketplace-v2 — Plugin Marketplace v2
    # ------------------------------------------------------------------
    async def marketplace_v2_handler(args: str) -> str:
        """
        Usage: /marketplace-v2 browse [category]
               /marketplace-v2 search <query>
               /marketplace-v2 publish <json>
               /marketplace-v2 review <name> <rating> [comment]
               /marketplace-v2 download <name>
               /marketplace-v2 update-check <name> <version>
               /marketplace-v2 compat <name>
               /marketplace-v2 stats
        """
        from lidco.community.marketplace import (
            MarketplacePlugin,
            PluginMarketplaceV2,
            PluginReview,
        )

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /marketplace-v2 <subcommand>\n"
                "  browse [category]                  browse plugins\n"
                "  search <query>                     search plugins\n"
                "  publish <json>                     publish a plugin\n"
                "  review <name> <rating> [comment]   review a plugin\n"
                "  download <name>                    record download\n"
                "  update-check <name> <version>      check for updates\n"
                "  compat <name>                      show compatibility\n"
                "  stats                              marketplace stats"
            )

        subcmd = parts[0].lower()
        mp = PluginMarketplaceV2()

        if subcmd == "browse":
            category = parts[1] if len(parts) > 1 else None
            plugins = mp.browse(category=category)
            if not plugins:
                return "No plugins found."
            lines = [f"Plugins ({len(plugins)}):"]
            for p in plugins:
                lines.append(f"  {p.name} v{p.version} by {p.author} ({p.downloads} downloads)")
            return "\n".join(lines)

        if subcmd == "search":
            if len(parts) < 2:
                return "Usage: /marketplace-v2 search <query>"
            query = " ".join(parts[1:])
            results = mp.search(query)
            if not results:
                return f"No plugins matching '{query}'."
            lines = [f"Results ({len(results)}):"]
            for p in results:
                lines.append(f"  {p.name} v{p.version} — {p.description}")
            return "\n".join(lines)

        if subcmd == "publish":
            raw = args.strip()[len("publish"):].strip()
            if not raw:
                return "Usage: /marketplace-v2 publish <json>"
            try:
                data = json.loads(raw)
                plugin = MarketplacePlugin(
                    name=data["name"],
                    version=data.get("version", "1.0.0"),
                    description=data.get("description", ""),
                    author=data.get("author", "anonymous"),
                    category=data.get("category", "general"),
                )
                mp.publish(plugin)
                return f"Published '{plugin.name}' v{plugin.version} by {plugin.author}"
            except (json.JSONDecodeError, KeyError) as exc:
                return f"Error: {exc}"

        if subcmd == "review":
            if len(parts) < 3:
                return "Usage: /marketplace-v2 review <name> <rating> [comment]"
            name = parts[1]
            try:
                rating = int(parts[2])
            except ValueError:
                return "Rating must be an integer 1-5."
            comment = " ".join(parts[3:]) if len(parts) > 3 else ""
            try:
                review = PluginReview(author="cli-user", rating=rating, comment=comment)
            except ValueError as exc:
                return str(exc)
            ok = mp.add_review(name, review)
            if not ok:
                return f"Plugin '{name}' not found."
            return f"Reviewed '{name}' with {rating}/5."

        if subcmd == "download":
            if len(parts) < 2:
                return "Usage: /marketplace-v2 download <name>"
            ok = mp.record_download(parts[1])
            if not ok:
                return f"Plugin '{parts[1]}' not found."
            return f"Downloaded '{parts[1]}'."

        if subcmd == "update-check":
            if len(parts) < 3:
                return "Usage: /marketplace-v2 update-check <name> <version>"
            latest = mp.check_update(parts[1], parts[2])
            if latest:
                return f"Update available: {parts[1]} v{latest}"
            return f"'{parts[1]}' is up to date."

        if subcmd == "compat":
            if len(parts) < 2:
                return "Usage: /marketplace-v2 compat <name>"
            entries = mp.compat_matrix(parts[1])
            if not entries:
                return f"No compatibility data for '{parts[1]}'."
            lines = [f"Compatibility for '{parts[1]}':"]
            for e in entries:
                status = "compatible" if e.compatible else "INCOMPATIBLE"
                lines.append(f"  plugin v{e.plugin_version} + lidco v{e.lidco_version}: {status}")
            return "\n".join(lines)

        if subcmd == "stats":
            st = mp.stats()
            return (
                f"Marketplace stats:\n"
                f"  Plugins: {st['total_plugins']}\n"
                f"  Downloads: {st['total_downloads']}\n"
                f"  Reviews: {st['total_reviews']}\n"
                f"  Categories: {', '.join(st['categories']) or 'none'}"
            )

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("marketplace-v2", "Plugin Marketplace v2 with ratings and reviews", marketplace_v2_handler)

    # ------------------------------------------------------------------
    # /theme-gallery — Theme Gallery
    # ------------------------------------------------------------------
    async def theme_gallery_handler(args: str) -> str:
        """
        Usage: /theme-gallery browse
               /theme-gallery search <query>
               /theme-gallery add <json>
               /theme-gallery install <name>
               /theme-gallery rate <name> <score>
               /theme-gallery preview <name>
               /theme-gallery trending
               /theme-gallery seasonal <season>
               /theme-gallery stats
        """
        from lidco.community.themes import Theme, ThemeGallery, ThemeSeason

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /theme-gallery <subcommand>\n"
                "  browse                browse themes\n"
                "  search <query>        search themes\n"
                "  add <json>            add a theme\n"
                "  install <name>        install a theme\n"
                "  rate <name> <score>   rate a theme\n"
                "  preview <name>        preview a theme\n"
                "  trending              trending themes\n"
                "  seasonal <season>     seasonal themes\n"
                "  stats                 gallery stats"
            )

        subcmd = parts[0].lower()
        gallery = ThemeGallery()

        if subcmd == "browse":
            themes = gallery.browse()
            if not themes:
                return "No themes in gallery."
            lines = [f"Themes ({len(themes)}):"]
            for t in themes:
                lines.append(f"  {t.name} by {t.author} ({t.installs} installs)")
            return "\n".join(lines)

        if subcmd == "search":
            if len(parts) < 2:
                return "Usage: /theme-gallery search <query>"
            results = gallery.search(" ".join(parts[1:]))
            if not results:
                return "No themes found."
            lines = [f"Results ({len(results)}):"]
            for t in results:
                lines.append(f"  {t.name} by {t.author}")
            return "\n".join(lines)

        if subcmd == "add":
            raw = args.strip()[len("add"):].strip()
            if not raw:
                return "Usage: /theme-gallery add <json>"
            try:
                data = json.loads(raw)
                theme = Theme(
                    name=data["name"],
                    author=data.get("author", "anonymous"),
                    description=data.get("description", ""),
                )
                gallery.add(theme)
                return f"Added theme '{theme.name}' by {theme.author}"
            except (json.JSONDecodeError, KeyError) as exc:
                return f"Error: {exc}"

        if subcmd == "install":
            if len(parts) < 2:
                return "Usage: /theme-gallery install <name>"
            ok = gallery.install_theme(parts[1])
            if not ok:
                return f"Theme '{parts[1]}' not found."
            return f"Installed theme '{parts[1]}'."

        if subcmd == "rate":
            if len(parts) < 3:
                return "Usage: /theme-gallery rate <name> <score>"
            try:
                score = int(parts[2])
            except ValueError:
                return "Score must be an integer 1-5."
            ok = gallery.rate_theme(parts[1], score)
            if not ok:
                return f"Theme '{parts[1]}' not found."
            return f"Rated '{parts[1]}' with {score}/5."

        if subcmd == "preview":
            if len(parts) < 2:
                return "Usage: /theme-gallery preview <name>"
            pv = gallery.preview(parts[1])
            if pv is None:
                return f"Theme '{parts[1]}' not found."
            return json.dumps(pv, indent=2)

        if subcmd == "trending":
            themes = gallery.trending()
            if not themes:
                return "No trending themes."
            lines = ["Trending themes:"]
            for t in themes:
                lines.append(f"  {t.name} (rating: {t.average_rating:.1f}, votes: {t.rating_count})")
            return "\n".join(lines)

        if subcmd == "seasonal":
            if len(parts) < 2:
                return "Usage: /theme-gallery seasonal <season>"
            try:
                season = ThemeSeason(parts[1].lower())
            except ValueError:
                valid = ", ".join(s.value for s in ThemeSeason)
                return f"Invalid season. Valid: {valid}"
            themes = gallery.seasonal(season)
            if not themes:
                return f"No {season.value} themes."
            lines = [f"{season.value.title()} themes:"]
            for t in themes:
                lines.append(f"  {t.name} by {t.author}")
            return "\n".join(lines)

        if subcmd == "stats":
            st = gallery.stats()
            return (
                f"Gallery stats:\n"
                f"  Themes: {st['total_themes']}\n"
                f"  Installs: {st['total_installs']}\n"
                f"  Seasons: {', '.join(st['seasons']) or 'none'}"
            )

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("theme-gallery", "Theme gallery with preview and ratings", theme_gallery_handler)

    # ------------------------------------------------------------------
    # /share-recipe — Recipe Sharing
    # ------------------------------------------------------------------
    async def share_recipe_handler(args: str) -> str:
        """
        Usage: /share-recipe publish <json>
               /share-recipe search <query>
               /share-recipe browse
               /share-recipe fork <recipe_id> <author> [name]
               /share-recipe rate <recipe_id> <score>
               /share-recipe download <recipe_id>
               /share-recipe stats
        """
        from lidco.community.recipes import Recipe, RecipeStep, RecipeStore

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /share-recipe <subcommand>\n"
                "  publish <json>                      publish a recipe\n"
                "  search <query>                      search recipes\n"
                "  browse                              browse recipes\n"
                "  fork <recipe_id> <author> [name]    fork a recipe\n"
                "  rate <recipe_id> <score>            rate a recipe\n"
                "  download <recipe_id>                download a recipe\n"
                "  stats                               store stats"
            )

        subcmd = parts[0].lower()
        store = RecipeStore()

        if subcmd == "publish":
            raw = args.strip()[len("publish"):].strip()
            if not raw:
                return "Usage: /share-recipe publish <json>"
            try:
                data = json.loads(raw)
                steps = [
                    RecipeStep(name=s.get("name", ""), action=s.get("action", ""), params=s.get("params", {}))
                    for s in data.get("steps", [])
                ]
                recipe = Recipe(
                    name=data["name"],
                    author=data.get("author", "anonymous"),
                    description=data.get("description", ""),
                    version=data.get("version", "1.0.0"),
                    steps=steps,
                    tags=data.get("tags", []),
                )
                rid = store.publish(recipe)
                return f"Published recipe '{recipe.name}' v{recipe.version} (id={rid})"
            except (json.JSONDecodeError, KeyError) as exc:
                return f"Error: {exc}"

        if subcmd == "search":
            if len(parts) < 2:
                return "Usage: /share-recipe search <query>"
            results = store.search(" ".join(parts[1:]))
            if not results:
                return "No recipes found."
            lines = [f"Results ({len(results)}):"]
            for r in results:
                lines.append(f"  {r.name} v{r.version} by {r.author} ({r.step_count} steps)")
            return "\n".join(lines)

        if subcmd == "browse":
            recipes = store.browse()
            if not recipes:
                return "No recipes in store."
            lines = [f"Recipes ({len(recipes)}):"]
            for r in recipes:
                lines.append(f"  {r.name} v{r.version} by {r.author}")
            return "\n".join(lines)

        if subcmd == "fork":
            if len(parts) < 3:
                return "Usage: /share-recipe fork <recipe_id> <author> [name]"
            recipe_id = parts[1]
            author = parts[2]
            name = parts[3] if len(parts) > 3 else None
            fid = store.fork_recipe(recipe_id, author, name)
            if fid is None:
                return f"Recipe '{recipe_id}' not found."
            return f"Forked as {fid}"

        if subcmd == "rate":
            if len(parts) < 3:
                return "Usage: /share-recipe rate <recipe_id> <score>"
            try:
                score = int(parts[2])
            except ValueError:
                return "Score must be an integer 1-5."
            ok = store.rate(parts[1], score)
            if not ok:
                return f"Recipe '{parts[1]}' not found."
            return f"Rated recipe with {score}/5."

        if subcmd == "download":
            if len(parts) < 2:
                return "Usage: /share-recipe download <recipe_id>"
            ok = store.record_download(parts[1])
            if not ok:
                return f"Recipe '{parts[1]}' not found."
            return f"Downloaded recipe '{parts[1]}'."

        if subcmd == "stats":
            st = store.stats()
            return (
                f"Recipe store stats:\n"
                f"  Recipes: {st['total_recipes']}\n"
                f"  Downloads: {st['total_downloads']}\n"
                f"  Forks: {st['total_forks']}\n"
                f"  Authors: {st['unique_authors']}"
            )

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("share-recipe", "Share automation recipes with the community", share_recipe_handler)

    # ------------------------------------------------------------------
    # /community — Community Dashboard
    # ------------------------------------------------------------------
    async def community_handler(args: str) -> str:
        """
        Usage: /community stats
               /community activity
               /community leaderboard
               /community contributor <name>
        """
        from lidco.community.dashboard import CommunityDashboard

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /community <subcommand>\n"
                "  stats                    community statistics\n"
                "  activity                 recent activity\n"
                "  leaderboard              top contributors\n"
                "  contributor <name>       contributor details"
            )

        subcmd = parts[0].lower()
        dash = CommunityDashboard()

        if subcmd == "stats":
            st = dash.get_stats()
            return (
                f"Community stats:\n"
                f"  Plugins: {st.total_plugins}\n"
                f"  Themes: {st.total_themes}\n"
                f"  Recipes: {st.total_recipes}\n"
                f"  Contributors: {st.total_contributors}\n"
                f"  Downloads: {st.total_downloads}\n"
                f"  Reviews: {st.total_reviews}"
            )

        if subcmd == "activity":
            entries = dash.recent_activity()
            if not entries:
                return "No recent activity."
            lines = ["Recent activity:"]
            for e in entries:
                lines.append(f"  {e.actor} {e.action} {e.target}")
            return "\n".join(lines)

        if subcmd == "leaderboard":
            leaders = dash.leaderboard()
            if not leaders:
                return "No contributors yet."
            lines = ["Leaderboard:"]
            for i, c in enumerate(leaders, 1):
                lines.append(f"  {i}. {c.name} (score: {c.score})")
            return "\n".join(lines)

        if subcmd == "contributor":
            if len(parts) < 2:
                return "Usage: /community contributor <name>"
            cs = dash.get_contributor(parts[1])
            if cs is None:
                return f"Contributor '{parts[1]}' not found."
            return (
                f"Contributor: {cs.name}\n"
                f"  Plugins: {cs.plugins}\n"
                f"  Themes: {cs.themes}\n"
                f"  Recipes: {cs.recipes}\n"
                f"  Reviews: {cs.reviews}\n"
                f"  Score: {cs.score}"
            )

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("community", "Community dashboard with stats and leaderboard", community_handler)
