from __future__ import annotations

import argparse
import errno
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import config as config_module
from . import copy as copy_module
from . import git
from . import hooks
from . import metadata
from . import output
from . import paths
from .errors import ExitCode, SafetyError, UsageError, WTError
from .shell import completion_script, init_script


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    try:
        exit_code = run(args)
    except WTError as error:
        output.print_error(error)
        raise SystemExit(int(error.exit_code)) from error
    except KeyboardInterrupt as error:
        output.print_line("error: interrupted", stderr=True)
        raise SystemExit(int(ExitCode.RUNTIME)) from error
    raise SystemExit(exit_code)


def run(argv: list[str]) -> int:
    if not argv:
        handle_home()
        return int(ExitCode.SUCCESS)

    parser = build_parser()
    namespace = parser.parse_args(argv)
    command = namespace.command

    if command in {"add", "new", "create"}:
        return handle_add(namespace)
    if command in {"delete", "rm"}:
        return handle_delete(namespace)
    if command in {"list", "ls"}:
        return handle_list(namespace)
    if command == "config":
        return handle_config(namespace)
    if command == "hooks":
        return handle_hooks(namespace)
    if command == "completion":
        output.print_line(completion_script(namespace.shell))
        return int(ExitCode.SUCCESS)
    if command == "init":
        output.print_line(init_script(namespace.shell))
        return int(ExitCode.SUCCESS)
    if command == "root":
        return handle_root(namespace)
    if command == "current":
        return handle_current(namespace)

    raise UsageError(f"unknown command: {command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wt", description="Developer-first git worktree workflow CLI")
    parser.add_argument("--version", action="version", version=f"wt {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", aliases=["new", "create"], help="create a linked worktree")
    add_parser.add_argument("branch")
    destination = add_parser.add_mutually_exclusive_group()
    destination.add_argument("--path")
    destination.add_argument("--worktrees-dir")
    add_parser.add_argument("--base")
    fetch = add_parser.add_mutually_exclusive_group()
    fetch.add_argument("--fetch", action="store_true", default=None)
    fetch.add_argument("--no-fetch", action="store_false", dest="fetch")
    add_parser.add_argument("--copy-local", action="store_true")
    add_parser.add_argument("--copy-ignored", action="store_true")
    add_parser.add_argument("--copy-untracked", action="store_true")
    add_parser.add_argument("--overwrite", action="store_true")
    add_parser.add_argument("--skip-hooks", action="store_true")
    add_parser.add_argument("--cleanup-on-failure", action="store_true")
    add_parser.add_argument("--post-create")
    cd_group = add_parser.add_mutually_exclusive_group()
    cd_group.add_argument("--cd", action="store_true", dest="cd", default=None)
    cd_group.add_argument("--no-cd", action="store_false", dest="cd")
    add_parser.add_argument("--json", action="store_true")

    delete_parser = subparsers.add_parser("delete", aliases=["rm"], help="delete a linked worktree")
    delete_parser.add_argument("target", nargs="?")
    delete_parser.add_argument("--force", action="store_true")
    branch_group = delete_parser.add_mutually_exclusive_group()
    branch_group.add_argument("--delete-branch", action="store_true", default=None)
    branch_group.add_argument("--keep-branch", action="store_false", dest="delete_branch")
    delete_parser.add_argument("--pre-delete")
    delete_parser.add_argument("--skip-hooks", action="store_true")
    delete_parser.add_argument("--json", action="store_true")

    list_parser = subparsers.add_parser("list", aliases=["ls"], help="list worktrees")
    list_parser.add_argument("--json", action="store_true")

    config_parser = subparsers.add_parser("config", help="read and write configuration")
    config_subparsers = config_parser.add_subparsers(dest="config_action", required=True)
    config_get = config_subparsers.add_parser("get")
    config_get.add_argument("key")
    config_set = config_subparsers.add_parser("set")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_subparsers.add_parser("list")
    config_unset = config_subparsers.add_parser("unset")
    config_unset.add_argument("key")

    hooks_parser = subparsers.add_parser("hooks", help="manage repo-local wt hook scripts")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_action", required=True)
    hooks_subparsers.add_parser("dir", help="print the repo-local hook directory")
    hooks_subparsers.add_parser("init", help="create local hook templates and configure them")
    hooks_path = hooks_subparsers.add_parser("path", help="print a local hook script path")
    hooks_path.add_argument("hook", choices=["post-create", "pre-delete"])
    hooks_edit = hooks_subparsers.add_parser("edit", help="open a local hook script in $EDITOR")
    hooks_edit.add_argument("hook", choices=["post-create", "pre-delete"])

    completion_parser = subparsers.add_parser("completion", help="print shell completion")
    completion_parser.add_argument("shell", choices=["bash", "zsh", "fish"])

    init_parser = subparsers.add_parser("init", help="print full shell integration")
    init_parser.add_argument("shell", choices=["bash", "zsh", "fish"])

    root_parser = subparsers.add_parser("root", help="print the main worktree root")
    root_parser.add_argument("--json", action="store_true")

    current_parser = subparsers.add_parser("current", help="print the current worktree name")
    current_parser.add_argument("--json", action="store_true")

    return parser


