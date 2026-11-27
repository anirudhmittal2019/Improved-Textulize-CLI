import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from rich_cli.__main__ import main
from rich_cli.sql import (
    SQLQueryError,
    column_names,
    format_value,
    query_warnings,
    run_query,
    table_alias,
    tokenize,
)

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
        ("SELECT 1; SELECT 2", "only one query can be run at a time"),
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
    [
        (None, ""),
        (3, "3"),
        (74.0, "74"),
        (22.99, "22.99"),
        ("text", "text"),
        (0.1 + 0.2, "0.3"),  # floating point noise is hidden
        (28.736711798839457, "28.7367117988395"),
    ],
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


# --- case sensitivity --------------------------------------------------------------


def names(query, header=HEADER, rows=ROWS):
    return [row[0] for row in run_query(header, rows, query)[1]]


def test_text_comparisons_ignore_case():
    assert names("SELECT Name FROM data WHERE Team = 'bal'") == ["Alice", "Carol"]
    assert names("SELECT Name FROM data WHERE 'bal' = Team") == ["Alice", "Carol"]
    assert names("SELECT Name FROM data WHERE Team IN ('nym', 'sf')") == ["Bob", "Dave"]
    assert names("SELECT Name FROM data WHERE Name LIKE 'ALI%'") == ["Alice"]


def test_collate_binary_is_case_sensitive():
    assert names("SELECT Name FROM data WHERE Team = 'bal' COLLATE BINARY") == []
    assert names("SELECT Name FROM data WHERE Team = 'BAL' COLLATE BINARY") == [
        "Alice",
        "Carol",
    ]


def test_case_insensitive_for_non_ascii_text():
    header, rows = ["Name"], [["\u00c9lodie"], ["Zo\u00eb"]]
    assert names("SELECT Name FROM data WHERE Name = '\u00e9LODIE'", header, rows) == [
        "\u00c9lodie"
    ]


def test_order_by_text_ignores_case():
    header, rows = ["Name"], [["banana"], ["Cherry"], ["apple"]]
    assert names("SELECT Name FROM data ORDER BY Name", header, rows) == [
        "apple",
        "banana",
        "Cherry",
    ]


def test_keywords_columns_and_tables_any_case():
    columns, rows = run_query(
        HEADER, ROWS, "sElEcT nAmE FrOm DaTa WhErE aGe > 50", alias="Players"
    )
    assert columns == ["Name"]  # the column's own name is used
    assert rows == [["Carol"]]
    assert run_query(HEADER, ROWS, "SELECT COUNT(*) FROM PLAYERS", alias="Players")[
        1
    ] == [["4"]]


# --- AND / OR ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query, expected",
    [
        ("SELECT Name FROM data WHERE Team = 'BAL' AND Age > 50", ["Carol"]),
        ("SELECT Name FROM data WHERE Team = 'SF' OR Age > 50", ["Carol", "Dave"]),
        ("select name from data where team = 'bal' and age > 50", ["Carol"]),
        # AND is applied before OR
        (
            "SELECT Name FROM data WHERE Team = 'NYM' OR Team = 'BAL' AND Age > 50",
            ["Bob", "Carol"],
        ),
        (
            "SELECT Name FROM data WHERE (Team = 'NYM' OR Team = 'BAL') AND Age > 20",
            ["Bob", "Carol"],
        ),
        ("SELECT Name FROM data WHERE NOT (Team = 'BAL' OR Age IS NULL)", ["Bob"]),
        (
            "SELECT Name FROM data WHERE Age BETWEEN 9 AND 31 OR Team = 'SF'",
            ["Alice", "Bob", "Dave"],
        ),
    ],
)
def test_and_or(query, expected):
    assert names(query) == expected


