"""Git History Intelligence — Q302.

Exports:
    HistoryAnalyzer  — commit analytics, contributor stats, hotspots
    BlameIntelligence — smart blame with skip-formatting, original author
    BisectAssistant  — binary-search bisect helper
    HistorySearch    — full-text search across commit messages and diffs
"""
from __future__ import annotations

from lidco.githistory.analyzer import HistoryAnalyzer
from lidco.githistory.blame import BlameIntelligence
from lidco.githistory.bisect import BisectAssistant
from lidco.githistory.search import HistorySearch

__all__ = [
    "HistoryAnalyzer",
    "BlameIntelligence",
    "BisectAssistant",
    "HistorySearch",
]