def handle_home() -> None:
    repo = git.try_repo(Path.cwd())
    if repo is None:
        output.print_home(None, None, None)
        return
    config = config_module.load_config(repo.main_root)
    current = repo.current_worktree.branch or repo.current_worktree.name
    output.print_home(repo.main_root, current, default_path_pattern(config))


def default_path_pattern(config: config_module.Config) -> str | None:
    worktrees_dir = config.get_str("defaults.worktreesDir")
    if not worktrees_dir:
        return None
    return str(Path(worktrees_dir) / "<branch-path>")


def handle_add(args: argparse.Namespace) -> int:
    if args.cd and args.json:
        raise UsageError("--cd and --json are mutually exclusive")

    repo = git.require_repo(Path.cwd())
    config = config_module.load_config(repo.main_root)

    shell_integration = os.environ.get("WT_SHELL_INTEGRATION") == "1"
    config_cd = config.get_bool("shell.cdAfterAdd") if shell_integration and not args.json else False
    cd_requested = args.cd is True or (args.cd is None and config_cd)
    if args.cd is True and not shell_integration:
        raise UsageError(
            "--cd requires shell integration",
            hint='run `eval "$(wt init zsh)"` or use `cd "$(wt add <branch> | tail -n 1)"`',
        )

    existing = find_worktree_by_branch(repo.worktrees, args.branch)
    if existing:
        print_add_result(
            branch=args.branch,
            base=None,
            path=existing.path,
            copied=copy_module.CopyCounts(),
            hook_result=hooks.HookResult(command=None, exit_code=None, skipped=True),
            json_output=args.json,
            existing=True,
            cd_requested=cd_requested,
        )
        return int(ExitCode.SUCCESS)

    if git.branch_exists(args.branch, repo.main_root):
        raise UsageError(
            f"branch already exists: {args.branch}",
            hint="choose a new branch name or delete/reuse the existing branch with git directly",
        )

    base = args.base or config.get_str("defaults.base") or git.infer_default_base(repo.main_root)
    fetch = args.fetch if args.fetch is not None else config.get_bool("defaults.fetch")
    if fetch:
        remote = git.remote_for_base(base, repo.main_root)
        if remote:
            git.run_git(["fetch", remote], cwd=repo.main_root)

    if not git.ref_exists(base, repo.main_root):
        raise UsageError(f"base ref does not exist: {base}", hint="pass --base <ref> or run git fetch")

    worktrees_dir = args.worktrees_dir
    if not worktrees_dir and not args.path:
        worktrees_dir = config.get_str("defaults.worktreesDir")
    destination = paths.resolve_destination(
        repo_root=repo.main_root,
        branch=args.branch,
        path=args.path,
        worktrees_dir=worktrees_dir,
    )
    if destination.exists():
        raise UsageError(
            f"destination already exists: {destination}",
            hint="choose a different --path or remove the existing directory",
        )
    destination.parent.mkdir(parents=True, exist_ok=True)

    copy_local = args.copy_local or config.get_bool("defaults.copyLocal")
    copy_ignored = args.copy_ignored or copy_local
    copy_untracked = args.copy_untracked or copy_local

    selection = copy_module.select_local_files(
        repo.current_root,
        copy_ignored=copy_ignored,
        copy_untracked=copy_untracked,
    )

    created = False
    branch_created = False
    try:
        git.add_worktree(args.branch, destination, base, repo.main_root)
        created = True
        branch_created = True

        copied = copy_module.copy_selected_files(
            repo.current_root,
            destination,
            selection,
            overwrite=args.overwrite,
        )

        hook_result = hooks.HookResult(command=None, exit_code=None, skipped=True)
        if not args.skip_hooks:
            hook_command = args.post_create or config.get_str("hooks.postCreate")
            hook_result = hooks.run_hook(
                hook_command,
                event="post-create",
                cwd=destination,
                env=hooks.hook_env(
                    event="post-create",
                    repo_root=repo.main_root,
                    worktree_path=destination,
                    worktree_name=destination.name,
                    branch=args.branch,
                    base=base,
                    copy_local=copy_local,
                    copy_ignored=copy_ignored,
                    copy_untracked=copy_untracked,
                    dirty=False,
                ),
                shell=config.get_str("hooks.shell"),
                timeout_seconds=config.get_int("hooks.timeoutSeconds"),
            )

        metadata.save_metadata(
            repo.main_root,
            metadata.WorktreeMetadata(path=str(destination), branch=args.branch, base=base),
        )
    except WTError as original_error:
        if args.cleanup_on_failure:
            try:
                cleanup_failed_add(repo.main_root, destination, args.branch, created, branch_created)
            except WTError as cleanup_error:
                original_error.details = append_details(
                    original_error.details,
                    f"cleanup also failed: {cleanup_error.message}",
                    cleanup_error.details,
                )
        raise

    print_add_result(
        branch=args.branch,
        base=base,
        path=destination,
        copied=copied,
        hook_result=hook_result,
        json_output=args.json,
        existing=False,
        cd_requested=cd_requested,
    )
    return int(ExitCode.SUCCESS)


