from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from rich_cli.__main__ import main, parse_line_ranges, select_line_blocks

TEST_DATA = Path(__file__).parent.parent / "test_data"
MLB_PLAYERS = str(TEST_DATA / "mlb_players.csv")
SECTIONS_TXT = str(TEST_DATA / "sections.txt")

# First data rows of mlb_players.csv (row 1 is the line after the header)
ROW_NAMES = {
    1: "Adam Donachie",
    2: "Paul Bako",
    3: "Ramon Hernandez",
    4: "Kevin Millar",
    5: "Chris Gomez",
    50: "Darin Erstad",
    51: "Rob Mackowiak",
    1033: "Randy Keisler",
    1034: "Josh Kinney",
}


def run(*args: str):
    return CliRunner().invoke(main, [*args, "--width", "200"])


def shown(output: str):
    """Return the row numbers (from ROW_NAMES) that appear in the output."""
    return {number for number, name in ROW_NAMES.items() if name in output}


def data_lines(output: str):
    return [line for line in output.splitlines() if line.startswith("│")]


def dividers(output: str):
    return [line for line in output.splitlines() if line.startswith("├")]


# --- parsing -----------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("50:70", [(50, 70)]),
        ("50:", [(50, None)]),
        (":70", [(None, 70)]),
        ("3:3", [(3, 3)]),
        ("7", [(7, 7)]),
        (" 2 : 4 ", [(2, 4)]),
        ("1:5,50:70,100:", [(1, 5), (50, 70), (100, None)]),
        ("1:5, 7 , 9:", [(1, 5), (7, 7), (9, None)]),
        (("1:5", "50:70,80"), [(1, 5), (50, 70), (80, 80)]),
        ("50-70", [(50, 70)]),
        ("50 - 70,3-4", [(50, 70), (3, 4)]),
        ("70:50", [(50, 70)]),  # backwards ranges are flipped
        ("70-50", [(50, 70)]),
        ((), None),
        (None, None),
    ],
)
def test_parse_line_ranges(value, expected):
    assert parse_line_ranges(None, None, value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        ":",
        "abc",
        "1:x",
        "0:5",
        "-3:4",
        "0",
        "1:2:3",
        "1:5,",
        ",1:5",
        "1:5,,7",
        "1:5,abc",
        "-w",
        "--csv",
        "1-2-3",
    ],
)
def test_parse_line_ranges_invalid(value):
    with pytest.raises(click.BadParameter):
        parse_line_ranges(None, None, (value,))


# --- single section ------------------------------------------------------------


def test_single_range_is_inclusive_and_excludes_header():
    result = run(MLB_PLAYERS, "--lines", "2:3")
    assert result.exit_code == 0, result.output
    assert "Name" in result.output  # header is still shown
    assert shown(result.output) == {2, 3}
    assert dividers(result.output) == []


def test_single_range_open_ended():
    result = run(MLB_PLAYERS, "--lines", ":1")
    assert result.exit_code == 0, result.output
    assert shown(result.output) == {1}

    # The file has 1034 data rows
    result = run(MLB_PLAYERS, "--lines", "1033:")
    assert result.exit_code == 0, result.output
    assert shown(result.output) == {1033, 1034}


# --- multiple sections ---------------------------------------------------------


def test_multiple_sections_comma_separated():
    result = run(MLB_PLAYERS, "--lines", "2:3,50:51,1034")
    assert result.exit_code == 0, result.output
    assert shown(result.output) == {2, 3, 50, 51, 1034}
    assert len(data_lines(result.output)) == 5
    # A divider between each of the three separate sections
    assert len(dividers(result.output)) == 2


def test_multiple_sections_repeated_option():
    result = run(MLB_PLAYERS, "--lines", "50:51", "--lines", "2")
    assert result.exit_code == 0, result.output
    assert shown(result.output) == {2, 50, 51}
    assert len(dividers(result.output)) == 1


def test_sections_shown_in_file_order():
    result = run(MLB_PLAYERS, "--lines", "50,2")
    assert result.exit_code == 0, result.output
    output = result.output
    assert output.index(ROW_NAMES[2]) < output.index(ROW_NAMES[50])


def test_overlapping_and_adjacent_sections_are_merged():
    result = run(MLB_PLAYERS, "--lines", "1:3,2:4,5")
    assert result.exit_code == 0, result.output
    assert shown(result.output) == {1, 2, 3, 4, 5}
    assert len(data_lines(result.output)) == 5  # no duplicated rows
    assert dividers(result.output) == []  # rows 1-5 are contiguous


def test_section_past_end_of_file_is_ignored():
    result = run(MLB_PLAYERS, "--lines", "2,5000:6000")
    assert result.exit_code == 0, result.output
    assert shown(result.output) == {2}
    assert dividers(result.output) == []


# --- errors --------------------------------------------------------------------


def test_invalid_section_errors():
    result = run(MLB_PLAYERS, "--lines", "1:5,0")
    assert result.exit_code != 0
    assert "line numbers start at 1" in result.output


