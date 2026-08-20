from __future__ import annotations

from pathlib import Path

from conftest import init_repo, run_wt


EXPECTED_BUILTIN_DEFAULTS = {
    "defaults.worktreesDir": ".worktrees",
    "defaults.fetch": "true",
    "defaults.copyLocal": "false",
    "defaults.copyExclude": "[]",
    "defaults.deleteBranch": "false",
    "shell.cdAfterAdd": "true",
}


def test_builtin_defaults(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")

    for key, expected in EXPECTED_BUILTIN_DEFAULTS.items():
        get_result = run_wt(["config", "get", key], cwd=repo, env=wt_env)

        assert get_result.returncode == 0, get_result.stderr
        assert get_result.stdout.strip() == expected


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


def test_config_init_path_and_edit_use_config_files(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    repo_config = repo / "wt.toml"
    global_config = tmp_path / "xdg" / "workthreads" / "config.toml"

    path_result = run_wt(["config", "path"], cwd=repo, env=wt_env)
    assert path_result.returncode == 0
    assert path_result.stdout.strip() == str(repo_config)

    global_path_result = run_wt(["config", "path", "--global"], cwd=repo, env=wt_env)
    assert global_path_result.returncode == 0
    assert global_path_result.stdout.strip() == str(global_config)

    init_result = run_wt(["config", "init"], cwd=repo, env=wt_env)
    assert init_result.returncode == 0, init_result.stderr
    assert f"created config: {repo_config}" in init_result.stdout
    config_text = repo_config.read_text(encoding="utf-8")
    assert 'worktreesDir = ".worktrees"' in config_text
    assert "fetch = true" in config_text
    assert "copyLocal = false" in config_text
    assert "copyExclude = []" in config_text
    assert "deleteBranch = false" in config_text
    assert "cdAfterAdd = true" in config_text

    for key, expected in EXPECTED_BUILTIN_DEFAULTS.items():
        get_result = run_wt(["config", "get", key], cwd=repo, env=wt_env)

        assert get_result.returncode == 0, get_result.stderr
        assert get_result.stdout.strip() == expected

    second_init = run_wt(["config", "init"], cwd=repo, env=wt_env)
    assert second_init.returncode == 0
    assert f"config exists: {repo_config}" in second_init.stdout

    repo_config.write_text("custom = true\n", encoding="utf-8")
    force_init = run_wt(["config", "init", "--force"], cwd=repo, env=wt_env)
    assert force_init.returncode == 0
    assert "custom = true" not in repo_config.read_text(encoding="utf-8")

    edit_result = run_wt(["config", "edit", "--global"], cwd=repo, env=wt_env)
    assert edit_result.returncode == 0
    assert edit_result.stdout.strip() == str(global_config)
    assert global_config.exists()


def test_config_set_reads_and_preserves_copy_exclude_array(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")

    set_excludes = run_wt(
        ["config", "set", "defaults.copyExclude", '["node_modules/", "*.log"]'],
        cwd=repo,
        env=wt_env,
    )
    set_fetch = run_wt(["config", "set", "defaults.fetch", "false"], cwd=repo, env=wt_env)
    get_excludes = run_wt(["config", "get", "defaults.copyExclude"], cwd=repo, env=wt_env)

    assert set_excludes.returncode == 0, set_excludes.stderr
    assert set_fetch.returncode == 0, set_fetch.stderr
    assert get_excludes.returncode == 0, get_excludes.stderr
    assert get_excludes.stdout.strip() == '["node_modules/", "*.log"]'
    assert 'copyExclude = ["node_modules/", "*.log"]' in (repo / "wt.toml").read_text(encoding="utf-8")

    invalid = run_wt(
        ["config", "set", "defaults.copyExclude", "[1]"],
        cwd=repo,
        env=wt_env,
    )
    unchanged = run_wt(["config", "get", "defaults.copyExclude"], cwd=repo, env=wt_env)

    assert invalid.returncode == 2
    assert "defaults.copyExclude must be an array of strings" in invalid.stderr
    assert unchanged.stdout.strip() == '["node_modules/", "*.log"]'


def test_repo_copy_exclude_replaces_global_array(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    global_config = Path(wt_env["XDG_CONFIG_HOME"]) / "workthreads" / "config.toml"
    global_config.parent.mkdir(parents=True)
    global_config.write_text('[defaults]\ncopyExclude = ["*.log"]\n', encoding="utf-8")
    (repo / "wt.toml").write_text('[defaults]\ncopyExclude = ["cache/"]\n', encoding="utf-8")

    result = run_wt(["config", "get", "defaults.copyExclude"], cwd=repo, env=wt_env)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '["cache/"]'


def test_add_rejects_non_array_copy_exclude_config(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "wt.toml").write_text(
        '[defaults]\nfetch = false\ncopyLocal = true\ncopyExclude = "cache/"\n',
        encoding="utf-8",
    )

    result = run_wt(["add", "feature/invalid-excludes", "--base", "HEAD"], cwd=repo, env=wt_env)

    assert result.returncode == 2
    assert "defaults.copyExclude must be an array of strings" in result.stderr
