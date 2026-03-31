"""Browser page reader with injectable fetch function."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import urljoin

try:
    from urllib.request import urlopen, Request
except ImportError:  # pragma: no cover
    urlopen = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]


@dataclass
class PageContent:
    """Parsed page content."""

    url: str
    title: str
    text: str
    code_blocks: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    fetched_at: float = 0.0


_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)
_CODE_RE = re.compile(
    r"<(?:code|pre)[^>]*>(.*?)</(?:code|pre)>", re.DOTALL | re.IGNORECASE
)
_LINK_RE = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\n{3,}")
_ENTITY_MAP = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&nbsp;": " "}
_ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|\w+);")


def _decode_entities(text: str) -> str:
    """Decode common HTML entities."""
    for ent, ch in _ENTITY_MAP.items():
        text = text.replace(ent, ch)

    def _replace_numeric(m: re.Match) -> str:
        tok = m.group(0)
        try:
            if tok.startswith("&#x"):
                return chr(int(tok[3:-1], 16))
            if tok.startswith("&#"):
                return chr(int(tok[2:-1]))
        except (ValueError, OverflowError):
            pass
        return tok

    return _ENTITY_RE.sub(_replace_numeric, text)


def _default_fetch(url: str) -> str:
    """Fetch URL using stdlib urllib."""
    if urlopen is None:
        raise RuntimeError("urllib not available")
    req = Request(url, headers={"User-Agent": "lidco-page-reader/1.0"})
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


class PageReader:
    """Read and parse web pages."""

    def __init__(self, fetch_fn: Optional[Callable[[str], str]] = None) -> None:
        self._fetch_fn: Callable[[str], str] = fetch_fn or _default_fetch

    def read(self, url: str) -> PageContent:
        """Fetch *url* and return parsed page content."""
        html = self._fetch_fn(url)
        return PageContent(
            url=url,
            title=self.extract_title(html),
            text=self.extract_text(html),
            code_blocks=self.extract_code_blocks(html),
            links=self.extract_links(html, base_url=url),
            fetched_at=time.time(),
        )

    @staticmethod
    def extract_text(html: str) -> str:
        """Strip tags and return plain text."""
        text = _SCRIPT_STYLE_RE.sub("", html)
        text = _TAG_RE.sub(" ", text)
        text = _decode_entities(text)
        # Collapse whitespace
        lines = [ln.strip() for ln in text.splitlines()]
        text = "\n".join(ln for ln in lines if ln)
        text = _WHITESPACE_RE.sub("\n\n", text)
        return text.strip()

    @staticmethod
    def extract_code_blocks(html: str) -> list[str]:
        """Extract content from <code> and <pre> tags."""
        blocks: list[str] = []
        for m in _CODE_RE.finditer(html):
            inner = _TAG_RE.sub("", m.group(1))
            inner = _decode_entities(inner).strip()
            if inner:
                blocks.append(inner)
        return blocks

    @staticmethod
    def extract_title(html: str) -> str:
        """Extract <title> content."""
        m = _TITLE_RE.search(html)
        if m:
            return _decode_entities(_TAG_RE.sub("", m.group(1))).strip()
        return ""

    @staticmethod
    def extract_links(html: str, base_url: str = "") -> list[str]:
        """Extract href values from <a> tags."""
        raw = _LINK_RE.findall(html)
        result: list[str] = []
        for href in raw:
            href = _decode_entities(href).strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            if base_url and not href.startswith(("http://", "https://", "//")):
                href = urljoin(base_url, href)
            result.append(href)
        return result
