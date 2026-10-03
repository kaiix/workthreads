from __future__ import annotations

import argparse
from dataclasses import dataclass
import errno
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

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
    if argv[0] == "__complete":
        return handle_complete_args(argv[1:])

    parser = build_parser()
    namespace = parser.parse_args(argv)
    command = namespace.command

    if command in {"add", "new", "create"}:
        return handle_add(namespace)
    if command in {"delete", "rm"}:
        return handle_delete(namespace)
    if command in {"list", "ls"}:
        return handle_list(namespace)
    if command == "cd":
        return handle_cd(namespace)
    if command == "config":
        return handle_config(namespace)
    if command == "hooks":
        return handle_hooks(namespace)
    if command == "shell":
        return handle_shell(namespace)
    if command == "root":
        return handle_root(namespace)
    if command == "current":
        return handle_current(namespace)

    raise UsageError(f"unknown command: {command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wt", description="Developer-first git worktree workflow CLI")
    parser.add_argument("--version", action="version", version=f"wt {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser(
        "add",
        aliases=["new", "create"],
        help="create a linked worktree",
        description="Create a linked worktree and branch.",
    )
    add_parser.add_argument("branch", help="branch name for the new worktree")
    destination = add_parser.add_mutually_exclusive_group()
    destination.add_argument("--path", metavar="PATH", help="exact destination path for this worktree")
    destination.add_argument(
        "--worktrees-dir",
        metavar="DIR",
        help="parent directory for generated paths (config: defaults.worktreesDir)",
    )
    add_parser.add_argument("--base", metavar="REF", help="ref used to create the branch (config: defaults.base)")
    fetch = add_parser.add_mutually_exclusive_group()
    fetch.add_argument(
        "--fetch",
        action="store_true",
        default=None,
        help="fetch the base remote before creation (config: defaults.fetch)",
    )
    fetch.add_argument(
        "--no-fetch",
        action="store_false",
        dest="fetch",
        help="do not fetch even when defaults.fetch is true",
    )
    add_parser.add_argument(
        "--copy-local",
        action="store_true",
        help="copy both ignored and untracked local files (config: defaults.copyLocal)",
    )
    add_parser.add_argument("--copy-ignored", action="store_true", help="copy ignored files only")
    add_parser.add_argument("--copy-untracked", action="store_true", help="copy untracked files only")
    add_parser.add_argument("--overwrite", action="store_true", help="replace copied local files if they exist")
    add_parser.add_argument("--skip-hooks", action="store_true", help="do not run lifecycle hooks")
    add_parser.add_argument(
        "--cleanup-on-failure",
        action="store_true",
        help="remove a partially created worktree if creation fails",
    )
    add_parser.add_argument("--post-create", metavar="CMD", help="one-off post-create hook command or script")
    cd_group = add_parser.add_mutually_exclusive_group()
    cd_group.add_argument(
        "--cd",
        action="store_true",
        dest="cd",
        default=None,
        help="enter the created worktree through shell integration",
    )
    cd_group.add_argument(
        "--no-cd",
        action="store_false",
        dest="cd",
        help="stay in place when shell.cdAfterAdd is true",
    )

    delete_parser = subparsers.add_parser("delete", aliases=["rm"], help="delete a linked worktree")
    delete_parser.add_argument("target", nargs="?")
    delete_parser.add_argument("--force", action="store_true")
    branch_group = delete_parser.add_mutually_exclusive_group()
    branch_group.add_argument("--delete-branch", action="store_true", default=None)
    branch_group.add_argument("--keep-branch", action="store_false", dest="delete_branch")
    delete_parser.add_argument("--pre-delete")
    delete_parser.add_argument("--skip-hooks", action="store_true")

    list_parser = subparsers.add_parser("list", aliases=["ls"], help="list worktrees")

    cd_parser = subparsers.add_parser("cd", help="print or enter a worktree")
    cd_parser.add_argument("target", nargs="?", help="branch, name, path, or unique prefix")

    config_parser = subparsers.add_parser("config", help="manage configuration files and values")
    config_subparsers = config_parser.add_subparsers(dest="config_action", required=True)
    config_get = config_subparsers.add_parser("get", help="print one resolved config value")
    config_get.add_argument("key")
    config_set = config_subparsers.add_parser("set", help="set one value in the writable config file")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_list = config_subparsers.add_parser("list", help="list resolved config values")
    config_list.add_argument("--plain", action="store_true", help="print key=value lines")
    config_init = config_subparsers.add_parser("init", help="create a commented config file")
    add_config_scope_flag(config_init)
    config_init.add_argument("--force", action="store_true", help="replace an existing config file")
    config_path = config_subparsers.add_parser("path", help="print the config file path")
    add_config_scope_flag(config_path)
    config_edit = config_subparsers.add_parser("edit", help="open the config file in $EDITOR")
    add_config_scope_flag(config_edit)
    config_unset = config_subparsers.add_parser("unset", help="remove one value from the writable config file")
    config_unset.add_argument("key")

    hooks_parser = subparsers.add_parser("hooks", help="manage repo-local wt hook scripts")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_action", required=True)
    hooks_subparsers.add_parser("dir", help="print the repo-local hook directory")
    hooks_subparsers.add_parser("init", help="create local hook templates and configure them")
    hooks_path = hooks_subparsers.add_parser("path", help="print a local hook script path")
    hooks_path.add_argument("hook", choices=["post-create", "pre-delete"])
    hooks_edit = hooks_subparsers.add_parser("edit", help="open a local hook script in $EDITOR")
    hooks_edit.add_argument("hook", choices=["post-create", "pre-delete"])

    shell_parser = subparsers.add_parser("shell", help="print shell setup scripts")
    shell_subparsers = shell_parser.add_subparsers(dest="shell_action", required=True)
    shell_init = shell_subparsers.add_parser("init", help="print full shell integration")
    shell_init.add_argument("shell", choices=["bash", "zsh", "fish"])
    shell_completion = shell_subparsers.add_parser("completion", help="print shell completion")
    shell_completion.add_argument("shell", choices=["bash", "zsh", "fish"])

    root_parser = subparsers.add_parser("root", help="print the main worktree root")

    current_parser = subparsers.add_parser("current", help="print the current worktree name")

    return parser


