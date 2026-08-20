from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from conftest import init_repo, run_git, run_wt
from workthreads import cli, output


def test_status_is_noop_without_rich(monkeypatch) -> None:
    monkeypatch.setattr(output, "Console", None)

    with output.status("creating worktree"):
        pass


def test_status_is_noop_when_stderr_is_not_terminal(monkeypatch) -> None:
    class FakeConsole:
        is_terminal = False

        def __init__(self, *, stderr: bool = False) -> None:
            self.stderr = stderr

        def status(self, text: str, *, spinner: str = "dots"):
            raise AssertionError("status should not be created for non-TTY output")

    monkeypatch.setattr(output, "Console", FakeConsole)

    with output.status("creating worktree"):
        pass


def test_status_uses_rich_status_on_interactive_stderr(monkeypatch) -> None:
    events: list[tuple[str, object, object]] = []

    class FakeStatus:
        def __enter__(self) -> None:
            events.append(("enter", None, None))

        def __exit__(self, exc_type, exc, traceback) -> None:
            events.append(("exit", None, None))

    class FakeConsole:
        is_terminal = True

        def __init__(self, *, stderr: bool = False) -> None:
            events.append(("console", stderr, None))

        def status(self, text: str, *, spinner: str = "dots") -> FakeStatus:
            events.append(("status", text, spinner))
            return FakeStatus()

    monkeypatch.setattr(output, "Console", FakeConsole)

    with output.status("creating worktree"):
        events.append(("body", None, None))

    assert events == [
        ("console", True, None),
        ("status", "creating worktree", "dots"),
        ("enter", None, None),
        ("body", None, None),
        ("exit", None, None),
    ]


def test_warning_is_highlighted_on_interactive_stderr(monkeypatch) -> None:
    events: list[tuple[object, ...]] = []

    class FakeConsole:
        is_terminal = True

        def __init__(self, *, stderr: bool = False) -> None:
            events.append(("console", stderr))

        def print(self, text: str, *, style: str, highlight: bool) -> None:
            events.append(("print", text, style, highlight))

    monkeypatch.setattr(output, "Console", FakeConsole)

    output.print_warning("regular copy is slower")

    assert events == [
        ("console", True),
        ("print", "warning: regular copy is slower", "bold yellow", False),
    ]


def test_add_warns_once_when_cow_falls_back(
    tmp_path: Path,
    monkeypatch,
    wt_env: dict[str, str],
    capsys,
) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text("*.local\n", encoding="utf-8")
    run_git(["add", ".gitignore"], cwd=repo)
    run_git(["commit", "-m", "ignore local files"], cwd=repo)
    (repo / "first.local").write_text("first\n", encoding="utf-8")
    (repo / "second.local").write_text("second\n", encoding="utf-8")

    monkeypatch.setattr(cli.copy_module, "try_clone_file", lambda _source, _destination: False)
    monkeypatch.setattr(output, "Console", None)
    for key, value in wt_env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(repo)

    destination = tmp_path / "threads" / "feature-fallback"
    args = cli.build_parser().parse_args(
        [
            "add",
            "feature/fallback",
            "--base",
            "HEAD",
            "--path",
            str(destination),
            "--copy-local",
        ]
    )

    assert cli.handle_add(args) == 0
    captured = capsys.readouterr()

    assert captured.err == (
        "warning: COW clone unavailable; using regular file copying, "
        "which is slower and may use additional disk space.\n"
    )
    assert (destination / "first.local").read_text(encoding="utf-8") == "first\n"
    assert (destination / "second.local").read_text(encoding="utf-8") == "second\n"


def test_add_spinner_phases_are_requested(
    tmp_path: Path,
    monkeypatch,
    wt_env: dict[str, str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".env.local\n", encoding="utf-8")
    run_git(["add", ".gitignore"], cwd=repo)
    run_git(["commit", "-m", "ignore local env"], cwd=repo)
    (repo / ".env.local").write_text("TOKEN=local\n", encoding="utf-8")
    (repo / "notes.txt").write_text("scratch\n", encoding="utf-8")

    hook = tmp_path / "post-create.sh"
    hook.write_text(
        "#!/bin/sh\n"
        "printf '%s' \"$WT_EVENT\" > \"$WT_WORKTREE_PATH/hook-event.txt\"\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)

    messages: list[str] = []

    @contextmanager
    def record_status(text: str, *, spinner: str = "dots", stderr: bool = True) -> Iterator[None]:
        messages.append(text)
        yield

    monkeypatch.setattr(cli.output, "status", record_status)
    for key, value in wt_env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(repo)

    destination = tmp_path / "threads" / "feature-status"
    args = argparse.Namespace(
        branch="feature/status",
        path=str(destination),
        worktrees_dir=None,
        base="HEAD",
        fetch=False,
        copy_local=True,
        copy_ignored=False,
        copy_untracked=False,
        overwrite=False,
        skip_hooks=False,
        cleanup_on_failure=False,
        post_create=str(hook),
        cd=False,
    )

    assert cli.handle_add(args) == 0
    assert messages == ["creating worktree", "copying local files", "running post-create hook"]
    assert (destination / ".env.local").exists()
    assert (destination / "notes.txt").exists()
    assert (destination / "hook-event.txt").read_text(encoding="utf-8") == "post-create"


def test_delete_spinner_phases_are_requested(
    tmp_path: Path,
    monkeypatch,
    wt_env: dict[str, str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    destination = tmp_path / "threads" / "feature-delete"
    run_git(["worktree", "add", "-b", "feature/delete", str(destination), "HEAD"], cwd=repo)

    hook = tmp_path / "pre-delete.sh"
    marker = tmp_path / "pre-delete-ran"
    hook.write_text(
        "#!/bin/sh\n"
        f"printf '%s' \"$WT_EVENT\" > {marker}\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)

    messages: list[str] = []

    @contextmanager
    def record_status(text: str, *, spinner: str = "dots", stderr: bool = True) -> Iterator[None]:
        messages.append(text)
        yield

    monkeypatch.setattr(cli.output, "status", record_status)
    for key, value in wt_env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(repo)

    args = argparse.Namespace(
        target="feature/delete",
        force=True,
        delete_branch=True,
        pre_delete=str(hook),
        skip_hooks=False,
    )

    assert cli.handle_delete(args) == 0
    assert messages == ["running pre-delete hook", "removing worktree"]
    assert marker.read_text(encoding="utf-8") == "pre-delete"
    assert not destination.exists()


def test_add_spinner_does_not_affect_captured_stdout_or_stderr(
    tmp_path: Path,
    wt_env: dict[str, str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    destination = tmp_path / "threads" / "feature-captured"

    result = run_wt(["add", "feature/captured", "--base", "HEAD", "--path", str(destination)], cwd=repo, env=wt_env)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout.splitlines()[-1] == str(destination)
