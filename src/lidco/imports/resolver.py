"""Import Resolver — detect undefined names and suggest missing imports (stdlib only).

Scans Python source via `ast`, collects names that are used but not defined
or imported, and maps them to well-known stdlib/third-party modules.
"""
from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass, field
from typing import Any


class ImportResolverError(Exception):
    """Raised when import resolution fails."""


@dataclass
class ImportSuggestion:
    """A suggested import statement for an undefined name."""

    name: str           # the undefined name
    module: str         # e.g. "os.path"
    import_stmt: str    # e.g. "from os.path import join" or "import os"
    confidence: float = 1.0   # 0.0–1.0
    is_stdlib: bool = True


@dataclass
class ResolverResult:
    """Output of ImportResolver.resolve()."""

    undefined_names: list[str]
    suggestions: list[ImportSuggestion]
    source_imports: list[str]   # imports already present in the source

    def has_suggestions(self) -> bool:
        return bool(self.suggestions)

    def import_block(self) -> str:
        """Return a deduplicated block of suggested import statements."""
        seen: set[str] = set()
        lines: list[str] = []
        for s in sorted(self.suggestions, key=lambda x: x.import_stmt):
            if s.import_stmt not in seen:
                seen.add(s.import_stmt)
                lines.append(s.import_stmt)
        return "\n".join(lines)


# ------------------------------------------------------------------ #
# Known name → import mapping                                          #
# ------------------------------------------------------------------ #

_STDLIB_MAP: dict[str, tuple[str, str]] = {
    # name: (module, import_stmt)
    "Path": ("pathlib", "from pathlib import Path"),
    "os": ("os", "import os"),
    "sys": ("sys", "import sys"),
    "json": ("json", "import json"),
    "re": ("re", "import re"),
    "time": ("time", "import time"),
    "datetime": ("datetime", "from datetime import datetime"),
    "timedelta": ("datetime", "from datetime import timedelta"),
    "date": ("datetime", "from datetime import date"),
    "dataclass": ("dataclasses", "from dataclasses import dataclass"),
    "field": ("dataclasses", "from dataclasses import field"),
    "asdict": ("dataclasses", "from dataclasses import asdict"),
    "Enum": ("enum", "from enum import Enum"),
    "ABC": ("abc", "from abc import ABC"),
    "abstractmethod": ("abc", "from abc import abstractmethod"),
    "defaultdict": ("collections", "from collections import defaultdict"),
    "OrderedDict": ("collections", "from collections import OrderedDict"),
    "Counter": ("collections", "from collections import Counter"),
    "deque": ("collections", "from collections import deque"),
    "namedtuple": ("collections", "from collections import namedtuple"),
    "partial": ("functools", "from functools import partial"),
    "wraps": ("functools", "from functools import wraps"),
    "lru_cache": ("functools", "from functools import lru_cache"),
    "reduce": ("functools", "from functools import reduce"),
    "chain": ("itertools", "from itertools import chain"),
    "product": ("itertools", "from itertools import product"),
    "combinations": ("itertools", "from itertools import combinations"),
    "permutations": ("itertools", "from itertools import permutations"),
    "contextmanager": ("contextlib", "from contextlib import contextmanager"),
    "suppress": ("contextlib", "from contextlib import suppress"),
    "asynccontextmanager": ("contextlib", "from contextlib import asynccontextmanager"),
    "sleep": ("time", "from time import sleep"),
    "Thread": ("threading", "from threading import Thread"),
    "Lock": ("threading", "from threading import Lock"),
    "Event": ("threading", "from threading import Event"),
    "Queue": ("queue", "from queue import Queue"),
    "PriorityQueue": ("queue", "from queue import PriorityQueue"),
    "subprocess": ("subprocess", "import subprocess"),
    "shutil": ("shutil", "import shutil"),
    "tempfile": ("tempfile", "import tempfile"),
    "hashlib": ("hashlib", "import hashlib"),
    "base64": ("base64", "import base64"),
    "uuid": ("uuid", "import uuid"),
    "copy": ("copy", "import copy"),
    "deepcopy": ("copy", "from copy import deepcopy"),
    "pprint": ("pprint", "from pprint import pprint"),
    "textwrap": ("textwrap", "import textwrap"),
    "difflib": ("difflib", "import difflib"),
    "math": ("math", "import math"),
    "random": ("random", "import random"),
    "string": ("string", "import string"),
    "struct": ("struct", "import struct"),
    "io": ("io", "import io"),
    "BytesIO": ("io", "from io import BytesIO"),
    "StringIO": ("io", "from io import StringIO"),
    "logging": ("logging", "import logging"),
    "getLogger": ("logging", "from logging import getLogger"),
    "TypeVar": ("typing", "from typing import TypeVar"),
    "Any": ("typing", "from typing import Any"),
    "Optional": ("typing", "from typing import Optional"),
    "Union": ("typing", "from typing import Union"),
    "List": ("typing", "from typing import List"),
    "Dict": ("typing", "from typing import Dict"),
    "Tuple": ("typing", "from typing import Tuple"),
    "Set": ("typing", "from typing import Set"),
    "Callable": ("typing", "from typing import Callable"),
    "Iterator": ("typing", "from typing import Iterator"),
    "Generator": ("typing", "from typing import Generator"),
    "cast": ("typing", "from typing import cast"),
    "TYPE_CHECKING": ("typing", "from typing import TYPE_CHECKING"),
    # third-party (lower confidence)
    "requests": ("requests", "import requests"),
    "pytest": ("pytest", "import pytest"),
    "numpy": ("numpy", "import numpy as np"),
    "np": ("numpy", "import numpy as np"),
    "pandas": ("pandas", "import pandas as pd"),
    "pd": ("pandas", "import pandas as pd"),
    "flask": ("flask", "from flask import Flask"),
    "Flask": ("flask", "from flask import Flask"),
    "fastapi": ("fastapi", "from fastapi import FastAPI"),
    "FastAPI": ("fastapi", "from fastapi import FastAPI"),
    "pydantic": ("pydantic", "from pydantic import BaseModel"),
    "BaseModel": ("pydantic", "from pydantic import BaseModel"),
    "click": ("click", "import click"),
}

