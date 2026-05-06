from __future__ import annotations

from pathlib import Path

import pytest

from workthreads.errors import WTError
from workthreads.hooks import hook_env, run_hook


def test_hook_env_contains_stable_values(tmp_path: Path) -> None:
    env = hook_env(
        event="post-create",
        repo_root=tmp_path / "repo",
        worktree_path=tmp_path / "threads" / "feature-a",
        worktree_name="feature-a",
        branch="feature/a",
        base="origin/main",
        copy_local=True,
        copy_ignored=True,
        copy_untracked=True,
    )

    assert env["WT_EVENT"] == "post-create"
    assert env["WT_BRANCH"] == "feature/a"
    assert env["WT_COPY_LOCAL"] == "1"
    assert env["WT_COPY_IGNORED"] == "1"
    assert env["WT_COPY_UNTRACKED"] == "1"


def test_hook_failure_is_structured(tmp_path: Path) -> None:
    with pytest.raises(WTError) as error:
        run_hook(
            "echo bad >&2; exit 7",
            event="post-create",
            cwd=tmp_path,
            env={},
        )

    assert error.value.message == "post-create hook failed"
    assert "bad" in (error.value.details or "")
