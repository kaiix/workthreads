# Lifecycle hooks

Status: active
Surface: hooks
Verified against: src/workthreads/hooks.py, src/workthreads/cli.py, tests/test_hooks.py, tests/test_hooks_helpers.py, tests/test_workflows.py

## Supported hooks

| Hook | Config key | CLI override | Runs | Failure behavior |
| --- | --- | --- | --- | --- |
| post-create | `hooks.postCreate` | `--post-create <cmd-or-path>` | After worktree creation and local file copy. | Command fails; worktree is kept unless cleanup is requested. |
| pre-delete | `hooks.preDelete` | `--pre-delete <cmd-or-path>` | Before deleting the target worktree. | Delete is blocked. |

## Examples

```bash
wt hooks init
wt hooks edit post-create
wt hooks edit pre-delete

wt add feature/foo --post-create ./scripts/bootstrap.sh
wt delete feature/foo --pre-delete ./scripts/cleanup.sh
```

## Hook script locations

Hook scripts should be local by default. Each developer may use a different setup flow, agents, dependency managers, or no hooks at all.

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

## Configuration guidance

- Use repo config for repo-specific local hooks.
- Use global user config for hooks shared across repositories.
- Use CLI flags for one-off hook commands.
- Avoid committing hook settings in `wt.toml` unless the team explicitly wants a shared workflow contract.

Repo-local helper commands:

```bash
wt hooks dir
wt hooks init
wt hooks edit post-create
wt hooks path post-create
```

Optional shared hook scripts are acceptable only when a repository intentionally wants shared hook behavior:

```text
scripts/
  wt/
    post-create.sh
    pre-delete.sh
```

## Execution rules

- Relative hook paths are resolved from the worktree where the hook runs.
- Repo-local untracked hook scripts should be configured through `wt hooks` helpers so the same setup works from every linked worktree.
- `post-create` runs in the newly created worktree.
- `pre-delete` runs in the target worktree before deletion.
- Hooks inherit the current environment.
- Hooks also receive stable `WT_*` variables.
- Non-zero exit codes are surfaced.
- `--skip-hooks` skips lifecycle hooks explicitly.
- Non-interactive runs must fail instead of hanging for input.

## Hook environment

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
