import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from rich_cli.__main__ import main
from rich_cli.sql import (
    SQLQueryError,
    column_names,
    format_value,
    run_query,
    table_alias,
)
from rich_cli.sql_help import explain_error, lint_query

TEST_DATA = Path(__file__).parent.parent / "test_data"
MLB_PLAYERS = str(TEST_DATA / "mlb_players.csv")
DENIRO = str(TEST_DATA / "deniro.csv")

HEADER = ["Name", "Team", "Age", "Height(inches)"]
ROWS = [
    ["Alice", "BAL", "9", "70"],
    ["Bob", "NYM", "30.5", "72"],
    ["Carol", "BAL", "100", ""],
    ["Dave", "SF", "", "68"],
]


# --- run_query -------------------------------------------------------------------


def test_select_columns():
    columns, rows = run_query(HEADER, ROWS, "SELECT Name, Team FROM data")
    assert columns == ["Name", "Team"]
    assert rows == [["Alice", "BAL"], ["Bob", "NYM"], ["Carol", "BAL"], ["Dave", "SF"]]


def test_numeric_columns_compare_as_numbers():
    # As text, '9' > '30.5' and '100' < '30.5'; as numbers it's the reverse
    _, rows = run_query(HEADER, ROWS, "SELECT Name FROM data WHERE Age > 10")
    assert rows == [["Bob"], ["Carol"]]
    _, rows = run_query(HEADER, ROWS, "SELECT Name FROM data ORDER BY Age DESC")
    assert [row[0] for row in rows] == ["Carol", "Bob", "Alice", "Dave"]


def test_filter_text_order_and_limit():
    _, rows = run_query(
        HEADER,
        ROWS,
        "SELECT Name FROM data WHERE Team = 'BAL' ORDER BY Name DESC LIMIT 1",
    )
    assert rows == [["Carol"]]


def test_empty_values_are_null():
    _, rows = run_query(HEADER, ROWS, "SELECT Name FROM data WHERE Age IS NULL")
    assert rows == [["Dave"]]
    _, rows = run_query(
        HEADER, ROWS, "SELECT COUNT(Age), AVG([Height(inches)]) FROM data"
    )
    assert rows == [["3", "70"]]


def test_aggregates_and_group_by():
    columns, rows = run_query(
        HEADER,
        ROWS,
        "SELECT Team, COUNT(*) AS players FROM data GROUP BY Team ORDER BY players DESC, Team",
    )
    assert columns == ["Team", "players"]
    assert rows == [["BAL", "2"], ["NYM", "1"], ["SF", "1"]]


def test_with_clause_and_like():
    _, rows = run_query(
        HEADER,
        ROWS,
        "WITH t AS (SELECT * FROM data WHERE Name LIKE '%a%') SELECT Name FROM t",
    )
    assert rows == [["Alice"], ["Carol"], ["Dave"]]


def test_column_names_are_case_insensitive():
    _, rows = run_query(HEADER, ROWS, "select name from DATA where team = 'SF'")
    assert rows == [["Dave"]]


def test_alias_table_name():
    _, rows = run_query(HEADER, ROWS, "SELECT COUNT(*) FROM players", alias="players")
    assert rows == [["4"]]
    _, rows = run_query(HEADER, ROWS, "SELECT COUNT(*) FROM my_file", alias="my-file")
    assert rows == [["4"]]


def test_no_header_and_ragged_rows():
    rows = [["a", "1"], ["b", "2", "extra"], ["c"]]
    columns, result = run_query([], rows, "SELECT * FROM data")
    assert columns == ["column1", "column2", "column3"]
    assert result == [["a", "1", ""], ["b", "2", "extra"], ["c", "", ""]]


@pytest.mark.parametrize(
    "query",
    [
        "DROP TABLE data",
        "DELETE FROM data",
        "INSERT INTO data (Name) VALUES ('x')",
        "UPDATE data SET Age = 1",
        "CREATE TABLE t (x)",
        "ATTACH DATABASE 'should_not_exist.db' AS x",
        "PRAGMA table_info(data)",
    ],
)
def test_only_select_is_allowed(query, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SQLQueryError, match="only SELECT queries are allowed"):
        run_query(HEADER, ROWS, query)
    assert os.listdir(tmp_path) == []  # nothing was written to disk