def add_config_scope_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--global",
        action="store_true",
        dest="use_global",
        help="use the global config file instead of repo wt.toml",
    )


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
    repo = git.require_repo(Path.cwd())
    config = config_module.load_config(repo.main_root)

    shell_integration = os.environ.get("WT_SHELL_INTEGRATION") == "1"
    config_cd = config.get_bool("shell.cdAfterAdd") if shell_integration else False
    cd_requested = args.cd is True or (args.cd is None and config_cd)
    if args.cd is True and not shell_integration:
        raise UsageError(
            "--cd requires shell integration",
            hint='run `eval "$(wt shell init zsh)"` or use `cd "$(wt add <branch> | tail -n 1)"`',
        )

    existing = find_worktree_by_branch(repo.worktrees, args.branch)
    if existing:
        if not git.is_worktree_available(existing):
            raise unavailable_worktree_error(existing)
        write_cd_target(existing.path, cd_requested)
        print_add_result(
            branch=args.branch,
            base=None,
            path=existing.path,
            copied=copy_module.CopyCounts(),
            hook_result=hooks.HookResult(command=None, exit_code=None, skipped=True),
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
            with output.status(f"fetching {remote}"):
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
        exclude_paths=local_copy_exclude_paths(repo, config),
        exclude_patterns=(
            config.get_str_list("defaults.copyExclude")
            if copy_ignored or copy_untracked
            else ()
        ),
    )

    created = False
    branch_created = False
    try:
        with output.status("creating worktree"):
            git.add_worktree(args.branch, destination, base, repo.main_root)
        created = True
        branch_created = True

        if selection.files:
            with output.status("copying local files"):
                copied = copy_module.copy_selected_files(
                    repo.current_root,
                    destination,
                    selection,
                    overwrite=args.overwrite,
                    on_clone_fallback=lambda: output.print_warning(
                        "COW clone unavailable; using regular file copying, "
                        "which is slower and may use additional disk space."
                    ),
                )
        else:
            copied = copy_module.CopyCounts()

        hook_result = hooks.HookResult(command=None, exit_code=None, skipped=True)
        if not args.skip_hooks:
            hook_command = args.post_create or config.get_str("hooks.postCreate")
            if hook_command:
                with output.status("running post-create hook"):
                    hook_result = run_post_create_hook(
                        hook_command,
                        repo=repo,
                        destination=destination,
                        branch=args.branch,
                        base=base,
                        copy_local=copy_local,
                        copy_ignored=copy_ignored,
                        copy_untracked=copy_untracked,
                        config=config,
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

    write_cd_target(destination, cd_requested)
    print_add_result(
        branch=args.branch,
        base=base,
        path=destination,
        copied=copied,
        hook_result=hook_result,
        existing=False,
        cd_requested=cd_requested,
    )
    return int(ExitCode.SUCCESS)


def run_post_create_hook(
    hook_command: str,
    *,
    repo: git.RepoContext,
    destination: Path,
    branch: str,
    base: str,
    copy_local: bool,
    copy_ignored: bool,
    copy_untracked: bool,
    config: config_module.Config,
) -> hooks.HookResult:
    return hooks.run_hook(
        hook_command,
        event="post-create",
        cwd=destination,
        env=hooks.hook_env(
            event="post-create",
            repo_root=repo.main_root,
            worktree_path=destination,
            worktree_name=destination.name,
            branch=branch,
            base=base,
            copy_local=copy_local,
            copy_ignored=copy_ignored,
            copy_untracked=copy_untracked,
            dirty=False,
        ),
        shell=config.get_str("hooks.shell"),
        timeout_seconds=config.get_int("hooks.timeoutSeconds"),
    )


def write_cd_target(path: Path, cd_requested: bool) -> bool:
    if not cd_requested:
        return False
    cd_file = os.environ.get("WT_CD_FILE")
    if not cd_file:
        return False
    try:
        Path(cd_file).write_text(str(path), encoding="utf-8")
    except OSError as error:
        raise WTError("failed to write shell cd target", details=str(error)) from error
    return True


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
    existing: bool,
    cd_requested: bool,
) -> None:
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
    if not git.is_worktree_available(target):
        raise unavailable_worktree_error(target)

    dirty = git.is_dirty(target.path)
    force_remove = args.force
    if dirty and not args.force:
        if sys.stdin.isatty():
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
        if hook_command:
            with output.status("running pre-delete hook"):
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

    with output.status("removing worktree"):
        git.remove_worktree(target.path, repo.main_root, force=force_remove)
    cleanup_empty_worktree_parents(target.path, worktrees_root(repo.main_root, config))
    delete_branch = args.delete_branch if args.delete_branch is not None else config.get_bool("defaults.deleteBranch")
    branch_state = "kept"
    if delete_branch and target.branch:
        git.delete_branch(target.branch, repo.main_root, force=True)
        branch_state = "deleted"

    metadata.remove_metadata(repo.main_root, target.path)
    deleting_current = target.path.resolve() == repo.current_root.resolve()
    write_cd_target(repo.main_root, deleting_current and os.environ.get("WT_SHELL_INTEGRATION") == "1")

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


