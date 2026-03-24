"""@-Mention External Context Providers — Continue.dev parity."""
from __future__ import annotations

import re
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class AtMentionProvider:
    name: str
    pattern: str  # regex string matching the full @mention token
    fetch_fn: Callable[[str], str]


@dataclass
class AtMentionResult:
    provider: str
    identifier: str
    content: str
    token_estimate: int
    error: str = ""


class AtMentionParser:
    """Parse @-mention tokens from text and resolve them via registered providers."""

    def __init__(self, providers: list[AtMentionProvider] | None = None) -> None:
        self._providers: list[AtMentionProvider] = list(providers or [])
        self._compiled: list[tuple[re.Pattern, AtMentionProvider]] = []
        for p in self._providers:
            self._compiled.append((re.compile(p.pattern), p))

    def add_provider(self, provider: AtMentionProvider) -> None:
        self._providers = [*self._providers, provider]
        self._compiled.append((re.compile(provider.pattern), provider))

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    def parse(self, text: str) -> list[AtMentionResult]:
        """Find and resolve all @-mentions in text. Returns results list."""
        results: list[AtMentionResult] = []
        for pattern, provider in self._compiled:
            for m in pattern.finditer(text):
                identifier = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
                result = self._fetch(provider, identifier)
                results.append(result)
        return results

    def resolve(self, text: str) -> tuple[str, list[AtMentionResult]]:
        """Return (clean_text, results). Replaces @-mentions in text with empty string."""
        results: list[AtMentionResult] = []
        clean = text
        for pattern, provider in self._compiled:
            def _replace(m: re.Match) -> str:
                identifier = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
                result = self._fetch(provider, identifier)
                results.append(result)
                return ""
            clean = pattern.sub(_replace, clean)
        return clean.strip(), results

    def _fetch(self, provider: AtMentionProvider, identifier: str) -> AtMentionResult:
        try:
            content = provider.fetch_fn(identifier)
            return AtMentionResult(
                provider=provider.name,
                identifier=identifier,
                content=content,
                token_estimate=len(content) // 4,
            )
        except Exception as exc:
            return AtMentionResult(
                provider=provider.name,
                identifier=identifier,
                content="",
                token_estimate=0,
                error=str(exc),
            )


# ------------------------------------------------------------------
# Built-in providers
# ------------------------------------------------------------------

def _fetch_github_issue(identifier: str) -> str:
    """Fetch GitHub issue body by number (requires GH_TOKEN env or public repo)."""
    import os
    token = os.environ.get("GH_TOKEN", "")
    repo = os.environ.get("GH_REPO", "")
    if not repo:
        return f"[gh-issue: GH_REPO not set for issue #{identifier}]"
    url = f"https://api.github.com/repos/{repo}/issues/{identifier}"
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "lidco/1.0"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            import json
            data = json.loads(resp.read())
            return f"Issue #{identifier}: {data.get('title', '')}\n\n{data.get('body', '')}"
    except Exception as exc:
        return f"[gh-issue error: {exc}]"


def _fetch_url(identifier: str) -> str:
    """Fetch URL content (plain text)."""
    try:
        req = urllib.request.Request(identifier, headers={"User-Agent": "lidco/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="replace")[:4000]
    except Exception as exc:
        return f"[url error: {exc}]"


def _fetch_file(identifier: str) -> str:
    """Read a local file."""
    try:
        return Path(identifier).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[file error: {exc}]"


def _fetch_shell(identifier: str) -> str:
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(
            identifier, shell=True, capture_output=True, text=True, timeout=15
        )
        return (result.stdout + result.stderr).strip()
    except Exception as exc:
        return f"[shell error: {exc}]"


def make_default_providers() -> list[AtMentionProvider]:
    """Return the built-in set of @-mention providers."""
    return [
        AtMentionProvider(
            name="gh-issue",
            pattern=r"@gh-issue\s+(\d+)",
            fetch_fn=_fetch_github_issue,
        ),
        AtMentionProvider(
            name="url",
            pattern=r"@url\s+(https?://\S+)",
            fetch_fn=_fetch_url,
        ),
        AtMentionProvider(
            name="file",
            pattern=r"@file\s+(\S+)",
            fetch_fn=_fetch_file,
        ),
        AtMentionProvider(
            name="shell",
            pattern=r"@shell\s+(.+?)(?=\s*@|\s*$)",
            fetch_fn=_fetch_shell,
        ),
    ]
