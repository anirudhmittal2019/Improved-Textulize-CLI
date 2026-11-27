"""Checks that keep the README in step with the code."""

import re
from pathlib import Path

from rich_cli.__main__ import main

README = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")


def options_reference() -> str:
    start = README.index("## Options reference")
    end = README.index("\n## ", start + 1)
    return README[start:end]


def test_every_option_is_in_the_options_reference():
    reference = options_reference()
    # Option names as written in the reference, e.g. `-n`, `--head LINES`
    documented = set(re.findall(r"`(--?[\w-]+)", reference))
    missing = [
        name
        for param in main.params
        for name in [*param.opts, *getattr(param, "secondary_opts", [])]
        if name.startswith("-") and name not in documented
    ]
    assert (
        not missing
    ), f"Add these options to the README's Options reference: {missing}"


def test_options_reference_has_no_unknown_options():
    known = {
        name
        for param in main.params
        for name in [*param.opts, *getattr(param, "secondary_opts", [])]
    } | {"--help"}
    reference = options_reference()
    # Only check the option column (the first cell of each table row)
    option_cells = re.findall(r"^\| ([^|]*) \|", reference, re.MULTILINE)
    unknown = {
        name
        for cell in option_cells
        for name in re.findall(r"`(--?[\w-]+)", cell)
        if name not in known
    }
    assert (
        not unknown
    ), f"The Options reference lists options that don't exist: {unknown}"
