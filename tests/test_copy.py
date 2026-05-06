from __future__ import annotations

from pathlib import Path

from conftest import init_repo, run_git
from workthreads.copy import copy_selected_files, select_local_files


def test_select_and_copy_ignored_and_untracked_files(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".env.local\n", encoding="utf-8")
    run_git(["add", ".gitignore"], cwd=repo)
    run_git(["commit", "-m", "ignore local env"], cwd=repo)

    (repo / ".env.local").write_text("SECRET=value\n", encoding="utf-8")
    (repo / "notes.txt").write_text("scratch\n", encoding="utf-8")
    destination = tmp_path / "destination"
    destination.mkdir()

    selection = select_local_files(repo, copy_ignored=True, copy_untracked=True)
    counts = copy_selected_files(repo, destination, selection, overwrite=False)

    assert selection.files[Path(".env.local")] == "ignored"
    assert selection.files[Path("notes.txt")] == "untracked"
    assert counts.ignored == 1
    assert counts.untracked == 1
    assert (destination / ".env.local").read_text(encoding="utf-8") == "SECRET=value\n"
    assert (destination / "notes.txt").read_text(encoding="utf-8") == "scratch\n"
