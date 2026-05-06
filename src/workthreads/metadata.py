from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json

from . import git


@dataclass(frozen=True)
class WorktreeMetadata:
    path: str
    branch: str
    base: str | None = None


def metadata_dir(repo_root: Path) -> Path:
    return git.common_dir(repo_root) / "workthreads" / "worktrees"


def metadata_id(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()


def save_metadata(repo_root: Path, metadata: WorktreeMetadata) -> None:
    directory = metadata_dir(repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{metadata_id(Path(metadata.path))}.json"
    path.write_text(json.dumps(asdict(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def remove_metadata(repo_root: Path, worktree_path: Path) -> None:
    path = metadata_dir(repo_root) / f"{metadata_id(worktree_path)}.json"
    if path.exists():
        path.unlink()


def load_metadata(repo_root: Path) -> list[WorktreeMetadata]:
    directory = metadata_dir(repo_root)
    if not directory.exists():
        return []
    entries: list[WorktreeMetadata] = []
    for path in directory.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        entries.append(WorktreeMetadata(**data))
    return entries


def metadata_by_path(repo_root: Path) -> dict[str, WorktreeMetadata]:
    return {entry.path: entry for entry in load_metadata(repo_root)}