def local_copy_exclude_paths(repo: git.RepoContext, config: config_module.Config) -> list[Path]:
    source_root = repo.current_root.resolve()
    exclude_paths: list[Path] = []

    configured_root = worktrees_root(repo.main_root, config)
    if configured_root is not None:
        append_relative_exclude_path(exclude_paths, configured_root, source_root)

    for worktree in repo.worktrees:
        append_relative_exclude_path(exclude_paths, worktree.path, source_root)

    return exclude_paths


def append_relative_exclude_path(exclude_paths: list[Path], path: Path, root: Path) -> None:
    try:
        relative_path = path.resolve().relative_to(root)
    except ValueError:
        return
    if not relative_path.parts or relative_path in exclude_paths:
        return
    exclude_paths.append(relative_path)


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


def unavailable_worktree_error(worktree: git.Worktree) -> WTError:
    details = f"path: {worktree.path}"
    if worktree.prunable_reason:
        details = append_details(details, f"reason: {worktree.prunable_reason}")
    hint = (
        "run `git worktree prune` to remove stale metadata"
        if worktree.is_prunable
        else "restore the path or inspect it with `git worktree list --porcelain`"
    )
    return WTError(
        f"worktree is unavailable: {worktree.branch or worktree.name}",
        hint=hint,
        details=details,
    )


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
                "status": worktree_status(worktree),
            }
        )

    print_worktree_table(rows)
    statuses = {row["status"] for row in rows}
    if "prunable" in statuses:
        output.print_warning("stale worktree metadata found; run `git worktree prune`")
    if "missing" in statuses:
        output.print_warning("one or more worktree paths are unavailable")
    return int(ExitCode.SUCCESS)


