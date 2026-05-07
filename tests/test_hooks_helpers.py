from __future__ import annotations

from pathlib import Path
import os

from conftest import init_repo, run_wt


def test_hooks_helpers_manage_repo_local_scripts(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    hook_dir = repo / ".git" / "workthreads" / "hooks"

    dir_result = run_wt(["hooks", "dir"], cwd=repo, env=wt_env)
    assert dir_result.returncode == 0, dir_result.stderr
    assert dir_result.stdout.strip() == str(hook_dir)

    path_result = run_wt(["hooks", "path", "post-create"], cwd=repo, env=wt_env)
    assert path_result.returncode == 0, path_result.stderr
    assert path_result.stdout.strip() == str(hook_dir / "post-create.sh")

    init_result = run_wt(["hooks", "init"], cwd=repo, env=wt_env)
    assert init_result.returncode == 0, init_result.stderr
    post_create = hook_dir / "post-create.sh"
    pre_delete = hook_dir / "pre-delete.sh"
    assert post_create.exists()
    assert pre_delete.exists()
    assert os.access(post_create, os.X_OK)
    assert os.access(pre_delete, os.X_OK)

    configured_hook = run_wt(["config", "get", "hooks.postCreate"], cwd=repo, env=wt_env)
    assert configured_hook.returncode == 0, configured_hook.stderr
    assert configured_hook.stdout.strip() == str(post_create)


def test_hooks_edit_prints_path_without_editor(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    result = run_wt(["hooks", "edit", "pre-delete"], cwd=repo, env=wt_env)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(repo / ".git" / "workthreads" / "hooks" / "pre-delete.sh")
