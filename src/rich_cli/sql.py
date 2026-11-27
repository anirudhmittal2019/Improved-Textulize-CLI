"""Run SQL queries against CSV data, using an in-memory SQLite database.

The CSV data is loaded in to a table called ``data``.

* Columns where every value is a number (ignoring blanks and placeholders
  such as ``N/A``) are stored as numbers, so ``Age > 30`` compares
  numerically. Numbers with leading zeros (e.g. zip codes such as ``02134``)
  are kept as text so they are shown unchanged.
* Empty values (and placeholders in number columns) are stored as NULL.
* Text comparisons ignore case, so ``Team = 'bal'`` matches ``BAL``. Add
  ``COLLATE BINARY`` to a comparison to make it case-sensitive.

Only read-only queries (SELECT, including WITH ... SELECT) are allowed.

When a query fails, `SQLQueryError.hints` explains what might be wrong (a
misspelled keyword or column, a missing FROM, a value that needs quotes...),
and `query_warnings` points out queries that run but may not do what was
intended (such as ``||`` used for "or").
"""

import difflib
import math
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Tuple

TABLE_NAME = "data"

# Case-insensitive collation used for text columns
COLLATION = "ICASE"

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_INTEGER = re.compile(r"[+-]?\d+")
_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
# Numbers such as zip codes or IDs with leading zeros (but not 0 or 0.5)
_LEADING_ZERO = re.compile(r"[+-]?0\d")
# Placeholders for a missing value, treated as NULL in number columns
_MISSING = {"", "na", "n/a", "nan", "null", "none", "-", "--", "?"}
# SQLite stores integers in 64 bits
_MAX_INTEGER = 2**63 - 1

# Authorizer actions that a read-only query needs.
_ALLOWED_ACTIONS = {
    getattr(sqlite3, name)
    for name in ("SQLITE_SELECT", "SQLITE_READ", "SQLITE_FUNCTION", "SQLITE_RECURSIVE")
    if hasattr(sqlite3, name)
}

# Keywords used to spot typos such as WHRE or SELCT
_KEYWORDS = [
    "SELECT",
    "FROM",
    "WHERE",
    "GROUP",
    "ORDER",
    "HAVING",
    "LIMIT",
    "OFFSET",
    "DISTINCT",
    "BETWEEN",
    "LIKE",
    "GLOB",
    "NULL",
    "NOT",
    "AND",
    "WITH",
    "UNION",
    "JOIN",
    "INNER",
    "LEFT",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "DESC",
    "ASC",
    "EXISTS",
    "COLLATE",
]
# Every SQL keyword that may be confused with a column name
_RESERVED = set(_KEYWORDS) | {
    "AS",
    "BY",
    "IN",
    "IS",
    "ON",
    "OR",
    "END",
    "ALL",
    "CROSS",
    "OUTER",
    "NATURAL",
    "USING",
    "VALUES",
    "INTERSECT",
    "EXCEPT",
    "ESCAPE",
    "CAST",
    "TABLE",
    "INDEX",
    "KEY",
    "PRIMARY",
    "DEFAULT",
    "CHECK",
    "REFERENCES",
    "TO",
    "INTO",
    "SET",
    "UPDATE",
    "DELETE",
    "INSERT",
    "CREATE",
    "DROP",
    "ALTER",
}
# Clauses that contain conditions
_CONDITION_CLAUSES = {"WHERE", "HAVING", "ON", "WHEN"}
# Words that start a new clause (so conditions before them are finished)
_CLAUSES = {
    "SELECT",
    "FROM",
    "WHERE",
    "GROUP",
    "ORDER",
    "HAVING",
    "LIMIT",
    "OFFSET",
    "UNION",
    "INTERSECT",
    "EXCEPT",
    "ON",
    "JOIN",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
}


class SQLQueryError(Exception):
    """The query could not be run.

    Attributes:
        columns: Column names of the ``data`` table.
        hints: Suggestions for fixing the query.
    """

    def __init__(
        self, message: str, columns: Sequence[str], hints: Sequence[str] = ()
    ) -> None:
        self.columns = list(columns)
        self.hints = list(hints)
        super().__init__(message)


# --- Tokenizing ------------------------------------------------------------------


@dataclass
class Token:
    kind: str  # word, number, string, identifier, symbol, unterminated
    text: str
    depth: int  # parenthesis depth


_SYMBOLS = ("||", "&&", "<=", ">=", "!=", "<>", "==", "<<", ">>")


