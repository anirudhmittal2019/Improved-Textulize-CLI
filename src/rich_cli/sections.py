"""Find and select named sections (headings) in text documents.

A section starts at a heading and runs until the next heading of the same or a
higher level (or the end of the document). Two heading styles are recognised:

* Markdown "ATX" headings, e.g. ``## Instructions``. The level is the number
  of ``#`` characters.
* Underlined headings, as used by Markdown (setext) and reStructuredText::

      Instructions            ============
      ============            Instructions
                              ============

  The level is determined by the order in which each underline style first
  appears in the document, as reStructuredText does. For Markdown this means
  ``===`` is level 1 and ``---`` is level 2 (when ``===`` appears first).

Lines inside fenced code blocks (``` or ~~~) are never treated as headings.

Titles are matched leniently: case, extra whitespace, surrounding quotes,
Markdown markup (``#``, ``**``, links) and a trailing colon are ignored. If that
finds nothing, leading numbering and symbols are ignored too, so ``Setup``
matches ``1. Setup`` or ``🚀 Setup``.
"""

import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

# Markdown ATX heading: up to 3 spaces, 1-6 '#', a space, the title, and an
# optional closing sequence of '#'.
_ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")

# A line made of one repeated punctuation character, as used to underline (or
# overline) headings in reStructuredText and Markdown.
_ADORNMENT = re.compile(r"^([=\-~^\"'`*+#:._!$%&,/;<>?@\\|])\1*[ \t]*$")

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


@dataclass
class Section:
    """A titled section of a document.

    Attributes:
        title: Heading text.
        level: Heading level (1 is the top level).
        start: Index of the first line of the section (its heading).
        end: Index one past the last line of the section.
    """

    title: str
    level: int
    start: int
    end: int

    @property
    def line_range(self) -> Tuple[int, int]:
        """1-based, inclusive (first, last) line numbers of the section."""
        return (self.start + 1, self.end)


