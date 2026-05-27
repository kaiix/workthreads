from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
import ctypes
import errno
import os
import shutil
import stat
import sys

from .errors import WTError
from . import git


EXCLUDED_COPY_PARTS = {".git", ".worktrees", ".workthreads"}
_DARWIN_CLONEFILE: Callable[[bytes, bytes, int], int] | None = None


@dataclass(frozen=True)
class CopyCounts:
    ignored: int = 0
    untracked: int = 0


@dataclass(frozen=True)
class CopySelection:
    files: dict[Path, str]
    exclude_paths: tuple[Path, ...] = ()

    @property
    def counts(self) -> CopyCounts:
        ignored = sum(1 for category in self.files.values() if category == "ignored")
        untracked = sum(1 for category in self.files.values() if category == "untracked")
        return CopyCounts(ignored=ignored, untracked=untracked)


def select_local_files(
    source_root: Path,
    *,
    copy_ignored: bool,
    copy_untracked: bool,
    exclude_paths: Iterable[Path] = (),
) -> CopySelection:
    files: dict[Path, str] = {}
    normalized_exclude_paths = tuple(exclude_paths)
    if copy_ignored:
        for path in git.ignored_files(source_root):
            if should_copy(path, exclude_paths=normalized_exclude_paths):
                files[path] = "ignored"
    if copy_untracked:
        for path in git.untracked_files(source_root):
            if (
                should_copy(path, exclude_paths=normalized_exclude_paths)
                and path not in files
            ):
                files[path] = "untracked"
    return CopySelection(files=files, exclude_paths=normalized_exclude_paths)


def should_copy(path: Path, *, exclude_paths: Iterable[Path] = ()) -> bool:
    if any(part in EXCLUDED_COPY_PARTS for part in path.parts):
        return False
    return not any(
        path == excluded_path or path.is_relative_to(excluded_path)
        for excluded_path in exclude_paths
    )


def copy_selected_files(
    source_root: Path,
    destination_root: Path,
    selection: CopySelection,
    *,
    overwrite: bool,
) -> CopyCounts:
    counts = {"ignored": 0, "untracked": 0}
    for relative_path, category in selection.files.items():
        copy_one(
            source_root / relative_path,
            destination_root / relative_path,
            overwrite=overwrite,
            relative_path=relative_path,
            exclude_paths=selection.exclude_paths,
        )
        counts[category] += 1
    return CopyCounts(ignored=counts["ignored"], untracked=counts["untracked"])


def copy_one(
    source: Path,
    destination: Path,
    *,
    overwrite: bool,
    relative_path: Path | None = None,
    exclude_paths: Iterable[Path] = (),
) -> None:
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
        copy_tree(source, destination, relative_path=relative_path, exclude_paths=exclude_paths)
    else:
        copy_file(source, destination)


def copy_tree(
    source: Path,
    destination: Path,
    *,
    relative_path: Path | None = None,
    exclude_paths: Iterable[Path] = (),
) -> None:
    destination.mkdir()
    for child in source.iterdir():
        child_relative_path = (
            relative_path / child.name
            if relative_path is not None
            else Path(child.name)
        )
        if not should_copy(child_relative_path, exclude_paths=exclude_paths):
            continue
        copy_one(
            child,
            destination / child.name,
            overwrite=False,
            relative_path=child_relative_path,
            exclude_paths=exclude_paths,
        )
    shutil.copystat(source, destination, follow_symlinks=False)


def copy_file(source: Path, destination: Path) -> None:
    if try_clone_file(source, destination):
        return
    shutil.copy2(source, destination)


def try_clone_file(source: Path, destination: Path) -> bool:
    try:
        if sys.platform == "darwin":
            clone_file_darwin(source, destination)
            return True
        if sys.platform.startswith("linux"):
            clone_file_linux(source, destination)
            return True
    except AttributeError:
        remove_partial_clone(destination)
    except OSError as error:
        if error.errno != errno.EEXIST:
            remove_partial_clone(destination)
    return False


def clone_file_darwin(source: Path, destination: Path) -> None:
    result = darwin_clonefile()(os.fsencode(source), os.fsencode(destination), 0)
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), str(destination))
    shutil.copystat(source, destination, follow_symlinks=False)


def darwin_clonefile() -> Callable[[bytes, bytes, int], int]:
    global _DARWIN_CLONEFILE
    if _DARWIN_CLONEFILE is None:
        libc = ctypes.CDLL("libc.dylib", use_errno=True)
        clonefile = libc.clonefile
        clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
        clonefile.restype = ctypes.c_int
        _DARWIN_CLONEFILE = clonefile
    return _DARWIN_CLONEFILE


def clone_file_linux(source: Path, destination: Path) -> None:
    import fcntl

    ficlone = 0x40049409
    mode = stat.S_IMODE(source.stat().st_mode)
    with source.open("rb") as source_file:
        destination_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        try:
            fcntl.ioctl(destination_fd, ficlone, source_file.fileno())
        finally:
            os.close(destination_fd)
    shutil.copystat(source, destination, follow_symlinks=False)


def remove_partial_clone(destination: Path) -> None:
    try:
        destination.unlink()
    except FileNotFoundError:
        return
    except IsADirectoryError:
        return
    except OSError as error:
        if error.errno != errno.ENOENT:
            raise