def cleanup_failed_add(repo_root: Path, destination: Path, branch: str, created: bool, branch_created: bool) -> None:
    if created:
        git.remove_worktree(destination, repo_root, force=True)
    if branch_created and git.branch_exists(branch, repo_root):
        git.delete_branch(branch, repo_root, force=True)
    if destination.exists():
        try:
            shutil.rmtree(destination)
        except OSError as error:
            raise WTError(f"failed to remove partial worktree directory: {destination}", details=str(error)) from error


def append_details(*parts: str | None) -> str:
    return "\n".join(part for part in parts if part)


def print_add_result(
    *,
    branch: str,
    base: str | None,
    path: Path,
    copied: copy_module.CopyCounts,
    hook_result: hooks.HookResult,
    json_output: bool,
    existing: bool,
    cd_requested: bool,
) -> None:
    if json_output:
        output.print_json(
            {
                "branch": branch,
                "base": base,
                "worktreePath": str(path),
                "copied": {"ignored": copied.ignored, "untracked": copied.untracked},
                "hooks": {
                    "postCreate": {
                        "command": hook_result.command,
                        "exitCode": hook_result.exit_code,
                        "skipped": hook_result.skipped,
                    }
                },
                "existing": existing,
                "cdRequested": cd_requested,
            }
        )
        return

    if existing:
        output.print_line(f"existing worktree {branch}")
    else:
        output.print_line(f"created worktree {branch} from {base}")
    output.print_line(f"path: {path}")
    output.print_line(f"copied: ignored={copied.ignored} untracked={copied.untracked}")
    if hook_result.skipped:
        output.print_line("hook post-create: skipped")
    else:
        output.print_line("hook post-create: ok")
    output.print_line(str(path))


