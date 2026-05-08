# Failure cleanup

Status: active
Surface: add cleanup
Verified against: src/workthreads/cli.py

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

This cleanup mode only applies to failed `wt add` runs. Normal deletion is handled by `wt delete`; see [delete safety](delete-safety.md).
