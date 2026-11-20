from __future__ import annotations

import os
from pathlib import Path
import stat
import sys

import pytest

from conftest import init_repo, run_git
from workthreads import copy as copy_module
from workthreads.copy import CopySelection, copy_one, copy_selected_files, select_local_files
from workthreads.errors import WTError


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


def test_copy_exclude_patterns_support_negation_and_root_anchoring(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "tmp").mkdir()
    (repo / "tmp" / "root.txt").write_text("exclude\n", encoding="utf-8")
    (repo / "nested" / "tmp").mkdir(parents=True)
    (repo / "nested" / "tmp" / "nested.txt").write_text("keep\n", encoding="utf-8")
    (repo / "nested" / "deep" / "drop.generated").parent.mkdir(parents=True)
    (repo / "nested" / "deep" / "drop.generated").write_text("exclude\n", encoding="utf-8")
    (repo / "debug.copyexclude").write_text("exclude\n", encoding="utf-8")
    (repo / "important.copyexclude").write_text("keep\n", encoding="utf-8")

    selection = select_local_files(
        repo,
        copy_ignored=False,
        copy_untracked=True,
        exclude_patterns=(
            "/tmp/",
            "nested/**/drop.generated",
            "*.copyexclude",
            "!important.copyexclude",
        ),
    )

    assert selection.files == {
        Path("important.copyexclude"): "untracked",
        Path("nested/tmp/nested.txt"): "untracked",
    }


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

    selection = select_local_files(
        repo,
        copy_ignored=True,
        copy_untracked=True,
        exclude_paths=(Path(".worktrees"), Path(".worktrees/feature-demo")),
        exclude_patterns=("!.worktrees/",),
    )
    counts = copy_selected_files(repo, destination, selection, overwrite=False)

    if os.name != "nt":
        assert selection.exclude_paths == ()
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


def test_copy_one_does_not_follow_destination_symlink_on_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "new.txt"
    source.write_text("replacement", encoding="utf-8")
    target = tmp_path / "original.txt"
    target.write_text("keep", encoding="utf-8")
    destination = tmp_path / "destination.txt"
    destination.symlink_to(target)

    with pytest.raises(WTError, match="destination already exists"):
        copy_one(source, destination, overwrite=False)
    assert destination.is_symlink()

    copy_one(source, destination, overwrite=True)
    assert not destination.is_symlink()
    assert destination.read_text(encoding="utf-8") == "replacement"
    assert target.read_text(encoding="utf-8") == "keep"


@pytest.mark.skipif(sys.platform != "darwin", reason="uses Darwin clonefile")
@pytest.mark.parametrize("mode", [0o751, 0o4751])
def test_darwin_clone_keeps_permissions_and_timestamps(tmp_path: Path, mode: int) -> None:
    source = tmp_path / "source.txt"
    source.write_text("original", encoding="utf-8")
    source.chmod(mode)
    os.utime(source, ns=(1714000000234567890, 1725000000123456789))
    original = source.stat()
    destination = tmp_path / "clone.txt"

    if not copy_module.try_clone_file(source, destination):
        pytest.skip("test filesystem does not support Darwin clones")

    cloned = destination.stat()
    assert stat.S_IMODE(cloned.st_mode) == stat.S_IMODE(original.st_mode)
    assert cloned.st_atime_ns == original.st_atime_ns
    assert cloned.st_mtime_ns == original.st_mtime_ns
    destination.write_text("changed", encoding="utf-8")
    assert source.read_text(encoding="utf-8") == "original"
