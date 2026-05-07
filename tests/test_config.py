from __future__ import annotations

from pathlib import Path

from conftest import init_repo, run_wt


def test_builtin_worktrees_dir_defaults_to_dot_worktrees(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")

    get_result = run_wt(["config", "get", "defaults.worktreesDir"], cwd=repo, env=wt_env)

    assert get_result.returncode == 0, get_result.stderr
    assert get_result.stdout.strip() == ".worktrees"


def test_config_set_get_and_list_repo_config(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")

    set_result = run_wt(["config", "set", "defaults.worktreesDir", "../threads"], cwd=repo, env=wt_env)
    assert set_result.returncode == 0, set_result.stderr

    get_result = run_wt(["config", "get", "defaults.worktreesDir"], cwd=repo, env=wt_env)
    assert get_result.returncode == 0
    assert get_result.stdout.strip() == "../threads"

    list_result = run_wt(["config", "list"], cwd=repo, env=wt_env)
    assert "defaults.worktreesDir" in list_result.stdout
    assert "../threads" in list_result.stdout
    assert "Parent directory for generated worktree paths." in list_result.stdout
    assert "defaults.copyLocal" in list_result.stdout
    assert "Copy ignored and untracked local files" in list_result.stdout
    plain_result = run_wt(["config", "list", "--plain"], cwd=repo, env=wt_env)
    assert "defaults.worktreesDir=../threads" in plain_result.stdout
    assert (repo / "wt.toml").exists()
