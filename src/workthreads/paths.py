from __future__ import annotations

from pathlib import Path
import re

from .errors import UsageError


def branch_slug(branch: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", branch)
    slug = re.sub(r"-+", "-", slug).strip("-._")
    return slug or "worktree"


def resolve_destination(
    *,
    repo_root: Path,
    branch: str,
    path: str | None,
    worktrees_dir: str | None,
) -> Path:
    if path and worktrees_dir:
        raise UsageError(
            "--path and --worktrees-dir are mutually exclusive",
            hint="choose --path for an exact destination or --worktrees-dir for a parent directory",
        )

    if path:
        destination = Path(path).expanduser()
    else:
        if not worktrees_dir:
            raise UsageError("missing worktrees directory", hint="set defaults.worktreesDir or pass --path")
        destination = Path(worktrees_dir).expanduser() / branch_slug(branch)

    if not destination.is_absolute():
        destination = repo_root / destination
    return destination.resolve()
