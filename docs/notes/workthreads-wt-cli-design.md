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
| Human-friendly and scriptable | Default output should help humans. Successful commands should keep stable plain-text contracts where scripts need them, such as `wt add` printing the worktree path as the final line. |
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
wt config set defaults.base origin/main
wt config set defaults.copyLocal true
wt config set hooks.postCreate /absolute/path/to/post-create.sh
wt config set hooks.preDelete /absolute/path/to/pre-delete.sh
```

The built-in worktree location is `.worktrees/<branch-path>` under the repo root, so the first setup step does not need to configure a path.

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
  --path ../external-worktrees/payment-retry \
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
| `wt hooks` | - | Manage repo-local hook scripts under git's common dir. |
| `wt completion <shell>` | - | Print shell completion for bash, zsh, or fish. |
| `wt init <shell>` | - | Print full shell integration for bash, zsh, or fish, including completion and `--cd` support. |
| `wt root` | - | Print the main worktree or repo root. |
| `wt current` | - | Print the current linked worktree branch/name. |

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
  wt delete [target]    delete current or named worktree
  wt list               list worktrees

Setup commands:
  wt config set <key> <value>  configure repo defaults
  wt hooks init                create local hook scripts
  wt init <shell>              enable shell integration
```

Outside a git repository, output should explain that worktree commands need a repo and show the common entry points:

```text
wt - git worktrees for parallel tasks
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
wt add feature/payment-retry --path ../external-worktrees/payment-retry

# Put the worktree under a parent directory.
wt add feature/payment-retry --worktrees-dir ../external-worktrees

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
| 4. Resolve path | Use `--path`, or generate `<worktreesDir>/<branch-path>`. | `[4/10] resolving path: .worktrees/feature/payment-retry` |
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
path: /repo/.worktrees/feature/payment-retry
copied: ignored=12 untracked=3
hook post-create: ok
/repo/.worktrees/feature/payment-retry
```

The final line is only the worktree path. Without shell integration, this is the portable way to enter the new worktree:

```bash
cd "$(wt add feature/payment-retry --base origin/main | tail -n 1)"
```

### Directory switching rules

`wt add` itself does not change the current directory. A standalone process cannot change the parent shell's cwd, so directory switching is a shell integration feature.

Rules:

- `wt add <branch>` creates the worktree and prints its path, but does not change directories.
- `wt add <branch> --cd` requests "create it, then enter it" and only works through shell integration.
- Without active shell integration, `wt add --cd` fails with exit code `2` and a fixable hint.
- `shell.cdAfterAdd = true` behaves like implicit `--cd` only in interactive shell integration.
- `wt add --no-cd` disables `shell.cdAfterAdd` for one command.

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
- Use copy-on-write clone/reflink for regular files when the platform and filesystem support it; fall back to normal copy.
- Copy directories recursively so regular files inside directories can still use clone/reflink.
- Do not overwrite existing destination files unless `--overwrite` is set.

## Lifecycle Hooks

First version hooks:

| Hook | Config key | CLI override | Runs | Failure behavior |
| --- | --- | --- | --- | --- |
| post-create | `hooks.postCreate` | `--post-create <cmd-or-path>` | After worktree creation and local file copy. | Command fails; worktree is kept unless cleanup is requested. |
| pre-delete | `hooks.preDelete` | `--pre-delete <cmd-or-path>` | Before deleting the target worktree. | Delete is blocked. |

Hook examples:

```bash
wt config set hooks.postCreate /absolute/path/to/post-create.sh
wt config set hooks.preDelete /absolute/path/to/pre-delete.sh

wt add feature/foo --post-create ./scripts/bootstrap.sh
wt delete feature/foo --pre-delete ./scripts/cleanup.sh
```

### Hook script locations

Hook scripts should be local by default. Each developer may use a different setup flow, different agents, different dependency managers, or no hooks at all.

Recommended repo-local layout:

```text
$GIT_COMMON_DIR/
  workthreads/
    hooks/
      post-create.sh
      pre-delete.sh
```

For a normal single-worktree clone, this is usually:

```text
.git/
  workthreads/
    hooks/
      post-create.sh
      pre-delete.sh
```

Why this is the best repo-local default:

- It is local to the clone and not committed.
- It is shared by all linked worktrees because git worktrees share a common git directory.
- It does not clutter the working tree.
- It avoids `scripts/`, which conventionally means tracked project automation.
- It avoids `.git/hooks`, which is reserved for Git's own hook mechanism and has different semantics.

Recommended user-global layout:

```text
~/.config/
  workthreads/
    config.toml
    hooks/
      post-create.sh
      pre-delete.sh
```

Why local hooks:

- Creating a worktree is part of a developer-local workflow, not necessarily a project contract.
- Developers may choose different worktree parent directories, bootstrap commands, package managers, editors, agents, and cleanup behavior.
- Local hooks match the Supacode-style model where setup/archive/delete scripts are user settings.
- Local hooks avoid surprising teammates who only want normal git worktree behavior.

