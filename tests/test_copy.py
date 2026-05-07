from __future__ import annotations

from pathlib import Path

from conftest import init_repo, run_git
from workthreads import copy as copy_module
from workthreads.copy import copy_one, copy_selected_files, select_local_files


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


def test_copy_one_uses_clone_fast_path_when_available(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("source\n", encoding="utf-8")
    calls: list[tuple[Path, Path]] = []

    def fake_clone(clone_source: Path, clone_destination: Path) -> bool:
        calls.append((clone_source, clone_destination))
        clone_destination.write_text("cloned\n", encoding="utf-8")
        return True

    monkeypatch.setattr(copy_module, "try_clone_file", fake_clone)

    copy_one(source, destination, overwrite=False)

    assert calls == [(source, destination)]
    assert destination.read_text(encoding="utf-8") == "cloned\n"


def test_copy_one_falls_back_when_clone_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("source\n", encoding="utf-8")
    monkeypatch.setattr(copy_module, "try_clone_file", lambda _source, _destination: False)

    copy_one(source, destination, overwrite=False)

    assert destination.read_text(encoding="utf-8") == "source\n"
