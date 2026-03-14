"""Permission engine — evaluates tool access against rules and permission modes.

Evaluation order (first match wins):
  1. bypass mode → allow everything
  2. session deny list (from "never" decisions) → deny
  3. config deny_rules → deny
  4. session allow list (from "always" decisions) → allow
  5. config allow_rules → allow
  6. config ask_rules → ask
  7. plan mode + write/execute tool → deny
  8. accept_edits mode + file_write/file_edit → allow
  9. dont_ask mode → deny
  10. legacy config.auto_allow / config.ask / config.deny → delegate
  11. default → ask
"""

from __future__ import annotations

import fnmatch
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from lidco.core.config import PermissionsConfig

logger = logging.getLogger(__name__)

# Tools that write or execute — blocked in "plan" mode
_WRITE_EXECUTE_TOOLS: frozenset[str] = frozenset(
    {"bash", "file_write", "file_edit", "git"}
)

# Tools that only edit files — allowed by "accept_edits" mode
_EDIT_TOOLS: frozenset[str] = frozenset({"file_write", "file_edit"})

# Risk level for color-coded prompts
_TOOL_RISK: dict[str, str] = {
    "bash": "yellow",
    "file_write": "yellow",
    "file_edit": "yellow",
    "git": "yellow",
    "file_read": "green",
    "glob": "green",
    "grep": "green",
    "web_search": "green",
    "web_fetch": "green",
    "tree": "green",
    "diff": "green",
}

_DANGEROUS_BASH_PATTERNS: tuple[str, ...] = (
    "rm -rf",
    "git push",
    "git push --force",
    "drop table",
    "truncate table",
    "> /dev/",
    "mkfs",
    "dd if=",
    "chmod -R 777",
    "sudo rm",
)


class PermissionMode(str, Enum):
    DEFAULT = "default"
    ACCEPT_EDITS = "accept_edits"
    PLAN = "plan"
    DONT_ASK = "dont_ask"
    BYPASS = "bypass"


@dataclass(frozen=True)
class PermissionResult:
    decision: str  # "allow" | "ask" | "deny"
    reason: str = ""
    rule: str = ""  # matching rule spec e.g. "Bash(pytest *)"
    risk: str = "yellow"  # "green" | "yellow" | "red"


@dataclass(frozen=True)
class ParsedRule:
    tool_name: str   # "Bash", "FileWrite", etc. (canonical, case-insensitive match)
    pattern: str     # "" means match all; "**/foo" matches path globs
    raw: str         # original spec string

    # Normalised tool name for comparison
    @property
    def tool_key(self) -> str:
        return self.tool_name.lower()


_TOOL_NAME_MAP: dict[str, str] = {
    "bash": "bash",
    "fileread": "file_read",
    "filewrite": "file_write",
    "fileedit": "file_edit",
    "git": "git",
    "websearch": "web_search",
    "webfetch": "web_fetch",
    "grep": "grep",
    "glob": "glob",
    "tree": "tree",
    "diff": "diff",
}


class RuleParser:
    """Parse 'Tool(pattern)' or plain 'ToolName' rule specs."""

    _SPEC_RE = re.compile(r"^(\w+)\((.+)\)$", re.DOTALL)

    @classmethod
    def parse(cls, spec: str) -> ParsedRule:
        spec = spec.strip()
        m = cls._SPEC_RE.match(spec)
        if m:
            return ParsedRule(tool_name=m.group(1), pattern=m.group(2).strip(), raw=spec)
        # Plain tool name — matches any invocation
        return ParsedRule(tool_name=spec, pattern="**", raw=spec)


class RuleMatcher:
    """Match a tool call against a parsed rule."""

    @staticmethod
    def matches(rule: ParsedRule, tool_name: str, args: dict[str, Any]) -> bool:
        # Normalize tool name for comparison
        rule_key = _TOOL_NAME_MAP.get(rule.tool_key, rule.tool_key)
        call_key = tool_name.lower()
        if rule_key != call_key:
            return False
        if rule.pattern in ("**", "*", ""):
            return True
        # For bash: match against command string
        if call_key == "bash":
            cmd = str(args.get("command", ""))
            return RuleMatcher._match_glob(rule.pattern, cmd)
        # For file tools: match against path
        path_arg = args.get("path") or args.get("file_path") or ""
        return RuleMatcher._match_glob(rule.pattern, str(path_arg))

    @staticmethod
    def _match_glob(pattern: str, value: str) -> bool:
        """Wildcard match: * = any chars except /, ** = any chars including /."""
        # Normalize path separators
        value = value.replace("\\", "/")
        pattern = pattern.replace("\\", "/")
        # Expand ** to match any path segment
        regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        return bool(re.search(regex, value))


