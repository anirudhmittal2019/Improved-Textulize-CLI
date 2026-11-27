from operator import itemgetter
import re
import sys
from typing import TYPE_CHECKING, List, NoReturn, Optional, Tuple, Union

import click
from pygments.util import ClassNotFound
from rich.console import Console, RenderableType
from rich.markup import escape
from rich.text import Text

console = Console()
error_console = Console(stderr=True)

if TYPE_CHECKING:
    from rich.console import ConsoleOptions, RenderResult
    from rich.measure import Measurement

    from .sections import Section

BOXES = [
    "none",
    "ascii",
    "ascii2",
    "square",
    "rounded",
    "heavy",
    "double",
]

BOX_TEXT = ", ".join(sorted(BOXES))

COMMON_LEXERS = {
    "html": "html",
    "py": "python",
    "md": "markdown",
    "js": "javascript",
    "xml": "xml",
    "json": "json",
    "toml": "toml",
}

VERSION = "1.8.0"


AUTO = 0
SYNTAX = 1
PRINT = 2
MARKDOWN = 3
RST = 4
JSON = 5
RULE = 6
INSPECT = 7
CSV = 8
IPYNB = 9


def on_error(message: str, error: Optional[Exception] = None, code=-1) -> NoReturn:
    """Render an error message then exit the app."""

    if error:
        error_text = Text(message)
        error_text.stylize("bold red")
        error_text += ": "
        error_text += error_console.highlighter(str(error))
        error_console.print(error_text)
    else:
        error_text = Text(message, style="bold red")
        error_console.print(error_text)
    sys.exit(code)


def warn(message: str) -> None:
    """Print a warning (to stderr) and carry on."""
    error_console.print(Text(f"Warning: {message}", style="yellow"), highlight=False)


def read_resource(path: str, lexer: Optional[str]) -> Tuple[str, Optional[str]]:
    """Read a resource form a file or stdin."""
    if not path:
        on_error("missing path or URL")

    if path.startswith(("http://", "https://")):
        import requests

        response = requests.get(path)

        text = response.text
        try:
            mime_type: str = response.headers["Content-Type"]
            if ";" in mime_type:
                mime_type = mime_type.split(";", 1)[0]
        except KeyError:
            pass
        else:
            if not lexer:
                _, dot, ext = path.rpartition(".")
                if dot and ext:
                    ext = ext.lower()
                    lexer = COMMON_LEXERS.get(ext, None)
                if lexer is None:
                    from pygments.lexers import get_lexer_for_mimetype

                    try:
                        lexer = get_lexer_for_mimetype(mime_type).name
                    except Exception:
                        pass
        return (text, lexer)
    try:
        if path == "-":
            return (sys.stdin.read(), None)

        with open(path, "rt", encoding="utf8", errors="replace") as resource_file:
            text = resource_file.read()
        if not lexer:
            _, dot, ext = path.rpartition(".")
            if dot and ext:
                ext = ext.lower()
                lexer = COMMON_LEXERS.get(ext, None)
        if not lexer:
            from pygments.lexers import guess_lexer_for_filename

            try:
                lexer = guess_lexer_for_filename(path, text).name
            except ClassNotFound:
                return (text, "text")
        return (text, lexer)
    except Exception as error:
        on_error(f"unable to read {escape(path)}", error)


class ForceWidth:
    """Force a renderable to a given width."""

    def __init__(self, renderable: "RenderableType", width: int = 80) -> None:
        self.renderable = renderable
        self.width = width

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        child_options = options.update_width(self.width)
        yield from console.render(self.renderable, child_options)

    def __rich_measure__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "Measurement":
        from rich.measure import Measurement

        return Measurement(self.width, self.width)


def blend_text(
    message: str, color1: Tuple[int, int, int], color2: Tuple[int, int, int]
) -> Text:
    """Blend text from one color to another."""
    text = Text(message)
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    dr = r2 - r1
    dg = g2 - g1
    db = b2 - b1
    size = len(text)
    for index in range(size):
        blend = index / size
        color = f"#{int(r1 + dr * blend):02X}{int(g1 + dg * blend):02X}{int(b1 + db * blend):02X}"
        text.stylize(color, index, index + 1)
    return text


