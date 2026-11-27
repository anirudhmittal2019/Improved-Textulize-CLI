"""Run SQL queries against CSV data, using an in-memory SQLite database.

The CSV data is loaded in to a table called ``data``.

* Columns where every value is a number are stored as numbers, so comparisons
  such as ``Age > 30`` work numerically. Values with a leading zero (such as
  zip codes, ``02134``) are kept as text. Placeholders such as ``N/A`` in an
  otherwise numeric column are treated as empty.
* Empty values are stored as NULL.
* Text comparisons (``=``, ``IN``, ``ORDER BY``, ``GROUP BY``, ``LIKE`` ...)
  ignore case, including for accented letters. Use ``COLLATE BINARY`` (or
  ``GLOB``) for a case-sensitive comparison.

Only read-only queries (SELECT, including WITH ... SELECT) are allowed.
"""

import re
import sqlite3
from functools import lru_cache
from typing import Any, Iterable, List, Optional, Pattern, Sequence, Tuple

TABLE_NAME = "data"

# Case-insensitive collation used for text columns
COLLATION = "UNICODE_NOCASE"

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Authorizer actions that a read-only query needs.
_ALLOWED_ACTIONS = {
    getattr(sqlite3, name)
    for name in ("SQLITE_SELECT", "SQLITE_READ", "SQLITE_FUNCTION", "SQLITE_RECURSIVE")
    if hasattr(sqlite3, name)
}

# Values treated as "missing" in otherwise numeric columns
NULL_MARKERS = {"n/a", "na", "null", "none", "nan", "-", "--"}

_INTEGER = re.compile(r"[+-]?\d+")
# A number with a leading zero, like a zip code or ID ("007"), but not "0" or "0.5"
_LEADING_ZERO = re.compile(r"[+-]?0\d")


class SQLQueryError(Exception):
    """The query could not be run.

    Attributes:
        columns: Column names of the ``data`` table.
        hints: Suggestions on how to fix the query.
    """

    def __init__(
        self, message: str, columns: Sequence[str], hints: Sequence[str] = ()
    ) -> None:
        self.columns = list(columns)
        self.hints = list(hints)
        super().__init__(message)


def column_names(header: Sequence[str], column_count: int) -> List[str]:
    """Make unique, non-empty column names from a CSV header.

    Missing or empty names become ``column1``, ``column2`` etc. (matching
    SQLite's own naming). Duplicates get a numeric suffix, e.g. ``Name_2``.
    """
    names: List[str] = []
    seen = set()
    for index in range(column_count):
        name = header[index].strip() if index < len(header) else ""
        if not name:
            name = f"column{index + 1}"
        unique_name = name
        suffix = 2
        while unique_name.casefold() in seen:
            unique_name = f"{name}_{suffix}"
            suffix += 1
        seen.add(unique_name.casefold())
        names.append(unique_name)
    return names


def _is_missing(value: str) -> bool:
    return not value or value.casefold() in NULL_MARKERS


def _column_type(values: Iterable[str]) -> str:
    """Pick INTEGER, REAL or TEXT for a column, based on its values.

    The column is numeric only if every value is a number (or missing).
    """
    column_type = "INTEGER"
    has_number = False
    for value in values:
        value = value.strip()
        if _is_missing(value):
            continue
        if _LEADING_ZERO.match(value):
            return "TEXT"  # e.g. zip codes: keep the leading zero
        if column_type == "INTEGER" and _INTEGER.fullmatch(value):
            has_number = True
            continue
        try:
            float(value)
        except ValueError:
            return "TEXT"
        if value.casefold().lstrip("+-") in ("inf", "infinity", "nan"):
            return "TEXT"
        column_type = "REAL"
        has_number = True
    return column_type if has_number else "TEXT"


def _convert(value: str, column_type: str) -> Any:
    """Convert a CSV value for storing in a column of the given type."""
    stripped = value.strip()
    if not stripped:
        return None
    if column_type == "INTEGER":
        return None if _is_missing(stripped) else int(stripped)
    if column_type == "REAL":
        return None if _is_missing(stripped) else float(stripped)
    return value


def table_alias(name: str) -> Optional[str]:
    """Turn a file name (without extension) in to a table name usable in SQL
    without quotes, e.g. ``mlb-players`` -> ``mlb_players``.

    Returns None if there is no usable alias.
    """
    alias = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not _IDENTIFIER.fullmatch(alias) or alias.lower() == TABLE_NAME:
        return None
    return alias


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def format_value(value: Any) -> str:
    """Format a value from a query result for display."""
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return repr(value)
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _authorizer(action: int, *_args: Any) -> int:
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def _compare_nocase(first: str, second: str) -> int:
    """Case-insensitive collation that also handles non-ASCII letters."""
    first_key, second_key = first.casefold(), second.casefold()
    return (first_key > second_key) - (first_key < second_key)


