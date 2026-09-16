from __future__ import annotations

from pathlib import Path
import shutil

from conftest import init_repo, run_git, run_wt


def add_worktree(repo: Path, env: dict[str, str], branch: str, destination: Path) -> None:
    result = run_wt(["add", branch, "--base", "HEAD", "--path", str(destination)], cwd=repo, env=env)
    assert result.returncode == 0, result.stderr


def test_cd_prints_exact_and_segment_matches(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    destination = tmp_path / "threads" / "feat" / "foo"
    add_worktree(repo, wt_env, "feat/foo", destination)

    exact = run_wt(["cd", "feat/foo"], cwd=repo, env=wt_env)
    assert exact.returncode == 0, exact.stderr
    assert exact.stdout.strip() == str(destination)

    segment = run_wt(["cd", "foo"], cwd=repo, env=wt_env)
    assert segment.returncode == 0, segment.stderr
    assert segment.stdout.strip() == str(destination)

    segment_prefix = run_wt(["cd", "fo"], cwd=repo, env=wt_env)
    assert segment_prefix.returncode == 0, segment_prefix.stderr
    assert segment_prefix.stdout.strip() == str(destination)

    main = run_wt(["cd", "main"], cwd=repo, env=wt_env)
    assert main.returncode == 0, main.stderr
    assert main.stdout.strip() == str(repo)


def test_cd_reports_ambiguous_segment_prefix(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    first = tmp_path / "threads" / "feat" / "foo"
    second = tmp_path / "threads" / "fix" / "foo"
    add_worktree(repo, wt_env, "feat/foo", first)
    add_worktree(repo, wt_env, "fix/foo", second)

    result = run_wt(["cd", "foo"], cwd=repo, env=wt_env)

    assert result.returncode == 2
    assert "ambiguous worktree prefix: foo" in result.stderr
    assert "feat/foo" in result.stderr
    assert "fix/foo" in result.stderr


def test_cd_reports_unknown_target(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")

    result = run_wt(["cd", "missing"], cwd=repo, env=wt_env)

    assert result.returncode == 2
    assert "unknown worktree: missing" in result.stderr
    assert "run wt list" in result.stderr


def test_cd_ignores_prunable_worktree(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    destination = tmp_path / "threads" / "stale"
    run_git(["worktree", "add", "-b", "feature/stale", str(destination), "HEAD"], cwd=repo)
    shutil.rmtree(destination)

    result = run_wt(["cd", "feature/stale"], cwd=repo, env=wt_env)

    assert result.returncode == 2
    assert "unknown worktree: feature/stale" in result.stderr


def test_cd_writes_shell_target_without_printing_path(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    destination = tmp_path / "threads" / "feat" / "foo"
    cd_file = tmp_path / "cd-target"
    env = wt_env | {"WT_SHELL_INTEGRATION": "1", "WT_CD_FILE": str(cd_file)}
    add_worktree(repo, wt_env, "feat/foo", destination)

    result = run_wt(["cd", "foo"], cwd=repo, env=env)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert cd_file.read_text(encoding="utf-8") == str(destination)


def test_complete_worktrees_uses_segment_prefix(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    add_worktree(repo, wt_env, "feat/foo", tmp_path / "threads" / "feat" / "foo")
    add_worktree(repo, wt_env, "bug/bar", tmp_path / "threads" / "bug" / "bar")

    result = run_wt(["__complete", "worktrees", "fo"], cwd=repo, env=wt_env)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["feat/foo"]
