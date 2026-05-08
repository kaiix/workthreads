# wt config defaults

Status: active
Surface: config
Verified against: src/workthreads/config.py, tests/test_config.py

This note is the design record for built-in `wt` defaults, the generated `wt config init` template, config file location, and the recommended local workflow. The CLI overview should link here instead of absorbing every defaults tradeoff.

## Current built-in defaults

| Key | Built-in and template value | Rationale |
| --- | --- | --- |
| `defaults.worktreesDir` | `.worktrees` | Gives a predictable repo-local location without requiring first-run setup. |
| `defaults.base` | unset | Lets `wt` infer the repository's default base ref instead of assuming every repo uses the same branch name. |
| `defaults.fetch` | `true` | Keeps remote base refs fresh before creating a worktree. `--no-fetch` remains the one-command opt-out for offline or latency-sensitive cases. |
| `defaults.copyLocal` | `false` | Avoids silently copying large ignored directories, secrets, scratch files, or local experiments into every new worktree. |
| `defaults.deleteBranch` | `false` | Keeps branch deletion explicit and avoids losing unmerged commits as a side effect of deleting a worktree. |
| `shell.cdAfterAdd` | `true` | Matches the interactive shell workflow: after creating a worktree, the next likely action is to work inside it. This only takes effect when full shell integration is active. |

The built-in defaults and `wt config init` template should stay in lockstep. If one changes, update the other and the config tests.

## Recommended local workflow

For a developer who frequently creates short-lived worktrees and wants them ready to run immediately:

```toml
[defaults]
fetch = true
copyLocal = true
deleteBranch = false

[shell]
cdAfterAdd = true
```

This keeps base refs fresh, copies local setup files when the user opts into that behavior, keeps branch deletion explicit, and enters new worktrees automatically when shell integration is installed.

## `copyLocal` tradeoff

A fresh Git worktree often cannot run the app because ignored local files like `.env`, local config, generated credentials, or scratch setup files are missing. `defaults.copyLocal = true` solves that by copying ignored and untracked local files into the new worktree.

That convenience is risky as a universal default because ignored and untracked files can include very large directories, stale build artifacts, secrets, or files the user intentionally did not want duplicated. The safest built-in default is therefore `false`, with README guidance that explains when to enable it.

Future mitigations if `copyLocal` becomes more opinionated:

- Pre-scan selected files before copying and report counts plus total size.
- Prompt in interactive terminals when the selection crosses a large-file or large-total-size threshold.
- Fail non-interactively with a clear hint when a configured threshold is exceeded.
- Provide an explicit override for scripts.
- Add configurable exclude patterns for dependency directories, build outputs, caches, and logs.

Avoid prompting on every `copyLocal` run; threshold-based prompts preserve the happy path.

## `deleteBranch` tradeoff

`defaults.deleteBranch = true` fits a "work thread" mental model where deleting a worktree retires the matching branch. It is not a safe built-in default yet because branch deletion is more destructive than removing the worktree directory.

Current `wt delete` behavior:

- The target worktree is checked with `git status --porcelain` before removal.
- Untracked files count as dirty and trigger the dirty-worktree path.
- In an interactive terminal, a dirty worktree prompts before deletion unless `--force` was passed.
- In non-interactive mode, a dirty worktree fails unless `--force` was passed.
- There is no separate unmerged-commit check before branch deletion.
- If branch deletion is enabled by `--delete-branch` or `defaults.deleteBranch = true`, the branch is deleted with force-delete semantics after the worktree is removed.

Deferred safety improvements:

- Make the dirty-worktree prompt explicitly mention modified and untracked files.
- Decide whether ignored-only files should also warn, especially when `copyLocal` copied them into the worktree.
- If branch deletion comes from `defaults.deleteBranch = true`, print that config is causing the branch deletion.
- Require interactive confirmation, or fail non-interactively with a clear override hint, before deleting a branch with unmerged commits.
- Avoid force-deleting branches by default unless the user has explicitly confirmed the unmerged-commit case.

For now, the built-in default should remain `deleteBranch = false`.

## Config file location

Repo config lives at:

```text
wt.toml
```

"Repo config" means the config is located at the repository root, not that it must be committed. A developer can keep `wt.toml` untracked for local workflow settings, or a repo can commit it when the team intentionally wants shared defaults.

Good candidates for committed shared config:

- Default base branch.
- Whether fetching before creation is expected for this repo.
- Naming/path conventions only if the team truly shares them.

Usually keep these settings local/untracked:

- Worktree parent directory.
- Hook scripts.
- Shell auto-cd preferences.
- Copying local ignored/untracked files.

## Config commands

```bash
wt config init
wt config init --global
wt config path
wt config path --global
wt config edit
wt config edit --global
wt config list
wt config list --plain
```

Direct key commands remain available for small updates and shell integration:

```bash
wt config get defaults.worktreesDir
wt config set defaults.worktreesDir ../external-worktrees
wt config set defaults.base origin/main
wt config set defaults.copyLocal true
wt config set hooks.postCreate /absolute/path/to/post-create.sh
wt config set shell.cdAfterAdd true
wt config unset hooks.postCreate
```

Precedence:

```text
CLI flag > repo config > global config > built-in default
```
