from __future__ import annotations

from pathlib import Path

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
