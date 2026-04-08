"""
Task 1703 — Data Fixtures

Manage test fixtures: YAML/JSON loading, per-test / shared scoping,
cleanup, versioned, dependency ordering.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class FixtureScope(str, Enum):
    """Scope of a fixture's lifecycle."""

    TEST = "test"           # created/destroyed per-test
    MODULE = "module"       # per-module (file)
    SESSION = "session"     # global / shared across suite


@dataclass(frozen=True)
class FixtureDef:
    """Definition of a single fixture."""

    name: str
    scope: FixtureScope = FixtureScope.TEST
    data: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    depends_on: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class FixtureSet:
    """An ordered collection of fixtures ready for use."""

    fixtures: tuple[FixtureDef, ...] = ()
    source: str = ""  # file path or descriptor

    @property
    def names(self) -> list[str]:
        return [f.name for f in self.fixtures]

    def get(self, name: str) -> Optional[FixtureDef]:
        for f in self.fixtures:
            if f.name == name:
                return f
        return None


@dataclass(frozen=True)
class CleanupAction:
    """Record of a cleanup action to execute when a fixture is torn down."""

    fixture_name: str
    action: str  # e.g. "delete", "truncate", "restore"
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# YAML stub — stdlib only, parse a minimal YAML-like format or JSON
# ---------------------------------------------------------------------------

def _load_file(path: str) -> Any:
    """Load JSON (or .json) file. For YAML, expect JSON-compatible subset."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# FixtureManager
# ---------------------------------------------------------------------------

class FixtureManager:
    """
    Load, resolve, and manage test fixtures.

    Fixtures can be loaded from JSON files or registered programmatically.
    Dependencies between fixtures are resolved with topological sort.
    """

    def __init__(self) -> None:
        self._fixtures: Dict[str, FixtureDef] = {}
        self._cleanup_actions: list[CleanupAction] = []
        self._active: Dict[str, FixtureDef] = {}

    # -- registration --------------------------------------------------------

    def register(self, fixture: FixtureDef) -> FixtureManager:
        """Return a new manager with the fixture added."""
        new_fx = {**self._fixtures, fixture.name: fixture}
        mgr = FixtureManager.__new__(FixtureManager)
        mgr._fixtures = new_fx
        mgr._cleanup_actions = list(self._cleanup_actions)
        mgr._active = dict(self._active)
        return mgr

    def register_many(self, fixtures: Sequence[FixtureDef]) -> FixtureManager:
        mgr = self
        for f in fixtures:
            mgr = mgr.register(f)
        return mgr

    # -- loading from files --------------------------------------------------

    def load_file(self, path: str) -> FixtureSet:
        """Load fixtures from a JSON file.

        Expected format::

            {
              "fixtures": [
                {"name": "users", "scope": "test", "data": {...}, "version": 1, "depends_on": []},
                ...
              ]
            }
        """
        raw = _load_file(path)
        items = raw.get("fixtures", []) if isinstance(raw, dict) else raw
        defs: list[FixtureDef] = []
        for item in items:
            fd = FixtureDef(
                name=item["name"],
                scope=FixtureScope(item.get("scope", "test")),
                data=item.get("data", {}),
                version=item.get("version", 1),
                depends_on=tuple(item.get("depends_on", [])),
                tags=tuple(item.get("tags", [])),
            )
            defs.append(fd)
        return FixtureSet(fixtures=tuple(defs), source=path)

    # -- dependency ordering -------------------------------------------------

    def resolve_order(self, names: Optional[Sequence[str]] = None) -> list[str]:
        """Topological sort of fixtures by depends_on."""
        pool = self._fixtures
        targets = list(names) if names else list(pool.keys())

        visited: set[str] = set()
        order: list[str] = []
        temp: set[str] = set()

        def visit(n: str) -> None:
            if n in temp:
                raise ValueError(f"Circular dependency detected involving {n!r}")
            if n in visited:
                return
            temp.add(n)
            fx = pool.get(n)
            if fx:
                for dep in fx.depends_on:
                    visit(dep)
            temp.discard(n)
            visited.add(n)
            order.append(n)

        for t in targets:
            visit(t)
        return order

    # -- setup / teardown ----------------------------------------------------

    def setup(self, names: Optional[Sequence[str]] = None) -> list[FixtureDef]:
        """Activate fixtures in dependency order; return them."""
        ordered = self.resolve_order(names)
        result: list[FixtureDef] = []
        for n in ordered:
            fx = self._fixtures.get(n)
            if fx:
                self._active[n] = fx
                result.append(fx)
        return result

    def teardown(self) -> list[CleanupAction]:
        """Tear down all active fixtures in reverse order and return actions."""
        actions: list[CleanupAction] = []
        for name in reversed(list(self._active.keys())):
            act = CleanupAction(fixture_name=name, action="delete")
            actions.append(act)
        self._active = {}
        return actions

    # -- query ---------------------------------------------------------------

    @property
    def registered_names(self) -> list[str]:
        return list(self._fixtures.keys())

    @property
    def active_names(self) -> list[str]:
        return list(self._active.keys())

    def get(self, name: str) -> Optional[FixtureDef]:
        return self._fixtures.get(name)
