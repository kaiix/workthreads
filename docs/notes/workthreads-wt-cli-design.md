# workthreads `wt` CLI Design

## Purpose

`wt` is a developer-first CLI for working with git worktrees. Its job is to make opening, preparing, and cleaning up a separate work thread feel natural during day-to-day development.

The tool should not feel like a thin wrapper around `git worktree`. It should behave like a workflow tool:

- Start a new task in an isolated worktree.
- Put that worktree exactly where the developer expects.
- Bring over local-only project data when needed.
- Run setup and cleanup scripts at the right lifecycle moments.
- Delete the current worktree without making the developer restate obvious context.
- Integrate with the shell through completion, stable output, and optional directory switching.

## Core Principle: DX First

Developer Experience is the first design constraint. Common actions should be short, obvious, safe by default, and easy to recover from when something goes wrong.

| Principle | Design impact |
| --- | --- |
| Context-aware | Detect the repo root automatically. If `wt delete` is run inside a linked worktree, delete that current worktree by default. |
| Short common path | The common commands are `wt add <branch>`, `wt delete`, and `wt list`. Aliases can exist, but docs and help should lead with the clearest names. |
| Safe by default | Do not silently delete dirty worktrees. Do not overwrite copied files by default. Do not auto-remove a partially created worktree unless the user asks for cleanup. |
| Human-friendly and scriptable | Default output should help humans. `--json` should be stable for scripts. Successful `wt add` should print the worktree path as the final line for shell integration. |
| Fixable errors | Errors should say what failed, why, and what to run next. |
| Shell-native | Completion is part of the first version. Optional `cd` behavior belongs to shell integration, not the standalone binary. |

## Naming Decisions

These names are optimized for the workthreads workflow, not for matching any existing tool.

| Need | Chosen name | Why |
| --- | --- | --- |
| Create a worktree for a task | `wt add <branch>` | Aligns with `git worktree add` while staying short. |
| Creation aliases | `wt new <branch>`, `wt create <branch>` | Useful for users who think in product language or search for "create", but not the primary spelling. |
| Delete a worktree | `wt delete [target]` | Destructive intent is explicit. |
| Short delete alias | `wt rm [target]` | Familiar for CLI users, but secondary because `delete` is clearer. |
| List worktrees | `wt list` | Clear in docs and help. |
| Short list alias | `wt ls` | Convenient for frequent CLI use. |
| Base branch/ref | `--base <ref>` | Matches the concept developers are choosing. |
| Exact destination | `--path <path>` | Means "put this worktree at exactly this path". |
| Parent directory for generated paths | `--worktrees-dir <dir>` | Clearly means the parent directory for generated worktree paths. |
| Copy local-only data | `--copy-local` | Best default DX for "bring my local env with me"; help text must define it as ignored + untracked files. |
| Granular copy controls | `--copy-ignored`, `--copy-untracked` | Explicit when a user wants only one category. |
| Creation hook override | `--post-create <cmd-or-path>` | Follows Git's `pre-*` / `post-*` hook convention. |
| Deletion hook override | `--pre-delete <cmd-or-path>` | Follows Git's `pre-*` / `post-*` hook convention. |
| Skip lifecycle hooks | `--skip-hooks` | Directly describes the action being requested. |
| Clean partial creation | `--cleanup-on-failure` | Says exactly when cleanup happens. |
| Enter the created worktree | `--cd` | Natural interactive shorthand for "create it, then go there"; requires shell integration. |
| Stay in the current directory | `--no-cd` | Explicit one-command override when shell auto-cd is enabled. |
| No-argument invocation | `wt` | Shows contextual help/status with no side effects. |

## Current Workflow

### 1. Configure once

```bash
wt config set defaults.worktreesDir ../workthreads
wt config set defaults.base origin/main
wt config set defaults.copyLocal true
wt config set hooks.postCreate ./scripts/wt-post-create.sh
wt config set hooks.preDelete ./scripts/wt-pre-delete.sh
```

Shell integration, including completion:

```bash
eval "$(wt init zsh)"
```

Completion-only setup is also available:

```bash
eval "$(wt completion zsh)"
```

Optional auto-cd for interactive shells:

```bash
wt config set shell.cdAfterAdd true
```

### 2. Start a new work thread

```bash
wt add feature/payment-retry
```

