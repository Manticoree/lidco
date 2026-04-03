"""Widget framework — base widget, event handling, focus management."""
from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class WidgetEvent:
    """An event dispatched to widgets."""

    type: str  # "focus" | "blur" | "keypress" | "click" | "resize"
    target: str
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Widget:
    """Base interactive widget with focus and visibility management."""

    def __init__(
        self,
        id: str,
        title: str = "",
        visible: bool = True,
        focusable: bool = True,
    ) -> None:
        self.id = id
        self.title = title
        self._visible = visible
        self.focusable = focusable
        self._focused = False

    def render(self) -> str:
        """Render widget to text. Base returns title."""
        return self.title

    def handle_event(self, event: WidgetEvent) -> bool:
        """Handle an event. Returns True if handled."""
        if event.type == "focus" and event.target == self.id:
            self.focus()
            return True
        if event.type == "blur" and event.target == self.id:
            self.blur()
            return True
        return False

    def focus(self) -> None:
        self._focused = True

    def blur(self) -> None:
        self._focused = False

    def is_focused(self) -> bool:
        return self._focused

    def show(self) -> None:
        self._visible = True

    def hide(self) -> None:
        self._visible = False

    def is_visible(self) -> bool:
        return self._visible


class WidgetManager:
    """Manages a collection of widgets with focus cycling."""

    def __init__(self) -> None:
        self._widgets: dict[str, Widget] = {}
        self._order: list[str] = []
        self._focus_index: int = -1

    def add(self, widget: Widget) -> Widget:
        self._widgets[widget.id] = widget
        if widget.id not in self._order:
            self._order.append(widget.id)
        return widget

    def remove(self, widget_id: str) -> bool:
        if widget_id not in self._widgets:
            return False
        w = self._widgets.pop(widget_id)
        w.blur()
        self._order.remove(widget_id)
        # Reset focus index if needed
        if self._focus_index >= len(self._order):
            self._focus_index = -1
        return True

    def get(self, widget_id: str) -> Widget | None:
        return self._widgets.get(widget_id)

    def focus_next(self) -> Widget | None:
        """Cycle focus to the next focusable visible widget."""
        focusable = [
            wid for wid in self._order
            if self._widgets[wid].focusable and self._widgets[wid].is_visible()
        ]
        if not focusable:
            return None
        # Blur current
        current = self.focused()
        if current is not None:
            current.blur()
        # Find next
        if current is not None and current.id in focusable:
            idx = focusable.index(current.id)
            next_idx = (idx + 1) % len(focusable)
        else:
            next_idx = 0
        next_widget = self._widgets[focusable[next_idx]]
        next_widget.focus()
        return next_widget

    def focused(self) -> Widget | None:
        for wid in self._order:
            if self._widgets[wid].is_focused():
                return self._widgets[wid]
        return None

    def render_all(self) -> str:
        """Render all visible widgets separated by newlines."""
        parts: list[str] = []
        for wid in self._order:
            w = self._widgets[wid]
            if w.is_visible():
                parts.append(w.render())
        return "\n".join(parts)

    def dispatch(self, event: WidgetEvent) -> bool:
        """Dispatch event. If target set, send to that widget; else broadcast."""
        if event.target:
            w = self._widgets.get(event.target)
            if w is not None:
                return w.handle_event(event)
            return False
        for wid in self._order:
            if self._widgets[wid].handle_event(event):
                return True
        return False

    def all_widgets(self) -> list[Widget]:
        return [self._widgets[wid] for wid in self._order]

    def summary(self) -> dict:
        focused = self.focused()
        return {
            "total": len(self._widgets),
            "visible": sum(1 for w in self._widgets.values() if w.is_visible()),
            "focused": focused.id if focused else None,
        }
