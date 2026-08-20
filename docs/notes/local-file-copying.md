# Local file copying

Status: active
Surface: local file copying
Verified against: src/workthreads/copy.py, src/workthreads/cli.py, tests/test_copy.py, tests/test_workflows.py

## Purpose

The common case is "make the new worktree feel like my current dev environment". Use:

```bash
wt add feature/payment-retry --copy-local
```

`--copy-local` means:

- Copy ignored files.
- Copy untracked files.

## Flags

| Flag | Copies |
| --- | --- |
| `--copy-local` | Ignored and untracked local files. |
| `--copy-ignored` | Files matched by git ignore rules, such as `.env.local` or local cache/config files. |
| `--copy-untracked` | Files not tracked by git and not ignored. |
| `--overwrite` | Allow copied files to overwrite existing destination files. |

## Implementation rules

- Use `git ls-files` to compute file sets.
- Never parse `.gitignore` manually.
- Never copy `.git/`.
- Avoid copying nested worktrees, including the default `.worktrees/` directory and any configured `defaults.worktreesDir` that lives inside the source worktree.
- Handle files, directories, and symlinks.
- Use copy-on-write clone/reflink for regular files when the platform and filesystem support it; fall back to normal copy.
- When fallback first occurs, emit one highlighted stderr warning that regular copying is slower and may use additional disk space.
- Copy directories recursively so regular files inside directories can still use clone/reflink.
- Apply `defaults.copyExclude` to ignored and untracked selections before copying.
- Do not overwrite existing destination files unless `--overwrite` is set.

## Default stance

`defaults.copyLocal` is intentionally `false` by default. See [config defaults](config-defaults.md) for the rationale and future large-copy mitigation ideas.

## Configurable exclusions

`defaults.copyExclude` applies root-level Git-ignore patterns to `--copy-local`, `--copy-ignored`, `--copy-untracked`, and config-enabled local copying:

```toml
[defaults]
copyExclude = [".venv/", "node_modules/", "*.log"]
```

Patterns filter source paths before copying. Ordered `!` negation follows normal Git ignore rules but cannot re-enable built-in safety exclusions. Repo config replaces the global exclusion array. See [local copy exclusions](copy-exclusions.md) for the full contract and implementation details.
