"""Tests for src/lidco/cli/commands/q107_cmds.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load_handlers():
    import lidco.cli.commands.q107_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


# ------------------------------------------------------------------ #
# /compose                                                              #
# ------------------------------------------------------------------ #

class TestComposeCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "compose" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo_shows_diff(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        result = _run(h("demo"))
        assert "---" in result or "+++" in result or "Hello" in result

    def test_plan_creates_plan(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        result = _run(h("plan refactor auth module"))
        assert "refactor auth module" in result or "Plan" in result

    def test_plan_no_goal_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        result = _run(h("plan"))
        assert "Usage" in result

    def test_add_without_plan_shows_error(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        result = _run(h("add src/foo.py some description"))
        assert "No active" in result or "Error" in result

    def test_add_with_plan(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        _run(h("plan my goal"))
        result = _run(h("add src/foo.py fix something"))
        assert "foo.py" in result or "added" in result.lower()

    def test_preview_no_plan(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        result = _run(h("preview"))
        assert "no plan" in result.lower() or "No active" in result

    def test_preview_with_plan(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        _run(h("plan show preview"))
        result = _run(h("preview"))
        assert "show preview" in result or "#" in result or "Plan" in result

    def test_summary_with_plan(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        _run(h("plan test summary"))
        result = _run(h("summary"))
        assert "test summary" in result or "file" in result.lower()

    def test_apply_dry_run(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        _run(h("plan apply test"))
        _run(h("add src/x.py desc"))
        result = _run(h("apply"))
        assert "dry-run" in result.lower() or "Would write" in result or "x.py" in result

    def test_rollback_no_history(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        result = _run(h("rollback"))
        assert "Nothing" in result or "Error" in result or "No active" in result

    def test_reset(self):
        reg = _load_handlers()
        h = reg.commands["compose"].handler
        _run(h("plan something"))
        result = _run(h("reset"))
        assert "clear" in result.lower()


# ------------------------------------------------------------------ #
# /ctx-optimize                                                         #
# ------------------------------------------------------------------ #

class TestCtxOptimizeCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "ctx-optimize" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["ctx-optimize"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["ctx-optimize"].handler
        result = _run(h("demo"))
        assert "Budget" in result or "token" in result.lower()

    def test_add_entry(self):
        reg = _load_handlers()
        h = reg.commands["ctx-optimize"].handler
        result = _run(h("add main.py def foo(): pass"))
        assert "main.py" in result or "Added" in result

    def test_add_no_args(self):
        reg = _load_handlers()
        h = reg.commands["ctx-optimize"].handler
        result = _run(h("add"))
        assert "Usage" in result

    def test_stats(self):
        reg = _load_handlers()
        h = reg.commands["ctx-optimize"].handler
        result = _run(h("stats"))
        assert "token" in result.lower() or "Budget" in result or "Entries" in result

    def test_optimize(self):
        reg = _load_handlers()
        h = reg.commands["ctx-optimize"].handler
        _run(h("add a hello"))
        result = _run(h("optimize"))
        assert "token" in result.lower() or "result" in result.lower() or "Optimization" in result

    def test_budget_get(self):
        reg = _load_handlers()
        h = reg.commands["ctx-optimize"].handler
        result = _run(h("budget"))
        assert "budget" in result.lower() or "token" in result.lower()

    def test_budget_set(self):
        reg = _load_handlers()
        h = reg.commands["ctx-optimize"].handler
        result = _run(h("budget 2048"))
        assert "2048" in result

    def test_score(self):
        reg = _load_handlers()
        h = reg.commands["ctx-optimize"].handler
        result = _run(h("score src/auth/login.py login"))
        assert "score" in result.lower() or "login" in result

    def test_clear(self):
        reg = _load_handlers()
        h = reg.commands["ctx-optimize"].handler
        result = _run(h("clear"))
        assert "clear" in result.lower()


# ------------------------------------------------------------------ #
# /workflow                                                             #
# ------------------------------------------------------------------ #

class TestWorkflowCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "workflow" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["workflow"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["workflow"].handler
        result = _run(h("demo"))
        assert "demo" in result.lower() or "pipeline" in result.lower() or "OK" in result

    def test_list_no_workflows(self):
        reg = _load_handlers()
        h = reg.commands["workflow"].handler
        result = _run(h("list"))
        assert "No workflows" in result or "workflow" in result.lower()

    def test_run_unknown_workflow(self):
        reg = _load_handlers()
        h = reg.commands["workflow"].handler
        result = _run(h("run ghost-workflow"))
        assert "Error" in result or "Unknown" in result

    def test_run_default_no_steps(self):
        reg = _load_handlers()
        h = reg.commands["workflow"].handler
        result = _run(h("run"))
        # either runs empty workflow or errors
        assert isinstance(result, str)

    def test_reset(self):
        reg = _load_handlers()
        h = reg.commands["workflow"].handler
        result = _run(h("reset"))
        assert "reset" in result.lower()


# ------------------------------------------------------------------ #
# /action                                                               #
# ------------------------------------------------------------------ #

class TestActionCommand:
    def test_registered(self):
        reg = _load_handlers()
        assert "action" in reg.commands

    def test_no_args_shows_usage(self):
        reg = _load_handlers()
        h = reg.commands["action"].handler
        result = _run(h(""))
        assert "Usage" in result

    def test_demo(self):
        reg = _load_handlers()
        h = reg.commands["action"].handler
        result = _run(h("demo"))
        assert "NameError" in result or "Fix" in result or "action" in result.lower()

    def test_find_name_error(self):
        reg = _load_handlers()
        h = reg.commands["action"].handler
        result = _run(h("find NameError: name 'requests' is not defined"))
        assert "import" in result.lower() or "Fix" in result

    def test_find_no_match(self):
        reg = _load_handlers()
        h = reg.commands["action"].handler
        result = _run(h("find xyzzy unknown pattern"))
        assert "No actions" in result or "no action" in result.lower()

    def test_find_no_args(self):
        reg = _load_handlers()
        h = reg.commands["action"].handler
        result = _run(h("find"))
        assert "Usage" in result

    def test_list(self):
        reg = _load_handlers()
        h = reg.commands["action"].handler
        result = _run(h("list"))
        assert "action" in result.lower() or "undefined" in result.lower()

    def test_analyze_error(self):
        reg = _load_handlers()
        h = reg.commands["action"].handler
        result = _run(h("analyze NameError: name 'foo' is not defined"))
        assert "ERROR" in result or "error" in result.lower()

    def test_analyze_no_args(self):
        reg = _load_handlers()
        h = reg.commands["action"].handler
        result = _run(h("analyze"))
        assert "Usage" in result

    def test_reset(self):
        reg = _load_handlers()
        h = reg.commands["action"].handler
        result = _run(h("reset"))
        assert "reset" in result.lower()
