# Delete safety

Status: active
Surface: delete
Verified against: src/workthreads/cli.py, src/workthreads/git.py, tests/test_workflows.py

## Common examples

```bash
# Inside a linked worktree or any child directory.
wt delete

# From the main worktree or another directory.
wt delete feature/payment-retry

# Keep or delete the branch explicitly.
wt delete feature/payment-retry --keep-branch
wt delete feature/payment-retry --delete-branch
```

## Target resolution

`wt delete` resolves the target in this order:

1. If a target is provided, match it as a branch/name/path.
2. If no target is provided and the current directory is inside a linked worktree, delete that linked worktree.
3. If no target is provided and the current directory is the main worktree, fail with a helpful message.

Main worktree error:

```text
error: current directory is the main worktree
hint: run `wt delete <branch-or-path>` from the main worktree, or cd into a linked worktree and run `wt delete`
```

## Deletion flow

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

## Known safety gap

`wt delete` currently treats untracked files as dirty because it uses `git status --porcelain`, but branch deletion does not yet check for unmerged commits before force-deleting a branch when branch deletion is enabled. See [config defaults](config-defaults.md) for the deferred `defaults.deleteBranch` safety improvements.