def worktree_status(worktree: git.Worktree) -> str:
    if worktree.is_prunable:
        return "prunable"
    if not git.is_worktree_available(worktree):
        return "missing"
    try:
        return "dirty" if git.is_dirty(worktree.path) else "clean"
    except WTError:
        if not git.is_worktree_available(worktree):
            return "missing"
        raise


def print_worktree_table(rows: list[dict[str, Any]]) -> None:
    output.print_line(f"{'BRANCH':<28} {'PATH':<40} {'BASE':<20} STATUS")
    for row in rows:
        branch = row["branch"] or "(detached)"
        path = row["path"]
        base = row["base"] or "-"
        status = row["status"]
        output.print_line(f"{branch:<28} {path:<40} {base:<20} {status}")


@dataclass(frozen=True)
class WorktreeCandidate:
    worktree: git.Worktree
    display: str
    aliases: tuple[str, ...]


def handle_cd(args: argparse.Namespace) -> int:
    repo = git.require_repo(Path.cwd())
    config = config_module.load_config(repo.main_root)
    candidates = worktree_candidates(repo, config)
    shell_integration = os.environ.get("WT_SHELL_INTEGRATION") == "1"

    candidate: WorktreeCandidate | None = None
    if args.target:
        try:
            candidate = resolve_cd_candidate(candidates, args.target, cwd=Path.cwd())
        except UsageError:
            if can_use_fzf():
                candidate = select_candidate_with_fzf(candidates, query=args.target)
                if candidate is None:
                    raise UsageError("no worktree selected")
            else:
                raise
    elif can_use_fzf():
        candidate = select_candidate_with_fzf(candidates, query=None)
        if candidate is None:
            raise UsageError("no worktree selected")
    else:
        raise UsageError(
            "missing worktree target",
            hint="pass a branch/name prefix or run wt list",
            details=format_candidate_details(candidates),
        )

    cd_written = write_cd_target(candidate.worktree.path, shell_integration)
    if not cd_written:
        output.print_line(str(candidate.worktree.path))
    return int(ExitCode.SUCCESS)


def handle_complete(args: argparse.Namespace) -> int:
    if args.complete_subject != "worktrees":
        raise UsageError(f"unknown completion subject: {args.complete_subject}")

    repo = git.try_repo(Path.cwd())
    if repo is None:
        return int(ExitCode.SUCCESS)

    config = config_module.load_config(repo.main_root)
    prefix = args.prefix or ""
    for candidate in completion_candidates(worktree_candidates(repo, config), prefix):
        output.print_line(candidate.display)
    return int(ExitCode.SUCCESS)


