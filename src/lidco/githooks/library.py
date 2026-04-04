"""HookLibrary — built-in hook definitions catalog.

Provides a registry of ready-made hook scripts that can be installed via
HookManagerV2. Hooks are organized by category and programming language.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from lidco.githooks.manager import HookType


@dataclass(frozen=True)
class HookDefinition:
    """A reusable hook recipe."""

    name: str
    type: HookType
    script: str
    description: str = ""
    category: str = "general"
    language: str = ""  # empty = language-agnostic


# ---------------------------------------------------------------------------
# Built-in hooks
# ---------------------------------------------------------------------------

_BUILTINS: List[HookDefinition] = [
    HookDefinition(
        name="no-debug",
        type=HookType.PRE_COMMIT,
        script="#!/bin/sh\n! grep -rn 'import pdb\\|breakpoint()' --include='*.py' .",
        description="Block commits containing pdb / breakpoint() calls.",
        category="quality",
        language="python",
    ),
    HookDefinition(
        name="trailing-whitespace",
        type=HookType.PRE_COMMIT,
        script="#!/bin/sh\n! grep -rn '\\s$' --include='*.py' .",
        description="Reject trailing whitespace in Python files.",
        category="style",
        language="python",
    ),
    HookDefinition(
        name="no-console-log",
        type=HookType.PRE_COMMIT,
        script="#!/bin/sh\n! grep -rn 'console\\.log' --include='*.js' --include='*.ts' .",
        description="Block commits with console.log statements.",
        category="quality",
        language="javascript",
    ),
    HookDefinition(
        name="commit-msg-length",
        type=HookType.COMMIT_MSG,
        script='#!/bin/sh\nMSG=$(head -1 "$1")\nif [ ${#MSG} -gt 72 ]; then echo "Commit message too long (max 72 chars)"; exit 1; fi',
        description="Enforce commit message length <= 72 chars.",
        category="convention",
    ),
    HookDefinition(
        name="branch-name-check",
        type=HookType.PRE_PUSH,
        script='#!/bin/sh\nBRANCH=$(git rev-parse --abbrev-ref HEAD)\necho "$BRANCH" | grep -qE "^(feat|fix|chore|docs|refactor|test)/" || { echo "Bad branch name"; exit 1; }',
        description="Enforce branch naming convention (feat/, fix/, etc.).",
        category="convention",
    ),
    HookDefinition(
        name="run-pytest",
        type=HookType.PRE_COMMIT,
        script="#!/bin/sh\npython -m pytest -q --tb=short || exit 1",
        description="Run pytest before committing.",
        category="testing",
        language="python",
    ),
    HookDefinition(
        name="eslint-check",
        type=HookType.PRE_COMMIT,
        script="#!/bin/sh\nnpx eslint --max-warnings=0 . || exit 1",
        description="Run ESLint before committing.",
        category="quality",
        language="javascript",
    ),
    HookDefinition(
        name="post-commit-notify",
        type=HookType.POST_COMMIT,
        script='#!/bin/sh\necho "Commit $(git rev-parse --short HEAD) created successfully."',
        description="Print commit hash after successful commit.",
        category="notification",
    ),
]

_BY_NAME: Dict[str, HookDefinition] = {h.name: h for h in _BUILTINS}


class HookLibrary:
    """Catalog of built-in hook definitions."""

    def __init__(self, extra: Optional[List[HookDefinition]] = None) -> None:
        self._hooks: Dict[str, HookDefinition] = dict(_BY_NAME)
        if extra:
            for h in extra:
                self._hooks[h.name] = h

    def builtin_hooks(self) -> List[HookDefinition]:
        """Return all registered hook definitions."""
        return list(self._hooks.values())

    def get(self, name: str) -> Optional[HookDefinition]:
        """Lookup a hook by name, returning None if missing."""
        return self._hooks.get(name)

    def categories(self) -> List[str]:
        """Return sorted unique category names."""
        return sorted({h.category for h in self._hooks.values()})

    def hooks_for_language(self, lang: str) -> List[HookDefinition]:
        """Return hooks matching the given language (case-insensitive)."""
        lang_lower = lang.lower()
        return [h for h in self._hooks.values() if h.language.lower() == lang_lower]