class RichCommand(click.Command):
    """Override Clicks help with a Richer version."""

    # TODO: Extract this in to a general tool, i.e. rich-click

    def format_help(self, ctx, formatter):

        from rich.highlighter import RegexHighlighter
        from rich.panel import Panel
        from rich.table import Table
        from rich.theme import Theme

        class OptionHighlighter(RegexHighlighter):
            highlights = [
                r"(?P<switch>\-\w)",
                r"(?P<option>\-\-[\w\-]+)",
            ]

        highlighter = OptionHighlighter()

        console = Console(
            theme=Theme(
                {
                    "option": "bold cyan",
                    "switch": "bold green",
                }
            ),
            highlighter=highlighter,
        )

        console.print(
            f"[b]Rich CLI[/b] [magenta]v{VERSION}[/] 🤑\n\n[dim]Rich text and formatting in the terminal\n",
            justify="center",
        )

        console.print(
            "Usage: [b]rich[/b] [b][OPTIONS][/] [b cyan]<PATH,TEXT,URL, or '-'>\n"
        )

        options_table = Table(highlight=True, box=None, show_header=False)

        for param in self.get_params(ctx)[1:]:

            short_opts = [opt for opt in param.opts if not opt.startswith("--")]
            long_opts = [opt for opt in param.opts if opt.startswith("--")]
            opt1 = highlighter(short_opts[0]) if short_opts else Text("")
            opt2 = highlighter(long_opts[0] if long_opts else param.opts[0])

            if param.metavar:
                opt2 += Text(f" {param.metavar}", style="bold yellow")

            options = Text(" ".join(reversed(param.opts)))
            help_record = param.get_help_record(ctx)
            if help_record is None:
                help = ""
            else:
                help = Text.from_markup(param.get_help_record(ctx)[-1], emoji=False)

            if param.metavar:
                options += f" {param.metavar}"

            options_table.add_row(opt1, opt2, highlighter(help))

        console.print(
            Panel(
                options_table, border_style="dim", title="Options", title_align="left"
            )
        )

        from rich.color import Color

        console.print(
            blend_text(
                "♥ https://www.textualize.io",
                Color.parse("#b169dd").triplet,
                Color.parse("#542c91").triplet,
            ),
            justify="left",
            style="bold",
        )


LineRange = Tuple[Optional[int], Optional[int]]


def _parse_line_number(text: str) -> Optional[int]:
    """Parse one side of a line range. Empty text means "open ended"."""
    text = text.strip()
    if not text:
        return None
    try:
        number = int(text)
    except ValueError:
        raise click.BadParameter(f"{text!r} is not a valid line number")
    if number < 1:
        hint = " (use --tail to show the last lines)" if number < 0 else ""
        raise click.BadParameter(f"line numbers start at 1, got {number}{hint}")
    return number


# START-END, accepted as an alternative to START:END
_DASH_RANGE = re.compile(r"(\d+)\s*-\s*(\d+)")


def _format_range(start: Optional[int], end: Optional[int]) -> str:
    if start is not None and start == end:
        return str(start)
    return f"{start or ''}:{end or ''}"


def _parse_section(section: str) -> LineRange:
    """Parse a single section: N, START:END, START-END, START: or :END.

    A backwards range (e.g. 50:10) is accepted, with a warning, and treated as
    the lines between the two numbers (10:50).
    """
    text = section.strip()
    if not text:
        raise click.BadParameter(
            "empty section, expected e.g. 50:70 or 1:5,50:70 (check for stray commas)"
        )
    if text.startswith("-") and not text[1:2].isdigit():
        # Most likely the value was left out, and Click took the next option
        raise click.BadParameter(
            f"expected line numbers such as 50:70, got {text!r} "
            "(did you forget the value?)"
        )
    dash_range = _DASH_RANGE.fullmatch(text)
    if dash_range:
        start_text, colon, end_text = dash_range.group(1), ":", dash_range.group(2)
    else:
        start_text, colon, end_text = text.partition(":")
    if not colon:
        number = _parse_line_number(text)
        return (number, number)
    if ":" in end_text or (not start_text.strip() and not end_text.strip()):
        raise click.BadParameter(
            f"{text!r} is not a valid range, expected START:END (e.g. 50:70)"
        )
    start = _parse_line_number(start_text)
    end = _parse_line_number(end_text)
    if start is not None and end is not None and start > end:
        warn(f"--lines {text} is backwards, showing {end}:{start} instead")
        start, end = end, start
    return (start, end)


def select_line_blocks(
    line_ranges: List[LineRange], count: int, unit: str = "lines"
) -> List[Tuple[int, int]]:
    """Work out which lines (or rows) to show.

    Args:
        line_ranges: Sections from --lines (1-based, inclusive).
        count: Number of lines available.
        unit: Used in warnings, e.g. "rows in the file".

    Returns:
        Sorted, non-overlapping (start, end) blocks of 0-based line indices,
        with `end` exclusive. Adjacent and overlapping sections are merged.
        Sections entirely past the end are skipped with a warning.
    """
    selected = set()
    for start, end in line_ranges:
        first = start or 1
        if first > count:
            warn(
                f"--lines {_format_range(start, end)} is past the end "
                f"({count} {unit})"
            )
            continue
        selected.update(range(first - 1, min(end or count, count)))

    blocks: List[List[int]] = []
    for index in sorted(selected):
        if blocks and blocks[-1][1] == index:
            blocks[-1][1] = index + 1
        else:
            blocks.append([index, index + 1])
    return [(block_start, block_end) for block_start, block_end in blocks]


