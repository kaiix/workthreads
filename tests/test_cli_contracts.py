from __future__ import annotations

from pathlib import Path

from conftest import init_repo, run_wt


def test_bare_wt_outside_repo_is_contextual_help(tmp_path: Path, wt_env: dict[str, str]) -> None:
    result = run_wt([], cwd=tmp_path, env=wt_env)

    assert result.returncode == 0
    assert "workthreads wt" in result.stdout
    assert "Run inside a git repository" in result.stdout


def test_bare_wt_inside_repo_lists_setup_commands(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")

    result = run_wt([], cwd=repo, env=wt_env)

    assert result.returncode == 0
    assert "Setup commands:" in result.stdout
    assert "wt config set <key> <value>" in result.stdout
    assert "wt hooks init" in result.stdout
    assert "wt init <shell>" in result.stdout


def test_cd_requires_shell_integration(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")

    result = run_wt(["add", "feature/cd", "--base", "HEAD", "--cd"], cwd=repo, env=wt_env)

    assert result.returncode == 2
    assert "--cd requires shell integration" in result.stderr


def test_cd_and_json_are_mutually_exclusive(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    env = wt_env | {"WT_SHELL_INTEGRATION": "1"}

    result = run_wt(["add", "feature/cd-json", "--base", "HEAD", "--cd", "--json"], cwd=repo, env=env)

    assert result.returncode == 2
    assert "--cd and --json are mutually exclusive" in result.stderr


def test_shell_integration_allows_cd_request(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    destination = tmp_path / "threads" / "feature-cd"
    env = wt_env | {"WT_SHELL_INTEGRATION": "1"}

    result = run_wt(
        ["add", "feature/cd", "--base", "HEAD", "--path", str(destination), "--cd"],
        cwd=repo,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == str(destination)
    assert destination.exists()


def test_completion_and_init_scripts_are_available(tmp_path: Path, wt_env: dict[str, str]) -> None:
    completion = run_wt(["completion", "zsh"], cwd=tmp_path, env=wt_env)
    init = run_wt(["init", "bash"], cwd=tmp_path, env=wt_env)

    assert completion.returncode == 0
    assert "compdef _wt wt" in completion.stdout
    assert init.returncode == 0
    assert "WT_SHELL_INTEGRATION=1" in init.stdout
    assert "wt_status" in init.stdout
    assert "local tmp status" not in init.stdout