def test_warning_for_and_or_without_parentheses():
    message = "AND is applied before OR"
    for query in (
        "SELECT * FROM data WHERE a = 1 OR b = 2 AND c = 3",
        "select * from data where a = 1 and b = 2 or c = 3",
    ):
        assert any(message in warning for warning in query_warnings(query))
    # Not when parentheses group them, or when only one is used
    assert query_warnings("SELECT * FROM data WHERE (a = 1 OR b = 2) AND c = 3") == []
    assert query_warnings("SELECT * FROM data WHERE a = 1 AND b = 2 AND c = 3") == []
    assert query_warnings("SELECT * FROM data WHERE a = 1 OR b = 2 OR c = 3") == []
    # The AND of BETWEEN doesn't count
    assert query_warnings("SELECT * FROM data WHERE a BETWEEN 1 AND 2 OR b = 3") == []
    # Nor do words inside strings
    assert query_warnings("SELECT * FROM data WHERE a = 'x and y or z'") == []


@pytest.mark.parametrize(
    "query, message",
    [
        ("SELECT * FROM data WHERE a > 1 || b = 2", "'||' joins text together"),
        ("SELECT * FROM data WHERE a > 1 | b = 2", "'|' is a bitwise operator"),
        ("SELECT * FROM data WHERE a > 1 & b = 2", "'&' is a bitwise operator"),
        ("SELECT a FROM data GROUP BY a HAVING a > 1 || b", "'||' joins text together"),
    ],
)
def test_warning_for_symbols_used_as_or_and(query, message):
    assert any(message in warning for warning in query_warnings(query))


def test_no_warning_for_text_concatenation():
    assert query_warnings("SELECT Name || ' (' || Team || ')' FROM data") == []
    assert query_warnings("SELECT * FROM data WHERE Name = 'a || b'") == []


def test_double_ampersand_is_an_error():
    with pytest.raises(SQLQueryError, match="'&&' isn't SQL") as error:
        run_query(HEADER, ROWS, "SELECT * FROM data WHERE Age > 1 && Team = 'BAL'")
    assert "use AND" in error.value.hints[0]
    # But it's fine inside a string
    assert names("SELECT Name FROM data WHERE Name = 'a && b'") == []


# --- wrong queries -----------------------------------------------------------------


def error_for(query, header=HEADER, rows=ROWS, alias=None):
    with pytest.raises(SQLQueryError) as error:
        run_query(header, rows, query, alias=alias)
    return str(error.value), " | ".join(error.value.hints)


@pytest.mark.parametrize(
    "query, message, hint",
    [
        ("SELECT Name WHERE Age > 1", "no such column: Name", "has no FROM clause"),
        ("SELECT Nme FROM data", "no such column: Nme", "Did you mean Name?"),
        (
            "SELECT Height(inches) FROM data",
            "no such column: inches",
            "Did you mean [Height(inches)]?",
        ),
        ("SELECT Height FROM data", "no such column: Height", "[Height(inches)]"),
        (
            "SELECT * FROM data WHERE Team = BAL",
            "no such column: BAL",
            "put it in single quotes: 'BAL'",
        ),
        ("SELECT * FROM players", "no such table: players", "The table is called data"),
        ("SELECT MEDIAN(Age) FROM data", "no such function: MEDIAN", "sqlite.org"),
        ("SELEC * FROM data", "syntax error", "Did you mean SELECT instead of SELEC?"),
        (
            "SELECT * FROM data WHRE Age > 1",
            "syntax error",
            "Did you mean WHERE instead of WHRE?",
        ),
        (
            "SELECT * FROM data ORDR BY Age",
            "syntax error",
            "Did you mean ORDER instead of ORDR?",
        ),
        ("Age > 30", "syntax error", "Queries start with SELECT"),
        ("SELECT * FROM data WHERE !(Age > 1)", "", "Use NOT instead of '!'"),
        (
            "SELECT * FROM data WHERE Age > 1 AND",
            "the query is incomplete",
            "ends with 'AND'",
        ),
        ("SELECT * FROM data WHERE", "the query is incomplete", "ends with 'WHERE'"),
        ("SELECT * FROM data WHERE Team = 'BAL", "a quote is not closed", "'BAL"),
        ("SELECT * FROM data; DROP TABLE data", "only one query", "Remove the ';'"),
    ],
)
def test_wrong_query_hints(query, message, hint):
    error_message, hints = error_for(query)
    assert message in error_message
    assert hint in hints