@dataclass
class _SessionDecision:
    """A decision made interactively during this session."""
    rule_spec: str  # e.g. "bash(pytest *)"
    parsed: ParsedRule


class PermissionEngine:
    """Evaluates tool permission for every call.

    Instantiate once per session. Thread-safe for reads; write operations
    (add_session_allow etc.) are not synchronized but LIDCO is single-threaded.
    """

    def __init__(self, config: PermissionsConfig) -> None:
        self._config = config
        try:
            self._mode = PermissionMode(config.mode)
        except (ValueError, TypeError):
            self._mode = PermissionMode.DEFAULT
        # Task 252: expand command_allowlist into Bash(pattern) allow rules (kept separate for summary)
        self._allowlist_rules: list[ParsedRule] = [
            RuleParser.parse(f"Bash({cmd})") for cmd in config.command_allowlist
        ]
        self._allow_rules: list[ParsedRule] = self._allowlist_rules + [
            RuleParser.parse(r) for r in config.allow_rules
        ]
        self._ask_rules: list[ParsedRule] = [RuleParser.parse(r) for r in config.ask_rules]
        self._deny_rules: list[ParsedRule] = [RuleParser.parse(r) for r in config.deny_rules]
        # Session-scoped decisions (cleared on session end)
        self._session_allowed: list[_SessionDecision] = []
        self._session_denied: list[_SessionDecision] = []
        # Persistent allow-list (loaded from .lidco/permissions.json)
        self._persistent_allowed: list[ParsedRule] = []
        self._persistent_denied: list[ParsedRule] = []
        self._persistent_path: Path | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, tool_name: str, args: dict[str, Any]) -> PermissionResult:
        """Return a PermissionResult for the given tool call."""
        risk = _TOOL_RISK.get(tool_name.lower(), "yellow")

        # Detect dangerous bash
        if tool_name.lower() == "bash":
            cmd = str(args.get("command", ""))
            for pat in _DANGEROUS_BASH_PATTERNS:
                if pat in cmd:
                    risk = "red"
                    break

        # 1. bypass mode
        if self._mode == PermissionMode.BYPASS:
            return PermissionResult("allow", "bypass mode", risk=risk)

        # 2. session deny
        for dec in self._session_denied:
            if RuleMatcher.matches(dec.parsed, tool_name, args):
                return PermissionResult("deny", "denied this session", dec.rule_spec, risk)

        # 3. config deny_rules + persistent denied
        for rule in self._deny_rules:
            if RuleMatcher.matches(rule, tool_name, args):
                return PermissionResult("deny", f"deny rule: {rule.raw}", rule.raw, risk)
        for rule in self._persistent_denied:
            if RuleMatcher.matches(rule, tool_name, args):
                return PermissionResult("deny", f"persistent deny: {rule.raw}", rule.raw, risk)

        # 4. persistent allowed
        for rule in self._persistent_allowed:
            if RuleMatcher.matches(rule, tool_name, args):
                return PermissionResult("allow", f"persistent rule: {rule.raw}", rule.raw, risk)

        # 5. session allowed
        for dec in self._session_allowed:
            if RuleMatcher.matches(dec.parsed, tool_name, args):
                return PermissionResult("allow", "allowed this session", dec.rule_spec, risk)

        # 6. config allow_rules
        for rule in self._allow_rules:
            if RuleMatcher.matches(rule, tool_name, args):
                return PermissionResult("allow", f"allow rule: {rule.raw}", rule.raw, risk)

        # 7. config ask_rules
        for rule in self._ask_rules:
            if RuleMatcher.matches(rule, tool_name, args):
                return PermissionResult("ask", f"ask rule: {rule.raw}", rule.raw, risk)

        # 8. plan mode blocks write/execute
        if self._mode == PermissionMode.PLAN:
            if tool_name.lower() in _WRITE_EXECUTE_TOOLS:
                return PermissionResult(
                    "deny", "plan mode: write/execute not allowed", risk=risk
                )

        # 9. accept_edits auto-allows file edits
        if self._mode == PermissionMode.ACCEPT_EDITS:
            if tool_name.lower() in _EDIT_TOOLS:
                return PermissionResult("allow", "accept_edits mode", risk=risk)

        # 10. dont_ask denies anything not explicitly allowed
        if self._mode == PermissionMode.DONT_ASK:
            return PermissionResult("deny", "dont_ask mode: no matching allow rule", risk=risk)

        # 11. legacy config lists
        legacy = self._check_legacy(tool_name)
        if legacy is not None:
            return PermissionResult(legacy, "legacy config", risk=risk)

        # 12. read-only tools are always allowed
        if tool_name.lower() in {"file_read", "glob", "grep", "tree", "diff", "web_search", "web_fetch"}:
            return PermissionResult("allow", "read-only tool", risk="green")

        # 13. default → ask
        return PermissionResult("ask", "default: requires approval", risk=risk)

    def set_mode(self, mode: str) -> None:
        self._mode = PermissionMode(mode)

    @property
    def mode(self) -> PermissionMode:
        return self._mode

    def add_session_allow(self, tool_name: str, args: dict[str, Any]) -> None:
        """Record an allow-for-session decision."""
        spec = self._make_spec(tool_name, args)
        parsed = RuleParser.parse(spec)
        self._session_allowed.append(_SessionDecision(spec, parsed))

    def add_session_deny(self, tool_name: str, args: dict[str, Any]) -> None:
        """Record a deny-for-session decision."""
        spec = self._make_spec(tool_name, args)
        parsed = RuleParser.parse(spec)
        self._session_denied.append(_SessionDecision(spec, parsed))

    def add_persistent_allow(self, rule_spec: str) -> None:
        """Add a persistent allow rule and save."""
        parsed = RuleParser.parse(rule_spec)
        self._persistent_allowed.append(parsed)
        self._save()

    def add_persistent_deny(self, rule_spec: str) -> None:
        """Add a persistent deny rule and save."""
        parsed = RuleParser.parse(rule_spec)
        self._persistent_denied.append(parsed)
        self._save()

    def remove_persistent_allow(self, index: int) -> bool:
        if 0 <= index < len(self._persistent_allowed):
            self._persistent_allowed.pop(index)
            self._save()
            return True
        return False

    def remove_persistent_deny(self, index: int) -> bool:
        if 0 <= index < len(self._persistent_denied):
            self._persistent_denied.pop(index)
            self._save()
            return True
        return False

    def load_persistent(self, path: Path) -> None:
        """Load .lidco/permissions.json if it exists."""
        self._persistent_path = path
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._persistent_allowed = [
                RuleParser.parse(r) for r in data.get("allow", [])
            ]
            self._persistent_denied = [
                RuleParser.parse(r) for r in data.get("deny", [])
            ]
        except Exception as exc:
            logger.warning("Failed to load permissions.json: %s", exc)

    def get_summary(self) -> dict[str, Any]:
        """Return a human-readable summary for /permissions command."""
        # allow_rules excludes the auto-expanded command_allowlist to avoid clutter
        config_allow = [r.raw for r in self._allow_rules if r not in self._allowlist_rules]
        return {
            "mode": self._mode.value,
            "allow_rules": config_allow,
            "command_allowlist": [r.raw for r in self._allowlist_rules],
            "ask_rules": [r.raw for r in self._ask_rules],
            "deny_rules": [r.raw for r in self._deny_rules],
            "persistent_allow": [r.raw for r in self._persistent_allowed],
            "persistent_deny": [r.raw for r in self._persistent_denied],
            "session_allowed": [d.rule_spec for d in self._session_allowed],
            "session_denied": [d.rule_spec for d in self._session_denied],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_legacy(self, tool_name: str) -> str | None:
        """Check old-style auto_allow / ask / deny lists."""
        cfg = self._config
        if tool_name in cfg.deny:
            return "deny"
        if tool_name in cfg.auto_allow:
            return "allow"
        return None

    def _save(self) -> None:
        if self._persistent_path is None:
            return
        try:
            self._persistent_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "allow": [r.raw for r in self._persistent_allowed],
                "deny": [r.raw for r in self._persistent_denied],
            }
            self._persistent_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("Failed to save permissions.json: %s", exc)

    @staticmethod
    def _make_spec(tool_name: str, args: dict[str, Any]) -> str:
        """Build a rule spec string from a tool call."""
        tool_cap = tool_name.capitalize()
        if tool_name.lower() == "bash":
            cmd = str(args.get("command", "")).strip()
            # Use first word + * as pattern
            first_word = cmd.split()[0] if cmd else "*"
            return f"Bash({first_word} *)"
        path = args.get("path") or args.get("file_path") or ""
        if path:
            return f"{tool_cap}({path})"
        return tool_cap
