"""Interactive Widgets — Q273."""
from __future__ import annotations

from lidco.widgets.framework import Widget, WidgetEvent, WidgetManager
from lidco.widgets.file_picker import FileEntry, FilePicker
from lidco.widgets.diff_viewer import DiffHunk, DiffViewer
from lidco.widgets.progress_dashboard import ProgressDashboard, TaskProgress

__all__ = [
    "Widget",
    "WidgetEvent",
    "WidgetManager",
    "FileEntry",
    "FilePicker",
    "DiffHunk",
    "DiffViewer",
    "ProgressDashboard",
    "TaskProgress",
]