def parse_line_ranges(
    ctx: Optional[click.Context],
    param: Optional[click.Parameter],
    value: Union[None, str, Tuple[str, ...]],
) -> Optional[List[LineRange]]:
    """Parse one or more --lines values into a list of sections.

    Each value may hold several comma separated sections, and --lines may be
    given more than once. A section is a single line number (N) or a range
    (START:END, START-END, START: or :END). Line numbers are 1-based and
    inclusive.
    """
    if not value:
        return None
    values = (value,) if isinstance(value, str) else value
    return [
        _parse_section(section)
        for option_value in values
        for section in option_value.split(",")
    ]


def check_sql_query(
    ctx: Optional[click.Context], param: Optional[click.Parameter], value: Optional[str]
) -> Optional[str]:
    """Catch a query that wasn't quoted, which the shell splits in to words
    (e.g. --sql SELECT Name FROM data gives just "SELECT")."""
    if value is not None and value.strip().upper() in {"SELECT", "WITH", "SELECT *"}:
        raise click.BadParameter(
            "put the whole query in quotes, "
            'e.g. --sql "SELECT Name FROM data WHERE Age > 30"'
        )
    return value


def parse_section_titles(
    ctx: Optional[click.Context],
    param: Optional[click.Parameter],
    value: Tuple[str, ...],
) -> Tuple[str, ...]:
    """Check --section values: titles must not be empty, and a value that is
    actually one of our options means the title was left out."""
    option_names = set()
    if ctx is not None:
        for command_param in ctx.command.params:
            option_names.update(getattr(command_param, "opts", []))
            option_names.update(getattr(command_param, "secondary_opts", []))
    for title in value:
        if not title.strip():
            raise click.BadParameter(
                "the section title is empty, e.g. use --section Instructions"
            )
        if title in option_names:
            raise click.BadParameter(
                f"expected a section title, got {title!r} (did you forget the title?)"
            )
    return value