@pytest.mark.parametrize(
    "query, message",
    [
        ("SELECT Nope FROM data", "no such column: Nope"),
        ("SELECT * FROM nope", "no such table: nope"),
        ("SELEC * FROM data", "syntax error"),
        ("SELECT 1; SELECT 2", "one statement"),
        ("   ", "the query is empty"),
    ],
)
def test_query_errors(query, message):
    with pytest.raises(SQLQueryError, match=message) as error:
        run_query(HEADER, ROWS, query)
    assert error.value.columns == HEADER


# --- helpers ---------------------------------------------------------------------


def test_column_names():
    assert column_names(["a", "", "A", " b ", "a"], 6) == [
        "a",
        "column2",
        "A_2",
        "b",
        "a_3",
        "column6",
    ]


@pytest.mark.parametrize(
    "value, expected",
    [(None, ""), (3, "3"), (74.0, "74"), (22.99, "22.99"), ("text", "text")],
)
def test_format_value(value, expected):
    assert format_value(value) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("mlb_players", "mlb_players"),
        ("mlb-players", "mlb_players"),
        ("my file", "my_file"),
        ("2024", None),
        ("data", None),
    ],
)
def test_table_alias(name, expected):
    assert table_alias(name) == expected


# --- command line ----------------------------------------------------------------


def run(*args: str):
    return CliRunner().invoke(main, [*args, "--width", "120"])


def test_cli_select_and_filter():
    result = run(
        MLB_PLAYERS,
        "--sql",
        "SELECT Name, Age FROM data WHERE Age > 44 ORDER BY Age DESC",
    )
    assert result.exit_code == 0, result.output
    assert "Julio Franco" in result.output
    assert "Jamie Moyer" in result.output
    assert "Team" not in result.output  # column not selected
    assert result.output.index("Julio Franco") < result.output.index("Jamie Moyer")


def test_cli_file_name_as_table():
    result = run(DENIRO, "--sql", "SELECT Title FROM deniro WHERE Score = 100")
    assert result.exit_code == 0, result.output
    assert "Dear America" in result.output


def test_cli_head_applies_to_results():
    result = run(
        MLB_PLAYERS,
        "--sql",
        "SELECT Name FROM data WHERE Team = 'BAL'",
        "--head",
        "2",
    )
    assert result.exit_code == 0, result.output
    assert "Adam Donachie" in result.output
    assert "Paul Bako" in result.output
    assert "Ramon Hernandez" not in result.output


def test_cli_lines_apply_to_results():
    result = run(
        MLB_PLAYERS,
        "--sql",
        "SELECT Name FROM data WHERE Team = 'BAL'",
        "--lines",
        "1,3",
    )
    assert result.exit_code == 0, result.output
    assert "Adam Donachie" in result.output
    assert "Paul Bako" not in result.output
    assert "Ramon Hernandez" in result.output


def test_cli_error_lists_columns():
    result = run(MLB_PLAYERS, "--sql", "SELECT Nme FROM data")
    assert result.exit_code != 0
    assert "SQL error: no such column: Nme" in result.output
    assert "Height(inches)" in result.output
    assert "mlb_players" in result.output


def test_cli_rejects_writes():
    result = run(MLB_PLAYERS, "--sql", "DROP TABLE data")
    assert result.exit_code != 0
    assert "only SELECT queries are allowed" in result.output


def test_cli_sql_requires_csv():
    result = run(str(TEST_DATA / "sections.txt"), "--sql", "SELECT 1")
    assert result.exit_code != 0
    assert "--sql requires CSV" in result.output


# --- case sensitivity ------------------------------------------------------------

PEOPLE_HEADER = ["Name", "Team", "Zip", "Score"]
PEOPLE = [
    ["José", "BAL", "02134", "90"],
    ["jose", "bal", "10001", "N/A"],
    ["JOSÉ", "Nym", "94105", "75"],
    ["Zoë", "SF", "00501", "-"],
]


def names(query: str):
    return [row[0] for row in run_query(PEOPLE_HEADER, PEOPLE, query)[1]]