def handle_complete_args(argv: list[str]) -> int:
    if not argv:
        raise UsageError("missing completion subject")
    if len(argv) > 2:
        raise UsageError("too many completion arguments")
    return handle_complete(argparse.Namespace(complete_subject=argv[0], prefix=argv[1] if len(argv) == 2 else None))


def worktree_candidates(repo: git.RepoContext, config: config_module.Config) -> list[WorktreeCandidate]:
    root = worktrees_root(repo.main_root, config)
    return [
        worktree_candidate(worktree, repo.main_root, root)
        for worktree in repo.worktrees
        if git.is_worktree_available(worktree)
    ]


def worktree_candidate(worktree: git.Worktree, repo_root: Path, worktrees_dir: Path | None) -> WorktreeCandidate:
    display = worktree.branch or worktree.name
    aliases = [
        display,
        worktree.name,
        worktree.path.name,
        str(worktree.path),
    ]

    if worktree.path.is_relative_to(repo_root):
        relative_to_repo = worktree.path.relative_to(repo_root).as_posix()
        aliases.append(relative_to_repo)
    if worktrees_dir and worktree.path.is_relative_to(worktrees_dir):
        relative_to_worktrees = worktree.path.relative_to(worktrees_dir).as_posix()
        aliases.append(relative_to_worktrees)

    return WorktreeCandidate(worktree=worktree, display=display, aliases=tuple(unique_strings(aliases)))


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def resolve_cd_candidate(candidates: list[WorktreeCandidate], target: str, *, cwd: Path) -> WorktreeCandidate:
    exact_matches = exact_candidate_matches(candidates, target, cwd=cwd)
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise ambiguous_worktree_error(target, exact_matches)

    full_prefix_matches = unique_worktree_candidates(
        candidate for candidate in candidates if candidate_matches_full_prefix(candidate, target)
    )
    if len(full_prefix_matches) == 1:
        return full_prefix_matches[0]
    if len(full_prefix_matches) > 1:
        raise ambiguous_worktree_error(target, full_prefix_matches)

    segment_prefix_matches = unique_worktree_candidates(
        candidate for candidate in candidates if candidate_matches_segment_prefix(candidate, target)
    )
    if len(segment_prefix_matches) == 1:
        return segment_prefix_matches[0]
    if len(segment_prefix_matches) > 1:
        raise ambiguous_worktree_error(target, segment_prefix_matches)

    raise UsageError(f"unknown worktree: {target}", hint="run wt list to see available worktrees")


def exact_candidate_matches(candidates: list[WorktreeCandidate], target: str, *, cwd: Path) -> list[WorktreeCandidate]:
    path_candidates = target_path_candidates(target, cwd)
    matches: list[WorktreeCandidate] = []
    for candidate in candidates:
        if candidate.worktree.path.resolve() in path_candidates or target in candidate.aliases:
            matches.append(candidate)
    return unique_worktree_candidates(matches)


def target_path_candidates(target: str, cwd: Path) -> set[Path]:
    target_path = Path(target).expanduser()
    candidates: set[Path] = set()
    if target_path.is_absolute():
        candidates.add(target_path.resolve())
    if "/" in target or target.startswith("."):
        candidates.add((cwd / target_path).resolve())
    return candidates


def candidate_matches_full_prefix(candidate: WorktreeCandidate, target: str) -> bool:
    return any(alias.startswith(target) for alias in candidate.aliases)


def candidate_matches_segment_prefix(candidate: WorktreeCandidate, target: str) -> bool:
    for alias in candidate.aliases:
        if Path(alias).is_absolute():
            continue
        for segment in alias.split("/"):
            if segment.startswith(target):
                return True
    return False