@lru_cache(maxsize=256)
def _like_pattern(pattern: str, escape: Optional[str]) -> Pattern[str]:
    """Convert a SQL LIKE pattern to a case-insensitive regular expression."""
    parts = []
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if escape is not None and character == escape and index + 1 < len(pattern):
            parts.append(re.escape(pattern[index + 1]))
            index += 2
            continue
        if character == "%":
            parts.append(".*")
        elif character == "_":
            parts.append(".")
        else:
            parts.append(re.escape(character))
        index += 1
    return re.compile("".join(parts), re.IGNORECASE | re.DOTALL)


def _like(pattern: Any, value: Any, escape: Any = None) -> Optional[int]:
    """SQL LIKE that ignores case for all letters (SQLite's only does A-Z)."""
    if pattern is None or value is None:
        return None
    if escape is not None and len(str(escape)) != 1:
        raise ValueError("ESCAPE expression must be a single character")
    if isinstance(value, float):
        value = format_value(value)
    match = _like_pattern(str(pattern), escape).fullmatch(str(value))
    return 1 if match else 0


def run_query(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    query: str,
    alias: Optional[str] = None,
) -> Tuple[List[str], List[List[str]]]:
    """Run a SQL query against CSV rows.

    Args:
        header: Column names from the CSV (may be empty if there is no header).
        rows: CSV data rows.
        query: A SELECT query. The data is in a table called ``data``.
        alias: Optional extra name for the table, typically the file name
            without its extension. See `table_alias`.

    Returns:
        The result's column names, and its rows formatted as strings.

    Raises:
        SQLQueryError: If the query is invalid or not read-only.
    """
    from .sql_help import explain_error

    column_count = max([len(header), *(len(row) for row in rows)], default=0)
    columns = column_names(header, column_count)
    alias = table_alias(alias) if alias else None

    if not query.strip():
        raise SQLQueryError(
            "the query is empty",
            columns,
            [f"For example: SELECT * FROM {TABLE_NAME} LIMIT 10"],
        )
    if not columns:
        raise SQLQueryError("there is no data to query", columns)

    # Pad or trim rows so they all have one value per column
    padded_rows = [
        list(row[:column_count]) + [""] * (column_count - len(row)) for row in rows
    ]
    column_types = [
        _column_type(row[index] for row in padded_rows) for index in range(column_count)
    ]

    connection = sqlite3.connect(":memory:")
    try:
        connection.create_collation(COLLATION, _compare_nocase)
        connection.create_function("like", 2, _like, deterministic=True)
        connection.create_function("like", 3, _like, deterministic=True)

        column_defs = ", ".join(
            f"{_quote(name)} {column_type}"
            + (f" COLLATE {COLLATION}" if column_type == "TEXT" else "")
            for name, column_type in zip(columns, column_types)
        )
        connection.execute(f"CREATE TABLE {TABLE_NAME} ({column_defs})")
        placeholders = ", ".join("?" * column_count)
        connection.executemany(
            f"INSERT INTO {TABLE_NAME} VALUES ({placeholders})",
            (
                [_convert(value, kind) for value, kind in zip(row, column_types)]
                for row in padded_rows
            ),
        )
        if alias:
            connection.execute(
                f"CREATE VIEW {_quote(alias)} AS SELECT * FROM {TABLE_NAME}"
            )

        def fail(error: Exception) -> SQLQueryError:
            message = str(error)
            if "not authorized" in message or "prohibited" in message:
                message = "only SELECT queries are allowed"
            hints = explain_error(message, query, columns, alias)
            return SQLQueryError(message, columns, hints)

        connection.set_authorizer(_authorizer)
        try:
            cursor = connection.execute(query)
        except (sqlite3.Error, sqlite3.Warning) as error:
            # sqlite3.Warning is raised by older Pythons for multiple statements
            raise fail(error) from None

        if cursor.description is None:
            raise SQLQueryError("only SELECT queries are allowed", columns)
        result_columns = [description[0] for description in cursor.description]
        try:
            result_rows = [
                [format_value(value) for value in row] for row in cursor.fetchall()
            ]
        except sqlite3.Error as error:
            raise fail(error) from None
        return result_columns, result_rows
    finally:
        connection.close()
