from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from conftest import init_repo, run_command, run_git, run_wt


def test_add_list_and_delete_worktree_with_copy_and_hooks(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".env.local\n", encoding="utf-8")
    run_git(["add", ".gitignore"], cwd=repo)
    run_git(["commit", "-m", "ignore local env"], cwd=repo)
    (repo / ".env.local").write_text("TOKEN=local\n", encoding="utf-8")
    (repo / "notes.txt").write_text("scratch\n", encoding="utf-8")

    hook = tmp_path / "post-create.sh"
    hook.write_text(
        "#!/bin/sh\n"
        "printf '%s' \"$WT_EVENT\" > \"$WT_WORKTREE_PATH/hook-event.txt\"\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)

    destination = tmp_path / "threads" / "feature-demo"
    add = run_wt(
        [
            "add",
            "feature/demo",
            "--base",
            "HEAD",
            "--path",
            str(destination),
            "--copy-local",
            "--post-create",
            str(hook),
        ],
        cwd=repo,
        env=wt_env,
    )

    assert add.returncode == 0, add.stderr
    assert add.stdout.splitlines()[-1] == str(destination)
    assert (destination / ".env.local").read_text(encoding="utf-8") == "TOKEN=local\n"
    assert (destination / "notes.txt").read_text(encoding="utf-8") == "scratch\n"
    assert (destination / "hook-event.txt").read_text(encoding="utf-8") == "post-create"

    listed = run_wt(["list"], cwd=repo, env=wt_env)
    assert listed.returncode == 0, listed.stderr
    assert "feature/demo" in listed.stdout
    assert str(destination) in listed.stdout
    assert "HEAD" in listed.stdout
    assert not (repo / ".workthreads").exists()

    deleted = run_wt(["delete", "feature/demo", "--force", "--delete-branch"], cwd=repo, env=wt_env)
    assert deleted.returncode == 0, deleted.stderr
    assert not destination.exists()
    branch_check = run_git(["show-ref", "--verify", "--quiet", "refs/heads/main"], cwd=repo)
    assert branch_check.returncode == 0
    missing_branch = run_command(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/feature/demo"],
        cwd=repo,
    )
    assert missing_branch.returncode != 0


def test_list_reports_prunable_worktree_without_failing(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    destination = tmp_path / "threads" / "stale"
    run_git(["worktree", "add", "-b", "feature/stale", str(destination), "HEAD"], cwd=repo)
    shutil.rmtree(destination)

    listed = run_wt(["list"], cwd=repo, env=wt_env)

    assert listed.returncode == 0, listed.stderr
    assert str(repo) in listed.stdout
    assert str(destination) in listed.stdout
    assert "prunable" in listed.stdout
    assert "git worktree prune" in listed.stderr
    assert "Traceback" not in listed.stderr


def test_delete_reports_prunable_worktree(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    destination = tmp_path / "threads" / "stale"
    run_git(["worktree", "add", "-b", "feature/stale", str(destination), "HEAD"], cwd=repo)
    shutil.rmtree(destination)

    deleted = run_wt(["delete", "feature/stale"], cwd=repo, env=wt_env)

    assert deleted.returncode == 1
    assert "worktree is unavailable: feature/stale" in deleted.stderr
    assert "git worktree prune" in deleted.stderr
    assert "Traceback" not in deleted.stderr


def test_add_copy_local_applies_configured_exclusions(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".env.local\ncache/\n", encoding="utf-8")
    (repo / "wt.toml").write_text(
        "[defaults]\n"
        "fetch = false\n"
        "copyLocal = true\n"
        'copyExclude = ["cache/", "*.log"]\n',
        encoding="utf-8",
    )
    run_git(["add", ".gitignore"], cwd=repo)
    run_git(["add", "-f", "wt.toml"], cwd=repo)
    run_git(["commit", "-m", "configure local copying"], cwd=repo)

    (repo / ".env.local").write_text("TOKEN=local\n", encoding="utf-8")
    (repo / "cache").mkdir()
    (repo / "cache" / "data.bin").write_text("cache\n", encoding="utf-8")
    (repo / "notes.txt").write_text("scratch\n", encoding="utf-8")
    (repo / "debug.log").write_text("log\n", encoding="utf-8")
    destination = tmp_path / "threads" / "copy-excludes"

    add = run_wt(
        ["add", "feature/copy-excludes", "--base", "HEAD", "--path", str(destination)],
        cwd=repo,
        env=wt_env,
    )

    assert add.returncode == 0, add.stderr
    assert "copied: ignored=1 untracked=1" in add.stdout
    assert (destination / ".env.local").read_text(encoding="utf-8") == "TOKEN=local\n"
    assert (destination / "notes.txt").read_text(encoding="utf-8") == "scratch\n"
    assert not (destination / "cache").exists()
    assert not (destination / "debug.log").exists()


@pytest.mark.parametrize(
    ("flag", "copied_name", "other_category_name"),
    [
        ("--copy-ignored", ".env.local", "notes.txt"),
        ("--copy-untracked", "notes.txt", ".env.local"),
    ],
)
def test_add_granular_copy_modes_apply_configured_exclusions(
    tmp_path: Path,
    wt_env: dict[str, str],
    flag: str,
    copied_name: str,
    other_category_name: str,
) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".env.local\nignored.omit\n", encoding="utf-8")
    (repo / "wt.toml").write_text(
        '[defaults]\nfetch = false\ncopyExclude = ["*.omit"]\n',
        encoding="utf-8",
    )
    run_git(["add", ".gitignore"], cwd=repo)
    run_git(["add", "-f", "wt.toml"], cwd=repo)
    run_git(["commit", "-m", "configure granular local copying"], cwd=repo)

    (repo / ".env.local").write_text("TOKEN=local\n", encoding="utf-8")
    (repo / "ignored.omit").write_text("ignored\n", encoding="utf-8")
    (repo / "notes.txt").write_text("scratch\n", encoding="utf-8")
    (repo / "scratch.omit").write_text("untracked\n", encoding="utf-8")
    mode = flag.removeprefix("--copy-")
    destination = tmp_path / "threads" / mode

    add = run_wt(
        ["add", f"feature/{mode}", "--base", "HEAD", "--path", str(destination), flag],
        cwd=repo,
        env=wt_env,
    )

    assert add.returncode == 0, add.stderr
    assert (destination / copied_name).exists()
    assert not (destination / other_category_name).exists()
    assert not (destination / "ignored.omit").exists()
    assert not (destination / "scratch.omit").exists()


def test_delete_current_linked_worktree_without_target(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    destination = tmp_path / "threads" / "current"
    cd_file = tmp_path / "cd-target"
    env = wt_env | {"WT_SHELL_INTEGRATION": "1", "WT_CD_FILE": str(cd_file)}

    add = run_wt(["add", "feature/current", "--base", "HEAD", "--path", str(destination)], cwd=repo, env=wt_env)
    assert add.returncode == 0, add.stderr

    deleted = run_wt(["delete", "--force"], cwd=destination, env=env)

    assert deleted.returncode == 0, deleted.stderr
    assert not destination.exists()
    assert cd_file.read_text(encoding="utf-8") == str(repo)


def test_add_uses_default_dot_worktrees_directory(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    destination = repo / ".worktrees" / "feature" / "default"

    add = run_wt(["add", "feature/default", "--base", "HEAD"], cwd=repo, env=wt_env)

    assert add.returncode == 0, add.stderr
    assert add.stdout.splitlines()[-1] == str(destination)
    assert destination.exists()

    deleted = run_wt(["delete", "feature/default", "--force", "--delete-branch"], cwd=repo, env=wt_env)
    assert deleted.returncode == 0, deleted.stderr
    assert not destination.exists()
    assert not (repo / ".worktrees" / "feature").exists()
    assert (repo / ".worktrees").exists()


def test_add_copy_local_skips_configured_worktrees_directory(tmp_path: Path, wt_env: dict[str, str]) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".env.local\nthreads/\n", encoding="utf-8")
    run_git(["add", ".gitignore"], cwd=repo)
    run_git(["commit", "-m", "ignore local files"], cwd=repo)
    config = run_wt(["config", "set", "defaults.worktreesDir", "threads"], cwd=repo, env=wt_env)
    assert config.returncode == 0, config.stderr

    (repo / ".env.local").write_text("TOKEN=local\n", encoding="utf-8")
    existing_worktree_dir = repo / "threads" / "existing"
    existing_worktree_dir.mkdir(parents=True)
    (existing_worktree_dir / "cache.txt").write_text("large cache\n", encoding="utf-8")
    destination = repo / "threads" / "feature" / "config-dir"

    add = run_wt(["add", "feature/config-dir", "--base", "HEAD", "--copy-local"], cwd=repo, env=wt_env)

    assert add.returncode == 0, add.stderr
    assert add.stdout.splitlines()[-1] == str(destination)
    assert (destination / ".env.local").read_text(encoding="utf-8") == "TOKEN=local\n"
    assert not (destination / "threads").exists()