def unique_worktree_candidates(candidates: Iterable[WorktreeCandidate]) -> list[WorktreeCandidate]:
    seen: set[Path] = set()
    unique: list[WorktreeCandidate] = []
    for candidate in candidates:
        key = candidate.worktree.path.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def ambiguous_worktree_error(target: str, candidates: list[WorktreeCandidate]) -> UsageError:
    return UsageError(
        f"ambiguous worktree prefix: {target}",
        hint="use a longer prefix or run wt list",
        details=format_candidate_details(candidates),
    )


def format_candidate_details(candidates: list[WorktreeCandidate]) -> str:
    if not candidates:
        return "candidates: none"
    display_width = max(len(candidate.display) for candidate in candidates)
    lines = ["candidates:"]
    for candidate in candidates:
        lines.append(f"  {candidate.display:<{display_width}}  {candidate.worktree.path}")
    return "\n".join(lines)


def completion_candidates(candidates: list[WorktreeCandidate], prefix: str) -> list[WorktreeCandidate]:
    if not prefix:
        return candidates
    return unique_worktree_candidates(
        candidate
        for candidate in candidates
        if candidate_matches_full_prefix(candidate, prefix) or candidate_matches_segment_prefix(candidate, prefix)
    )


def can_use_fzf() -> bool:
    return sys.stdin.isatty() and shutil.which("fzf") is not None


def select_candidate_with_fzf(candidates: list[WorktreeCandidate], query: str | None) -> WorktreeCandidate | None:
    rows = [fzf_row(candidate) for candidate in candidates]
    args = ["fzf", "--prompt=wt cd> "]
    if query:
        args.extend(["--query", query])
    result = subprocess.run(args, input="\n".join(rows) + "\n", text=True, stdout=subprocess.PIPE, check=False)
    if result.returncode != 0:
        return None
    selected = result.stdout.rstrip("\n")
    if not selected:
        return None
    selected_path = selected.rsplit("\t", 1)[-1]
    for candidate in candidates:
        if str(candidate.worktree.path) == selected_path:
            return candidate
    return None


def fzf_row(candidate: WorktreeCandidate) -> str:
    return f"{candidate.display}\t{candidate.worktree.path}"


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

    if args.config_action == "list":
        rows = flatten_config(config.values)
        if args.plain:
            for key, value in rows:
                output.print_line(f"{key}={format_config_value(value)}")
        else:
            print_config_table(rows)
        return int(ExitCode.SUCCESS)

    if args.config_action == "path":
        output.print_line(str(config_command_path(repo_root, args.use_global)))
        return int(ExitCode.SUCCESS)

    if args.config_action == "init":
        path = config_command_path(repo_root, args.use_global)
        if path.exists() and not args.force:
            output.print_line(f"config exists: {path}")
        else:
            config_module.write_default_config_file(path)
            output.print_line(f"created config: {path}")
        return int(ExitCode.SUCCESS)

    if args.config_action == "edit":
        path = config_command_path(repo_root, args.use_global)
        if not path.exists():
            config_module.write_default_config_file(path)
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if not editor:
            output.print_line(str(path))
            return int(ExitCode.SUCCESS)
        result = subprocess.run([*shlex.split(editor), str(path)], check=False)
        return int(result.returncode)

    path = config_module.writable_config_path(repo_root)
    persisted = config_module.read_toml(path) if path.exists() else {}

    if args.config_action == "set":
        value = config_module.parse_config_value(args.value)
        if args.key == "defaults.copyExclude":
            config_module.require_str_list(args.key, value)
        config_module.set_nested(persisted, args.key, value)
        config_module.write_config_file(path, persisted)
        return int(ExitCode.SUCCESS)

    if args.config_action == "unset":
        config_module.unset_nested(persisted, args.key)
        config_module.write_config_file(path, persisted)
        return int(ExitCode.SUCCESS)

    raise UsageError(f"unknown config action: {args.config_action}")


def config_command_path(repo_root: Path | None, use_global: bool) -> Path:
    if use_global or repo_root is None:
        return config_module.global_config_path()
    return config_module.repo_config_path(repo_root)


