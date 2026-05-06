from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess

from .errors import WTError


@dataclass(frozen=True)
class HookResult:
    command: str | None
    exit_code: int | None
    skipped: bool = False


def hook_env(
    *,
    event: str,
    repo_root: Path,
    worktree_path: Path,
    worktree_name: str,
    branch: str | None,
    base: str | None,
    copy_local: bool = False,
    copy_ignored: bool = False,
    copy_untracked: bool = False,
    dirty: bool = False,
) -> dict[str, str]:
    return {
        "WT_EVENT": event,
        "WT_REPO_ROOT": str(repo_root),
        "WT_WORKTREE_PATH": str(worktree_path),
        "WT_WORKTREE_NAME": worktree_name,
        "WT_BRANCH": branch or "",
        "WT_BASE": base or "",
        "WT_COPY_LOCAL": "1" if copy_local else "0",
        "WT_COPY_IGNORED": "1" if copy_ignored else "0",
        "WT_COPY_UNTRACKED": "1" if copy_untracked else "0",
        "WT_DIRTY": "1" if dirty else "0",
        "WT_CONFIG_FILE": str(repo_root / ".workthreads" / "config.toml"),
    }


def run_hook(
    command: str | None,
    *,
    event: str,
    cwd: Path,
    env: dict[str, str],
    shell: str | None = None,
    timeout_seconds: int = 0,
) -> HookResult:
    if not command:
        return HookResult(command=None, exit_code=None, skipped=True)

    merged_env = os.environ.copy()
    merged_env.update(env)
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=merged_env,
            shell=True,
            executable=shell or None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds or None,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise WTError(
            f"{event} hook timed out",
            hint="increase hooks.timeoutSeconds or fix the hook",
            details=str(error),
        ) from error
    if completed.returncode != 0:
        details = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
        raise WTError(
            f"{event} hook failed",
            hint="fix the hook or rerun with --skip-hooks",
            details=details or None,
        )
    return HookResult(command=command, exit_code=completed.returncode)
