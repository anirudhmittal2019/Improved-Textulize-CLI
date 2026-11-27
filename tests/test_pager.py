"""Tests for the interactive pager, driven headlessly with Textual's test pilot."""

import asyncio
import re

from rich.console import Console

from rich_cli.pager import PagerApp, PagerRenderable

WIDTH, HEIGHT = 40, 10


def make_app(line_count: int = 100, width: int = WIDTH) -> PagerApp:
    console = Console(width=width)
    text = "\n".join(f"line {number}" for number in range(1, line_count + 1))
    lines = console.render_lines(
        text, console.options.update(width=width - 1), new_lines=True
    )
    return PagerApp(content=PagerRenderable(lines, width=width), title="test.txt")


def run(scenario):
    """Run an async test scenario (no pytest plugin needed)."""
    asyncio.run(scenario())


def test_keys_scroll_the_content():
    async def scenario():
        app = make_app()
        async with app.run_test(size=(WIDTH, HEIGHT)) as pilot:
            body = app.body
            assert body.scroll_y == 0

            await pilot.press("j", "j", "j")  # vi: j is down
            await pilot.pause()
            assert body.scroll_y == 3

            await pilot.press("k")  # vi: k is up
            await pilot.pause()
            assert body.scroll_y == 2

            await pilot.press("down")
            await pilot.pause()
            assert body.scroll_y == 3

            await pilot.press("end")
            await pilot.pause()
            assert body.scroll_y == body.max_scroll_y > 0

            await pilot.press("home")
            await pilot.pause()
            assert body.scroll_y == 0

            await pilot.press("space")  # a page down
            await pilot.pause()
            assert body.scroll_y >= HEIGHT - 2

    run(scenario)


def test_half_page_keys():
    async def scenario():
        app = make_app()
        async with app.run_test(size=(WIDTH, HEIGHT)) as pilot:
            body = app.body
            await pilot.press("ctrl+d")
            await pilot.wait_for_scheduled_animations()
            assert body.scroll_y == HEIGHT // 2
            await pilot.press("ctrl+u")
            await pilot.wait_for_scheduled_animations()
            assert body.scroll_y == 0

    run(scenario)


def test_q_quits():
    async def scenario():
        app = make_app()
        async with app.run_test(size=(WIDTH, HEIGHT)) as pilot:
            await pilot.press("q")
            await pilot.pause()
            assert not app.is_running

    run(scenario)


def test_title_and_content():
    async def scenario():
        app = make_app(line_count=3)
        async with app.run_test(size=(WIDTH, HEIGHT)):
            assert app.title == "test.txt"
            svg = app.export_screenshot()
            screen = "".join(re.findall(r"<text[^>]*>(.*?)</text>", svg))
            screen = screen.replace("&#160;", " ")
            assert "line 1" in screen and "line 3" in screen

    run(scenario)
