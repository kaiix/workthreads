# Paths and base refs

Status: active
Surface: paths
Verified against: src/workthreads/paths.py, src/workthreads/git.py, tests/test_paths.py, tests/test_workflows.py

## Path flags

- `--path <path>` is the exact destination.
- `--worktrees-dir <dir>` is the parent directory used to generate the destination.
- `--path` and `--worktrees-dir` are mutually exclusive.
- If neither is passed, use configured `defaults.worktreesDir`.
- Relative paths are resolved from the main worktree root.
- If the destination path is already used by another worktree, fail with a fixable error.
- If the branch already has a worktree, return that existing path.

By default, generated worktrees live under:

```text
.worktrees/<branch-path>
```

For example:

```bash
wt add feature/payment-retry
```

creates:

```text
.worktrees/feature/payment-retry
```

## Base ref rules

- `--base <ref>` has highest priority.
- Then repo config.
- Then global config.
- Then inferred defaults such as `origin/main`, `origin/master`, `main`, `master`, or `HEAD`.
- Before creation, validate that `<ref>^{commit}` exists.
- If fetching is enabled, fetch the remote implied by the base ref when possible.
- `--no-fetch` disables fetching when config enables `defaults.fetch`.

## Examples

```bash
# Choose the base ref for one worktree.
wt add feature/payment-retry --base origin/main

# Put the worktree at an exact path.
wt add feature/payment-retry --path ../external-worktrees/payment-retry

# Put the worktree under a parent directory.
wt add feature/payment-retry --worktrees-dir ../external-worktrees
```
