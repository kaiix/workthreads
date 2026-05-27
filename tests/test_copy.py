from __future__ import annotations

from pathlib import Path

from conftest import init_repo, run_git
from workthreads import copy as copy_module
from workthreads.copy import CopySelection, copy_one, copy_selected_files, select_local_files


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


def test_select_local_files_skips_default_worktrees_directory(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".env.local\n.worktrees/\n", encoding="utf-8")
    run_git(["add", ".gitignore"], cwd=repo)
    run_git(["commit", "-m", "ignore local files"], cwd=repo)

    (repo / ".env.local").write_text("SECRET=value\n", encoding="utf-8")
    nested_worktree = repo / ".worktrees" / "feature-demo"
    nested_worktree.mkdir(parents=True)
    (nested_worktree / "local-cache.txt").write_text("large local cache\n", encoding="utf-8")
    destination = tmp_path / "destination"
    destination.mkdir()

    selection = select_local_files(repo, copy_ignored=True, copy_untracked=True)
    counts = copy_selected_files(repo, destination, selection, overwrite=False)

    assert selection.files == {Path(".env.local"): "ignored"}
    assert counts.ignored == 1
    assert counts.untracked == 0
    assert (destination / ".env.local").exists()
    assert not (destination / ".worktrees").exists()


def test_copy_tree_skips_excluded_children(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "keep.txt").write_text("keep\n", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("private git data\n", encoding="utf-8")
    (source / ".worktrees" / "feature").mkdir(parents=True)
    (source / ".worktrees" / "feature" / "cache.txt").write_text("cache\n", encoding="utf-8")
    (source / ".workthreads").mkdir()
    (source / ".workthreads" / "cache.txt").write_text("cache\n", encoding="utf-8")

    copy_one(source, destination, overwrite=False)

    assert (destination / "keep.txt").read_text(encoding="utf-8") == "keep\n"
    assert not (destination / ".git").exists()
    assert not (destination / ".worktrees").exists()
    assert not (destination / ".workthreads").exists()


def test_selection_exclude_paths_apply_during_recursive_copy(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / ".local").mkdir()
    (source / ".local" / "config.json").write_text("{}\n", encoding="utf-8")
    configured_worktrees = source / ".local" / "worktrees" / "feature-demo"
    configured_worktrees.mkdir(parents=True)
    (configured_worktrees / "cache.txt").write_text("cache\n", encoding="utf-8")
    destination.mkdir()

    selection = CopySelection(
        files={Path(".local"): "ignored"},
        exclude_paths=(Path(".local/worktrees"),),
    )
    counts = copy_selected_files(source, destination, selection, overwrite=False)

    assert counts.ignored == 1
    assert (destination / ".local" / "config.json").exists()
    assert not (destination / ".local" / "worktrees").exists()


def test_copy_selected_files_preserves_destination_git_file(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    nested = source / "scratch"
    nested.mkdir()
    (nested / "keep.txt").write_text("keep\n", encoding="utf-8")
    (nested / ".git").mkdir()
    (nested / ".git" / "config").write_text("private git data\n", encoding="utf-8")
    destination.mkdir()
    (destination / ".git").write_text("gitdir: existing-worktree\n", encoding="utf-8")

    selection = CopySelection(files={Path("scratch"): "untracked"})
    counts = copy_selected_files(source, destination, selection, overwrite=False)

    assert counts.untracked == 1
    assert (destination / ".git").read_text(encoding="utf-8") == "gitdir: existing-worktree\n"
    assert (destination / "scratch" / "keep.txt").exists()
    assert not (destination / "scratch" / ".git").exists()


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
