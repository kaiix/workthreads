from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from .errors import WTError
from . import git


@dataclass(frozen=True)
class CopyCounts:
    ignored: int = 0
    untracked: int = 0


@dataclass(frozen=True)
class CopySelection:
    files: dict[Path, str]

    @property
    def counts(self) -> CopyCounts:
        ignored = sum(1 for category in self.files.values() if category == "ignored")
        untracked = sum(1 for category in self.files.values() if category == "untracked")
        return CopyCounts(ignored=ignored, untracked=untracked)


def select_local_files(source_root: Path, *, copy_ignored: bool, copy_untracked: bool) -> CopySelection:
    files: dict[Path, str] = {}
    if copy_ignored:
        for path in git.ignored_files(source_root):
            if should_copy(path):
                files[path] = "ignored"
    if copy_untracked:
        for path in git.untracked_files(source_root):
            if should_copy(path) and path not in files:
                files[path] = "untracked"
    return CopySelection(files=files)


def should_copy(path: Path) -> bool:
    parts = path.parts
    return ".git" not in parts and ".workthreads" not in parts


def copy_selected_files(source_root: Path, destination_root: Path, selection: CopySelection, *, overwrite: bool) -> CopyCounts:
    counts = {"ignored": 0, "untracked": 0}
    for relative_path, category in selection.files.items():
        copy_one(source_root / relative_path, destination_root / relative_path, overwrite=overwrite)
        counts[category] += 1
    return CopyCounts(ignored=counts["ignored"], untracked=counts["untracked"])


def copy_one(source: Path, destination: Path, *, overwrite: bool) -> None:
    if destination.exists() or destination.is_symlink():
        if not overwrite:
            raise WTError(
                f"destination already exists while copying local file: {destination}",
                hint="pass --overwrite to replace existing copied files",
            )
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()

    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(source.readlink())
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination)
