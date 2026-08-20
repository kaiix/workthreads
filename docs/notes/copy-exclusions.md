# Local copy exclusions

Status: active
Surface: local file copying, config
Verified against: src/workthreads/config.py, src/workthreads/git.py, src/workthreads/copy.py, src/workthreads/cli.py, tests/test_config.py, tests/test_copy.py, tests/test_workflows.py

This note defines configurable local-copy exclusions.

## Decision

Use a list-valued config key for files that must not be copied by local-copy operations:

```toml
[defaults]
copyLocal = true
copyExclude = [
  "node_modules/",
  ".cache/",
  "*.log",
  "/tmp/",
]
```

Use `copyExclude`, not `copyLocalExclude`, because the setting applies to every local-copy mode. Do not use a bare `exclude` key because its scope would be ambiguous in the `[defaults]` table.

## Scope

`defaults.copyExclude` applies whenever any of these modes select files:

- `--copy-local`
- `--copy-ignored`
- `--copy-untracked`
- `defaults.copyLocal = true`

The patterns filter ignored and untracked source paths before copying. They do not affect tracked files, Git ignore configuration, or files outside the source worktree.

The feature is config-only. Do not add a CLI `--copy-exclude` flag until a concrete one-off exclusion use case justifies it.

## Pattern semantics

Each array entry is one Git-ignore pattern interpreted relative to the source worktree root. Use the same behavior developers expect from a root-level `.gitignore`:

- `*.log` matches at any depth.
- `node_modules/` matches directories with that name.
- `/tmp/` matches only the root `tmp` directory.
- `**` supports recursive matching.
- `!` negates an earlier pattern, subject to normal Git ignore rules.
- Pattern order is significant.
- Patterns use `/` as the separator on every platform.

Git should interpret these patterns. Do not add an independent Python glob or `.gitignore` parser.

## Precedence

Configuration keeps the existing precedence:

```text
repo config > global config > built-in default
```

The built-in value is an empty array. A repo-level array replaces the global array rather than merging with it; this matches the existing config override model and avoids special-case list behavior.

## Safety invariants

Existing safety exclusions remain unconditional:

- `.git`
- `.worktrees`
- `.workthreads`
- The configured worktree directory when it is inside the source worktree.
- Existing nested worktrees.

A negated `copyExclude` pattern must not re-enable any safety-excluded path.

Exclusions must be resolved before file copying starts. Unwanted files must never be copied temporarily and then deleted by a hook.

## Implementation

Keep Git responsible for both candidate discovery and exclusion matching:

1. Select ignored files with the existing standard-ignore query.
2. Select untracked files with the existing query.
3. When `copyExclude` is non-empty, run a separate `git ls-files --others --ignored` query using only the configured `--exclude` patterns.
4. Subtract those matched paths from both candidate sets.
5. Apply the existing unconditional path exclusions and copy the remaining paths.

This preserves Git-ignore semantics, including ordered negation, without adding a matching dependency. The extra Git query should be skipped for an empty pattern list.

## Config behavior

The config layer:

- Defines `defaults.copyExclude = []` in built-in defaults and the generated template.
- Uses a typed string-list getter.
- Rejects a scalar or an array containing non-string values when assigned with `wt config set` or used by local copying.
- Reads and writes TOML arrays without converting them to strings.
- Preserves arrays when another key is changed with `wt config set` or `wt config unset`.

Assign the key directly with TOML array syntax:

```bash
wt config set defaults.copyExclude '["node_modules/", ".cache/", "*.log"]'
```

## Output and tests

The feature does not change the stable `wt add` output. Excluded paths simply do not contribute to copied-file counts.

Tests cover:

- Ignored and untracked exclusions.
- Directory, wildcard, recursive, and root-anchored patterns.
- Ordered negation.
- All three local-copy flags and `defaults.copyLocal`.
- Safety exclusions remaining non-negatable.
- Invalid config value types.
- TOML array parsing, serialization, and repo/global precedence.
- An end-to-end `wt add` workflow that copies required local files while omitting excluded files.
