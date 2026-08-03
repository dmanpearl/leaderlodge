"""Keep docs/management-commands.md in sync with project management commands."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DOC = REPO_ROOT / "docs" / "management-commands.md"
# Each project command must have a heading like: ### find_fake_accounts
_COMMAND_HEADING_RE = re.compile(r"^### `?([a-z][a-z0-9_]*)`?\s*$", re.MULTILINE)


def discover_project_management_commands() -> set[str]:
    """Return stems of leaderlodge/*/management/commands/*.py (no __init__)."""
    names: set[str] = set()
    for path in (REPO_ROOT / "leaderlodge").glob("*/management/commands/*.py"):
        if path.name.startswith("_"):
            continue
        names.add(path.stem)
    return names


def documented_management_commands(text: str) -> set[str]:
    return set(_COMMAND_HEADING_RE.findall(text))


def test_management_commands_doc_matches_filesystem():
    discovered = discover_project_management_commands()
    assert discovered, "expected at least one project management command"

    assert COMMANDS_DOC.is_file(), f"missing {COMMANDS_DOC.relative_to(REPO_ROOT)}"
    documented = documented_management_commands(COMMANDS_DOC.read_text(encoding="utf-8"))

    missing = sorted(discovered - documented)
    extra = sorted(documented - discovered)
    assert not missing, (
        "Add a ### heading for each new command in docs/management-commands.md. "
        f"Missing: {missing}"
    )
    assert not extra, (
        "docs/management-commands.md documents commands that are not on disk. "
        f"Extra: {extra}"
    )