class SectionNotFound(Exception):
    """Raised when one or more requested sections do not exist."""

    def __init__(
        self,
        missing: List[str],
        available: List[Section],
        suggestions: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.missing = missing
        self.available = available
        self.suggestions = suggestions or {}
        super().__init__(", ".join(repr(name) for name in missing))


# Markdown link or image: [text](url) -> text
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
# Quotes a title may be wrapped in, including "smart" quotes
_QUOTES = "\"'\u2018\u2019\u201c\u201d\u00ab\u00bb\u201e\u201a`"
# Leading numbering, e.g. "1. ", "2) ", "1.2.3 ", "3 - ", "Step 4: "
_NUMBERING = re.compile(
    r"^(?:step\s+)?\(?\d+(?:\.\d+)*[.):]?(?:\s*[-\u2013\u2014:])?\s+"
)


def display_title(title: str) -> str:
    """Clean a heading for display, e.g. ``[Usage](#usage)`` -> ``Usage``."""
    return " ".join(_LINK.sub(r"\1", title).split())


def normalize_title(title: str) -> str:
    """Normalize a title for matching.

    Ignores case, extra whitespace, surrounding quotes, leading ``#`` marks,
    Markdown emphasis (``*``, ``_``, backticks), links and a trailing colon
    or full stop.
    """
    title = unicodedata.normalize("NFKC", title)
    title = _LINK.sub(r"\1", title)
    title = title.strip().lstrip("#").strip().strip(_QUOTES)
    title = re.sub(r"[*_`]", "", title)
    title = title.strip().rstrip(":.").strip()
    return " ".join(title.split()).casefold()


def loose_title(title: str) -> str:
    """A looser normalization that also ignores leading numbering (``1.``),
    leading symbols or emoji, and trailing ``!``, ``?`` or ``…``.

    Other trailing symbols are kept, so ``C#`` and ``C++`` stay different.
    """
    title = _NUMBERING.sub("", normalize_title(title))
    title = re.sub(r"^[\W_]+", "", title)
    return title.rstrip("!?\u2026").strip()


def _is_adornment(line: str, min_length: int) -> Optional[str]:
    """Return the adornment character if `line` is an underline/overline."""
    match = _ADORNMENT.match(line)
    if match and len(line.rstrip()) >= min_length:
        return match.group(1)
    return None


def _find_headings(lines: List[str]) -> List[Tuple[int, int, str, Tuple]]:
    """Find headings, returning (start, end, title, style) tuples.

    `start` is the first line of the heading (the overline, if any) and `end`
    is the index one past the heading's last line.
    """
    headings = []
    fence: Optional[str] = None
    index = 0
    line_count = len(lines)
    while index < line_count:
        line = lines[index]

        fence_match = _FENCE.match(line)
        if fence is not None:
            if fence_match and fence_match.group(1)[0] == fence[0]:
                if len(fence_match.group(1)) >= len(fence):
                    fence = None
            index += 1
            continue
        if fence_match:
            fence = fence_match.group(1)
            index += 1
            continue

        atx = _ATX_HEADING.match(line)
        if atx and atx.group(2).strip():
            level = len(atx.group(1))
            headings.append((index, index + 1, atx.group(2).strip(), ("atx", level)))
            index += 1
            continue

        # Overlined heading: adornment / title / same adornment
        if index + 2 < line_count:
            title = lines[index + 1].strip()
            char = _is_adornment(line, 3)
            if (
                char
                and title
                and _is_adornment(lines[index + 2], 3) == char
                and not _ADORNMENT.match(title)
            ):
                headings.append((index, index + 3, title, ("over", char)))
                index += 3
                continue

        # Underlined heading: title / adornment. The title must not be
        # indented (which would make it code or a quote in Markdown and RST).
        if index + 1 < line_count:
            title = line.rstrip()
            if title and not title[0].isspace() and not _ADORNMENT.match(title):
                char = _is_adornment(lines[index + 1], min(3, len(title)))
                if char:
                    headings.append((index, index + 2, title, ("under", char)))
                    index += 2
                    continue

        index += 1
    return headings


def find_sections(text: str) -> List[Section]:
    """Find all sections in a document, in document order."""
    lines = text.splitlines()
    headings = _find_headings(lines)

    # Underline styles get levels by order of first appearance (as in RST).
    style_levels: Dict[Tuple, int] = {}
    levels = []
    for _start, _end, _title, style in headings:
        if style[0] == "atx":
            levels.append(style[1])
        else:
            if style not in style_levels:
                style_levels[style] = len(style_levels) + 1
            levels.append(style_levels[style])

    sections = []
    for position, (start, _end, title, _style) in enumerate(headings):
        level = levels[position]
        end = len(lines)
        for next_position in range(position + 1, len(headings)):
            if levels[next_position] <= level:
                end = headings[next_position][0]
                break
        # Don't include trailing blank lines
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        sections.append(Section(display_title(title), level, start, end))
    return sections


def _suggest(name: str, sections: List[Section]) -> List[str]:
    """Suggest section titles for a name that didn't match."""
    titles: List[str] = []
    for section in sections:
        if section.title not in titles:
            titles.append(section.title)
    wanted = loose_title(name)
    if not wanted:
        return []
    by_key = {loose_title(title): title for title in titles}
    # Titles containing the name (or contained in it), e.g. "Install"
    # for "Installation"
    partial = [
        title
        for key, title in by_key.items()
        if key and (wanted in key or key in wanted)
    ]
    close = [
        by_key[key]
        for key in difflib.get_close_matches(wanted, list(by_key), n=3, cutoff=0.6)
    ]
    suggestions = []
    for title in partial + close:
        if title not in suggestions:
            suggestions.append(title)
    return suggestions[:5]


def select_sections(text: str, names: Iterable[str]) -> List[Section]:
    """Select sections by title.

    Titles are matched leniently (see `normalize_title`). If a name matches
    no title exactly, it is matched again ignoring numbering and symbols (see
    `loose_title`). Every section whose title matches one of `names` is
    returned, in document order. Sections nested inside another selected
    section are not returned separately, as they are already part of it.

    Raises:
        SectionNotFound: If any name doesn't match a section.
    """
    sections = find_sections(text)
    matched: Dict[int, Section] = {}
    missing: List[str] = []
    for name in names:
        for normalize in (normalize_title, loose_title):
            key = normalize(name)
            matches = [
                section
                for section in sections
                if key and normalize(section.title) == key
            ]
            if matches:
                break
        if not matches:
            if name not in missing:
                missing.append(name)
        for section in matches:
            matched[section.start] = section

    if missing:
        suggestions = {name: _suggest(name, sections) for name in missing}
        raise SectionNotFound(missing, sections, suggestions)

    selected: List[Section] = []
    for start in sorted(matched):
        section = matched[start]
        if selected and section.end <= selected[-1].end:
            continue  # nested inside a section we already have
        selected.append(section)
    return selected
