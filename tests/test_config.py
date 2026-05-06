from __future__ import annotations

from pathlib import Path

from conftest import init_repo, run_wt


def test_config_set_get_and_list_repo_local(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")

    set_result = run_wt(["config", "set", "defaults.worktreesDir", "../threads"], cwd=repo, env=wt_env)
    assert set_result.returncode == 0, set_result.stderr

    get_result = run_wt(["config", "get", "defaults.worktreesDir"], cwd=repo, env=wt_env)
    assert get_result.returncode == 0
    assert get_result.stdout.strip() == "../threads"

    list_result = run_wt(["config", "list"], cwd=repo, env=wt_env)
    assert "defaults.worktreesDir=../threads" in list_result.stdout
    assert (repo / "workthreads.toml").exists()


def test_legacy_repo_config_is_read_but_new_writes_use_workthreads_toml(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    legacy_config = repo / ".workthreads" / "config.toml"
    legacy_config.parent.mkdir()
    legacy_config.write_text("[defaults]\nworktreesDir = \"../legacy\"\n", encoding="utf-8")

    get_result = run_wt(["config", "get", "defaults.worktreesDir"], cwd=repo, env=wt_env)
    assert get_result.returncode == 0
    assert get_result.stdout.strip() == "../legacy"

    set_result = run_wt(["config", "set", "defaults.base", "origin/main"], cwd=repo, env=wt_env)
    assert set_result.returncode == 0
    assert (repo / "workthreads.toml").exists()