@click.command(cls=RichCommand)
@click.argument("resource", metavar="<PATH or TEXT or '-'>", default="")
@click.option(
    "--print",
    "-p",
    "_print",
    is_flag=True,
    help="Print [u]console markup[/u]. [dim]See https://rich.readthedocs.io/en/latest/markup.html",
)
@click.option("--rule", "-u", is_flag=True, help="Display a horizontal [u]rule[/u].")
@click.option("--json", "-J", is_flag=True, help="Display as [u]JSON[/u].")
@click.option("--markdown", "-m", is_flag=True, help="Display as [u]markdown[/u].")
@click.option("--rst", is_flag=True, help="Display [u]restructured text[/u].")
@click.option("--csv", is_flag=True, help="Display [u]CSV[/u] as a table.")
@click.option("--ipynb", is_flag=True, help="Display [u]Jupyter notebook[/u].")
@click.option("--syntax", is_flag=True, help="[u]Syntax[/u] highlighting.")
@click.option("--inspect", is_flag=True, help="[u]Inspect[/u] a python object.")
@click.option(
    "--head",
    "-h",
    type=click.IntRange(min=1),
    metavar="LINES",
    default=None,
    help="Display first [b]LINES[/] of the file (requires --syntax or --csv).",
)
@click.option(
    "--tail",
    "-t",
    type=click.IntRange(min=1),
    metavar="LINES",
    default=None,
    help="Display last [b]LINES[/] of the file (requires --syntax or --csv).",
)
@click.option(
    "--lines",
    "--line",
    "line_ranges",
    metavar="SECTIONS",
    multiple=True,
    callback=parse_line_ranges,
    help="Display only the lines in [b]SECTIONS[/] of a text file, or rows of a CSV file "
    "(1-based, inclusive). Separate sections with commas or repeat --lines. "
    "[dim]e.g. 50:70 or 1:5,50:70,100:",
)
@click.option(
    "--sql",
    metavar="QUERY",
    default=None,
    callback=check_sql_query,
    help="Query a CSV file with SQL. The table is called [b]data[/]. "
    '[dim]e.g. "SELECT Name, Age FROM data WHERE Age > 30 ORDER BY Age LIMIT 10"',
)
@click.option(
    "--section",
    "sections",
    metavar="TITLE",
    multiple=True,
    callback=parse_section_titles,
    help="Display only the section with heading [b]TITLE[/] from a text, Markdown or RST file "
    "(case-insensitive). Repeat to select several. [dim]e.g. --section Instructions",
)
@click.option(
    "--emoji", "-j", is_flag=True, help="Enable emoji code. [dim]e.g. :sparkle:"
)
@click.option("--left", "-l", is_flag=True, help="Align to left.")
@click.option("--right", "-r", is_flag=True, help="Align to right.")
@click.option("--center", "-c", is_flag=True, help="Align to center.")
@click.option("--text-left", "-L", is_flag=True, help="Justify text to left.")
@click.option("--text-right", "-R", is_flag=True, help="Justify text to right.")
@click.option("--text-center", "-C", is_flag=True, help="Justify text to center.")
@click.option(
    "--text-full", "-F", is_flag=True, help="Justify text to both left and right edges."
)
@click.option(
    "--soft", is_flag=True, help="Enable soft wrapping of text (requires --print)."
)
@click.option(
    "--expand", "-e", is_flag=True, help="Expand to full width (requires --panel)."
)
@click.option(
    "--width",
    "-w",
    metavar="SIZE",
    type=int,
    help="Fit output to [b]SIZE[/] characters.",
    default=-1,
)
@click.option(
    "--max-width",
    "-W",
    metavar="SIZE",
    type=int,
    help="Set maximum width to [b]SIZE[/] characters.",
    default=-1,
)
@click.option(
    "--style", "-s", metavar="STYLE", help="Set text style to [b]STYLE[/b].", default=""
)
@click.option(
    "--rule-style",
    metavar="STYLE",
    help="Set rule style to [b]STYLE[/b].",
    default="bright_green",
)
@click.option(
    "--rule-char",
    metavar="CHARACTER",
    default="─",
    help="Use [b]CHARACTER[/b] to generate a line with --rule.",
)
@click.option(
    "--padding",
    "-d",
    metavar="TOP,RIGHT,BOTTOM,LEFT",
    help="Padding around output. [dim]1, 2 or 4 comma separated integers, e.g. 2,4",
)
@click.option(
    "--panel",
    "-a",
    default="none",
    type=click.Choice(BOXES),
    metavar="BOX",
    help=f"Set panel type to [b]BOX[/b]. [dim]{BOX_TEXT}",
)
@click.option(
    "--panel-style",
    "-S",
    default="",
    metavar="STYLE",
    help="Set the panel style to [b]STYLE[/b] (requires --panel).",
)
@click.option(
    "--theme",
    metavar="THEME",
    help="Set syntax theme to [b]THEME[/b]. [dim]See https://pygments.org/styles/",
    default="ansi_dark",
    envvar="RICH_THEME",
)
@click.option(
    "--line-numbers", "-n", is_flag=True, help="Enable line number in syntax."
)
@click.option(
    "--guides",
    "-g",
    is_flag=True,
    help="Enable indentation guides in syntax highlighting",
)
@click.option(
    "--lexer",
    "-x",
    metavar="LEXER",
    default=None,
    help="Use [b]LEXER[/b] for syntax highlighting. [dim]See https://pygments.org/docs/lexers/",
)
@click.option("--hyperlinks", "-y", is_flag=True, help="Render hyperlinks in markdown.")
@click.option(
    "--no-wrap", is_flag=True, help="Don't word wrap syntax highlighted files."
)
@click.option(
    "--title", metavar="TEXT", default="", help="Set panel title to [b]TEXT[/]."
)
@click.option(
    "--caption", metavar="TEXT", default="", help="Set panel caption to [b]TEXT[/]."
)
@click.option(
    "--force-terminal",
    is_flag=True,
    help="Force terminal output when not writing to a terminal.",
)
@click.option(
    "--export-html",
    "-o",
    metavar="PATH",
    default="",
    help="Write HTML to [b]PATH[/b].",
)
@click.option(
    "--export-svg", metavar="PATH", default="", help="Write SVG to [b]PATH[/b]."
)
@click.option("--pager", is_flag=True, help="Display in an interactive pager.")
@click.option("--version", "-v", is_flag=True, help="Print version and exit.")
def main(
    resource: str,
    version: bool = False,
    _print: bool = False,
    syntax: bool = False,
    rule: bool = False,
    rule_char: Optional[str] = None,
    json: bool = False,
    markdown: bool = False,
    rst: bool = False,
    csv: bool = False,
    ipynb: bool = False,
    inspect: bool = True,
    emoji: bool = False,
    left: bool = False,
    right: bool = False,
    center: bool = False,
    text_left: bool = False,
    text_right: bool = False,
    text_center: bool = False,
    soft: bool = False,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    line_ranges: Optional[List[LineRange]] = None,
    sections: Tuple[str, ...] = (),
    sql: Optional[str] = None,
    text_full: bool = False,
    expand: bool = False,
    width: int = -1,
    max_width: int = -1,
    style: str = "",
    rule_style: str = "",
    no_wrap: bool = True,
    padding: str = "",
    panel: str = "",
    panel_style: str = "",
    title: str = "",
    caption: str = "",
    theme: str = "",
    line_numbers: bool = False,
    guides: bool = False,
    lexer: str = "",
    hyperlinks: bool = False,
    force_terminal: bool = False,
    export_html: str = "",
    export_svg: str = "",
    pager: bool = False,
):
    """Rich toolbox for console output."""
    if version:
        sys.stdout.write(f"{VERSION}\n")
        return
    console = Console(
        emoji=emoji,
        record=bool(export_html or export_svg),
        force_terminal=force_terminal if force_terminal else None,
    )

    def print_usage() -> None:
        console.print(
            r"Usage: [b]rich [OPTIONS][/b] [b cyan]<PATH,TEXT,URL, or '-'>[/]"
        )
        console.print("See [bold green]rich --help[/] for options")
        console.print()
        sys.exit(0)

    if width > 0:
        expand = True

    print_padding: List[int] = []
    if padding:
        try:
            print_padding = [int(pad) for pad in padding.split(",")]
        except Exception:
            on_error(f"padding should be 1, 2 or 4 integers separated by commas")
        else:
            if len(print_padding) not in (1, 2, 4):
                on_error(f"padding should be 1, 2 or 4 integers separated by commas")

    renderable: RenderableType = ""

    resource_format = AUTO
    if _print:
        resource_format = PRINT
    elif syntax:
        resource_format = SYNTAX
    elif json:
        resource_format = JSON
    elif markdown:
        resource_format = MARKDOWN
    elif rule:
        resource_format = RULE
    elif inspect:
        resource_format = INSPECT
    elif csv:
        resource_format = CSV
    elif rst:
        resource_format = RST
    elif ipynb:
        resource_format = IPYNB

    if resource_format == AUTO and "." in resource:
        import os.path

        ext = ""
        if resource.startswith(("http://", "https://")):
            from urllib.parse import urlparse

            try:
                path = urlparse(resource).path
            except Exception:
                pass
            else:
                ext = os.path.splitext(path)[-1].lower()
        else:
            ext = os.path.splitext(resource)[-1].lower()

        if ext == ".md":
            resource_format = MARKDOWN
        elif ext == ".json":
            resource_format = JSON
        elif ext in (".csv", ".tsv"):
            resource_format = CSV
        elif ext == ".rst":
            resource_format = RST
        elif ext == ".ipynb":
            resource_format = IPYNB

    if resource_format == AUTO:
        resource_format = SYNTAX

    if line_ranges is not None:
        if resource_format not in (CSV, SYNTAX, MARKDOWN, RST):
            hint = {
                JSON: " (add --syntax to select lines of the raw JSON)",
                IPYNB: " (add --syntax to select lines of the raw notebook)",
            }.get(resource_format, "")
            on_error(
                "--lines works with CSV, text, Markdown and reStructuredText files"
                + hint
            )
        if head is not None or tail is not None:
            on_error("cannot combine --lines with --head or --tail")
        if sections:
            on_error("cannot combine --lines with --section")

    if sql is not None and resource_format != CSV:
        on_error("--sql requires CSV input (use --csv or a .csv/.tsv file)")

    if sections:
        if resource_format not in (SYNTAX, MARKDOWN, RST):
            on_error(
                {
                    CSV: "--section doesn't work with CSV data, which has no headings. "
                    "To select rows, use --lines (e.g. --lines 50:70) or --sql",
                    JSON: "--section doesn't work with JSON, which has no headings. "
                    "To select lines, use --syntax --lines 10:20",
                    IPYNB: "--section doesn't work with Jupyter notebooks",
                }.get(
                    resource_format,
                    "--section requires a text, Markdown or reStructuredText file",
                )
            )
        if head is not None or tail is not None:
            on_error("cannot combine --section with --head or --tail")

    if resource_format in (PRINT, RULE):
        from rich.text import Text

        justify = "default"
        if text_left:
            justify = "left"
        elif text_right:
            justify = "right"
        elif text_center:
            justify = "center"
        elif text_full:
            justify = "full"

        try:
            if resource == "-":
                renderable = Text.from_markup(
                    sys.stdin.read(), justify=justify, emoji=emoji
                )
            else:
                renderable = Text.from_markup(resource, justify=justify, emoji=emoji)
            renderable.no_wrap = no_wrap

        except Exception as error:
            on_error(f"unable to parse console markup", error)

        if rule:
            from rich.rule import Rule
            from rich.style import Style

            try:
                render_rule_style = Style.parse(rule_style)
            except Exception as error:
                on_error("unable to parse rule style", error)

            renderable = Rule(
                resource,
                style=render_rule_style,
                characters=rule_char or "─",
                align="center" if justify in ("full", "default") else justify,
            )

    elif resource_format == JSON:
        from rich.json import JSON as RichJSON

        json_data, _lexer = read_resource(resource, lexer)
        try:
            renderable = RichJSON(json_data)
        except Exception as error:
            on_error("unable to read json", error)

    elif resource_format == MARKDOWN:
        from .markdown import Markdown

        markdown_data, lexer = read_resource(resource, lexer)
        if sections:
            markdown_data = sections_text(markdown_data, sections)
        elif line_ranges is not None:
            markdown_data = lines_text(markdown_data, line_ranges)
        renderable = Markdown(markdown_data, code_theme=theme, hyperlinks=hyperlinks)

    elif resource_format == RST:
        from rich_rst import RestructuredText

        rst_data, _ = read_resource(resource, lexer)
        if sections:
            rst_data = sections_text(rst_data, sections)
        elif line_ranges is not None:
            rst_data = lines_text(rst_data, line_ranges)
        renderable = RestructuredText(
            rst_data,
            code_theme=theme,
            default_lexer=lexer or "python",
            show_errors=False,
        )

    elif resource_format == INSPECT:
        try:
            inspect_data = eval(resource)
        except Exception:
            console.print_exception()
            on_error(f"unable to eval {resource!r}")

        from rich._inspect import Inspect

        renderable = Inspect(
            inspect_data, help=False, dunder=False, all=False, methods=True
        )

    elif resource_format == CSV:

        renderable = render_csv(resource, head, tail, title, caption, line_ranges, sql)

    elif resource_format == IPYNB:

        renderable = render_ipynb(
            resource,
            theme,
            hyperlinks,
            lexer,
            head,
            tail,
            line_numbers,
            guides,
            no_wrap,
        )

    else:
        if not resource:
            print_usage()
        from rich.syntax import Syntax

        try:
            if resource == "-":
                code = sys.stdin.read()
            else:
                code, lexer = read_resource(resource, lexer)

            num_lines = len(code.splitlines())
            if sections:
                # One Syntax per section, so line numbers match the file
                line_ranges_to_show = [
                    section.line_range for section in find_text_sections(code, sections)
                ]
            elif line_ranges is not None:
                line_ranges_to_show = [
                    (block_start + 1, block_end)
                    for block_start, block_end in select_line_blocks(
                        line_ranges, num_lines, "lines in the file"
                    )
                ]
            else:
                line_ranges_to_show = [_line_range(head, tail, num_lines)]
            syntaxes: List[RenderableType] = []
            for line_range in line_ranges_to_show:
                if syntaxes:
                    syntaxes.append("")
                syntaxes.append(
                    Syntax(
                        code,
                        lexer,
                        theme=theme,
                        line_numbers=line_numbers,
                        indent_guides=guides,
                        word_wrap=not no_wrap,
                        line_range=line_range,
                    )
                )
            if not syntaxes:
                renderable = ""
            elif len(syntaxes) == 1:
                renderable = syntaxes[0]
            else:
                from rich.console import Group

                renderable = Group(*syntaxes)

        except Exception as error:
            on_error("unable to read file", error)

    if print_padding:
        from rich.padding import Padding

        renderable = Padding(renderable, tuple(print_padding), expand=expand)

    if panel != "none":
        from rich import box
        from rich.panel import Panel
        from rich.style import Style

        try:
            render_border_style = Style.parse(panel_style)
        except Exception as error:
            on_error("unable to parse panel style", error)

        renderable = Panel(
            renderable,
            getattr(box, panel.upper()),
            expand=expand,
            title=title,
            subtitle=caption,
            border_style=render_border_style,
        )

    if style:
        from rich.style import Style
        from rich.styled import Styled

        try:
            text_style = Style.parse(style)
        except Exception as error:
            on_error("unable to parse style", error)
        else:
            renderable = Styled(renderable, text_style)

    if width > 0 and not pager:
        renderable = ForceWidth(renderable, width=width)

    justify = "default"
    if left:
        justify = "left"
    elif right:
        justify = "right"
    elif center:
        justify = "center"

    if pager:
        if justify != "default":
            from rich.align import Align

            renderable = Align(renderable, justify)

        from .pager import PagerApp, PagerRenderable

        if width < 0:
            width = console.width
        render_options = console.options.update(width=width - 1)
        lines = console.render_lines(renderable, render_options, new_lines=True)
        PagerApp.run(title=resource, content=PagerRenderable(lines, width=width))

    else:
        try:
            console.print(
                renderable,
                width=None if max_width <= 0 else max_width,
                soft_wrap=soft,
                justify=justify,
            )
        except Exception as error:
            on_error("failed to print resource", error)

    if export_html:
        try:
            console.save_html(export_html, clear=False)
        except Exception as error:
            on_error("failed to save HTML", error)

    if export_svg:
        try:
            console.save_svg(export_svg, clear=False)
        except Exception as error:
            on_error("failed to save SVG", error)