def handle_delete(args: argparse.Namespace) -> int:
    repo = git.require_repo(Path.cwd())
    config = config_module.load_config(repo.main_root)
    target = resolve_delete_target(repo, args.target)

    if target.path.resolve() == repo.main_root.resolve():
        raise SafetyError("refusing to delete the main worktree")

    dirty = git.is_dirty(target.path)
    force_remove = args.force
    if dirty and not args.force:
        if sys.stdin.isatty() and not args.json:
            answer = input(f"worktree {target.path} has local changes; delete it? [y/N] ")
            if answer.lower() not in {"y", "yes"}:
                raise SafetyError("delete cancelled")
            force_remove = True
        else:
            raise SafetyError(
                f"worktree is dirty: {target.path}",
                hint="commit/stash changes or rerun with --force",
            )

    hook_result = hooks.HookResult(command=None, exit_code=None, skipped=True)
    if not args.skip_hooks:
        hook_command = args.pre_delete or config.get_str("hooks.preDelete")
        hook_result = hooks.run_hook(
            hook_command,
            event="pre-delete",
            cwd=target.path,
            env=hooks.hook_env(
                event="pre-delete",
                repo_root=repo.main_root,
                worktree_path=target.path,
                worktree_name=target.name,
                branch=target.branch,
                base=None,
                dirty=dirty,
            ),
            shell=config.get_str("hooks.shell"),
            timeout_seconds=config.get_int("hooks.timeoutSeconds"),
        )

    git.remove_worktree(target.path, repo.main_root, force=force_remove)
    cleanup_empty_worktree_parents(target.path, worktrees_root(repo.main_root, config))
    delete_branch = args.delete_branch if args.delete_branch is not None else config.get_bool("defaults.deleteBranch")
    branch_state = "kept"
    if delete_branch and target.branch:
        git.delete_branch(target.branch, repo.main_root, force=True)
        branch_state = "deleted"

    metadata.remove_metadata(repo.main_root, target.path)

    if args.json:
        output.print_json(
            {
                "branch": target.branch,
                "path": str(target.path),
                "branchState": branch_state,
                "hooks": {
                    "preDelete": {
                        "command": hook_result.command,
                        "exitCode": hook_result.exit_code,
                        "skipped": hook_result.skipped,
                    }
                },
            }
        )
    else:
        output.print_line(f"deleted worktree {target.branch or target.name}")
        output.print_line(f"path: {target.path}")
        output.print_line(f"branch: {branch_state}")
    return int(ExitCode.SUCCESS)


def worktrees_root(repo_root: Path, config: config_module.Config) -> Path | None:
    worktrees_dir = config.get_str("defaults.worktreesDir")
    if not worktrees_dir:
        return None
    root = Path(worktrees_dir).expanduser()
    if not root.is_absolute():
        root = repo_root / root
    return root.resolve()


def cleanup_empty_worktree_parents(target_path: Path, root: Path | None) -> None:
    if root is None:
        return

    current = target_path.resolve().parent
    if not current.is_relative_to(root):
        return

    while current != root:
        try:
            current.rmdir()
        except OSError as error:
            if error.errno in {errno.ENOENT, errno.ENOTEMPTY, errno.EEXIST}:
                return
            raise
        current = current.parent


def resolve_delete_target(repo: git.RepoContext, target: str | None) -> git.Worktree:
    if target:
        matched = match_worktree(repo.worktrees, target, cwd=Path.cwd())
        if matched:
            return matched
        raise UsageError(f"unknown worktree: {target}", hint="run wt list to see available worktrees")

    if repo.in_linked_worktree:
        return repo.current_worktree

    raise UsageError(
        "current directory is the main worktree",
        hint="run `wt delete <branch-or-path>` from the main worktree, or cd into a linked worktree and run `wt delete`",
    )