def tokenize(query: str) -> List[Token]:
    """Split a query in to tokens, skipping comments.

    Strings ('...') and quoted names ("...", [...], `...`) are single tokens,
    so words inside them are never mistaken for keywords.
    """
    tokens: List[Token] = []
    depth = 0
    index = 0
    length = len(query)
    closing = {"'": "'", '"': '"', "`": "`", "[": "]"}
    while index < length:
        char = query[index]
        if char.isspace():
            index += 1
        elif query.startswith("--", index):
            newline = query.find("\n", index)
            index = length if newline == -1 else newline + 1
        elif query.startswith("/*", index):
            end = query.find("*/", index + 2)
            index = length if end == -1 else end + 2
        elif char in closing:
            close = closing[char]
            end = index + 1
            while True:
                end = query.find(close, end)
                if end == -1:
                    tokens.append(Token("unterminated", query[index:], depth))
                    return tokens
                # A doubled quote is an escaped quote ('' or "")
                if close != "]" and query.startswith(close * 2, end):
                    end += 2
                    continue
                break
            kind = "string" if char == "'" else "identifier"
            tokens.append(Token(kind, query[index : end + 1], depth))
            index = end + 1
        elif char.isalpha() or char == "_":
            end = index
            while end < length and (query[end].isalnum() or query[end] in "_$"):
                end += 1
            tokens.append(Token("word", query[index:end], depth))
            index = end
        elif char.isdigit() or (char == "." and query[index + 1 : index + 2].isdigit()):
            match = _NUMBER.match(query, index)
            end = match.end() if match else index + 1
            tokens.append(Token("number", query[index:end], depth))
            index = end
        else:
            symbol = next((s for s in _SYMBOLS if query.startswith(s, index)), char)
            if symbol == ")":
                depth = max(depth - 1, 0)
            tokens.append(Token("symbol", symbol, depth))
            if symbol == "(":
                depth += 1
            index += len(symbol)
    return tokens


def _words(tokens: Iterable[Token]) -> List[str]:
    return [token.text.upper() for token in tokens if token.kind == "word"]


# --- Warnings for queries that run, but may not do what was intended -----------


def query_warnings(query: str) -> List[str]:
    """Find likely mistakes in a query that is valid SQL.

    * ``||``, ``|`` or ``&`` used in a condition, where OR / AND was meant.
    * AND and OR mixed without parentheses (AND is applied first).
    """
    warnings: List[str] = []

    def add(message: str) -> None:
        if message not in warnings:
            warnings.append(message)

    # Track, per parenthesis depth, the current clause and whether AND / OR
    # have been seen in it.
    clause = {0: ""}
    seen_and = {0: False}
    seen_or = {0: False}
    between = {0: False}
    for token in tokenize(query):
        depth = token.depth
        if token.kind == "symbol" and token.text == "(":
            inner = depth + 1
            clause[inner] = clause.get(depth, "")
            seen_and[inner] = seen_or[inner] = between[inner] = False
            continue
        clause.setdefault(depth, "")
        seen_and.setdefault(depth, False)
        seen_or.setdefault(depth, False)
        between.setdefault(depth, False)

        if token.kind == "word":
            word = token.text.upper()
            if word in _CLAUSES:
                clause[depth] = word
                seen_and[depth] = seen_or[depth] = between[depth] = False
            elif word == "BETWEEN":
                between[depth] = True
            elif word == "AND":
                if between[depth]:
                    between[depth] = False  # the AND of BETWEEN x AND y
                else:
                    seen_and[depth] = True
            elif word == "OR":
                seen_or[depth] = True
            if seen_and[depth] and seen_or[depth]:
                add(
                    "AND is applied before OR, so 'A OR B AND C' means "
                    "'A OR (B AND C)'. Add parentheses if you meant '(A OR B) AND C'"
                )
        elif token.kind == "symbol" and clause[depth] in _CONDITION_CLAUSES:
            if token.text == "||":
                add(
                    "'||' joins text together in SQL, it doesn't mean 'or'. "
                    "To combine conditions, use OR"
                )
            elif token.text == "|":
                add("'|' is a bitwise operator in SQL. To combine conditions, use OR")
            elif token.text == "&":
                add("'&' is a bitwise operator in SQL. To combine conditions, use AND")
    return warnings


# --- Explaining errors -------------------------------------------------------------


def _column_reference(name: str) -> str:
    """How to write a column name in a query."""
    if _IDENTIFIER.fullmatch(name) and name.upper() not in _RESERVED:
        return name
    return f"[{name}]"