def find_text_sections(text: str, names: Tuple[str, ...]) -> "List[Section]":
    """Select the named sections from a text document, or exit with an error
    listing the sections that are available."""
    from .sections import SectionNotFound, select_sections

    try:
        return select_sections(text, names)
    except SectionNotFound as error:
        missing = ", ".join(repr(name) for name in error.missing)
        noun = "section" if len(error.missing) == 1 else "sections"
        error_console.print(Text(f"{noun} not found: {missing}", style="bold red"))
        for name in error.missing:
            suggestions = error.suggestions.get(name)
            if suggestions:
                prefix = f"Did you mean" + (
                    f" (for {name!r})" if len(error.missing) > 1 else ""
                )
                error_console.print(
                    Text(f"{prefix}: ").append(
                        ", ".join(suggestions), style="bold green"
                    ),
                    highlight=False,
                )
        if error.available:
            top_level = min(section.level for section in error.available)
            error_console.print("\nAvailable sections:")
            for section in error.available:
                indent = "  " * (section.level - top_level + 1)
                error_console.print(Text(f"{indent}{section.title}"), highlight=False)
        else:
            error_console.print(
                "No headings found in this file. Sections start at Markdown headings "
                "(e.g. '## Title') or underlined titles (e.g. 'Title' over '=====')."
            )
        sys.exit(-1)


