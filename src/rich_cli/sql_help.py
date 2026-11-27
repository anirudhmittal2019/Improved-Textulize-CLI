"""Friendly warnings and hints for SQL queries.

`lint_query` finds queries that run but probably don't do what was meant
(e.g. ``||`` used as "or"). `explain_error` turns SQLite error messages in to
hints on how to fix the query (e.g. "Did you mean WHERE?").
"""

import difflib
import re
from typing import Dict, List, NamedTuple, Optional, Sequence

from .sql import TABLE_NAME

# fmt: off
KEYWORDS = {
    "ALL", "AND", "AS", "ASC", "BETWEEN", "BY", "CASE", "CAST", "COLLATE",
    "CROSS", "DESC", "DISTINCT", "ELSE", "END", "ESCAPE", "EXCEPT", "EXISTS",
    "FROM", "GLOB", "GROUP", "HAVING", "IN", "INNER", "INTERSECT", "IS", "JOIN",
    "LEFT", "LIKE", "LIMIT", "NOT", "NULL", "NULLS", "OFFSET", "ON", "OR",
    "ORDER", "OUTER", "OVER", "PARTITION", "RECURSIVE", "SELECT", "THEN",
    "UNION", "USING", "VALUES", "WHEN", "WHERE", "WINDOW", "WITH", "FIRST",
    "LAST", "INTEGER", "REAL", "TEXT", "NUMERIC", "BINARY", "NOCASE",
}

FUNCTIONS = {
    "ABS", "AVG", "CHAR", "COALESCE", "COUNT", "DATE", "DATETIME", "GROUP_CONCAT",
    "HEX", "IFNULL", "IIF", "INSTR", "JULIANDAY", "LENGTH", "LOWER", "LTRIM",
    "MAX", "MIN", "NULLIF", "PRINTF", "FORMAT", "RANDOM", "REPLACE", "ROUND",
    "RTRIM", "SIGN", "STRFTIME", "SUBSTR", "SUBSTRING", "SUM", "TIME", "TOTAL",
    "TRIM", "TYPEOF", "UNICODE", "UPPER", "ROW_NUMBER", "RANK", "DENSE_RANK",
    "LAG", "LEAD", "NTILE", "FIRST_VALUE", "LAST_VALUE", "CEIL", "FLOOR",
    "POWER", "SQRT", "MOD", "LOG", "EXP", "PI",
}

# Keywords that start a new part of a query
_CLAUSES = {
    "SELECT", "FROM", "WHERE", "GROUP", "HAVING", "ORDER", "LIMIT", "OFFSET",
    "ON", "USING", "JOIN", "UNION", "EXCEPT", "INTERSECT", "WINDOW", "CASE",
    "WHEN", "THEN", "ELSE", "END", "WITH", "VALUES",
}
# fmt: on

# Parts of a query that hold conditions
_CONDITION_CLAUSES = {"WHERE", "HAVING", "ON", "WHEN"}

_COMPARISONS = {"=", "==", "!=", "<>", "<", ">", "<=", ">=", "LIKE", "GLOB", "IS"}

_TOKEN = re.compile(
    r"""
    (?P<space>\s+)
    | (?P<comment>--[^\n]*|/\*.*?(?:\*/|$))
    | (?P<string>'(?:[^']|'')*'?)
    | (?P<quoted>"(?:[^"]|"")*"?|\[[^\]]*\]?|`(?:[^`]|``)*`?)
    | (?P<number>\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+)
    | (?P<word>[^\W\d]\w*)
    | (?P<op>\|\||&&|<=|>=|<>|!=|==|[-+*/%<>=&|~!(),;.])
    | (?P<other>.)
    """,
    re.VERBOSE | re.DOTALL,
)


class Token(NamedTuple):
    kind: str
    text: str
    depth: int  # parenthesis depth

    @property
    def upper(self) -> str:
        return self.text.upper()


def tokenize(query: str) -> List[Token]:
    """Split a query in to tokens, skipping whitespace and comments."""
    tokens = []
    depth = 0
    for match in _TOKEN.finditer(query):
        kind = match.lastgroup or "other"
        text = match.group()
        if kind in ("space", "comment"):
            continue
        if text == ")":
            depth = max(0, depth - 1)
        tokens.append(Token(kind, text, depth))
        if text == "(":
            depth += 1
    return tokens


