from pathlib import Path

import pytest
from click.testing import CliRunner

from rich_cli.__main__ import main
from rich_cli.sections import (
    SectionNotFound,
    display_title,
    find_sections,
    loose_title,
    normalize_title,
    select_sections,
)

TEST_DATA = Path(__file__).parent.parent / "test_data"
SECTIONS_TXT = str(TEST_DATA / "sections.txt")
README = str(Path(__file__).parent.parent / "README.md")

MARKDOWN = """\
# Guide

Intro.

## Setup ##

```bash
# Not a heading
echo hi
```

## Example

First example.

## Usage

### Example

Nested example.

## Last

The end.
"""


def titles(sections):
    return [(section.title, section.level) for section in sections]


def section_lines(text, section):
    return text.splitlines()[section.start : section.end]


# --- finding headings ----------------------------------------------------------


def test_markdown_headings_and_levels():
    assert titles(find_sections(MARKDOWN)) == [
        ("Guide", 1),
        ("Setup", 2),  # closing '##' removed
        ("Example", 2),
        ("Usage", 2),
        ("Example", 3),
        ("Last", 2),
    ]  # '# Not a heading' inside the code fence is ignored


def test_section_ends_at_next_heading_of_same_or_higher_level():
    sections = {s.title + str(s.level): s for s in find_sections(MARKDOWN)}
    usage = section_lines(MARKDOWN, sections["Usage2"])
    assert usage[0] == "## Usage"
    assert "Nested example." in usage  # includes the nested ### Example
    assert "## Last" not in usage
    # The top level section runs to the end of the document
    assert section_lines(MARKDOWN, sections["Guide1"])[-1] == "The end."


def test_trailing_blank_lines_are_not_included():
    section = select_sections(MARKDOWN, ["setup"])[0]
    assert section_lines(MARKDOWN, section)[-1] == "```"


def test_underlined_headings_levels_by_first_appearance():
    text = Path(SECTIONS_TXT).read_text()
    assert titles(find_sections(text)) == [
        ("Project Setup Guide", 1),
        ("Overview", 2),
        ("Instructions", 2),
        ("Windows notes", 3),
        ("Troubleshooting", 2),
    ]


def test_overlined_rst_heading():
    text = "#####\nTitle\n#####\n\nText.\n\nSub\n===\n\nMore.\n"
    sections = find_sections(text)
    assert titles(sections) == [("Title", 1), ("Sub", 2)]
    assert sections[0].start == 0  # overline is part of the section


def test_not_headings():
    text = "\n".join(
        [
            "#hashtag",  # no space after '#'
            "    # indented code comment",
            "",
            "---",  # rule after a blank line
            "",
            "    indented",  # indented text is not a title
            "    ========",
            "| a | b |",
            "|---|---|",
        ]
    )
    assert find_sections(text) == []


def test_normalize_title():
    assert normalize_title("  **Getting   Started** ") == "getting started"
    assert normalize_title("`rich` CLI") == normalize_title("Rich cli")


@pytest.mark.parametrize(
    "title",
    [
        "Instructions",
        "INSTRUCTIONS",
        "instructions",
        "  Instructions  ",
        "\u201cInstructions\u201d",  # smart quotes
        "'Instructions'",
        '"Instructions"',
        "## Instructions",
        "Instructions:",
        "**Instructions**",
        "[Instructions](#instructions)",
        "\uff29\uff4e\uff53\uff54\uff52\uff55\uff43\uff54\uff49\uff4f\uff4e\uff53",  # full width
    ],
)
def test_normalize_title_variants(title):
    assert normalize_title(title) == "instructions"


@pytest.mark.parametrize(
    "title, expected",
    [
        ("1. Getting Started", "getting started"),
        ("2) Setup", "setup"),
        ("1.2.3 - Deep Dive", "deep dive"),
        ("Step 4: Build", "build"),
        ("\U0001f680 Launch!", "launch"),
        ("Why?", "why"),
        ("C++", "c++"),  # trailing symbols are kept...
        ("C#", "c#"),  # ...so these stay different
    ],
)
def test_loose_title(title, expected):
    assert loose_title(title) == expected