def sections_text(text: str, names: Tuple[str, ...]) -> str:
    """Return only the text of the named sections, separated by blank lines."""
    lines = text.splitlines()
    return "\n\n".join(
        "\n".join(lines[section.start : section.end])
        for section in find_text_sections(text, names)
    )


def query_csv(
    resource: str, header: List[str], rows: List[List[str]], query: str
) -> Tuple[List[str], List[List[str]]]:
    """Run a SQL query against CSV data, or exit with a helpful error."""
    import os.path

    from .sql import TABLE_NAME, SQLQueryError, query_warnings, run_query, table_alias

    alias = None
    if resource != "-" and not resource.startswith(("http://", "https://")):
        alias = table_alias(os.path.splitext(os.path.basename(resource))[0])

    for message in query_warnings(query):
        warn(message)
    try:
        columns, result_rows = run_query(header, rows, query, alias=alias)
    except SQLQueryError as error:
        error_console.print(Text(f"SQL error: {error}", style="bold red"))
        for hint in error.hints:
            error_console.print(Text(hint, style="yellow"), highlight=False)
        if error.columns:
            table_names = Text("\nTable: ").append(TABLE_NAME, style="bold")
            if alias:
                table_names.append(" (or ").append(alias, style="bold").append(")")
            error_console.print(table_names, highlight=False)
            error_console.print(
                Text("Columns: ").append(", ".join(error.columns), style="bold"),
                highlight=False,
            )
        sys.exit(-1)
    if not result_rows:
        warn("the query returned no rows")
    return columns, result_rows


