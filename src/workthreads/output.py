from __future__ import annotations

from pathlib import Path
import sys

from .errors import WTError

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:  # pragma: no cover - fallback for minimal environments
    Console = None  # type: ignore[assignment]
    Table = None  # type: ignore[assignment]


def console(stderr: bool = False):
    if Console is None:
        return None
    return Console(stderr=stderr)


def print_line(text: str = "", *, stderr: bool = False) -> None:
    stream = sys.stderr if stderr else sys.stdout
    print(text, file=stream)


def print_error(error: WTError) -> None:
    print_line(f"error: {error.message}", stderr=True)
    if error.hint:
        print_line(f"hint: {error.hint}", stderr=True)
    if error.details:
        print_line(error.details, stderr=True)


def print_home(repo_root: Path | None, current: str | None, default_path: str | None) -> None:
    print_line("wt - git worktrees for parallel tasks")
    if repo_root is None:
        print_line("Run inside a git repository to manage worktrees.")
        print_line()
        print_line("Common commands:")
        print_line("  wt add <branch>")
        print_line("  wt list")
        print_line("  wt completion <shell>")
        return

    print_line(f"repo: {repo_root}")
    print_line(f"current: {current or 'unknown'}")
    if default_path:
        print_line(f"default path: {default_path}")
    print_line()
    print_line("Common commands:")
    print_line("  wt add <branch>       create a worktree")
    print_line("  wt delete [target]    delete current or named worktree")
    print_line("  wt list               list worktrees")
    print_line()
    print_line("Setup commands:")
    print_line("  wt config set <key> <value>  configure repo defaults")
    print_line("  wt hooks init                create local hook scripts")
    print_line("  wt init <shell>              enable shell integration")
