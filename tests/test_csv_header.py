from pathlib import Path

import pytest
from click.testing import CliRunner

from rich_cli.__main__ import main

TEST_DATA = Path(__file__).parent.parent / "test_data"
AIRTRAVEL = str(TEST_DATA / "airtravel.csv")  # header not detected automatically
MLB_PLAYERS = str(TEST_DATA / "mlb_players.csv")  # header detected automatically


def run(*args: str):
    return CliRunner().invoke(main, [*args, "--width", "120"])


def header_line(output: str) -> str:
    """The line of the table with the column headers (between ┃ characters)."""
    for line in output.splitlines():
        if line.startswith("┃"):
            return line
    return ""


def test_header_not_detected_by_default():
    result = run(AIRTRAVEL, "--head", "1")
    assert result.exit_code == 0, result.output
    assert header_line(result.output) == ""  # no header row
    assert "Month" in result.output  # the first row is shown as data


def test_header_forces_first_row_as_header():
    result = run(AIRTRAVEL, "--header", "--head", "1")
    assert result.exit_code == 0, result.output
    assert "Month" in header_line(result.output)
    assert "1960" in header_line(result.output)
    assert "JAN" in result.output
    assert "FEB" not in result.output  # --head counts rows after the header


def test_no_header_treats_first_row_as_data():
    result = run(MLB_PLAYERS, "--no-header", "--head", "2")
    assert result.exit_code == 0, result.output
    assert header_line(result.output) == ""
    assert "Name" in result.output  # the header row is now data row 1
    assert "Adam Donachie" in result.output
    assert "Paul Bako" not in result.output


def test_header_with_lines():
    result = run(AIRTRAVEL, "--header", "--lines", "2")
    assert result.exit_code == 0, result.output
    assert "FEB" in result.output
    assert "JAN" not in result.output


def test_header_with_sql():
    result = run(
        AIRTRAVEL,
        "--header",
        "--sql",
        "SELECT Month, [1960] FROM data WHERE [1960] > 600",
    )
    assert result.exit_code == 0, result.output
    assert "Warning" not in result.output
    assert "JUL" in result.output and "AUG" in result.output
    assert "JUN" not in result.output  # 535


def test_sql_guesses_header_with_warning_by_default():
    result = run(AIRTRAVEL, "--sql", "SELECT Month FROM data LIMIT 1")
    assert result.exit_code == 0, result.output
    assert "add --header to do this without a warning" in " ".join(
        result.output.split()
    )
    assert "JAN" in result.output


def test_no_header_turns_off_sql_header_guessing():
    result = run(AIRTRAVEL, "--no-header", "--sql", "SELECT Month FROM data")
    assert result.exit_code != 0
    assert "no such column: Month" in result.output
    assert "column1" in result.output  # listed as the available columns


def test_no_header_sql_uses_numbered_columns():
    result = run(
        MLB_PLAYERS, "--no-header", "--sql", "SELECT column1 FROM data LIMIT 2"
    )
    assert result.exit_code == 0, result.output
    assert "Name" in result.output  # header row is data
    assert "Adam Donachie" in result.output


def test_header_from_stdin():
    csv_text = (TEST_DATA / "airtravel.csv").read_text()
    result = CliRunner().invoke(
        main,
        ["-", "--csv", "--header", "--head", "1", "--width", "120"],
        input=csv_text,
    )
    assert result.exit_code == 0, result.output
    assert "Month" in header_line(result.output)


@pytest.mark.parametrize("option", ["--header", "--no-header"])
def test_header_requires_csv(option):
    result = run(str(TEST_DATA / "sections.txt"), option)
    assert result.exit_code != 0
    assert "--header and --no-header only work with CSV" in result.output


def test_help_shows_both_forms():
    result = CliRunner().invoke(main, ["--help"])
    assert "--header / --no-header" in result.output
