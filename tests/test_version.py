import re
from importlib import metadata
from pathlib import Path

from click.testing import CliRunner

from rich_cli import __main__ as rich_main

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def pyproject_version() -> str:
    match = re.search(r'^version = "([^"]+)"', PYPROJECT.read_text(), re.MULTILINE)
    assert match, "no version found in pyproject.toml"
    return match.group(1)


def test_version_matches_pyproject():
    result = CliRunner().invoke(rich_main.main, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == pyproject_version(), (
        "rich --version doesn't match pyproject.toml. If you changed the version, "
        "reinstall the package: python -m pip install -e ."
    )


def test_version_shown_in_help():
    result = CliRunner().invoke(rich_main.main, ["--help"])
    assert f"v{rich_main.VERSION}" in result.output


def test_version_when_not_installed(monkeypatch):
    def not_installed(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", not_installed)
    assert rich_main._get_version() == "unknown"