Create and enter the new worktree when shell integration is enabled:

```bash
wt add feature/payment-retry --cd
```

With one-off overrides:

```bash
wt add feature/payment-retry \
  --base origin/main \
  --path ../workthreads/payment-retry \
  --fetch \
  --copy-local \
  --post-create ./scripts/bootstrap.sh
```

### 3. Work normally

The created directory is a normal git worktree. The developer can run their editor, tests, agents, or local services there. If `--cd` or shell auto-cd was used, the interactive shell is already inside the new worktree.

### 4. Delete the current worktree

From inside the linked worktree:

```bash
wt delete
```

From the main worktree or elsewhere:

```bash
wt delete feature/payment-retry
```

## Command Overview

| Command | Alias | Purpose |
| --- | --- | --- |
| `wt` | - | Show contextual help/status with no side effects. |
| `wt add <branch>` | `wt new <branch>`, `wt create <branch>` | Create a new linked worktree and branch. |
| `wt delete [target]` | `wt rm [target]` | Delete a linked worktree. `target` is optional inside a linked worktree. |
| `wt list` | `wt ls` | List worktrees. |
| `wt config` | - | Read and write defaults. |
| `wt completion <shell>` | - | Print shell completion for bash, zsh, or fish. |
| `wt init <shell>` | - | Print full shell integration for bash, zsh, or fish, including completion and `--cd` support. |
| `wt root` | - | Print the main worktree or repo root. |
| `wt current` | - | Print the current linked worktree branch/name. |

## Bare `wt`

Running `wt` with no arguments is always side-effect free.

Inside a git repository, interactive output should be a compact contextual home screen:

```text
workthreads wt
repo: /repo
current: main

Common commands:
  wt add <branch>       create a worktree
  wt delete [target]    delete current or named worktree
  wt list               list worktrees
```

Outside a git repository, output should explain that worktree commands need a repo and show the common entry points:

```text
workthreads wt
Run inside a git repository to manage worktrees.

Common commands:
  wt add <branch>
  wt list
  wt completion <shell>
```

`wt` should not alias to `wt list`; that is convenient but less discoverable and slightly surprising for a root command.

## `wt add`

### Common examples

```bash
# Use configured defaults.
wt add feature/payment-retry

# Choose the base ref for this one worktree.
wt add feature/payment-retry --base origin/main

# Put the worktree at an exact path.
wt add feature/payment-retry --path ../workthreads/payment-retry

# Put the worktree under a parent directory.
wt add feature/payment-retry --worktrees-dir ../workthreads

# Bring ignored and untracked local files.
wt add feature/payment-retry --copy-local

# Use granular copy controls.
wt add feature/payment-retry --copy-ignored --copy-untracked

# Create and enter the worktree through shell integration.
wt add feature/payment-retry --cd

# Stay in place even when shell auto-cd is enabled.
wt add feature/payment-retry --no-cd
```

### Execution flow

| Step | Behavior | Example output |
| --- | --- | --- |
| 1. Read context | Resolve repo root, main worktree, existing worktrees, and local branches. | `[1/10] reading repository metadata` |
| 2. Resolve branch | Use `<branch>` and validate the name. | `[2/10] resolving branch: feature/payment-retry` |
| 3. Check conflicts | Ensure the branch/worktree does not conflict unless reuse is explicitly allowed. | `[3/10] checking existing branches and worktrees` |
| 4. Resolve path | Use `--path`, or generate `<worktreesDir>/<branch>`. | `[4/10] resolving path: ../workthreads/payment-retry` |
| 5. Resolve base | Use `--base`, repo config, global config, or a safe default. | `[5/10] resolving base: origin/main` |
| 6. Fetch | If `--fetch` is set, fetch the matching remote. | `[6/10] fetching origin` |
| 7. Count local files | Count ignored/untracked files requested by copy flags. | `[7/10] counting local files: ignored=12 untracked=3` |
| 8. Create worktree | Run `git worktree add -b <branch> <path> <base>`. | `[8/10] creating worktree` |
| 9. Copy local files | Copy requested local files. | `[9/10] copying .env.local` |
| 10. Run hook | Run the post-create hook in the new worktree. | `[10/10] running post-create hook` |

### Success output

Default output:

```text
created worktree feature/payment-retry from origin/main
path: /workthreads/payment-retry
copied: ignored=12 untracked=3
hook post-create: ok
/workthreads/payment-retry
```

The final line is only the worktree path. Without shell integration, this is the portable way to enter the new worktree:

```bash
cd "$(wt add feature/payment-retry --base origin/main | tail -n 1)"
```

JSON output:

```json
{
  "repoRoot": "/repo",
  "worktreePath": "/workthreads/payment-retry",
  "branch": "feature/payment-retry",
  "base": "origin/main",
  "copied": {
    "ignored": 12,
    "untracked": 3
  },
  "hooks": {
    "postCreate": {
      "command": "./scripts/bootstrap.sh",
      "exitCode": 0
    }
  }
}
```

### Directory switching rules

`wt add` itself does not change the current directory. A standalone process cannot change the parent shell's cwd, so directory switching is a shell integration feature.

Rules:

- `wt add <branch>` creates the worktree and prints its path, but does not change directories.
- `wt add <branch> --cd` requests "create it, then enter it" and only works through shell integration.
- Without active shell integration, `wt add --cd` fails with exit code `2` and a fixable hint.
- `shell.cdAfterAdd = true` behaves like implicit `--cd` only in interactive shell integration.
- `wt add --no-cd` disables `shell.cdAfterAdd` for one command.
- `--cd` and `--json` are mutually exclusive; JSON output is for scripts and should not imply interactive shell mutation.

Helpful failure when `--cd` is used without shell integration:

```text
error: --cd requires shell integration
hint: run `eval "$(wt init zsh)"` or use `cd "$(wt add feature/foo | tail -n 1)"`
```

### Path rules

- `--path <path>` is the exact destination.
- `--worktrees-dir <dir>` is the parent directory used to generate the destination.
- `--path` and `--worktrees-dir` are mutually exclusive; passing both should fail with a usage error.
- If neither is passed, use configured `defaults.worktreesDir`.
- Relative paths are resolved from the repo root.
- If the destination path is already used by another worktree, fail with a fixable error.
- If the branch already has a worktree, return that existing path.

### Base rules

- `--base <ref>` has highest priority.
- Then repo config.
- Then global config.
- Then the current `HEAD` or default branch policy.
- Before creation, validate that `<ref>^{commit}` exists.
- If `--fetch` is set, fetch the remote implied by the base ref when possible.
- `--no-fetch` disables fetching when config enables `defaults.fetch`.

## Copying Local Files

The common case is "make the new worktree feel like my current dev environment". Use:

```bash
wt add feature/payment-retry --copy-local
```

`--copy-local` means:

- Copy ignored files.
- Copy untracked files.

Granular controls:

| Flag | Copies |
| --- | --- |
| `--copy-ignored` | Files matched by git ignore rules, such as `.env.local` or local cache/config files. |
| `--copy-untracked` | Files not tracked by git and not ignored. |
| `--overwrite` | Allow copied files to overwrite existing destination files. |
| `--verbose` | Print copy progress. |

Implementation rules:

- Use `git ls-files` to compute file sets.
- Never parse `.gitignore` manually.
- Never copy `.git/`.
- Avoid copying nested worktrees.
- Handle files, directories, and symlinks.
- Prefer clone/reflink copy when available; fall back to normal copy.
- Do not overwrite existing destination files unless `--overwrite` is set.

## Lifecycle Hooks

First version hooks:

| Hook | Config key | CLI override | Runs | Failure behavior |
| --- | --- | --- | --- | --- |
| post-create | `hooks.postCreate` | `--post-create <cmd-or-path>` | After worktree creation and local file copy. | Command fails; worktree is kept unless cleanup is requested. |
| pre-delete | `hooks.preDelete` | `--pre-delete <cmd-or-path>` | Before deleting the target worktree. | Delete is blocked. |

Hook examples:

```bash
wt config set hooks.postCreate ./scripts/wt-post-create.sh
wt config set hooks.preDelete ./scripts/wt-pre-delete.sh

wt add feature/foo --post-create ./scripts/bootstrap.sh
wt delete feature/foo --pre-delete ./scripts/cleanup.sh
```

Hook execution rules:

- `post-create` runs in the new worktree directory.
- `pre-delete` runs in the target worktree directory.
- Hooks inherit the current environment.
- Hooks also receive stable `WT_*` variables.
- Non-zero exit codes are surfaced.
- `--skip-hooks` skips lifecycle hooks explicitly.
- Non-interactive runs must fail instead of hanging for input.

Hook environment:

```text
WT_EVENT=post-create|pre-delete
WT_REPO_ROOT=/repo
WT_WORKTREE_PATH=/workthreads/payment-retry
WT_WORKTREE_NAME=payment-retry
WT_BRANCH=feature/payment-retry
WT_BASE=origin/main
WT_COPY_LOCAL=0|1
WT_COPY_IGNORED=0|1
WT_COPY_UNTRACKED=0|1
WT_DIRTY=0|1
WT_CONFIG_FILE=/repo/workthreads.toml
```

## Cleanup on Failure

`--cleanup-on-failure` handles partial `wt add` failures. It is intentionally explicit because automatic cleanup can destroy useful debugging context.

Typical partial failures:

- The worktree was created but local file copy failed.
- The post-create hook failed.
- Metadata or output writing failed after creation.

Default behavior:

- Keep the created worktree.
- Show the failing step.
- Show the path that was left behind.
- Suggest cleanup commands.

Explicit cleanup:

```bash
wt add feature/foo --cleanup-on-failure
```

Cleanup behavior:

1. If the worktree is registered, run `git worktree remove --force <path>`.
2. If this command created a local branch, delete that branch.
3. If the directory still exists, remove it or move it to a temporary recovery location.
4. Report cleanup success or failure without hiding the original error.

This cleanup mode only applies to failed `wt add` runs. Normal deletion is handled by `wt delete`.

## `wt delete`

### Common examples

```bash
# Inside a linked worktree or any child directory.
wt delete

# From the main worktree or another directory.
wt delete feature/payment-retry

# Keep or delete the branch explicitly.
wt delete feature/payment-retry --keep-branch
wt delete feature/payment-retry --delete-branch
```

### Target resolution

`wt delete` resolves the target in this order:

1. If a target is provided, match it as a branch/name/path.
2. If no target is provided and the current directory is inside a linked worktree, delete that linked worktree.
3. If no target is provided and the current directory is the main worktree, fail with a helpful message.

Main worktree error:

```text
error: current directory is the main worktree
hint: run `wt delete <branch-or-path>` from the main worktree, or cd into a linked worktree and run `wt delete`
```

### Deletion flow

1. Resolve target worktree.
2. Refuse to delete the main worktree.
3. Check dirty state.
4. If dirty and not forced:
   - Ask for confirmation in a TTY.
   - Fail in non-interactive mode.
5. Run the pre-delete hook.
6. Run `git worktree remove <path>`.
7. Keep or delete the local branch according to flags/config.
8. Print the result.

Branch behavior:

- Built-in default: keep the branch.
- `--delete-branch` deletes the local branch after worktree removal.
- `--keep-branch` keeps the local branch.
- `--delete-branch` and `--keep-branch` are mutually exclusive.

Success output:

```text
deleted worktree feature/payment-retry
path: /workthreads/payment-retry
branch: kept
```

No separate `wt trash` command exists in this design. If deletion safety needs a recovery mechanism, it should be expressed through the `wt delete` workflow and documented guarantees, not as a separate command with unclear semantics.

## `wt list`

Default output should be readable:

```text
BRANCH                  PATH                              BASE
feature/payment-retry   /workthreads/payment-retry        origin/main
feature/webhook-audit   /workthreads/webhook-audit        origin/main
```

JSON output should be stable:

```bash
wt list --json
```

Example:

```json
[
  {
    "branch": "feature/payment-retry",
    "path": "/workthreads/payment-retry",
    "head": "abc123",
    "isMain": false,
    "dirty": false
  }
]
```

## Configuration

Repo-local config should live at the repository root:

```text
workthreads.toml
```

This is better than `.workthreads/config.toml` for the editable project configuration because it is easy to discover, review, and commit. Internal workthreads state should not live in the working tree; it belongs under git's common directory.

For migration, the CLI may read an existing `.workthreads/config.toml` as a legacy fallback when present, but new `wt config set` writes should target `workthreads.toml`.

Suggested repo-local config:

```toml
[defaults]
worktreesDir = "../workthreads"
base = "origin/main"
fetch = true
copyLocal = true
deleteBranch = false

[hooks]
postCreate = "./scripts/wt-post-create.sh"
preDelete = "./scripts/wt-pre-delete.sh"
shell = "/bin/zsh"
timeoutSeconds = 0

[shell]
cdAfterAdd = false
```

Config commands:

```bash
wt config get defaults.worktreesDir
wt config set defaults.worktreesDir ../workthreads
wt config set defaults.base origin/main
wt config set defaults.copyLocal true
wt config set hooks.postCreate ./scripts/wt-post-create.sh
wt config set shell.cdAfterAdd true
wt config list
wt config unset hooks.postCreate
```

Precedence:

```text
CLI flag > repo config > global config > built-in default
```

## Shell Completion and Integration

First version supports:

```bash
wt completion bash
wt completion zsh
wt completion fish

wt init bash
wt init zsh
wt init fish
```

Completion should cover:

- Subcommands.
- Flags.
- Local branches.
- Existing worktrees.
- Config keys.
- Hook names.

Completion-only setup:

```bash
eval "$(wt completion zsh)"
```

Full shell integration:

```bash
eval "$(wt init zsh)"
```

`wt init <shell>` should install completion and a small shell wrapper that delegates to the real binary. The wrapper is responsible for changing directories after a successful `wt add --cd` or when `shell.cdAfterAdd` is enabled.

Target experience:

- `wt add <tab>` completes branch/base candidates.
- `wt delete <tab>` completes existing worktrees.
- `wt config set <tab>` completes config keys.
- `wt add --cd` changes the interactive shell cwd after successful creation.
- `shell.cdAfterAdd = true` makes successful interactive `wt add` enter the new worktree by default.
- `wt add --no-cd` keeps the shell in place even when auto-cd is enabled.

## First Version Scope

The first version should fully support the easiest workflow:

1. Configure defaults.
2. Create a worktree.
3. Copy local-only files when requested.
4. Run setup hook.
5. List worktrees.
6. Delete the current or named worktree.
7. Run cleanup hook.
8. Use shell completion and optional shell `cd` integration.

Required command support:

| Area | Required support |
| --- | --- |
| root command | Bare `wt` contextual help/status with no side effects |
| `add/new/create` | `--path`, `--worktrees-dir`, `--base`, `--fetch`, `--no-fetch`, `--copy-local`, `--copy-ignored`, `--copy-untracked`, `--overwrite`, `--skip-hooks`, `--cleanup-on-failure`, `--post-create`, `--cd`, `--no-cd`, `--json` |
| `delete/rm` | Optional target inside linked worktree, branch/name/path target resolution, dirty checks, `--force`, `--delete-branch`, `--keep-branch`, `--pre-delete`, `--skip-hooks`, `--json` |
| `list/ls` | Table output and JSON output |
| hooks | Repo config, CLI override, stable environment, non-zero exit handling |
| config | Get/set repo defaults |
| shell | bash, zsh, fish completion; `wt init <shell>` wrapper support for `--cd` and `shell.cdAfterAdd` |
| errors | Stage, command, exit code, stderr summary, and suggested next action |

## Stable Contracts

### `wt add` success guarantees

- The target path is a valid git worktree.
- The branch was created from the selected base ref.
- Requested local files were copied.
- The post-create hook ran successfully unless skipped.
- The final line of normal output is the worktree path.
- The standalone binary does not change cwd.
- `--cd` changes cwd only through shell integration.
- JSON output follows a stable schema.

### Bare `wt` guarantees

- Running `wt` with no arguments has no side effects.
- Inside a repository, it shows contextual help/status.
- Outside a repository, it shows general help and a repo-required hint.

### `wt delete` success guarantees

- The pre-delete hook ran successfully unless skipped.
- The target worktree was removed from git's worktree list.
- The branch was kept or deleted according to flags/config.
- Dirty worktrees are not silently deleted without `--force` or confirmation.
- Running `wt delete` inside a linked worktree deletes that current worktree by default.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Runtime failure, such as git command failure, hook failure, or copy failure. |
| `2` | Usage error, such as incompatible flags, missing required input, or `--cd` without shell integration. |
| `3` | Safety refusal, such as dirty worktree deletion without `--force` in a non-interactive context. |

Scripts should rely on these categories rather than parsing human-readable output.