def test_text_comparisons_ignore_case():
    assert names("SELECT Name FROM data WHERE Team = 'BAL'") == ["José", "jose"]
    assert names("SELECT Name FROM data WHERE Team IN ('nym', 'sf')") == ["JOSÉ", "Zoë"]
    assert names("SELECT Name FROM data WHERE Name = 'josé'") == ["José", "JOSÉ"]


def test_like_ignores_case_for_all_letters():
    assert names("SELECT Name FROM data WHERE Name LIKE 'JOS%'") == [
        "José",
        "jose",
        "JOSÉ",
    ]
    assert names("SELECT Name FROM data WHERE Name LIKE 'zoË'") == ["Zoë"]


def test_order_and_group_ignore_case():
    assert names("SELECT Team FROM data ORDER BY Team") == ["BAL", "bal", "Nym", "SF"]
    _, rows = run_query(
        PEOPLE_HEADER, PEOPLE, "SELECT COUNT(*) FROM data GROUP BY Team ORDER BY Team"
    )
    assert rows == [["2"], ["1"], ["1"]]


def test_case_sensitive_comparison_is_still_possible():
    assert names("SELECT Name FROM data WHERE Team = 'bal' COLLATE BINARY") == ["jose"]
    assert names("SELECT Name FROM data WHERE Team GLOB 'bal'") == ["jose"]


def test_keywords_columns_and_table_ignore_case():
    _, rows = run_query(
        PEOPLE_HEADER, PEOPLE, "select NAME from DATA where team = 'sf'"
    )
    assert rows == [["Zoë"]]


# --- data types ------------------------------------------------------------------


def test_leading_zeros_are_kept():
    assert names("SELECT Zip FROM data") == ["02134", "10001", "94105", "00501"]
    assert names("SELECT Name FROM data WHERE Zip = '02134'") == ["José"]


def test_missing_value_markers_in_numeric_columns():
    # 'N/A' and '-' are treated as empty, so Score is still numeric
    assert names("SELECT Name FROM data WHERE Score > 80") == ["José"]
    assert names("SELECT Name FROM data WHERE Score IS NULL") == ["jose", "Zoë"]


@pytest.mark.parametrize(
    "values, expected",
    [
        (["1", "2", ""], "INTEGER"),
        (["1", "2.5"], "REAL"),
        (["1", "N/A", "null", "-"], "INTEGER"),
        (["N/A", ""], "TEXT"),
        (["007", "12"], "TEXT"),
        (["0", "0.5", "-3"], "REAL"),
        (["1", "abc"], "TEXT"),
        (["inf", "1"], "TEXT"),
        (["1e3", "2"], "REAL"),
    ],
)
def test_column_type(values, expected):
    from rich_cli.sql import _column_type

    assert _column_type(values) == expected


# --- warnings (queries that run, but may be wrong) --------------------------------

LINT_COLUMNS = ["Name", "Team", "Age"]


@pytest.mark.parametrize(
    "query, warning",
    [
        (
            "SELECT * FROM data WHERE Team = 'A' OR Team = 'B' AND Age > 1",
            "AND is applied before OR",
        ),
        (
            "SELECT * FROM data WHERE Age BETWEEN 1 AND 5 AND Team = 'A' OR Age = 9",
            "AND is applied before OR",
        ),
        ("SELECT * FROM data WHERE Age > 1 || Team = 'x'", "'||' joins text"),
        ('SELECT * FROM data WHERE Team = "BAL"', "Use single quotes for text: 'BAL'"),
    ],
)
def test_lint_warnings(query, warning):
    warnings = lint_query(query, LINT_COLUMNS)
    assert len(warnings) == 1
    assert warning in warnings[0]


@pytest.mark.parametrize(
    "query",
    [
        "SELECT Name || ' (' || Team || ')' FROM data",
        "SELECT * FROM data WHERE Team = 'A' AND Age > 3",
        "SELECT * FROM data WHERE Team = 'A' OR Age > 3",
        "SELECT * FROM data WHERE (Team = 'A' OR Team = 'B') AND Age > 3",
        "SELECT * FROM data WHERE Age BETWEEN 1 AND 5 OR Team = 'A'",
        "SELECT CASE WHEN Age > 3 AND Team = 'A' THEN 1 WHEN Age < 2 OR Team = 'B' THEN 2 END FROM data",
        "SELECT * FROM data WHERE Name = 'this AND that OR other'",
        "SELECT * FROM data -- a OR b AND c\nWHERE Age > 1",
        'SELECT "Name" FROM data WHERE "Team" = \'x\'',
        'SELECT * FROM data WHERE Team = "Team"',
        "SELECT * FROM data WHERE Team IN (SELECT Team FROM data WHERE Age > 1 OR Age < 0) AND Age > 3",
    ],
)
def test_lint_no_false_positives(query):
    assert lint_query(query, LINT_COLUMNS) == []


