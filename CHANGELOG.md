# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `--lines START:END` option to display a range of rows from a CSV file, e.g. `--lines 50:70`
- `--lines` accepts multiple sections, comma separated or by repeating the option, e.g. `--lines "1:5,50:70,100:"`. Skipped rows between sections are marked with a divider
- `--lines` works with text, Markdown and reStructuredText files, and can also be written as `--line`. Ranges may be written as `50-70`. Backwards ranges (`70:50`) are flipped with a warning, and ranges past the end of the file show a warning
- `--section TITLE` option to display only the named section of a text, Markdown or reStructuredText file, e.g. `--section "Instructions"`. Repeat to select several sections. Titles are matched leniently (case, quotes including “smart quotes”, `#` marks, a trailing colon, Markdown formatting and links are ignored, with a fallback that ignores leading numbering and emoji). Missing sections show "Did you mean" suggestions, empty or forgotten titles are reported clearly, and using `--section` on CSV, JSON or notebook files explains what to use instead
- `--sql QUERY` option to query CSV files with SQL (select columns, filter, sort, group, limit), e.g. `--sql "SELECT Name, Age FROM data WHERE Age > 30"`. Only read-only `SELECT` queries are allowed. Text comparisons ignore case (use `COLLATE BINARY` for exact case). Failed queries explain what might be wrong (misspelled keywords or columns, missing `FROM`, unquoted values, unclosed quotes, `&&`, `!`), and warnings point out `||` used for "or", `AND`/`OR` mixed without parentheses, and queries that return no rows. Number columns ignore placeholders such as `N/A`, numbers with leading zeros are kept as text, and very large numbers no longer crash

## [1.8.1] - 2025-07-04

### Fixed

- "UserWarning: The parameter -j is used more than once" in https://github.com/Textualize/rich-cli/pull/74
- Fixed generic blend text in https://github.com/Textualize/rich-cli/pull/51

### Changed

- Rich-CLI now assumes that the input file is encoded in UTF-8 https://github.com/Textualize/rich-cli/pull/56
- The JSON display mode is now `-J/--json`
- _Python >= 3.9_ is now required, so no more support for 3.7 and 3.8
- Hard-code UTF-8 encoding for the input file in https://github.com/Textualize/rich-cli/pull/56
- Updated pyproject.toml to PEP621 and Poetry 2.* in https://github.com/Textualize/rich-cli/pull/103

## [1.8.0] - 2022-05-07

### Changed

- Bumped Rich for improved SVG export

## [1.7.0] - 2022-05-1

## Added

- Added Jupyter Notebook support https://github.com/Textualize/rich-cli/pull/47
- Added --export-svg option
- Added support for vi navigation to pager https://github.com/Textualize/rich-cli/pull/44/

## [1.6.1] - 2022-04-23

### Fixed

- Fixed wrong version number reported

## [1.6.0] - 2022-04-23

### Added

- Added space key to page down to pager

### Changed

- Change how code blocks in markdown are rendered (remove border, adding padding)
