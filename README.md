# Rich-CLI

Rich-CLI is a command line toolbox for fancy output in the terminal, built with [Rich](https://github.com/Textualize/rich).

Use the `rich` command to highlight a variety of file types in the terminal, with specialized rendering for Markdown and JSON files. Additionally you can markup and format text from the command line.

![splash image](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/rich-cli-splash.jpg)

## What's new in this version

This version of Rich-CLI adds three ways to show **only the part of a file you need**:

| Feature | Option | Works with | Example |
| --- | --- | --- | --- |
| **Line selector** | `--lines` | CSV, text, code, Markdown, RST | `rich data.csv --lines 50:70` |
| **Section selector** | `--section` | text, code, Markdown, RST | `rich notes.txt --section "Instructions"` |
| **SQL queries** | `--sql` | CSV, TSV | `rich data.csv --sql "SELECT Name FROM data WHERE Age > 30"` |
| **Header override** | `--header` / `--no-header` | CSV, TSV | `rich airtravel.csv --header` |

It also upgrades to **Rich 15** and **Textual 8**, so Markdown tables now display properly in the terminal, and the pager has been rebuilt (see [Pager](#pager)).

Each feature is explained below, with examples you can copy and paste from the root of this repository (they use the sample files in [`test_data/`](test_data)). See the [CHANGELOG](CHANGELOG.md) for the full list of changes.

> **Tip:** you can read any part of this README in the terminal with the new section selector, e.g. `rich README.md --section "SQL cheat sheet"`.

## Contents

- [Quick start](#quick-start)
- [Installation](#installation)
  - [Installing from this repository (for the team)](#installing-from-this-repository-for-the-team)
- [Rich command](#rich-command)
- [Syntax highlighting](#syntax-highlighting) · [Markdown](#markdown) · [reStructuredText](#restructuredtext) · [Jupyter notebook](#jupyter-notebook) · [JSON](#json) · [CSV](#csv) · [Rules](#rules) · [Inspect](#inspect)
- **New:** [Selecting lines and rows (`--lines`)](#selecting-lines-and-rows---lines)
- **New:** [Selecting sections of a document (`--section`)](#selecting-sections-of-a-document---section)
- **New:** [Querying CSV files with SQL (`--sql`)](#querying-csv-files-with-sql---sql)
- [Which options work together](#which-options-work-together)
- [Pager](#pager) · [Network](#network) · [Exporting](#exporting) · [Rich Printing](#rich-printing) · [Reading from Stdin](#reading-from-stdin) · [General Options](#general-options)
- [Options reference](#options-reference)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## Quick start

From the project folder (the one with `pyproject.toml`), install this version and try the new features on the sample files:

```
python -m pip install -e .
rich test_data/mlb_players.csv --lines 50:70
rich test_data/sections.txt --section "Instructions"
rich test_data/mlb_players.csv --sql "SELECT Name, Team, Age FROM data WHERE Age > 40 ORDER BY Age DESC"
rich test_data/airtravel.csv --header
```

Run `rich --help` to see every option, or see the [Options reference](#options-reference).

## Installation

There are a few options for installing Rich-CLI.

> **Note:** `pipx`, Homebrew, `pip install rich-cli` and `conda` install the **official release** of Rich-CLI, which doesn't include the new features in this version (`--lines`, `--section`, `--sql`, `--header`). To use this version, see [Installing from this repository](#installing-from-this-repository-for-the-team).

### Windows / Linux

You can install Rich-CLI with [pipx](https://pypa.github.io/pipx/).

```
pipx install rich-cli
```

### MacOS

You can install Rich-CLI with [Homebrew](https://brew.sh/).

```
brew install rich
```

### Universal

Rich-CLI may be installed as a Python package, either using `pip`:

```
python -m pip install rich-cli
```

Or using `conda` or `mamba`:

```
mamba install -c conda-forge rich-cli
```

### Installing from this repository (for the team)

To use the version in this repository (including the new features), install it in _editable_ mode from the folder that contains `pyproject.toml`. Editable mode means the `rich` command runs the code in this folder, so your changes take effect without reinstalling.

```
python -m pip install -e .
```

On Windows, run this in PowerShell from the project folder. Python 3.9 or newer is required. Check it worked with:

```
rich --help
rich test_data/mlb_players.csv --lines 1:5
```

If you move the project to another folder (or unzip a fresh copy), run `python -m pip install -e .` again from the new folder. Also run it again after pulling changes to `pyproject.toml` (for example, the upgrade to Rich 15 and Textual 8), so the new dependencies are installed. See [Troubleshooting](#troubleshooting) if the `rich` command doesn't work.

## Rich command

Once installed you should have the `rich` command in your path. Run the following to see usage / help:

```
rich --help
```

## Syntax highlighting

To syntax highlight a file enter `rich` followed by a path. Many file formats are supported.

```
rich loop.py
```

![syntax1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/syntax1.png)

Add the `--line-numbers` or `-n` switch to enable line numbers. Add `--guides` or `-g` to enable indentation guides.

```
rich loop.py -n -g
```

![syntax2](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/syntax2.png)

You can specify a [theme](https://pygments.org/styles/) with `--theme`.

```
rich loop.py --theme dracula
```

You can set the default theme via the `RICH_THEME` environment variable. So the following is equivalent to the above command:

```
RICH_THEME=dracula rich loop.py
```

In PowerShell, set the variable first:

```
$env:RICH_THEME = "dracula"
rich loop.py
```

![syntax3](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/syntax3.png)

By default, `rich` will wrap lines if they don't fit within the available width. You can disable this behavior with `--no-wrap`.

`Rich` will try to deduce the format of the file from its name. If you want to override the auto-detected _lexer_ you can explicitly set it with the `--lexer` or `-x` switch.

## Markdown

You can request markdown rendering by adding the `--markdown` switch or `-m`. If the file ends with `.md` markdown will be auto-detected.

```
rich README.md
```

![markdown1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/markdown1.png)

If your terminal supports hyperlinks, you can add `--hyperlinks` or `-y` which will output hyperlinks rather than full URLs.

```
rich README.md --hyperlinks
```

## reStructuredText

You can request reStructuredText rendering by adding the `--rst` switch. If the file ends with `.rst` reStructuredText will be auto-detected.

```
rich test_data/test.rst
```

## Jupyter notebook

You can request Jupyter notebook rendering by adding the `--ipynb` switch. If the file ends with `.ipynb` Jupyter notebook will be auto-detected.

```
rich test_data/notebook.ipynb
```

All options that apply to syntax highlighting can be applied to code cells, and all options that apply to Markdown can be
applied to Markdown cells.

## JSON

You can request JSON pretty formatting and highlighting with the `--json` or `-J` switches. If the file ends with `.json` then JSON will be auto-detected.

```
rich cats.json
```

![json1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/json1.png)

## CSV

Rich can display the contents of a CSV (or TSV) as a table. If the file ends with `.csv` or `.tsv` then CSV will be auto-detected.

```
rich test_data/deniro.csv
```

![csv1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/csv1.png)

Large files can be trimmed with `--head` and `--tail`:

```
rich test_data/mlb_players.csv --head 10
rich test_data/mlb_players.csv --tail 10
```

To pick out specific rows use [`--lines`](#selecting-lines-and-rows---lines), and to filter, sort or pick columns use [`--sql`](#querying-csv-files-with-sql---sql).

### Header row

Rich guesses whether the first row of a CSV file is a header (column names) or data. The guess is sometimes wrong. For example, [`test_data/airtravel.csv`](test_data/airtravel.csv) starts with `Month, 1958, 1959, 1960`, which looks like data because of the years. Use `--header` or `--no-header` to tell Rich:

```
rich test_data/airtravel.csv --header
rich test_data/mlb_players.csv --no-header --head 3
```

| Option | The first row is... |
| --- | --- |
| _(neither)_ | guessed |
| `--header` | the column names |
| `--no-header` | data. Columns are unnamed (in `--sql` they're called `column1`, `column2`, ...) |

This also affects `--head`, `--tail` and `--lines`, which count rows after the header, and the column names you can use in `--sql`.

## Rules

You can render a horizontal rule with `--rule` or `-u`. Specify a rule style with `--rule-style`. Set the character(s) to render the line with `--rule-char`.

```
rich "Hello [b]World[/b]!" --rule
rich "Hello [b]World[/b]!" --rule --rule-style "red"
rich "Hello [b]World[/b]!" --rule --rule-style "red" --rule-char "="
```

![syntax1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/rules1.png)

## Inspect

Add `--inspect` to show information about a Python object: its type, documentation and methods. The argument is evaluated as a Python expression.

```
rich "[1, 2, 3]" --inspect
rich "{'a': 1}" --inspect
```

> **Warning:** because the argument is run as Python code, only use `--inspect` with expressions you trust.

## Selecting lines and rows (`--lines`)

Use `--lines` to show only some of the lines of a file, or some of the rows of a CSV file.

```
rich test_data/mlb_players.csv --lines 50:70
rich test_data/sections.txt --lines 12:18 -n
```

`--line` works too, as another name for `--lines`.

### How to write a selection

| You write | You get |
| --- | --- |
| `50:70` | lines 50 to 70 (both included) |
| `50-70` | the same as `50:70` |
| `50:` | line 50 to the end |
| `:20` | the first 20 lines |
| `7` | just line 7 |
| `1:5,50:70,100:` | several sections at once, separated by commas |

Line numbers start at 1. You can also repeat the option instead of using commas:

```
rich test_data/mlb_players.csv --lines 1:5 --lines 50:70 --lines 100
```

> **PowerShell:** put comma-separated sections in quotes, e.g. `--lines "1:5,50:70"`. Without quotes, PowerShell treats the comma as a list separator. Repeating `--lines` also works.

### How lines are counted

- **CSV files:** `--lines` counts **rows after the header**, so `--lines 1:5` shows the first five data rows. The header is always shown.
- **Text and code files:** `--lines` counts the lines of the file. Add `-n` to show the original line numbers.
- **Markdown and reStructuredText:** the selected lines are rendered (formatted), e.g. `rich README.md --lines 1:20`.

### Multiple sections

When you select several sections:

- They are shown in the order they appear in the file, whatever order you write them in.
- Overlapping sections are merged, so no line is shown twice.
- In CSV tables, a divider line marks each place where rows were skipped. In text files, a blank line separates sections. Use `-n` to see the gaps in the line numbers.

```
rich test_data/mlb_players.csv --lines "2:3,50:51,1034"
```

```
┃ Name            ┃ Team ┃ Position       ┃ ...
┡━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━╇ ...
│ Paul Bako       │ BAL  │ Catcher        │ ...
│ Ramon Hernandez │ BAL  │ Catcher        │ ...
├─────────────────┼──────┼────────────────┼ ...   <- rows skipped here
│ Darin Erstad    │ CWS  │ Outfielder     │ ...
│ Rob Mackowiak   │ CWS  │ Outfielder     │ ...
├─────────────────┼──────┼────────────────┼ ...   <- rows skipped here
│ Josh Kinney     │ STL  │ Relief Pitcher │ ...
```

### Edge cases

| Situation | What happens |
| --- | --- |
| Backwards range, e.g. `--lines 70:50` | Treated as `50:70`, with a warning |
| Range past the end of the file, e.g. `--lines 5000:6000` | Skipped, with a warning saying how many lines (or rows) there are |
| `0` or a negative number, e.g. `--lines -5:` | Error. Line numbers start at 1. Use `--tail 5` for the last lines |
| Missing value, e.g. `--lines -n` | Error: `did you forget the value?` |
| Stray comma, e.g. `--lines "1:5,"` | Error: `empty section` |
| Used with `--head`, `--tail` or `--section` | Error: these can't be combined |
| Used with JSON or a notebook | Error. Add `--syntax` to select lines of the raw file instead |
| Used with `--sql` | Selects rows from the **query results** (see [SQL](#querying-csv-files-with-sql---sql)) |

## Selecting sections of a document (`--section`)

Use `--section` to show only the part of a document under a heading.

```
rich test_data/sections.txt --section "Instructions"
rich README.md --section "Pager"
```

Repeat the option to show several sections. They appear in the order they're in the file:

```
rich test_data/sections.txt --section "Overview" --section "Troubleshooting"
```

### What counts as a section

A section starts at a heading and continues until the next heading of the **same or a higher level**. Sub-sections are included. Two styles of heading are recognised:

```
## Instructions              <- Markdown heading (level = number of #)

Instructions                 <- Underlined heading, as in reStructuredText
============                    and Markdown (levels go by the order the
                                underline styles first appear in the file)
```

For example, in [`test_data/sections.txt`](test_data/sections.txt):

```
Project Setup Guide          <- level 1
===================
Overview                     <- level 2
--------
Instructions                 <- level 2   --section "Instructions" shows from here...
------------
Windows notes                <- level 3   (a sub-section, so it's included)
~~~~~~~~~~~~~
Troubleshooting              <- level 2   ...up to here
---------------
```

Good to know:

- `#` lines inside fenced code blocks (```` ``` ````) are not treated as headings.
- If a title appears more than once, every matching section is shown.
- With text and code files, add `-n` to show the original line numbers. Markdown and RST sections are rendered (formatted).

### How titles are matched

Titles are matched leniently. All of these find a heading called `Instructions`:

| You type | Why it matches |
| --- | --- |
| `instructions`, `INSTRUCTIONS` | Case is ignored |
| `"Instructions"`, `“Instructions”` | Surrounding quotes (including curly "smart" quotes) are ignored |
| `## Instructions` | Leading `#` marks are ignored |
| `Instructions:` | A trailing colon or full stop is ignored |
| `Instructions` for `**Instructions**` or `[Instructions](#link)` | Markdown formatting and links in headings are ignored |

If nothing matches exactly, numbering and emoji at the **start** of a heading are ignored as well, so `--section "Getting Started"` finds `1. Getting Started`, `Step 1: Getting Started` or `🚀 Getting Started`. An exact match always wins: if a file has both `Setup` and `1. Setup`, `--section Setup` shows only `Setup`.

### When a section isn't found

Rich suggests similar titles and lists all the sections in the file:

```
rich test_data/sections.txt --section "Instruction"
```

```
section not found: 'Instruction'
Did you mean: Instructions

Available sections:
  Project Setup Guide
    Overview
    Instructions
      Windows notes
    Troubleshooting
```

A near-miss is only suggested, never shown automatically, so you always get exactly the section you asked for.

### Edge cases

| Situation | What happens |
| --- | --- |
| Section doesn't exist | Error with "Did you mean" suggestions and the list of sections |
| File has no headings | Error explaining which heading styles are supported |
| Empty title, e.g. `--section ""` | Error: `the section title is empty` |
| Missing title, e.g. `--section -n` | Error: `did you forget the title?` |
| Used with a CSV file | Error suggesting `--lines` or `--sql` instead (CSV files have no headings) |
| Used with JSON or a notebook | Error (these files have no headings) |
| Used with `--head`, `--tail` or `--lines` | Error: these can't be combined |

## Querying CSV files with SQL (`--sql`)

Use `--sql` to select columns, filter, sort, group and limit the rows of a CSV (or TSV) file with an SQL query. The data is in a table called **`data`**.

```
rich test_data/mlb_players.csv --sql "SELECT Name, Team, Age FROM data WHERE Age > 40 ORDER BY Age DESC"
```

```
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━┓
┃ Name              ┃ Team ┃   Age ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━┩
│ Julio Franco      │ NYM  │ 48.52 │
│ Jamie Moyer       │ PHI  │ 44.28 │
│ Randy Johnson     │ ARZ  │ 43.47 │
│ ...               │      │       │
```

Queries use [SQLite's SQL](https://www.sqlite.org/lang_select.html) and run on an in-memory copy of the data. Your CSV file is never changed.

### SQL cheat sheet

| To... | Write |
| --- | --- |
| Show some columns | `SELECT Name, Team FROM data` |
| Show all columns | `SELECT * FROM data` |
| Filter rows | `SELECT * FROM data WHERE Team = 'BAL'` |
| Filter on numbers | `SELECT * FROM data WHERE Age >= 30 AND Age < 35` |
| Filter on a range | `SELECT * FROM data WHERE Age BETWEEN 30 AND 35` |
| Match one of several values | `SELECT * FROM data WHERE Team IN ('BAL', 'NYM')` |
| Search text | `SELECT * FROM data WHERE Name LIKE 'jo%'` (`%` = anything, `_` = one character) |
| Exclude rows | `SELECT * FROM data WHERE NOT Team = 'BAL'` or `WHERE Team != 'BAL'` |
| Find empty values | `SELECT * FROM data WHERE Age IS NULL` |
| Sort | `SELECT * FROM data ORDER BY Age DESC` |
| Show the first N rows | `SELECT * FROM data LIMIT 10` |
| Skip rows | `SELECT * FROM data LIMIT 10 OFFSET 20` |
| Count rows | `SELECT COUNT(*) FROM data` |
| Group and summarise | `SELECT Team, COUNT(*) AS players, ROUND(AVG(Age), 1) AS avg_age FROM data GROUP BY Team` |
| Filter groups | `SELECT Team, COUNT(*) FROM data GROUP BY Team HAVING COUNT(*) > 35` |
| Unique values | `SELECT DISTINCT Team FROM data` |
| Rename a column | `SELECT Name AS player FROM data` |

More examples:

```
rich test_data/mlb_players.csv --sql "SELECT Team, COUNT(*) AS players, ROUND(AVG(Age), 1) AS avg_age FROM mlb_players GROUP BY Team ORDER BY players DESC LIMIT 5"
rich test_data/deniro.csv --sql "SELECT Title, Score FROM data WHERE Title LIKE '%taxi%'"
rich test_data/deniro.csv --sql "SELECT Year, Title FROM data WHERE Score >= 90 ORDER BY Year"
```

### Table and column names

- The table is called `data`. You can also use the file name: `mlb_players.csv` can be queried as `mlb_players`. Any `-` or spaces in the file name become `_`.
- Column names come from the CSV header. Put names containing spaces or symbols in **square brackets**: `SELECT [Height(inches)] FROM data`. Do the same for names that are SQL keywords, such as `[Order]` or `[Group]`.
- If the header has duplicate names, later ones get a suffix: `Name`, `Name_2`.
- If a file has no header, the columns are called `column1`, `column2`, and so on. If Rich didn't detect a header that is there, add `--header` (see [Header row](#header-row)).

### Upper and lower case

- **Text values ignore case**, including accented letters. `Team = 'bal'` matches `BAL`, and `Name = 'josé'` matches `JOSÉ`. This applies to `=`, `!=`, `IN`, `LIKE`, `ORDER BY`, `GROUP BY` and `DISTINCT`.
- **Keywords, column names and the table name** can be written in any case: `select name from DATA` works.
- **To match exact case**, add `COLLATE BINARY` or use `GLOB`:

```
rich test_data/mlb_players.csv --sql "SELECT Name FROM data WHERE Team = 'BAL' COLLATE BINARY"
rich test_data/mlb_players.csv --sql "SELECT Name FROM data WHERE Name GLOB 'Jo*'"
```

Accents are not ignored: `jose` and `josé` are different.

### Combining conditions: AND, OR, NOT

Use `AND`, `OR` and `NOT` (in any case). **`AND` is applied before `OR`**, so use parentheses to group conditions:

```
rich test_data/mlb_players.csv --sql "SELECT Name, Team, Age FROM data WHERE (Team = 'NYM' OR Team = 'PHI') AND Age > 40"
```

| You write | SQL reads it as |
| --- | --- |
| `Team = 'NYM' OR Team = 'PHI' AND Age > 40` | `Team = 'NYM' OR (Team = 'PHI' AND Age > 40)`: **every** NYM player, plus PHI players over 40 |
| `(Team = 'NYM' OR Team = 'PHI') AND Age > 40` | NYM or PHI players who are over 40 |

Rich warns you if you mix `AND` and `OR` without parentheses. Don't use `&&` or `||`:

- `&&` is not valid SQL. Rich tells you to use `AND`.
- `||` **joins text together** in SQL (`Name || ' (' || Team || ')'`), it does not mean "or". If you use it in a `WHERE` clause, Rich warns you to use `OR`.

### Text, numbers and empty values

- **Text values go in single quotes**: `Team = 'BAL'`. Double quotes are for column names, and Rich warns if you put text in them.
- **Numbers:** columns where every value is a number are treated as numbers, so `Age > 30` compares numerically, not alphabetically.
- **Leading zeros:** values such as zip codes (`02134`) or IDs (`007`) are kept as text, so the leading zero isn't lost.
- **Empty values** are `NULL`. Find them with `IS NULL`. They are skipped by `COUNT(column)`, `AVG` and `SUM`.
- **Placeholders** `N/A`, `NA`, `null`, `none`, `nan` and `-` count as empty in columns that otherwise contain numbers, so they don't stop the column being numeric. They appear blank in the results.

### Combining with other options

`--head`, `--tail` and `--lines` apply to the **results** of the query:

```
rich test_data/mlb_players.csv --sql "SELECT Name, Age FROM data WHERE Team = 'BAL' ORDER BY Age" --head 3
rich test_data/mlb_players.csv --sql "SELECT Name, Age FROM data WHERE Team = 'BAL' ORDER BY Age" --lines "1:2,10"
```

General options such as `--title`, `--caption`, `--panel`, `--width` and `--export-html` work as usual.

### When a query goes wrong

If SQLite rejects a query, Rich shows the error, a hint on how to fix it, and the table's column names:

```
rich test_data/mlb_players.csv --sql "SELECT Name FROM data WHER Age > 40"
```

```
SQL error: near "Age": syntax error
Hint: Did you mean WHERE instead of WHER?

Table: data (or mlb_players)
Columns: Name, Team, Position, [Height(inches)], [Weight(lbs)], Age
```

| Mistake | Hint |
| --- | --- |
| Misspelled keyword: `SELEC`, `WHER`, `ORDR BY` | `Did you mean WHERE instead of WHER?` |
| Misspelled column: `SELECT Nmae` | `Did you mean Name?` |
| Missing table: `SELECT Name WHERE Age > 40` | `Add FROM data` |
| Text without quotes: `Team = BAL` | `put it in single quotes: 'BAL'` |
| Unclosed quote: `Team = 'BAL` | `A quote or bracket isn't closed` |
| `&&` instead of `AND` | `Use AND instead of &&` |
| Column with symbols: `SELECT Height(inches)` | `Put column names ... in square brackets, e.g. [Height(inches)]` |
| Keyword as a column: `SELECT Order` | `Put the column name in square brackets: [Order]` |
| Misspelled function: `COUNTT(*)` | `Did you mean COUNT()?` |
| `COUNT()` in `WHERE` | Use `GROUP BY ... HAVING` instead |
| Wrong table: `FROM players` | `The table is called data (or mlb_players)` |
| Query cut short: `... WHERE` | `The query is incomplete` |

Rich also shows a **warning** (and still runs the query) when a query probably doesn't do what you meant:

- `||` used as "or"
- `AND` and `OR` mixed without parentheses
- text in double quotes, e.g. `Team = "BAL"`
- the query returned no rows

### Safety

Only `SELECT` queries are allowed (including `WITH ... SELECT`). Statements that change data or touch files, such as `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ATTACH` and `PRAGMA`, are blocked, as is running more than one statement at once.

### Writing queries in PowerShell

- Put the whole query in **double quotes** and text values in **single quotes**: `--sql "SELECT * FROM data WHERE Team = 'BAL'"`.
- Use **square brackets** for column names with symbols rather than double quotes. Some versions of PowerShell drop double quotes inside an argument.

### Limitations

- CSV header detection is a guess and is sometimes wrong. For example, [`test_data/airtravel.csv`](test_data/airtravel.csv) has a header of years (`Month, 1958, 1959, 1960`), which is read as data, so its columns are `column1` to `column4`. Add `--header` to fix this: `rich test_data/airtravel.csv --header --sql "SELECT Month, [1960] FROM data"`. Without `--header`, if a query uses a name from the first row (e.g. `SELECT Month ...`), Rich uses the first row as the header and shows a warning. With `--no-header` it never does.
- Large files are loaded into memory. A 200,000-row file takes a few seconds.

## Which options work together

| | Text / code | Markdown / RST | CSV / TSV | JSON | Notebook |
| --- | :---: | :---: | :---: | :---: | :---: |
| `--lines` | ✅ | ✅ | ✅ rows | ❌ (use `--syntax`) | ❌ (use `--syntax`) |
| `--section` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `--sql` | ❌ | ❌ | ✅ | ❌ | ❌ |
| `--header` / `--no-header` | ❌ | ❌ | ✅ | ❌ | ❌ |

- Use only one of `--lines`, `--section`, `--head` or `--tail` at a time. Combining them is an error.
- With `--sql`, you can add one of `--lines`, `--head` or `--tail` to pick rows from the query results.
- All of them work with the general options (`--panel`, `--title`, `--width`, `--export-html`, ...), and with `-n` for line numbers on text and code files.
- They work with input from stdin (`-`). Add `--csv` or `--markdown` so Rich knows the format, e.g. `cat data.csv | rich - --csv --lines 1:10`.

## Pager

Add `--pager` to display the content with a built in pager application.

Scroll the pager with cursor keys, page up/down, home, end. Alternatively use the scrollbar which will be visible to the right of the terminal. Or use the vi navigation (j, k, ctrl-d, ctrl-u).

| Key | Action |
| --- | --- |
| `↑` `↓` / `k` `j` | Scroll up / down a line |
| `Page Up` `Page Down` / `space` | Scroll a page |
| `ctrl+u` `ctrl+d` | Scroll half a page up / down |
| `Home` `End` | Jump to the start / end |
| `q` | Quit |

```
rich src/rich_cli/__main__.py -n -g --theme monokai --pager
```

![pager](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/pager1.png)

## Network

The `rich` command can read files from the internet if you give it a URL starting with `http://` or `https://`.

```
rich https://raw.githubusercontent.com/Textualize/rich-cli/main/README.md --markdown
```

![network](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/network1.png)

## Exporting

In addition to rendering to the console, `rich` can write an HTML file. This works with any command. Add `--export-html` or `-o` followed by the output path.

```
rich README.md -o readme.html
```

After running this command you should find a "readme.html" in your current working directory.

To write an SVG image instead (useful for documentation and slides), use `--export-svg`:

```
rich README.md --export-svg readme.svg
```

The output is still shown in the terminal as well.

## Rich Printing

If you add the `--print` or `-p` option then Rich will treat the first argument as [console markup](https://rich.readthedocs.io/en/latest/markup.html) which allows you to insert styles with a markup similar in design to bbcode.

```
rich "Hello, [bold magenta]World[/]!" --print
```

![printing1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/printing1.png)

### Emoji

Add `--emoji` or `-j` to replace emoji codes with emoji.

```
rich "I :heart: Rich" --print --emoji
```

### Soft wrapping

Rich will word wrap your text by default by inserting newlines where appropriate. If you don't want this behavior you can enable _soft_ wrapping with `--soft`.

## Reading from Stdin

Where `rich` accepts a path, you can enter `-` which reads the content from stdin. You may want this if you are piping output from another process.

Note that when rich isn't writing directly to the terminal it will disable ansi color codes, so you may want to add `--force-terminal` to tell `rich` you want to keep ansi codes in the output.

```
cat README.md | rich - --markdown --force-terminal
```

In PowerShell, use `Get-Content` instead of `cat`:

```
Get-Content README.md | rich - --markdown --force-terminal
```

## General Options

There are a number of additional switches you may add to modify the content rendered to the terminal. These options are universal and apply to all of the above features.

### Style

You can set a style to apply to the output with `--style` or `-s`. The styles are specified with [this syntax](https://rich.readthedocs.io/en/latest/style.html).

```
rich "Hello, [b]World[/b]!" --print --style "on blue"
```

![style1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/style1.png)

### Alignment

You can align output to the left, center, or right with the `--left`, `--center`, or `--right` options, or their single letter counterparts: `-l`, `-c`, or `-r`.

```
rich "Hello [b]World[/b]!" --print --center
```

![alignment1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/alignment1.png)

### Width

You can set the width of the output with `--width` or `-w` and the desired width. Note that the default behavior is to wrap text.

```
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -w 40
```

`--width` sets an exact width. To set a maximum instead, use `--max-width` or `-W`: the output is never wider than the given size, but may be narrower on a small terminal.

```
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -W 40
```

![width](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/width1.png)

### Text Justify

You can set how `rich` will justify text with `--text-left`, `--text-right`, `--text-center`, and `--text-full`; or the single letter equivalents: `-L`, `-R`, `-C`, and `-F`.

The difference between `--left` and `--text-left` may not be obvious unless you specify the width of the output. The `--left`, `--center`, and `--right` options will center the block of text within the terminal dimensions. Whereas, the `--text-left`, `--text-center`, and `--text-right` options define how text is rendered _within_ that block.

In the following examples, we specify a width of 40 (`-w 40`) which is center aligned with the `-c` switch. Note how the `-R`, `-C` and `-F` apply the text justification within the 40 character block:

```
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -w 40 -c -L
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -w 40 -c -R
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -w 40 -c -C
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -w 40 -c -F
```

### Padding

You can apply _padding_ around the output with `--padding` or `-d`.

```
rich "Hello [b]World[/b]!" -p -c --padding 3 --style "on blue"
```

![padding1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/padding1.png)

### Panel

You can draw a _panel_ around content with `--panel` or `-a`, which takes one of a number of [styles](https://rich.readthedocs.io/en/latest/appendix/box.html).

```
rich "Hello, [b]World[/b]!" -p -a heavy
```

Set the panel's border style with `--panel-style` or `-S`, add a title and caption with `--title` and `--caption`, and make the panel fill the width of the terminal with `--expand` or `-e`:

```
rich "Hello, [b]World[/b]!" -p -a rounded -S red --title Greeting --caption "rich-cli" -e
```

`--title` and `--caption` also set the title and caption of the table when displaying a CSV file.

![panel1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/panel1.png)

## Options reference

Every option of the `rich` command. Run `rich --help` for the same list in the terminal.

**What to display.** Rich picks the format from the file extension. Use these to choose it yourself:

| Option | Description |
| --- | --- |
| `--syntax` | Syntax highlighting (the default for files Rich doesn't otherwise recognise) |
| `-m`, `--markdown` | Markdown (`.md`) |
| `--rst` | reStructuredText (`.rst`) |
| `-J`, `--json` | JSON (`.json`) |
| `--csv` | CSV or TSV as a table (`.csv`, `.tsv`) |
| `--ipynb` | Jupyter notebook (`.ipynb`) |
| `-p`, `--print` | Print the argument as [console markup](https://rich.readthedocs.io/en/latest/markup.html) |
| `-u`, `--rule` | Draw a horizontal rule, with the argument as its title |
| `--inspect` | Inspect a Python object (the argument is evaluated as Python) |

**Showing part of a file:**

| Option | Description |
| --- | --- |
| `-h`, `--head LINES` | Show the first LINES lines (or CSV rows). Note that `-h` is `--head`, not help. Use `--help` for help |
| `-t`, `--tail LINES` | Show the last LINES lines (or CSV rows) |
| `--lines`, `--line SECTIONS` | Show the given lines, e.g. `50:70` or `"1:5,50:70"` (see [`--lines`](#selecting-lines-and-rows---lines)) |
| `--section TITLE` | Show the section under a heading (see [`--section`](#selecting-sections-of-a-document---section)) |

**CSV files:**

| Option | Description |
| --- | --- |
| `--sql QUERY` | Query the data with SQL (see [`--sql`](#querying-csv-files-with-sql---sql)) |
| `--header` / `--no-header` | The first row is the header / is data (see [Header row](#header-row)) |

**Code and Markdown:**

| Option | Description |
| --- | --- |
| `-n`, `--line-numbers` | Show line numbers |
| `-g`, `--guides` | Show indentation guides |
| `--theme THEME` | [Syntax theme](https://pygments.org/styles/), e.g. `dracula`. Can also be set with the `RICH_THEME` environment variable |
| `-x`, `--lexer LEXER` | Choose the [syntax highlighting lexer](https://pygments.org/docs/lexers/), e.g. `python` |
| `--no-wrap` | Don't wrap long lines |
| `-y`, `--hyperlinks` | Show Markdown links as clickable hyperlinks (if your terminal supports them) |

**Text** (with `--print` and `--rule`):

| Option | Description |
| --- | --- |
| `-j`, `--emoji` | Replace emoji codes such as `:heart:` with emoji |
| `--soft` | Soft wrapping: don't insert line breaks |
| `-L`, `--text-left` / `-R`, `--text-right` / `-C`, `--text-center` / `-F`, `--text-full` | Justify text within its block |
| `--rule-style STYLE` | Style of the rule, e.g. `red` |
| `--rule-char CHARACTER` | Character(s) to draw the rule with |

**Layout and style:**

| Option | Description |
| --- | --- |
| `-l`, `--left` / `-c`, `--center` / `-r`, `--right` | Align the output in the terminal |
| `-w`, `--width SIZE` | Set the width of the output |
| `-W`, `--max-width SIZE` | Set the maximum width of the output |
| `-s`, `--style STYLE` | [Style](https://rich.readthedocs.io/en/latest/style.html) to apply, e.g. `"bold on blue"` |
| `-d`, `--padding TOP,RIGHT,BOTTOM,LEFT` | Padding around the output: 1, 2 or 4 numbers, e.g. `2,4` |
| `-a`, `--panel BOX` | Draw a panel around the output: `none`, `ascii`, `ascii2`, `square`, `rounded`, `heavy` or `double` |
| `-S`, `--panel-style STYLE` | Style of the panel border |
| `-e`, `--expand` | Make the panel fill the width |
| `--title TEXT` | Title of the panel, or of the table for CSV files |
| `--caption TEXT` | Caption of the panel, or of the table for CSV files |

**Output:**

| Option | Description |
| --- | --- |
| `--pager` | Show the output in an interactive pager (see [Pager](#pager)) |
| `-o`, `--export-html PATH` | Also save the output as HTML |
| `--export-svg PATH` | Also save the output as an SVG image |
| `--force-terminal` | Keep colours and styles when the output isn't a terminal, e.g. when piping |
| `-v`, `--version` | Show the version |
| `--help` | Show help |

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'rich_cli'` when running `rich` | The installed `rich` command points at a folder that moved or no longer exists. From the project folder run `python -m pip uninstall -y rich-cli`, then `python -m pip install -e .` |
| `ERROR: To modify pip, please run ...` on Windows | Upgrade pip through Python: `python -m pip install --upgrade pip` |
| `rich` runs an old version without the new options | Check which `rich` is first on your PATH (`where.exe rich` on Windows, `which rich` elsewhere), or run `python -m rich_cli ...` instead |
| `rich --version` shows an old version number | The version is read from the installed package. Reinstall after pulling changes: `python -m pip install -e .` |
| `no such option: --group` when installing | Your pip is too old. Run `python -m pip install --upgrade pip` first |
| `No such option` | Check the spelling, e.g. `--lines` and `--section`. Run `rich --help` for the list of options |
| `unable to read ...` / file not found | Paths are relative to the current folder. The sample files are in `test_data/`, e.g. `rich test_data/mlb_players.csv` |
| `--lines "1:5,50:70"` fails in PowerShell | Put the value in quotes, or repeat `--lines` for each section |
| SQL query fails in PowerShell but looks right | Use single quotes for text and square brackets for column names (see [Writing queries in PowerShell](#writing-queries-in-powershell)) |
| CSV header shown as a data row, or SQL columns are called `column1`, `column2`, ... | The header wasn't detected. Add `--header` (see [Header row](#header-row)) |
| `ModuleNotFoundError: No module named 'textual.widgets'` or other import errors after pulling changes | The dependencies changed. Reinstall: `python -m pip install -e . --group dev` |
| `section not found` | Check the suggestions and the list of sections in the message. Headings must be Markdown headings (`## Title`) or underlined titles |

## Development

### Setup

Install the project in editable mode together with the development tools (`pytest`, `black` and `mypy`, from the `dev` dependency group in `pyproject.toml`):

```
python -m pip install --upgrade pip
python -m pip install -e . --group dev
```

`--group` needs pip 25.1 or newer, hence the first command. If you can't upgrade pip, install the tools directly: `python -m pip install -e . "pytest>=8.3,<9" black==22.3.0 mypy==0.942`.

If you use Poetry instead, run `poetry install --with dev`.

### Running the tests

```
python -m pytest
```

| Test file | Covers |
| --- | --- |
| `tests/test_csv_lines.py` | `--lines` on CSV and text files, including edge cases |
| `tests/test_sections.py` | `--section`: heading detection, title matching, errors |
| `tests/test_sql.py` | `--sql`: queries, case sensitivity, data types, warnings and hints, safety |
| `tests/test_csv_header.py` | `--header` / `--no-header`, including with `--lines` and `--sql` |
| `tests/test_pager.py` | The pager's keys, driven headlessly with Textual's test pilot |
| `tests/test_main.py` | Checks no two options use the same flag |
| `tests/test_readme.py` | Checks every option is in the [Options reference](#options-reference) |
| `tests/test_version.py` | `rich --version` matches `pyproject.toml` |

### Project layout

| File | What it does |
| --- | --- |
| `src/rich_cli/__main__.py` | The `rich` command: options, checks, and rendering for each file type. Contains the `--lines` parsing (`parse_line_ranges`, `select_line_blocks`) and CSV rendering (`render_csv`) |
| `src/rich_cli/sections.py` | `--section`: finds headings, works out where sections start and end, and matches titles |
| `src/rich_cli/sql.py` | `--sql`: loads CSV data into an in-memory SQLite database, works out column types, and runs read-only queries |
| `src/rich_cli/sql_help.py` | `--sql`: the hints for failed queries and warnings for likely mistakes |
| `src/rich_cli/pager.py` | `--pager`: the interactive pager, built with Textual |
| `src/rich_cli/markdown.py` | Customises how Markdown code blocks are displayed (syntax highlighted and indented) |
| `test_data/` | Sample files used in the examples and tests. `sections.txt` is a sample document for `--section` |

### Version number

The version is defined in **one place**: `version` in `pyproject.toml`. `rich --version` reads it from the installed package, so after changing it, reinstall with `python -m pip install -e .` (the tests check that the two match).

### Changing dependencies

After changing dependencies in `pyproject.toml`, regenerate the lock file with `poetry lock` and commit `poetry.lock` too. `pip` doesn't use the lock file, but Poetry refuses to install from an out-of-date one.

### Conventions

- Format code with `black` (version 22.3.0, as pinned in `pyproject.toml`): `black src tests`.
- Files use Windows (CRLF) line endings. Keep them that way so diffs only show real changes.
- Add tests for new behaviour and edge cases, and update this README and the [CHANGELOG](CHANGELOG.md). When you add an option, add it to the [Options reference](#options-reference) (a test checks this).