def _unquote(text: str) -> str:
    if text[:1] == "[":
        return text[1:].rstrip("]")
    if text[:1] in '"`':
        quote = text[0]
        return text[1:].rstrip(quote).replace(quote * 2, quote)
    return text


def column_reference(name: str) -> str:
    """How to refer to a column in a query, e.g. ``[Height(inches)]``."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) and name.upper() not in KEYWORDS:
        return name
    return f"[{name}]"


def _close_matches(word: str, candidates: Sequence[str], cutoff: float = 0.7):
    """Case-insensitive close matches, returning the original candidates."""
    by_key: Dict[str, str] = {}
    for candidate in candidates:
        by_key.setdefault(candidate.casefold(), candidate)
    matches = difflib.get_close_matches(word.casefold(), list(by_key), 3, cutoff)
    return [by_key[match] for match in matches]


# --- warnings for queries that run, but may not do what was meant -------------


def lint_query(query: str, columns: Sequence[str]) -> List[str]:
    """Return warnings about likely mistakes in a query that will still run."""
    tokens = tokenize(query)
    warnings: List[str] = []
    column_keys = {column.casefold() for column in columns}

    def add(message: str) -> None:
        if message not in warnings:
            warnings.append(message)

    # State for each parenthesis depth: the current clause, and whether AND
    # and OR have been seen (BETWEEN x AND y doesn't count)
    clause: Dict[int, str] = {}
    seen_and: Dict[int, bool] = {}
    seen_or: Dict[int, bool] = {}
    between: Dict[int, bool] = {}

    def check_and_or(depth: int) -> None:
        if seen_and.get(depth) and seen_or.get(depth):
            add(
                "AND is applied before OR, so 'a OR b AND c' means "
                "'a OR (b AND c)'. Add parentheses if you meant "
                "'(a OR b) AND c'."
            )
        seen_and[depth] = seen_or[depth] = between[depth] = False

    previous: Optional[Token] = None
    for token in tokens:
        depth = token.depth
        if token.text == "(":
            clause[depth + 1] = clause.get(depth, "")
            seen_and[depth + 1] = seen_or[depth + 1] = between[depth + 1] = False
        elif token.text == ")":
            check_and_or(depth + 1)
        elif token.kind == "word":
            word = token.upper
            if word in _CLAUSES:
                check_and_or(depth)
                clause[depth] = word
            elif word == "BETWEEN":
                between[depth] = True
            elif word == "AND":
                if between.get(depth):
                    between[depth] = False
                else:
                    seen_and[depth] = True
            elif word == "OR":
                seen_or[depth] = True
        elif token.text == "||" and clause.get(depth) in _CONDITION_CLAUSES:
            add("'||' joins text together in SQL, it doesn't mean 'or'. Use OR.")
        elif (
            token.kind == "quoted"
            and token.text.startswith('"')
            and previous is not None
            and previous.upper in _COMPARISONS
            and _unquote(token.text).casefold() not in column_keys
        ):
            value = _unquote(token.text)
            add(
                f'"{value}" is in double quotes, which SQL uses for column '
                f"names. Use single quotes for text: '{value}'."
            )
        previous = token
    check_and_or(0)
    return warnings


# --- hints for errors ----------------------------------------------------------


def _has_top_level_from(tokens: List[Token]) -> bool:
    return any(
        token.kind == "word" and token.upper == "FROM" and token.depth == 0
        for token in tokens
    )


def _unknown_words(tokens: List[Token], columns: Sequence[str]) -> List[str]:
    """Words that aren't keywords, functions or columns, and aren't aliases."""
    known = {column.casefold() for column in columns} | {TABLE_NAME}
    unknown = []
    previous = None
    for token in tokens:
        if (
            token.kind == "word"
            and token.upper not in KEYWORDS
            and token.upper not in FUNCTIONS
            and token.text.casefold() not in known
            and not (previous is not None and previous.upper == "AS")
        ):
            unknown.append(token.text)
        previous = token
    return unknown


def explain_error(
    message: str,
    query: str,
    columns: Sequence[str],
    alias: Optional[str] = None,
) -> List[str]:
    """Return hints on how to fix a query that SQLite rejected."""
    tokens = tokenize(query)
    hints: List[str] = []
    tables = f"{TABLE_NAME}" + (f" (or {alias})" if alias else "")

    def add(hint: str) -> None:
        if hint not in hints:
            hints.append(hint)

    def did_you_mean(word: str) -> bool:
        """Suggest a keyword, function or column close to `word`."""
        if word.upper() in KEYWORDS or word.upper() in FUNCTIONS:
            return False
        if word.casefold() in {column.casefold() for column in columns}:
            return False  # already a column name
        column_matches = _close_matches(word, columns)
        if column_matches:
            add(f"Did you mean {column_reference(column_matches[0])}?")
            return True
        keyword_matches = _close_matches(word, sorted(KEYWORDS | FUNCTIONS), 0.75)
        if keyword_matches:
            add(f"Did you mean {keyword_matches[0]} instead of {word}?")
            return True
        return False

    def symbol_columns(word: str) -> List[str]:
        """Columns with spaces or symbols that start or contain `word`."""
        key = word.casefold()
        return [
            column
            for column in columns
            if column_reference(column) != column
            and key in re.split(r"[^\w]+", column.casefold())
        ]

    if "&&" in (token.text for token in tokens):
        add("Use AND instead of && to combine conditions.")

    no_column = re.match(r"no such column: (.+)", message)
    no_function = re.match(r"no such function: (.+)", message)
    near = re.match(r'near "(.*)": syntax error', message, re.DOTALL)

    if no_column:
        name = no_column.group(1).split(".")[-1]
        if not _has_top_level_from(tokens):
            add(f"Add FROM {TABLE_NAME}, e.g. SELECT {name} FROM {TABLE_NAME} ...")
        for column in symbol_columns(name):
            add(
                "Put column names with spaces or symbols in square brackets, "
                f"e.g. {column_reference(column)}"
            )
            break
        else:
            is_column = name.casefold() in {column.casefold() for column in columns}
            if not is_column and not did_you_mean(name):
                add(
                    f"If {name} is a value rather than a column, put it in "
                    f"single quotes: '{name}'"
                )

    elif no_function:
        name = no_function.group(1)
        for column in symbol_columns(name):
            add(
                "Put column names with spaces or symbols in square brackets, "
                f"e.g. {column_reference(column)}"
            )
            break
        else:
            matches = _close_matches(name, sorted(FUNCTIONS), 0.6)
            if matches:
                add(f"Did you mean {matches[0]}()?")

    elif message.startswith("no such table"):
        add(f"The table is called {tables}.")

    elif message.startswith("unrecognized token"):
        if re.search(r"""["'`\[]""", message):
            add(
                "A quote or bracket isn't closed. Text values go in single "
                "quotes, e.g. 'BAL'."
            )

    elif message.startswith("misuse of aggregate"):
        add(
            "Functions like COUNT() and AVG() can't be used in WHERE. Use "
            "GROUP BY with HAVING instead, e.g. "
            "SELECT Team, COUNT(*) FROM data GROUP BY Team HAVING COUNT(*) > 30"
        )

    elif message == "incomplete input":
        add("The query is incomplete. Check the end of the query.")

    elif near:
        word = near.group(1)
        if word.upper() in KEYWORDS and word.casefold() in {
            column.casefold() for column in columns
        }:
            add(
                f"{word} is an SQL keyword. Put the column name in square "
                f"brackets: [{word}]"
            )
        # Misspelt keywords are often not where SQLite notices the problem
        # (e.g. in "WHER Age > 30", SQLite complains about "Age")
        for unknown in [word, *_unknown_words(tokens, columns)]:
            if unknown.strip() and did_you_mean(unknown):
                break
        if not _has_top_level_from(tokens) and tokens and tokens[0].upper == "SELECT":
            add(f"Did you forget FROM {TABLE_NAME}?")

    return hints