def match_worktree(worktrees: list[git.Worktree], target: str, *, cwd: Path) -> git.Worktree | None:
    target_path = Path(target).expanduser()
    path_candidates: set[Path] = set()
    if target_path.is_absolute():
        path_candidates.add(target_path.resolve())
    if "/" in target or target.startswith("."):
        path_candidates.add((cwd / target_path).resolve())

    for worktree in worktrees:
        if worktree.path.resolve() in path_candidates:
            return worktree
        if worktree.branch == target:
            return worktree
        if worktree.name == target:
            return worktree
        if worktree.path.name == target:
            return worktree
    return None


def find_worktree_by_branch(worktrees: list[git.Worktree], branch: str) -> git.Worktree | None:
    for worktree in worktrees:
        if worktree.branch == branch:
            return worktree
    return None


def handle_list(args: argparse.Namespace) -> int:
    repo = git.require_repo(Path.cwd())
    meta = metadata.metadata_by_path(repo.main_root)
    rows: list[dict[str, Any]] = []
    for worktree in repo.worktrees:
        entry = meta.get(str(worktree.path))
        rows.append(
            {
                "branch": worktree.branch,
                "path": str(worktree.path),
                "head": worktree.head,
                "base": entry.base if entry else None,
                "isMain": worktree.path.resolve() == repo.main_root.resolve(),
                "dirty": git.is_dirty(worktree.path),
            }
        )

    if args.json:
        output.print_json(rows)
    else:
        print_worktree_table(rows)
    return int(ExitCode.SUCCESS)


def print_worktree_table(rows: list[dict[str, Any]]) -> None:
    output.print_line(f"{'BRANCH':<28} {'PATH':<40} {'BASE':<20} DIRTY")
    for row in rows:
        branch = row["branch"] or "(detached)"
        path = row["path"]
        base = row["base"] or "-"
        dirty = "yes" if row["dirty"] else "no"
        output.print_line(f"{branch:<28} {path:<40} {base:<20} {dirty}")


def handle_config(args: argparse.Namespace) -> int:
    repo = git.try_repo(Path.cwd())
    repo_root = repo.main_root if repo else None
    config = config_module.load_config(repo_root)

    if args.config_action == "get":
        try:
            value = config_module.get_nested(config.values, args.key)
        except KeyError:
            raise UsageError(f"unknown config key: {args.key}")
        output.print_line(format_config_value(value))
        return int(ExitCode.SUCCESS)

    path = config_module.writable_config_path(repo_root)
    persisted = config_module.read_toml(path) if path.exists() else {}

    if args.config_action == "set":
        config_module.set_nested(persisted, args.key, config_module.parse_config_value(args.value))
        config_module.write_config_file(path, persisted)
        return int(ExitCode.SUCCESS)

    if args.config_action == "unset":
        config_module.unset_nested(persisted, args.key)
        config_module.write_config_file(path, persisted)
        return int(ExitCode.SUCCESS)

    if args.config_action == "list":
        for key, value in flatten_config(config.values):
            output.print_line(f"{key}={format_config_value(value)}")
        return int(ExitCode.SUCCESS)

    raise UsageError(f"unknown config action: {args.config_action}")


HOOK_FILENAMES = {
    "post-create": "post-create.sh",
    "pre-delete": "pre-delete.sh",
}


HOOK_CONFIG_KEYS = {
    "post-create": "hooks.postCreate",
    "pre-delete": "hooks.preDelete",
}


