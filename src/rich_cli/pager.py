"""An interactive pager, built with Textual.

Keys: cursor keys, page up/down, home and end scroll as usual. There are also
vi-style keys: j (down), k (up), ctrl+d / ctrl+u (half a page down / up) and
space (a page down). Press q to quit.
"""

from typing import Iterable, List, Optional

from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.measure import Measurement
from rich.segment import Segment
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.widgets import Static


class PagerRenderable:
    def __init__(
        self, lines: Iterable[List[Segment]], new_lines: bool = False, width: int = 80
    ) -> None:
        """A simple renderable containing a number of lines of segments. May be used as an intermediate
        in rendering process.

        Args:
            lines (Iterable[List[Segment]]): Lists of segments forming lines.
            new_lines (bool, optional): Insert new lines after each line. Defaults to False.
        """
        self.lines = list(lines)
        self.new_lines = new_lines
        self.width = width

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        if self.new_lines:
            new_line = Segment.line()
            for line in self.lines:
                yield from line
                yield new_line
        else:
            for line in self.lines:
                yield from line

    def __rich_measure__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> Measurement:
        return Measurement(self.width, self.width)


class PagerApp(App[None]):
    """App to scroll a renderable."""

    CSS = """
    #body {
        height: 1fr;
    }
    #content {
        width: auto;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("j", "scroll_lines(1)", "Down", show=False),
        Binding("k", "scroll_lines(-1)", "Up", show=False),
        Binding("space", "page_down", "Page down", show=False),
        Binding("ctrl+d", "half_page(1)", "Half page down", show=False),
        Binding("ctrl+u", "half_page(-1)", "Half page up", show=False),
    ]

    def __init__(
        self, content: RenderableType = "", title: Optional[str] = None
    ) -> None:
        super().__init__()
        self.content = content
        if title:
            self.title = title

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="body"):
            yield Static(self.content, id="content")

    def on_mount(self) -> None:
        self.body.focus()

    @property
    def body(self) -> ScrollableContainer:
        return self.query_one("#body", ScrollableContainer)

    def action_scroll_lines(self, lines: int) -> None:
        self.body.scroll_relative(y=lines, animate=False)

    def action_page_down(self) -> None:
        self.body.scroll_page_down(animate=False)

    def action_half_page(self, direction: int) -> None:
        half_page = max(1, self.body.size.height // 2)
        self.body.scroll_relative(y=direction * half_page, animate=True)
