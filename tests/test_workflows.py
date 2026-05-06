from __future__ import annotations

from pathlib import Path
import json

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

    listed = run_wt(["list", "--json"], cwd=repo, env=wt_env)
    assert listed.returncode == 0, listed.stderr
    rows = json.loads(listed.stdout)
    feature_row = next(row for row in rows if row["branch"] == "feature/demo")
    assert feature_row["path"] == str(destination)
    assert feature_row["base"] == "HEAD"

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

    add = run_wt(["add", "feature/current", "--base", "HEAD", "--path", str(destination)], cwd=repo, env=wt_env)
    assert add.returncode == 0, add.stderr

    deleted = run_wt(["delete", "--force"], cwd=destination, env=wt_env)

    assert deleted.returncode == 0, deleted.stderr
    assert not destination.exists()
