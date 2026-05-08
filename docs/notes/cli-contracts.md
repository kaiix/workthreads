# CLI contracts

Status: active
Surface: CLI contracts
Verified against: src/workthreads/cli.py, tests/test_cli_contracts.py, tests/test_workflows.py, tests/test_cd.py

## Bare `wt`

Running `wt` with no arguments is always side-effect free.

Inside a git repository, interactive output should be a compact contextual home screen:

```text
wt - git worktrees for parallel tasks
repo: /repo
current: main
default path: .worktrees/<branch-path>

Common commands:
  wt add <branch>       create a worktree
  wt cd <target>        enter an existing worktree
  wt delete [target]    delete current or named worktree
  wt list               list worktrees

Setup commands:
  wt config init        create a commented wt.toml
  wt hooks init         create local hook scripts
  wt shell init <shell> enable shell integration
```

Outside a git repository, output should explain that worktree commands need a repo and show the common entry points:

```text
wt - git worktrees for parallel tasks
Run inside a git repository to manage worktrees.

Common commands:
  wt add <branch>
  wt list
  wt shell completion <shell>
```

`wt` should not alias to `wt list`; that is convenient but less discoverable and slightly surprising for a root command.

## `wt add` success guarantees

- The target path is a valid git worktree.
- The branch was created from the selected base ref.
- Requested local files were copied.
- The post-create hook ran successfully unless skipped.
- The final line of normal output is the worktree path.
- The standalone binary does not change cwd.
- `--cd` changes cwd only through shell integration.

Default output:

```text
created worktree feature/payment-retry from origin/main
path: /repo/.worktrees/feature/payment-retry
copied: ignored=12 untracked=3
hook post-create: ok
/repo/.worktrees/feature/payment-retry
```

The final line is only the worktree path. Without shell integration, this is the portable way to enter the new worktree:

```bash
cd "$(wt add feature/payment-retry --base origin/main | tail -n 1)"
```

## Bare `wt` guarantees

- Running `wt` with no arguments has no side effects.
- Inside a repository, it shows contextual help/status.
- Outside a repository, it shows general help and a repo-required hint.

## `wt cd` success guarantees

- The target path is an existing git worktree.
- Without shell integration, the command prints the destination path.
- With shell integration, the command writes the destination to `WT_CD_FILE` and lets the shell wrapper change cwd.
- Deterministic matching uses exact, full-prefix, and segment-prefix matches only.
- Fuzzy substring matching requires interactive `fzf` confirmation.

## `wt delete` success guarantees

- The pre-delete hook ran successfully unless skipped.
- The target worktree was removed from git's worktree list.
- The branch was kept or deleted according to flags/config.
- Dirty worktrees are not silently deleted without `--force` or confirmation.
- Running `wt delete` inside a linked worktree deletes that current worktree by default.

## `wt list`

Default output should be readable:

```text
BRANCH                  PATH                                      BASE
feature/payment-retry   /repo/.worktrees/feature/payment-retry    origin/main
feature/webhook-audit   /repo/.worktrees/feature/webhook-audit    origin/main
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Runtime failure, such as git command failure, hook failure, or copy failure. |
| `2` | Usage error, such as incompatible flags, missing required input, or `--cd` without shell integration. |
| `3` | Safety refusal, such as dirty worktree deletion without `--force` in a non-interactive context. |

Scripts should rely on these categories rather than parsing human-readable output.