def test_display_title():
    assert display_title("[Usage](#usage)") == "Usage"
    assert display_title("See  ![logo](x.png) here") == "See logo here"


# --- selecting sections --------------------------------------------------------


def test_select_is_case_insensitive():
    assert titles(select_sections(MARKDOWN, ["USAGE"])) == [("Usage", 2)]


def test_select_returns_every_match_in_document_order():
    assert titles(select_sections(MARKDOWN, ["last", "example"])) == [
        ("Example", 2),
        ("Example", 3),
        ("Last", 2),
    ]


def test_select_skips_sections_nested_in_another_selection():
    assert titles(select_sections(MARKDOWN, ["usage", "example"])) == [
        ("Example", 2),
        ("Usage", 2),  # contains the level 3 Example, so it isn't repeated
    ]


NUMBERED = """\
# 1. Getting Started

Hi

## Setup:

x

## [Usage](#usage)

y

## \U0001f680 Launch!

z

## C++

cpp
"""


@pytest.mark.parametrize(
    "name, expected",
    [
        ("getting started", "1. Getting Started"),
        ("1. getting started", "1. Getting Started"),
        ("setup", "Setup:"),
        ("usage", "Usage"),
        ("launch", "\U0001f680 Launch!"),
        ("\u201cSetup\u201d", "Setup:"),
        ("## SETUP", "Setup:"),
    ],
)
def test_select_lenient_matching(name, expected):
    assert [section.title for section in select_sections(NUMBERED, [name])] == [
        expected
    ]


def test_select_does_not_confuse_similar_symbols():
    with pytest.raises(SectionNotFound):
        select_sections(NUMBERED, ["C#"])


def test_select_prefers_exact_match_over_loose_match():
    text = "# Setup\n\na\n\n# 1. Setup\n\nb\n"
    assert [s.title for s in select_sections(text, ["setup"])] == ["Setup"]
    assert [s.title for s in select_sections(text, ["1. setup"])] == ["1. Setup"]


def test_select_missing_section_suggestions():
    text = Path(SECTIONS_TXT).read_text()
    with pytest.raises(SectionNotFound) as error:
        select_sections(text, ["Instruction", "windows", "Troubleshoting", "zzz"])
    assert error.value.missing == ["Instruction", "windows", "Troubleshoting", "zzz"]
    assert error.value.suggestions["Instruction"] == ["Instructions"]
    assert error.value.suggestions["windows"] == ["Windows notes"]
    assert error.value.suggestions["Troubleshoting"] == ["Troubleshooting"]
    assert error.value.suggestions["zzz"] == []


def test_select_near_miss_is_not_selected_automatically():
    text = Path(SECTIONS_TXT).read_text()
    with pytest.raises(SectionNotFound):
        select_sections(text, ["Windows"])  # only suggests "Windows notes"


def test_select_same_name_twice():
    assert titles(select_sections(MARKDOWN, ["usage", "USAGE"])) == [("Usage", 2)]


def test_select_missing_section_raises():
    with pytest.raises(SectionNotFound) as error:
        select_sections(MARKDOWN, ["usage", "nope"])
    assert error.value.missing == ["nope"]
    assert "Usage" in [section.title for section in error.value.available]


# --- command line --------------------------------------------------------------


def run(*args: str):
    return CliRunner().invoke(main, [*args, "--width", "100"])


def test_cli_text_file_section():
    result = run(SECTIONS_TXT, "--section", "Instructions")
    assert result.exit_code == 0, result.output
    assert "1. Clone the repository." in result.output
    assert "Windows notes" in result.output  # nested sub-section
    assert "Overview" not in result.output
    assert "Troubleshooting" not in result.output


def test_cli_line_numbers_match_the_file():
    result = run(SECTIONS_TXT, "--section", "troubleshooting", "-n")
    assert result.exit_code == 0, result.output
    lines = Path(SECTIONS_TXT).read_text().splitlines()
    number = lines.index("Troubleshooting") + 1
    assert f"{number} Troubleshooting" in result.output