def lines_text(text: str, line_ranges: List[LineRange]) -> str:
    """Return only the selected lines of `text`, with a blank line between
    sections that aren't next to each other."""
    lines = text.splitlines()
    return "\n\n".join(
        "\n".join(lines[block_start:block_end])
        for block_start, block_end in select_line_blocks(
            line_ranges, len(lines), "lines in the file"
        )
    )


def render_csv(
    resource: str,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    title: Optional[str] = None,
    caption: Optional[str] = None,
    line_ranges: Optional[List[LineRange]] = None,
    sql: Optional[str] = None,
) -> RenderableType:
    """Render resource as CSV.

    Args:
        resource (str): Resource string.
        head (int, optional): Display only the first `head` rows.
        tail (int, optional): Display only the last `tail` rows.
        title (str, optional): Table title.
        caption (str, optional): Table caption.
        line_ranges (list, optional): Sections of rows to display, as a list of
            inclusive, 1-based (start, end) tuples. Either bound may be None to
            leave it open. Rows are counted after the header, if there is one.
            Rows are shown once each, in file order, with a divider wherever
            rows were skipped between sections.
        sql (str, optional): SQL query to run against the data (in a table
            called ``data``). `head`, `tail` and `line_ranges` are applied to
            the query's results.

    Returns:
        RenderableType: Table renderable.
    """
    import io
    import csv
    import re
    from rich import box
    from rich.table import Table
    from operator import itemgetter

    is_number = re.compile(r"\-?[0-9]*?\.?[0-9]*?").fullmatch

    csv_data, _ = read_resource(resource, "csv")
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(csv_data[:1024], delimiters=",\t|;")
        has_header = sniffer.has_header(csv_data[:1024])
    except csv.Error as error:
        if resource.lower().endswith(".csv"):
            dialect = csv.get_dialect("excel")
            has_header = True
        elif resource.lower().endswith(".tsv"):
            dialect = csv.get_dialect("excel-tab")
            has_header = True
        else:
            on_error(str(error))

    csv_file = io.StringIO(csv_data)
    reader = csv.reader(csv_file, dialect=dialect)

    rows = iter(reader)
    header: List[str] = next(rows, []) if has_header else []
    table_rows = [row for row in rows if row]

    if sql is not None:
        header, table_rows = query_csv(resource, header, table_rows, sql)
        has_header = True

    table = Table(
        show_header=has_header,
        box=box.HEAVY_HEAD if has_header else box.SQUARE,
        border_style="blue",
        title=title,
        caption=caption,
        caption_justify="right",
    )
    for column in header:
        table.add_column(column)

    if head is not None:
        table_rows = table_rows[:head]
    elif tail is not None:
        table_rows = table_rows[-tail:]

    # Positions in table_rows after which a divider should be drawn
    section_ends: "set[int]" = set()
    if line_ranges is not None:
        unit = "rows in the query results" if sql is not None else "rows in the file"
        selected_rows: List[List[str]] = []
        for block_start, block_end in select_line_blocks(
            line_ranges, len(table_rows), unit
        ):
            if selected_rows:
                section_ends.add(len(selected_rows) - 1)
            selected_rows.extend(table_rows[block_start:block_end])
        table_rows = selected_rows
    for position, row in enumerate(table_rows):
        if row:
            table.add_row(*row, end_section=position in section_ends)

    for index, table_column in enumerate(table.columns):
        get_index = itemgetter(index)

        for row in table_rows:
            try:
                value = get_index(row)
                if value and not is_number(value):
                    break
            except Exception:
                break
        else:
            table_column.justify = "right"
            table_column.style = "bold green"
            table_column.header_style = "bold green"

    return table