_THIRD_PARTY = {"requests", "pytest", "numpy", "np", "pandas", "pd",
                "flask", "Flask", "fastapi", "FastAPI", "pydantic",
                "BaseModel", "click"}


class ImportResolver:
    """Analyse Python source and suggest missing imports.

    Usage::

        resolver = ImportResolver()
        result = resolver.resolve('data = Path("./data")\\nprint(json.dumps(data))')
        print(result.import_block())
        # from pathlib import Path
        # import json
    """

    def __init__(self, extra_map: dict[str, tuple[str, str]] | None = None) -> None:
        self._map: dict[str, tuple[str, str]] = dict(_STDLIB_MAP)
        if extra_map:
            self._map.update(extra_map)
        self._builtin_names: set[str] = set(dir(builtins))

    # ------------------------------------------------------------------ #
    # Analysis                                                             #
    # ------------------------------------------------------------------ #

    def resolve(self, source: str) -> ResolverResult:
        """Analyse source and return import suggestions."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise ImportResolverError(f"Syntax error: {exc}") from exc

        defined, imported, used = self._collect_names(tree)
        source_imports = sorted(imported)

        undefined = sorted(
            name for name in used
            if name not in defined
            and name not in imported
            and name not in self._builtin_names
        )

        suggestions: list[ImportSuggestion] = []
        for name in undefined:
            if name in self._map:
                module, stmt = self._map[name]
                suggestions.append(ImportSuggestion(
                    name=name,
                    module=module,
                    import_stmt=stmt,
                    confidence=0.8 if name in _THIRD_PARTY else 1.0,
                    is_stdlib=name not in _THIRD_PARTY,
                ))

        return ResolverResult(
            undefined_names=undefined,
            suggestions=suggestions,
            source_imports=source_imports,
        )

    def _collect_names(
        self, tree: ast.AST
    ) -> tuple[set[str], set[str], set[str]]:
        """Return (defined_names, imported_names, used_names)."""
        defined: set[str] = set()
        imported: set[str] = set()
        used: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined.add(target.id)
            elif isinstance(node, (ast.Import,)):
                for alias in node.names:
                    imported.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported.add(alias.asname or alias.name)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    used.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used.add(node.value.id)

        return defined, imported, used

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def suggest_for_name(self, name: str) -> ImportSuggestion | None:
        """Return suggestion for a single name, or None."""
        if name not in self._map:
            return None
        module, stmt = self._map[name]
        return ImportSuggestion(
            name=name,
            module=module,
            import_stmt=stmt,
            confidence=0.8 if name in _THIRD_PARTY else 1.0,
            is_stdlib=name not in _THIRD_PARTY,
        )

    def add_mapping(self, name: str, module: str, import_stmt: str) -> None:
        """Register a custom name → import mapping."""
        self._map[name] = (module, import_stmt)

    def known_names(self) -> list[str]:
        return sorted(self._map.keys())

    def prepend_imports(self, source: str, result: ResolverResult) -> str:
        """Return source with suggested imports prepended."""
        block = result.import_block()
        if not block:
            return source
        return block + "\n\n" + source