def _close_matches(word: str, options: Sequence[str], cutoff: float = 0.7) -> List[str]:
    by_key = {option.casefold(): option for option in options}
    return [
        by_key[key]
        for key in difflib.get_close_matches(
            word.casefold(), list(by_key), n=3, cutoff=cutoff
        )
    ]


def _explain(
    message: str, query: str, columns: Sequence[str], tables: Sequence[str]
) -> Tuple[str, List[str]]:
    """Reword a SQLite error message and suggest how to fix the query."""
    tokens = tokenize(query)
    words = _words(tokens)
    hints: List[str] = []
    table_list = " or ".join(tables)

    def keyword_typos() -> None:
        known = {column.casefold() for column in columns} | {
            table.casefold() for table in tables
        }
        for position, token in enumerate(tokens):
            if token.kind != "word" or len(token.text) < 3:
                continue
            word = token.text.upper()
            if word in _RESERVED or token.text.casefold() in known:
                continue
            following = tokens[position + 1] if position + 1 < len(tokens) else None
            if following and following.text == "(":
                continue  # a function call
            for keyword in _close_matches(word, _KEYWORDS, cutoff=0.75)[:1]:
                hints.append(f"Did you mean {keyword} instead of {token.text}?")

    match = re.match(r"no such column: (.+)", message)
    if match:
        name = match.group(1)
        bare_name = name.rsplit(".", 1)[-1]
        if "FROM" not in words:
            hints.append(
                f"The query has no FROM clause. Add FROM {TABLE_NAME}, "
                f"e.g. SELECT {_column_reference(columns[0]) if columns else '*'} "
                f"FROM {TABLE_NAME}"
            )
        else:
            similar = _close_matches(bare_name, columns)
            # Part of a column name with spaces or symbols, e.g. inches
            # from Height(inches)
            similar += [
                column
                for column in columns
                if column not in similar
                and not _IDENTIFIER.fullmatch(column)
                and bare_name.casefold() in column.casefold()
            ]
            if similar:
                hints.append(
                    "Did you mean "
                    + " or ".join(_column_reference(column) for column in similar)
                    + "?"
                )
            if any(not _IDENTIFIER.fullmatch(column) for column in similar):
                hints.append(
                    "Put column names with spaces or symbols in square brackets, "
                    "e.g. [Height(inches)]"
                )
            if not similar:
                hints.append(
                    f"If {bare_name} is a text value rather than a column, put it "
                    f"in single quotes: '{bare_name}'"
                )
        return message, hints

    match = re.match(r"no such table: (.+)", message)
    if match:
        hints.append(
            f"The table is called {table_list}, e.g. SELECT * FROM {TABLE_NAME}"
        )
        return message, hints

    match = re.match(r"no such function: (.+)", message)
    if match:
        name = match.group(1)
        bracketed = [
            column
            for column in columns
            if column.casefold().startswith(name.casefold())
            and not _IDENTIFIER.fullmatch(column)
        ]
        if bracketed:
            hints.append(
                f"To use the column {bracketed[0]}, put it in square brackets: "
                f"[{bracketed[0]}]"
            )
        else:
            hints.append(
                "See https://www.sqlite.org/lang_corefunc.html and "
                "https://www.sqlite.org/lang_aggfunc.html for the available functions"
            )
        return message, hints

    if message == "incomplete input":
        last = next(
            (token.text for token in reversed(tokens) if token.kind != "unterminated"),
            "",
        )
        unterminated = [token for token in tokens if token.kind == "unterminated"]
        if unterminated:
            return "a quote is not closed", [
                f"Check the quotes in: {unterminated[0].text}"
            ]
        if last.upper() in {
            "WHERE",
            "AND",
            "OR",
            "NOT",
            "BY",
            "FROM",
            "SELECT",
            "=",
            ",",
        }:
            hints.append(f"The query ends with '{last}'. Something is missing after it")
        return "the query is incomplete (it ends too early)", hints

    match = re.match(r'unrecognized token: "(.*)"', message, re.S)
    if match:
        token_text = match.group(1)
        if token_text[:1] in "'\"[`":
            return "a quote is not closed", [f"Check the quotes in: {token_text}"]
        if token_text == "!":
            hints.append("Use NOT instead of '!', e.g. WHERE NOT (Age > 30)")
        return message, hints

    if "one statement at a time" in message:
        return "only one query can be run at a time", [
            "Remove the ';' and anything after it"
        ]

    match = re.match(r'near "(.*)": syntax error', message, re.S)
    if match:
        near = match.group(1)
        column_keywords = [
            column
            for column in columns
            if near.upper() in _RESERVED and column.upper() == near.upper()
        ]
        if column_keywords:
            hints.append(
                f"{near} is a SQL keyword. To use the column {column_keywords[0]}, "
                f"put it in square brackets: [{column_keywords[0]}]"
            )
        if any(token.kind == "symbol" and token.text == "!" for token in tokens):
            hints.append("Use NOT instead of '!', e.g. WHERE NOT (Age > 30)")
        keyword_typos()
        first_word = words[0] if words else ""
        if first_word not in {"SELECT", "WITH", "VALUES"}:
            hints.append(
                f"Queries start with SELECT, e.g. SELECT * FROM {TABLE_NAME} "
                "WHERE Age > 30"
            )
        return message, hints

    return message, hints