def handle_hooks(args: argparse.Namespace) -> int:
    repo = git.require_repo(Path.cwd())
    hook_dir = repo_hook_dir(repo)

    if args.hooks_action == "dir":
        output.print_line(str(hook_dir))
        return int(ExitCode.SUCCESS)

    if args.hooks_action == "path":
        output.print_line(str(hook_path(repo, args.hook)))
        return int(ExitCode.SUCCESS)

    if args.hooks_action == "init":
        created = init_hook_templates(repo)
        configure_hook_paths(repo)
        output.print_line(f"hook dir: {hook_dir}")
        for hook_name, path in created.items():
            output.print_line(f"{hook_name}: {path}")
        output.print_line(f"configured: {config_module.repo_config_path(repo.main_root)}")
        return int(ExitCode.SUCCESS)

    if args.hooks_action == "edit":
        path = ensure_hook_template(repo, args.hook)
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if not editor:
            output.print_line(str(path))
            return int(ExitCode.SUCCESS)
        result = subprocess.run([*shlex.split(editor), str(path)], check=False)
        return int(result.returncode)

    raise UsageError(f"unknown hooks action: {args.hooks_action}")


def repo_hook_dir(repo: git.RepoContext) -> Path:
    return git.common_dir(repo.main_root) / "workthreads" / "hooks"


def hook_path(repo: git.RepoContext, hook_name: str) -> Path:
    try:
        filename = HOOK_FILENAMES[hook_name]
    except KeyError as error:
        raise UsageError(f"unknown hook: {hook_name}") from error
    return repo_hook_dir(repo) / filename


def init_hook_templates(repo: git.RepoContext) -> dict[str, Path]:
    return {hook_name: ensure_hook_template(repo, hook_name) for hook_name in HOOK_FILENAMES}


def ensure_hook_template(repo: git.RepoContext, hook_name: str) -> Path:
    path = hook_path(repo, hook_name)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(hook_template(hook_name), encoding="utf-8")
        path.chmod(0o755)
    return path


def hook_template(hook_name: str) -> str:
    if hook_name == "post-create":
        return """#!/bin/sh
set -eu

# Runs inside the newly created worktree.
# Use WT_WORKTREE_PATH, WT_REPO_ROOT, WT_BRANCH, and WT_BASE.
:
"""
    if hook_name == "pre-delete":
        return """#!/bin/sh
set -eu

# Runs inside the worktree before deletion.
# Example: copy local agent artifacts back to the main worktree.
# if [ -d "$WT_WORKTREE_PATH/.local" ]; then
#   mkdir -p "$WT_REPO_ROOT/.local"
#   rsync -a "$WT_WORKTREE_PATH/.local/" "$WT_REPO_ROOT/.local/"
# fi
:
"""
    raise UsageError(f"unknown hook: {hook_name}")


def configure_hook_paths(repo: git.RepoContext) -> None:
    path = config_module.writable_config_path(repo.main_root)
    persisted = config_module.read_toml(path) if path.exists() else {}
    for hook_name, key in HOOK_CONFIG_KEYS.items():
        config_module.set_nested(persisted, key, str(hook_path(repo, hook_name)))
    config_module.write_config_file(path, persisted)


def flatten_config(values: dict[str, object], prefix: str = "") -> list[tuple[str, object]]:
    rows: list[tuple[str, object]] = []
    for key, value in values.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            rows.extend(flatten_config(value, dotted))
        else:
            rows.append((dotted, value))
    return rows


def format_config_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def handle_root(args: argparse.Namespace) -> int:
    repo = git.require_repo(Path.cwd())
    if args.json:
        output.print_json({"root": str(repo.main_root)})
    else:
        output.print_line(str(repo.main_root))
    return int(ExitCode.SUCCESS)


def handle_current(args: argparse.Namespace) -> int:
    repo = git.require_repo(Path.cwd())
    current = repo.current_worktree.branch or repo.current_worktree.name
    if args.json:
        output.print_json(
            {
                "branch": repo.current_worktree.branch,
                "name": repo.current_worktree.name,
                "path": str(repo.current_worktree.path),
                "isMain": not repo.in_linked_worktree,
            }
        )
    else:
        output.print_line(current)
    return int(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