def test_cli_multiple_sections():
    result = run(SECTIONS_TXT, "--section", "troubleshooting", "--section", "overview")
    assert result.exit_code == 0, result.output
    output = result.output
    assert "Instructions" not in output
    # Document order, not command line order
    assert output.index("Overview") < output.index("Troubleshooting")


def test_cli_markdown_section():
    result = run(README, "--section", "pager")
    assert result.exit_code == 0, result.output
    assert "Pager" in result.output
    assert "--pager" in result.output
    assert "Network" not in result.output  # the next section


def test_cli_rst_section():
    result = run(SECTIONS_TXT, "--rst", "--section", "overview")
    assert result.exit_code == 0, result.output
    assert "Overview" in result.output
    assert "Instructions" not in result.output


def test_cli_missing_section_lists_available():
    result = run(SECTIONS_TXT, "--section", "nope")
    assert result.exit_code != 0
    assert "section not found: 'nope'" in result.output
    assert "Available sections" in result.output
    assert "Instructions" in result.output


def test_cli_file_without_headings():
    result = run(str(TEST_DATA / "airtravel.csv"), "--syntax", "--section", "x")
    assert result.exit_code != 0
    assert "No headings found" in result.output


@pytest.mark.parametrize(
    "args, message",
    [
        (
            [str(TEST_DATA / "airtravel.csv")],
            "--section doesn't work with CSV data, which has no headings. "
            "To select rows, use --lines",
        ),
        ([str(TEST_DATA / "notebook.ipynb")], "doesn't work with Jupyter notebooks"),
        (["hello", "--print"], "--section requires a text, Markdown"),
    ],
)
def test_cli_section_unsupported_formats(args, message):
    result = CliRunner().invoke(main, [*args, "--section", "x", "--width", "200"])
    assert result.exit_code != 0
    assert message in " ".join(result.output.split())  # ignore line wrapping


def test_cli_section_json(tmp_path):
    json_file = tmp_path / "data.json"
    json_file.write_text('{"a": 1}')
    result = run(str(json_file), "--section", "a")
    assert result.exit_code != 0
    assert "doesn't work with JSON" in result.output


@pytest.mark.parametrize(
    "title",
    [
        "instructions",
        "INSTRUCTIONS",
        "\u201cInstructions\u201d",
        "## Instructions",
        "Instructions:",
    ],
)
def test_cli_title_variants(title):
    result = run(SECTIONS_TXT, "--section", title)
    assert result.exit_code == 0, result.output
    assert "1. Clone the repository." in result.output


@pytest.mark.parametrize("title", ["", "   "])
def test_cli_empty_title(title):
    result = run(SECTIONS_TXT, "--section", title)
    assert result.exit_code != 0
    assert "the section title is empty" in result.output


@pytest.mark.parametrize("option", ["-n", "--csv", "--lines"])
def test_cli_forgotten_title(option):
    result = CliRunner().invoke(main, [SECTIONS_TXT, "--section", option])
    assert result.exit_code != 0
    assert "did you forget the title?" in result.output


def test_cli_did_you_mean():
    result = run(SECTIONS_TXT, "--section", "Instruction")
    assert result.exit_code != 0
    assert "section not found: 'Instruction'" in result.output
    assert "Did you mean: Instructions" in result.output


def test_cli_several_missing_sections():
    result = run(
        SECTIONS_TXT,
        "--section",
        "Overview",
        "--section",
        "Nope",
        "--section",
        "Trouble",
    )
    assert result.exit_code != 0
    assert "sections not found: 'Nope', 'Trouble'" in result.output
    assert "Did you mean (for 'Trouble'): Troubleshooting" in result.output
    assert "Did you mean (for 'Nope')" not in result.output


def test_cli_section_conflicts_with_head_and_tail():
    for option in ("--head", "--tail"):
        result = run(SECTIONS_TXT, "--section", "overview", option, "2")
        assert result.exit_code != 0
        assert "cannot combine --section" in result.output