# --- hints for errors --------------------------------------------------------------


@pytest.mark.parametrize(
    "query, hint",
    [
        ("SELEC Name FROM data", "Did you mean SELECT instead of SELEC?"),
        ("SELECT Name FROM data WHER Age > 40", "Did you mean WHERE instead of WHER?"),
        ("SELECT Name FROM data ORDR BY Age", "Did you mean ORDER instead of ORDR?"),
        ("SELECT Nmae FROM data", "Did you mean Name?"),
        ("SELECT Name WHERE Age > 40", "Add FROM data"),
        ("SELECT Name FROM data WHERE Team = BAL", "put it in single quotes: 'BAL'"),
        ("SELECT Name FROM data WHERE Team = 'BAL", "A quote or bracket isn't closed"),
        (
            "SELECT Name FROM data WHERE Age > 40 && Team = 'NYM'",
            "Use AND instead of &&",
        ),
        ("SELECT Name FROM data WHERE COUNT(*) > 1", "HAVING"),
        ("SELECT COUNTT(*) FROM data", "Did you mean COUNT()?"),
        ("SELECT * FROM players", "The table is called data"),
        ("SELECT Name FROM data WHERE", "The query is incomplete"),
        ("SELECT Height(inches) FROM data", "[Height(inches)]"),
        ("   ", "SELECT * FROM data LIMIT 10"),
    ],
)
def test_error_hints(query, hint):
    header = ["Name", "Team", "Age", "Height(inches)"]
    with pytest.raises(SQLQueryError) as error:
        run_query(header, ROWS, query)
    assert any(hint in text for text in error.value.hints), error.value.hints


def test_no_misleading_hints_for_real_columns():
    with pytest.raises(SQLQueryError) as error:
        run_query(HEADER, ROWS, "SELECT Name WHERE Age > 40")
    assert error.value.hints == ["Add FROM data, e.g. SELECT Name FROM data ..."]


def test_keyword_column_hint():
    hints = explain_error(
        'near "Order": syntax error', "SELECT Order FROM data", ["Order"]
    )
    assert (
        hints[0]
        == "Order is an SQL keyword. Put the column name in square brackets: [Order]"
    )


# --- command line edge cases ---------------------------------------------------------


def test_cli_case_insensitive_value():
    result = run(
        MLB_PLAYERS, "--sql", "SELECT Name FROM data WHERE Team = 'bal' LIMIT 1"
    )
    assert result.exit_code == 0, result.output
    assert "Adam Donachie" in result.output


def test_cli_hints_are_shown():
    result = run(MLB_PLAYERS, "--sql", "SELECT Name FROM data WHER Age > 40")
    assert result.exit_code != 0
    assert "Hint: Did you mean WHERE instead of WHER?" in result.output
    assert "[Height(inches)]" in result.output  # columns listed as they're written


def test_cli_warnings_are_shown():
    result = run(
        MLB_PLAYERS, "--sql", "SELECT Name FROM data WHERE Age > 44 || Team = 'XYZ'"
    )
    assert result.exit_code == 0, result.output
    assert "'||' joins text together" in result.output
    assert "the query returned no rows" in result.output


def test_cli_first_row_used_as_header_when_not_detected(tmp_path):
    # The CSV sniffer doesn't detect this header
    csv_file = tmp_path / "people.csv"
    csv_file.write_text(
        "Zip,Name,Score,City\n02134,José,90,Boston\n10001,jose,N/A,new york\n"
    )
    result = run(str(csv_file), "--sql", "SELECT Name FROM people WHERE Score > 80")
    assert result.exit_code == 0, result.output
    assert "using the first row of the file as the column names" in result.output
    assert "José" in result.output
    assert "jose" not in result.output
