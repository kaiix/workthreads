# wt CLI overview

Status: active
Surface: CLI overview
Verified against: README.md, src/workthreads/cli.py, tests/test_cli_contracts.py, tests/test_workflows.py

## Purpose

`wt` is a developer-first CLI for working with git worktrees. Its job is to make opening, preparing, listing, navigating, and cleaning up separate work threads feel natural during day-to-day development.

The tool should not feel like a thin wrapper around `git worktree`. It should behave like a workflow tool:

- Start a new task in an isolated worktree.
- Put that worktree exactly where the developer expects.
- Bring over local-only project data when requested.
- Run setup and cleanup scripts at lifecycle moments.
- Delete the current worktree without making the developer restate obvious context.
- Navigate between existing worktrees from the shell.
- Integrate with the shell through completion, stable output, and optional directory switching.

## Core principle: DX first

Developer experience is the first design constraint. Common actions should be short, obvious, safe by default, and easy to recover from when something goes wrong.

| Principle | Design impact |
| --- | --- |
| Context-aware | Detect the repo root automatically. If `wt delete` is run inside a linked worktree, delete that current worktree by default. |
| Short common path | Lead with `wt add <branch>`, `wt cd <target>`, `wt delete`, and `wt list`. |
| Safe by default | Do not silently delete dirty worktrees. Do not overwrite copied files by default. Keep branch deletion explicit. |
| Human-friendly and scriptable | Default output should help humans. Successful commands keep stable plain-text contracts where scripts need them. |
| Fixable errors | Errors should say what failed, why, and what to run next. |
| Shell-native | Completion is part of the core workflow. Directory switching belongs to shell integration, not the standalone binary. |

## Command map

| Command | Alias | Purpose | Focused note |
| --- | --- | --- | --- |
| `wt` | - | Show contextual help/status with no side effects. | [contracts](cli-contracts.md) |
| `wt add <branch>` | `wt new`, `wt create` | Create a new linked worktree and branch. | [paths](paths.md), [local file copying](local-file-copying.md), [hooks](hooks.md) |
| `wt delete [target]` | `wt rm` | Delete a linked worktree. `target` is optional inside a linked worktree. | [delete safety](delete-safety.md) |
| `wt list` | `wt ls` | List worktrees. | [contracts](cli-contracts.md) |
| `wt cd [target]` | - | Print or enter an existing worktree. | [shell integration](shell-integration.md) |
| `wt config` | - | Create, edit, inspect, and update configuration. | [config defaults](config-defaults.md) |
| `wt hooks` | - | Manage repo-local hook scripts under git's common dir. | [hooks](hooks.md) |
| `wt shell completion <shell>` | - | Print shell completion for bash, zsh, or fish. | [shell integration](shell-integration.md) |
| `wt shell init <shell>` | - | Print full shell integration, including completion and `--cd` support. | [shell integration](shell-integration.md) |
| `wt root` | - | Print the main worktree or repo root. | [contracts](cli-contracts.md) |
| `wt current` | - | Print the current linked worktree branch/name. | [contracts](cli-contracts.md) |

## Naming decisions

| Need | Chosen name | Why |
| --- | --- | --- |
| Create a worktree for a task | `wt add <branch>` | Aligns with `git worktree add` while staying short. |
| Creation aliases | `wt new <branch>`, `wt create <branch>` | Useful for users who think in product language, but not the primary spelling. |
| Delete a worktree | `wt delete [target]` | Destructive intent is explicit. |
| Short delete alias | `wt rm [target]` | Familiar for CLI users, but secondary because `delete` is clearer. |
| List worktrees | `wt list` | Clear in docs and help. |
| Short list alias | `wt ls` | Convenient for frequent CLI use. |
| Navigate to a worktree | `wt cd [target]` | Matches the user's intent when shell integration can actually change cwd. |
| Base branch/ref | `--base <ref>` | Matches the concept developers are choosing. |
| Exact destination | `--path <path>` | Means "put this worktree at exactly this path". |
| Parent directory for generated paths | `--worktrees-dir <dir>` | Clearly means the parent directory for generated worktree paths. |
| Copy local-only data | `--copy-local` | Means ignored plus untracked local files. |
| Granular copy controls | `--copy-ignored`, `--copy-untracked` | Explicit when a user wants only one category. |
| Creation hook override | `--post-create <cmd-or-path>` | Follows Git's `pre-*` / `post-*` hook convention. |
| Deletion hook override | `--pre-delete <cmd-or-path>` | Follows Git's `pre-*` / `post-*` hook convention. |
| Skip lifecycle hooks | `--skip-hooks` | Directly describes the action being requested. |
| Clean partial creation | `--cleanup-on-failure` | Says exactly when cleanup happens. |
| Enter the created worktree | `--cd` | Natural shorthand for "create it, then go there"; requires shell integration. |
| Stay in the current directory | `--no-cd` | One-command override when shell auto-cd is enabled. |
| No-argument invocation | `wt` | Shows contextual help/status with no side effects. |

## Current workflow

Configure once:

```bash
wt config init
wt config edit
eval "$(wt shell init zsh)"
```

Create a worktree:

```bash
wt add feature/payment-retry
```

Use one-off overrides when needed:

```bash
wt add feature/payment-retry \
  --base origin/main \
  --path ../external-worktrees/payment-retry \
  --copy-local \
  --post-create ./scripts/bootstrap.sh
```

Work normally in the created directory. With full shell integration, `wt add` enters the new worktree by default and `wt cd payment-retry` jumps between existing worktrees.

Delete the current linked worktree:

```bash
wt delete
```

Delete a named worktree from elsewhere:

```bash
wt delete feature/payment-retry
```

## First version scope

The first version should fully support:

1. Configure defaults.
2. Create a worktree.
3. Copy local-only files when requested.
4. Run setup hook.
5. List worktrees.
6. Delete the current or named worktree.
7. Run cleanup hook.
8. Navigate between worktrees.
9. Use shell completion and optional shell `cd` integration.

## Focused notes

- [Config defaults](config-defaults.md)
- [Paths and base refs](paths.md)
- [Local file copying](local-file-copying.md)
- [Lifecycle hooks](hooks.md)
- [Shell integration](shell-integration.md)
- [Delete safety](delete-safety.md)
- [Cleanup on failure](failure-cleanup.md)
- [CLI contracts](cli-contracts.md)