def render_ipynb(
    resource: str,
    theme: str,
    hyperlinks: bool,
    lexer: str,
    head: Optional[int],
    tail: Optional[int],
    line_numbers: bool,
    guides: bool,
    no_wrap: bool,
) -> RenderableType:
    """Render resource as Jupyter notebook.

    Args:
        resource (str): Resource string.
        theme (str): Syntax theme for code cells.
        hyperlinks (bool): Whether to render hyperlinks in Markdown cells.
        lexer (str): Lexer for code cell syntax highlighting (if no language set in notebook).
        head (int): Display first `head` lines of each cell.
        tail (int): Display last `tail` lines of each cell.
        line_numbers (bool): Enable line number in code cells.
        guides (bool): Enable indentation guides in code cell syntax highlighting.
        no_wrap (bool): Don't word wrap syntax highlighted cells.

    Returns:
        RenderableType: Notebook as Markdown renderable.
    """
    import json
    from rich.syntax import Syntax
    from rich.console import Group
    from rich.panel import Panel
    from .markdown import Markdown

    notebook_str, _ = read_resource(resource, None)
    notebook_dict = json.loads(notebook_str)
    lexer = lexer or notebook_dict.get("metadata", {}).get("kernelspec", {}).get(
        "language", ""
    )

    renderable: RenderableType
    new_line = True
    cells: List[RenderableType] = []
    for cell in notebook_dict["cells"]:
        if new_line:
            cells.append("")
        if "execution_count" in cell:
            execution_count = cell["execution_count"] or " "
            cells.append(f"[green]In [[#66ff00]{execution_count}[/#66ff00]]:[/green]")
        source = "".join(cell["source"])
        if cell["cell_type"] == "code":
            num_lines = len(source.splitlines())
            line_range = _line_range(head, tail, num_lines)
            renderable = Panel(
                Syntax(
                    source,
                    lexer,
                    theme=theme,
                    line_numbers=line_numbers,
                    indent_guides=guides,
                    word_wrap=not no_wrap,
                    line_range=line_range,
                ),
                border_style="dim",
            )
        elif cell["cell_type"] == "markdown":
            renderable = Markdown(source, code_theme=theme, hyperlinks=hyperlinks)
        else:
            renderable = Text(source)
        new_line = True
        cells.append(renderable)
        for output in cell.get("outputs", []):
            output_type = output["output_type"]
            if output_type == "stream":
                renderable = Text.from_ansi("".join(output["text"]))
                new_line = False
            elif output_type == "error":
                renderable = Text.from_ansi("\n".join(output["traceback"]).rstrip())
                new_line = True
            elif output_type == "execute_result":
                execution_count = output.get("execution_count", " ") or " "
                renderable = Text.from_markup(
                    f"[red]Out[[#ee4b2b]{execution_count}[/#ee4b2b]]:[/red]\n"
                )
                data = output["data"].get("text/plain", "")
                if isinstance(data, list):
                    renderable += Text.from_ansi("".join(data))
                else:
                    renderable += Text.from_ansi(data)
                new_line = True
            else:
                continue

            cells.append(renderable)

    renderable = Group(*cells)

    return renderable


def _line_range(
    head: Optional[int], tail: Optional[int], num_lines: int
) -> Optional[Tuple[int, int]]:
    if head and tail:
        on_error("cannot specify both head and tail")
    if head:
        line_range = (1, head)
    elif tail:
        start_line = num_lines - tail + 2
        finish_line = num_lines + 1
        line_range = (start_line, finish_line)
    else:
        line_range = None
    return line_range


def run():
    main()


if __name__ == "__main__":
    run()