# --- Loading data and running queries -------------------------------------------


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
    return value.strip().casefold() in _MISSING


def _column_type(values: Iterable[str]) -> str:
    """Pick INTEGER, REAL or TEXT for a column, based on its values.

    A column is a number column if every value is a number or a placeholder
    for a missing value (blank, N/A, null...), and there is at least one
    number. Numbers with leading zeros (zip codes, IDs) make it TEXT, as do
    numbers too large for SQLite.
    """
    column_type = ""
    for value in values:
        value = value.strip()
        if _is_missing(value):
            continue
        if not _NUMBER.fullmatch(value) or _LEADING_ZERO.match(value):
            return "TEXT"
        if _INTEGER.fullmatch(value):
            if abs(int(value)) > _MAX_INTEGER:
                return "TEXT"
            column_type = column_type or "INTEGER"
        else:
            if not math.isfinite(float(value)):
                return "TEXT"
            column_type = "REAL"
    return column_type or "TEXT"


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
        # 15 significant digits hides floating point noise (0.1 + 0.2)
        return f"{value:.15g}"
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _authorizer(action: int, *_args: Any) -> int:
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def _compare_ignoring_case(first: str, second: str) -> int:
    first, second = first.casefold(), second.casefold()
    return (first > second) - (first < second)


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
    column_count = max([len(header), *(len(row) for row in rows)], default=0)
    columns = column_names(header, column_count)
    alias = table_alias(alias) if alias else None
    tables = [TABLE_NAME] + ([alias] if alias else [])

    if not query.strip():
        raise SQLQueryError(
            "the query is empty", columns, [f"e.g. SELECT * FROM {TABLE_NAME}"]
        )
    if not columns:
        raise SQLQueryError("there is no data to query", columns)
    if any(token.kind == "symbol" and token.text == "&&" for token in tokenize(query)):
        raise SQLQueryError(
            "'&&' isn't SQL", columns, ["To combine conditions, use AND (or OR)"]
        )

    # Pad or trim rows so they all have one value per column
    padded_rows = [
        list(row[:column_count]) + [""] * (column_count - len(row)) for row in rows
    ]
    column_types = [
        _column_type(row[index] for row in padded_rows) for index in range(column_count)
    ]

    def convert(value: str, column_type: str) -> Any:
        if column_type == "TEXT":
            return value if value.strip() else None
        if _is_missing(value):
            return None
        if column_type == "INTEGER":
            return int(value.strip())
        return float(value.strip())

    connection = sqlite3.connect(":memory:")
    try:
        connection.create_collation(COLLATION, _compare_ignoring_case)
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
                [convert(value, kind) for value, kind in zip(row, column_types)]
                for row in padded_rows
            ),
        )
        if alias:
            connection.execute(
                f"CREATE VIEW {_quote(alias)} AS SELECT * FROM {TABLE_NAME}"
            )

        connection.set_authorizer(_authorizer)
        try:
            cursor = connection.execute(query)
            if cursor.description is None:
                raise SQLQueryError("only SELECT queries are allowed", columns)
            result_columns = [description[0] for description in cursor.description]
            result_rows = [
                [format_value(value) for value in row] for row in cursor.fetchall()
            ]
        except (sqlite3.Error, sqlite3.Warning, OverflowError) as error:
            # sqlite3.Warning is raised by older Pythons for multiple statements
            message = str(error)
            if "not authorized" in message or "prohibited" in message:
                raise SQLQueryError(
                    "only SELECT queries are allowed", columns
                ) from None
            message, hints = _explain(message, query, columns, tables)
            raise SQLQueryError(message, columns, hints) from None
        return result_columns, result_rows
    finally:
        connection.close()
