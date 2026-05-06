from __future__ import annotations

from pathlib import Path

import pytest

from workthreads.errors import UsageError
from workthreads.paths import branch_slug, resolve_destination


def test_branch_slug_keeps_names_short_and_path_safe() -> None:
    assert branch_slug("feature/payment retry") == "feature-payment-retry"
    assert branch_slug("///") == "worktree"


def test_resolve_destination_from_repo_root() -> None:
    path = resolve_destination(
        repo_root=Path("/repo"),
        branch="feature/payment-retry",
        path=None,
        worktrees_dir="../workthreads",
    )

    assert path == Path("/workthreads/feature-payment-retry")


def test_path_and_worktrees_dir_are_mutually_exclusive() -> None:
    with pytest.raises(UsageError):
        resolve_destination(
            repo_root=Path("/repo"),
            branch="feature/a",
            path="../exact",
            worktrees_dir="../parent",
        )