def test_keyword_column_hint():
    message, hints = error_for(
        "SELECT Name, Order FROM data", ["Name", "Order"], [["a", "1"]]
    )
    assert "syntax error" in message
    assert "put it in square brackets: [Order]" in hints
    # Works with brackets
    assert run_query(["Name", "Order"], [["a", "1"]], "SELECT [Order] FROM data")[
        1
    ] == [["1"]]


def test_no_false_keyword_hint_for_normal_columns():
    _, hints = error_for("SELECT * FROM data WHRE Age > 1")
    assert "SQL keyword" not in hints


def test_trailing_semicolon_is_fine():
    assert names("SELECT Name FROM data WHERE Team = 'SF';") == ["Dave"]


def test_comments_are_ignored():
    assert names("SELECT Name -- the name\nFROM data /* all */ WHERE Team = 'SF'") == [
        "Dave"
    ]


def test_tokenize_strings_and_names():
    tokens = tokenize("SELECT [a b], \"c\"\"d\" FROM t WHERE x = 'it''s || and'")
    kinds = [(token.kind, token.text) for token in tokens]
    assert ("identifier", "[a b]") in kinds
    assert ("identifier", '"c""d"') in kinds
    assert ("string", "'it''s || and'") in kinds
    assert ("symbol", "||") not in kinds


# --- data types --------------------------------------------------------------------

EDGE_HEADER = ["zip", "score", "id", "note", "ratio"]
EDGE_ROWS = [
    ["02134", "10", "12345678901234567890123", "a", "1e3"],
    ["10001", "N/A", "2", "b", "-"],
    ["94105", "7.5", "3", "nan", "0.5"],
]


def edge(query):
    return run_query(EDGE_HEADER, EDGE_ROWS, query)[1]


def test_leading_zeros_are_kept():
    assert edge("SELECT zip FROM data") == [["02134"], ["10001"], ["94105"]]
    assert edge("SELECT zip FROM data WHERE zip = '02134'") == [["02134"]]


def test_missing_value_placeholders_in_number_columns():
    # N/A doesn't stop score being a number column
    assert edge("SELECT score FROM data WHERE score > 8") == [["10"]]
    assert edge("SELECT COUNT(*) FROM data WHERE score IS NULL") == [["1"]]
    assert edge("SELECT ratio FROM data ORDER BY ratio DESC") == [
        ["1000"],
        ["0.5"],
        [""],
    ]


def test_placeholders_are_kept_in_text_columns():
    assert edge("SELECT note FROM data") == [["a"], ["b"], ["nan"]]


def test_huge_numbers_do_not_crash():
    assert edge("SELECT id FROM data WHERE zip = '02134'") == [
        ["12345678901234567890123"]
    ]


# --- command line: edge cases -----------------------------------------------------


def test_cli_case_insensitive_values():
    result = run(
        MLB_PLAYERS, "--sql", "select name from data where team = 'bal'", "--head", "1"
    )
    assert result.exit_code == 0, result.output
    assert "Adam Donachie" in result.output


def test_cli_prints_warnings():
    result = run(
        MLB_PLAYERS,
        "--sql",
        "SELECT Name FROM data WHERE Team = 'NYM' OR Team = 'BAL' AND Age > 40",
    )
    assert result.exit_code == 0, result.output
    assert "Warning: AND is applied before OR" in result.output


def test_cli_no_rows_warning():
    result = run(MLB_PLAYERS, "--sql", "SELECT * FROM data WHERE Age > 100")
    assert result.exit_code == 0, result.output
    assert "Warning: the query returned no rows" in result.output


def test_cli_prints_hints():
    result = run(MLB_PLAYERS, "--sql", "SELECT Name, Age WHERE Age > 40")
    assert result.exit_code != 0
    assert "SQL error: no such column: Name" in result.output
    assert "The query has no FROM clause" in result.output
    assert "Columns: Name, Team" in result.output


@pytest.mark.parametrize("value", ["SELECT", "select", "WITH"])
def test_cli_unquoted_query(value):
    # The shell splits an unquoted query in to words
    result = CliRunner().invoke(
        main, [MLB_PLAYERS, "--sql", value, "Name", "FROM", "data"]
    )
    assert result.exit_code != 0
    assert "put the whole query in quotes" in result.output
