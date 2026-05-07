from __future__ import annotations

from pathlib import Path

import pytest

from workthreads.errors import UsageError
from workthreads.paths import branch_path, branch_slug, resolve_destination


def test_branch_slug_keeps_names_short_and_path_safe() -> None:
    assert branch_slug("payment retry") == "payment-retry"
    assert branch_slug("...") == "worktree"


def test_branch_path_preserves_branch_hierarchy() -> None:
    assert branch_path("feature/payment retry") == Path("feature/payment-retry")
    assert branch_path("///") == Path("worktree")


def test_resolve_destination_from_repo_root() -> None:
    path = resolve_destination(
        repo_root=Path("/repo"),
        branch="feature/payment-retry",
        path=None,
        worktrees_dir=".worktrees",
    )

    assert path == Path("/repo/.worktrees/feature/payment-retry")


def test_path_and_worktrees_dir_are_mutually_exclusive() -> None:
    with pytest.raises(UsageError):
        resolve_destination(
            repo_root=Path("/repo"),
            branch="feature/a",
            path="../exact",
            worktrees_dir="../parent",
        )
