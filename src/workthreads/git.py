from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import os
import subprocess

from .errors import WTError, UsageError


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class Worktree:
    path: Path
    head: str | None = None
    branch: str | None = None
    detached: bool = False
    bare: bool = False

    @property
    def name(self) -> str:
        if self.branch:
            return self.branch.rsplit("/", 1)[-1]
        return self.path.name


@dataclass(frozen=True)
class RepoContext:
    current_root: Path
    main_root: Path
    worktrees: list[Worktree]

    @property
    def current_worktree(self) -> Worktree:
        current = self.current_root.resolve()
        for worktree in self.worktrees:
            if worktree.path.resolve() == current:
                return worktree
        return Worktree(path=current)

    @property
    def main_worktree(self) -> Worktree:
        return self.worktrees[0]

    @property
    def in_linked_worktree(self) -> bool:
        return self.current_root.resolve() != self.main_root.resolve()


def run_command(
    args: list[str],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    input_text: str | None = None,
) -> CommandResult:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    completed = subprocess.run(
        args,
        cwd=str(cwd) if cwd is not None else None,
        env=merged_env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    result = CommandResult(
        args=args,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and result.returncode != 0:
        command = " ".join(args)
        raise WTError(
            f"command failed: {command}",
            details=(result.stderr or result.stdout).strip() or None,
        )
    return result


def run_git(
    args: list[str],
    *,
    cwd: Path | str | None = None,
    check: bool = True,
    input_text: str | None = None,
) -> CommandResult:
    return run_command(["git", *args], cwd=cwd, check=check, input_text=input_text)


def require_repo(cwd: Path | str | None = None) -> RepoContext:
    root_result = run_git(["rev-parse", "--show-toplevel"], cwd=cwd, check=False)
    if root_result.returncode != 0:
        raise UsageError(
            "not inside a git repository",
            hint="run wt inside a git repository",
            details=root_result.stderr.strip() or None,
        )

    current_root = Path(root_result.stdout.strip()).resolve()
    worktrees = list_worktrees(current_root)
    if not worktrees:
        raise WTError("git did not return any worktrees")

    return RepoContext(
        current_root=current_root,
        main_root=worktrees[0].path.resolve(),
        worktrees=worktrees,
    )


def try_repo(cwd: Path | str | None = None) -> RepoContext | None:
    try:
        return require_repo(cwd)
    except UsageError:
        return None


def list_worktrees(cwd: Path | str | None = None) -> list[Worktree]:
    result = run_git(["worktree", "list", "--porcelain"], cwd=cwd)
    return parse_worktree_porcelain(result.stdout)


def parse_worktree_porcelain(output: str) -> list[Worktree]:
    worktrees: list[Worktree] = []
    current: dict[str, object] = {}

    def flush() -> None:
        nonlocal current
        if "path" not in current:
            current = {}
            return
        worktrees.append(
            Worktree(
                path=Path(str(current["path"])).resolve(),
                head=current.get("head") if isinstance(current.get("head"), str) else None,
                branch=current.get("branch") if isinstance(current.get("branch"), str) else None,
                detached=bool(current.get("detached", False)),
                bare=bool(current.get("bare", False)),
            )
        )
        current = {}

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line.startswith("worktree "):
            if current:
                flush()
            current["path"] = line.removeprefix("worktree ")
        elif line.startswith("HEAD "):
            current["head"] = line.removeprefix("HEAD ")
        elif line.startswith("branch "):
            branch_ref = line.removeprefix("branch ")
            current["branch"] = branch_ref.removeprefix("refs/heads/")
        elif line == "detached":
            current["detached"] = True
        elif line == "bare":
            current["bare"] = True
    if current:
        flush()
    return worktrees


def branch_exists(branch: str, cwd: Path | str) -> bool:
    result = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=cwd, check=False)
    return result.returncode == 0


def ref_exists(ref: str, cwd: Path | str) -> bool:
    result = run_git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=cwd, check=False)
    return result.returncode == 0


def infer_default_base(cwd: Path | str) -> str:
    for candidate in ("origin/main", "origin/master", "main", "master", "HEAD"):
        if ref_exists(candidate, cwd):
            return candidate
    raise UsageError("could not infer a base ref", hint="pass --base <ref>")


def remotes(cwd: Path | str) -> list[str]:
    result = run_git(["remote"], cwd=cwd, check=False)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def remote_for_base(base: str, cwd: Path | str) -> str | None:
    if "/" not in base:
        return None
    candidate = base.split("/", 1)[0]
    return candidate if candidate in remotes(cwd) else None


def status_porcelain(cwd: Path | str) -> str:
    return run_git(["status", "--porcelain"], cwd=cwd).stdout


def is_dirty(cwd: Path | str) -> bool:
    return bool(status_porcelain(cwd).strip())


def current_branch(cwd: Path | str) -> str | None:
    result = run_git(["branch", "--show-current"], cwd=cwd, check=False)
    branch = result.stdout.strip()
    return branch or None


def common_dir(cwd: Path | str) -> Path:
    result = run_git(["rev-parse", "--git-common-dir"], cwd=cwd)
    path = Path(result.stdout.strip())
    if not path.is_absolute():
        path = Path(cwd) / path
    return path.resolve()


def add_worktree(branch: str, path: Path, base: str, cwd: Path | str) -> None:
    run_git(["worktree", "add", "-b", branch, str(path), base], cwd=cwd)


def remove_worktree(path: Path, cwd: Path | str, *, force: bool = False) -> None:
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(path))
    run_git(args, cwd=cwd)


def delete_branch(branch: str, cwd: Path | str, *, force: bool = True) -> None:
    flag = "-D" if force else "-d"
    run_git(["branch", flag, branch], cwd=cwd)


def ignored_files(cwd: Path | str) -> list[Path]:
    result = run_git(["ls-files", "--others", "-i", "--exclude-standard"], cwd=cwd)
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def untracked_files(cwd: Path | str) -> list[Path]:
    result = run_git(["ls-files", "--others", "--exclude-standard"], cwd=cwd)
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def files_matching_exclude_patterns(cwd: Path | str, patterns: Iterable[str]) -> list[Path]:
    exclude_args = [f"--exclude={pattern}" for pattern in patterns]
    if not exclude_args:
        return []
    result = run_git(["ls-files", "--others", "--ignored", *exclude_args], cwd=cwd)
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]