Where to configure hooks:

- Use repo config for repo-specific local hooks.
- Use global user config for hooks shared across repositories.
- Use CLI flags for one-off hook commands.
- Avoid committing hook settings in `wt.toml` unless the team explicitly wants a shared workflow contract.

Repo-local hook config example:

```bash
wt hooks dir
wt hooks init
wt hooks edit post-create
wt hooks path post-create
```

`wt hooks` helper commands create and manage scripts in the repo-local hook directory so users do not need to manually type git-common-dir paths.

Optional shared hook scripts:

```text
scripts/
  wt/
    post-create.sh
    pre-delete.sh
```

This is acceptable only when a repository intentionally wants shared hook behavior. It should not be the default recommendation.

Hook path rules:

- Relative hook paths are resolved from the worktree where the hook runs.
- Repo-local untracked hook scripts should be configured through `wt hooks` helpers so the same setup works from every linked worktree.
- `post-create` runs in the newly created worktree.
- `pre-delete` runs in the target worktree before deletion.
- Local hook scripts should usually use absolute paths or `~` paths.
- Shared hook scripts must be tracked files available from the selected base ref.

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
WT_WORKTREE_PATH=/repo/.worktrees/feature/payment-retry
WT_WORKTREE_NAME=payment-retry
WT_BRANCH=feature/payment-retry
WT_BASE=origin/main
WT_COPY_LOCAL=0|1
WT_COPY_IGNORED=0|1
WT_COPY_UNTRACKED=0|1
WT_DIRTY=0|1
WT_CONFIG_FILE=/repo/wt.toml
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
path: /repo/.worktrees/feature/payment-retry
branch: kept
```

No separate `wt trash` command exists in this design. If deletion safety needs a recovery mechanism, it should be expressed through the `wt delete` workflow and documented guarantees, not as a separate command with unclear semantics.

## `wt list`

Default output should be readable:

```text
BRANCH                  PATH                                      BASE
feature/payment-retry   /repo/.worktrees/feature/payment-retry    origin/main
feature/webhook-audit   /repo/.worktrees/feature/webhook-audit    origin/main
```

## Configuration

### Config file location

```text
wt.toml
```

Use `wt.toml` as the repo config file in v1. "Repo config" means the config is located at the repository root, not that it must be committed. A developer can keep `wt.toml` untracked for local workflow settings, or a repo can commit it when the team intentionally wants shared defaults.

Current naming default:

| Surface | Name | Reason |
| --- | --- | --- |
| Project/repo/package | `workthreads` | Names the product/workflow concept. |
| CLI | `wt` | Short, high-frequency, and naturally maps to `git worktree`. |
| Repo config | `wt.toml` | Polished and CLI-aligned without overloading Git's `worktree` terminology. |

If committed, shared `wt.toml` should stay small. Good candidates:

- Default base branch.
- Whether fetching before creation is expected for this repo.
- Naming/path conventions only if the team truly shares them.

Usually keep these settings local/untracked:

- Worktree parent directory.
- Hook scripts.
- Shell auto-cd preferences.
- Copying local ignored/untracked files.

Suggested local `wt.toml`:

```toml
[defaults]
worktreesDir = ".worktrees"
base = "origin/main"
fetch = true
copyLocal = true
deleteBranch = false

[hooks]
postCreate = "/absolute/path/to/post-create.sh"
preDelete = "/absolute/path/to/pre-delete.sh"

[shell]
cdAfterAdd = false
```

Config commands:

```bash
wt config get defaults.worktreesDir
wt config set defaults.worktreesDir ../external-worktrees
wt config set defaults.base origin/main
wt config set defaults.copyLocal true
wt config set hooks.postCreate /absolute/path/to/post-create.sh
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

The wrapper should not pipe all `wt` output through `tee` or command substitution. Interactive commands such as `wt hooks edit` must keep direct access to the terminal. For cd handoff, the wrapper should pass a temporary `WT_CD_FILE`; `wt add` writes the target path there after success, and the wrapper reads it to `cd`.

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
| `add/new/create` | `--path`, `--worktrees-dir`, `--base`, `--fetch`, `--no-fetch`, `--copy-local`, `--copy-ignored`, `--copy-untracked`, `--overwrite`, `--skip-hooks`, `--cleanup-on-failure`, `--post-create`, `--cd`, `--no-cd` |
| `delete/rm` | Optional target inside linked worktree, branch/name/path target resolution, dirty checks, `--force`, `--delete-branch`, `--keep-branch`, `--pre-delete`, `--skip-hooks` |
| `list/ls` | Table output |
| `hooks` | `dir`, `init`, `path <hook>`, `edit <hook>` for repo-local hook scripts |
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