HOOK_FILENAMES = {
    "post-create": "post-create.sh",
    "pre-delete": "pre-delete.sh",
}


HOOK_CONFIG_KEYS = {
    "post-create": "hooks.postCreate",
    "pre-delete": "hooks.preDelete",
}


CONFIG_DESCRIPTIONS = {
    "defaults.worktreesDir": "Parent directory for generated worktree paths.",
    "defaults.base": "Ref used when --base is not provided.",
    "defaults.fetch": "Fetch the base remote before creating a worktree.",
    "defaults.copyLocal": "Copy ignored and untracked local files into new worktrees.",
    "defaults.copyExclude": "Git-ignore patterns omitted from all local-copy modes.",
    "defaults.deleteBranch": "Delete the local branch when deleting a worktree.",
    "hooks.postCreate": "Command or script run after creating a worktree.",
    "hooks.preDelete": "Command or script run before deleting a worktree.",
    "hooks.shell": "Shell used to run lifecycle hook commands.",
    "hooks.timeoutSeconds": "Hook timeout in seconds. 0 means no timeout.",
    "shell.cdAfterAdd": "Enter new worktrees automatically through shell integration.",
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
        configure_hook_paths(repo, HOOK_CONFIG_KEYS)
        output.print_line(f"hook dir: {hook_dir}")
        for hook_name, path in created.items():
            output.print_line(f"{hook_name}: {path}")
        output.print_line(f"configured: {config_module.repo_config_path(repo.main_root)}")
        return int(ExitCode.SUCCESS)

    if args.hooks_action == "edit":
        path = ensure_hook_template(repo, args.hook)
        configure_hook_paths(repo, (args.hook,))
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if not editor:
            output.print_line(str(path))
            return int(ExitCode.SUCCESS)
        result = subprocess.run([*shlex.split(editor), str(path)], check=False)
        return int(result.returncode)

    raise UsageError(f"unknown hooks action: {args.hooks_action}")


def handle_shell(args: argparse.Namespace) -> int:
    if args.shell_action == "completion":
        output.print_line(completion_script(args.shell))
        return int(ExitCode.SUCCESS)
    if args.shell_action == "init":
        output.print_line(init_script(args.shell))
        return int(ExitCode.SUCCESS)
    raise UsageError(f"unknown shell action: {args.shell_action}")


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


def configure_hook_paths(repo: git.RepoContext, hook_names: Iterable[str]) -> None:
    path = config_module.writable_config_path(repo.main_root)
    persisted = config_module.read_toml(path) if path.exists() else {}
    for hook_name in hook_names:
        config_module.set_nested(persisted, HOOK_CONFIG_KEYS[hook_name], str(hook_path(repo, hook_name)))
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


def print_config_table(rows: list[tuple[str, object]]) -> None:
    rendered = [(key, format_config_display_value(value), CONFIG_DESCRIPTIONS.get(key, "")) for key, value in rows]
    key_width = max([len("KEY"), *(len(key) for key, _, _ in rendered)])
    value_width = max([len("VALUE"), *(len(value) for _, value, _ in rendered)])

    output.print_line(f"{'KEY':<{key_width}}  {'VALUE':<{value_width}}  DESCRIPTION")
    for key, value, description in rendered:
        output.print_line(f"{key:<{key_width}}  {value:<{value_width}}  {description}")


def format_config_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return config_module.format_toml_value(value)
    if value is None:
        return ""
    return str(value)


def format_config_display_value(value: object) -> str:
    formatted = format_config_value(value)
    return formatted if formatted else "-"


def handle_root(args: argparse.Namespace) -> int:
    repo = git.require_repo(Path.cwd())
    output.print_line(str(repo.main_root))
    return int(ExitCode.SUCCESS)


def handle_current(args: argparse.Namespace) -> int:
    repo = git.require_repo(Path.cwd())
    current = repo.current_worktree.branch or repo.current_worktree.name
    output.print_line(current)
    return int(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