def test_negative_line_number_suggests_tail():
    result = run(MLB_PLAYERS, "--lines", "-5:")
    assert result.exit_code != 0
    assert "use --tail" in result.output


def test_missing_value_is_explained():
    # Without a value, Click takes the next option as the value
    result = CliRunner().invoke(main, [MLB_PLAYERS, "--lines", "--head", "3"])
    assert result.exit_code != 0
    assert "did you forget the value?" in result.output


# --- edge cases ----------------------------------------------------------------


def test_line_is_an_alias_for_lines():
    result = run(MLB_PLAYERS, "--line", "2:3")
    assert result.exit_code == 0, result.output
    assert shown(result.output) == {2, 3}


def test_backwards_range_is_flipped_with_warning():
    result = run(MLB_PLAYERS, "--lines", "3:2")
    assert result.exit_code == 0, result.output
    assert "--lines 3:2 is backwards, showing 2:3 instead" in result.output
    assert shown(result.output) == {2, 3}


def test_dash_range():
    result = run(MLB_PLAYERS, "--lines", "50-51")
    assert result.exit_code == 0, result.output
    assert shown(result.output) == {50, 51}


def test_range_past_the_end_warns():
    result = run(MLB_PLAYERS, "--lines", "1,5000:6000")
    assert result.exit_code == 0, result.output
    assert "--lines 5000:6000 is past the end (1034 rows in the file)" in result.output
    assert shown(result.output) == {1}


def test_range_past_the_end_of_query_results_warns():
    result = run(MLB_PLAYERS, "--sql", "SELECT Name FROM data LIMIT 2", "--lines", "3:")
    assert result.exit_code == 0, result.output
    assert "past the end (2 rows in the query results)" in result.output


@pytest.mark.parametrize(
    "line_ranges, count, expected",
    [
        ([(2, 4)], 10, [(1, 4)]),
        ([(None, 2)], 10, [(0, 2)]),
        ([(8, None)], 10, [(7, 10)]),
        ([(1, 3), (2, 5), (6, 6)], 10, [(0, 6)]),  # overlapping + adjacent
        ([(9, 9), (1, 1)], 10, [(0, 1), (8, 9)]),  # sorted
        ([(5, 50)], 10, [(4, 10)]),  # clipped to the end
        ([(11, 20)], 10, []),  # entirely past the end
        ([(1, 5)], 0, []),  # nothing to select
    ],
)
def test_select_line_blocks(line_ranges, count, expected):
    assert select_line_blocks(line_ranges, count) == expected


def test_lines_conflicts_with_head_and_tail():
    for option in ("--head", "--tail"):
        result = run(MLB_PLAYERS, "--lines", "1:5", option, "2")
        assert result.exit_code != 0
        assert "cannot combine --lines" in result.output


def test_lines_conflicts_with_section():
    result = run(SECTIONS_TXT, "--lines", "1:5", "--section", "Overview")
    assert result.exit_code != 0
    assert "cannot combine --lines with --section" in result.output


@pytest.mark.parametrize(
    "args, hint",
    [
        ([str(TEST_DATA / "notebook.ipynb")], "add --syntax"),
        (["hello", "--print"], ""),
    ],
)
def test_lines_unsupported_formats(args, hint):
    result = run(*args, "--lines", "1:5")
    assert result.exit_code != 0
    assert (
        "--lines works with CSV, text, Markdown and reStructuredText" in result.output
    )
    assert hint in result.output


# --- text files ----------------------------------------------------------------

TEXT_LINES = Path(SECTIONS_TXT).read_text().splitlines()


def test_text_file_lines_with_original_line_numbers():
    result = run(SECTIONS_TXT, "--lines", "12:13", "-n")
    assert result.exit_code == 0, result.output
    assert "12 Instructions" in result.output
    assert "13 ------------" in result.output
    assert "Overview" not in result.output
    assert "1. Clone" not in result.output  # line 15


def test_text_file_multiple_sections():
    result = run(SECTIONS_TXT, "--lines", "1,26", "-n")
    assert result.exit_code == 0, result.output
    assert f"1 {TEXT_LINES[0]}" in result.output
    assert f"26 {TEXT_LINES[25]}" in result.output
    assert "Overview" not in result.output


def test_text_file_backwards_and_past_end():
    result = run(SECTIONS_TXT, "--line", "13:12,100:200")
    assert result.exit_code == 0, result.output
    assert "backwards, showing 12:13" in result.output
    assert f"past the end ({len(TEXT_LINES)} lines in the file)" in result.output
    assert "Instructions" in result.output


def test_stdin_lines():
    result = CliRunner().invoke(main, ["-", "--lines", "2:3"], input="a\nb\nc\nd\n")
    assert result.exit_code == 0, result.output
    assert result.output.split() == ["b", "c"]


def test_markdown_lines_are_rendered():
    readme = str(Path(__file__).parent.parent / "README.md")
    result = run(readme, "--lines", "1:3")
    assert result.exit_code == 0, result.output
    assert "Rich-CLI" in result.output
    assert "# Rich-CLI" not in result.output  # rendered, not raw
    assert "Installation" not in result.output
