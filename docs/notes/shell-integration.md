# Shell integration

Status: active
Surface: shell integration
Verified against: src/workthreads/shell.py, src/workthreads/cli.py, tests/test_cd.py, tests/test_cli_contracts.py

## Commands

```bash
wt shell completion bash
wt shell completion zsh
wt shell completion fish

wt shell init bash
wt shell init zsh
wt shell init fish
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
eval "$(wt shell completion zsh)"
```

Full shell integration:

```bash
eval "$(wt shell init zsh)"
```

## Directory switching

`wt add` itself does not change the current directory. A standalone process cannot change the parent shell's cwd, so directory switching is a shell integration feature.

Rules:

- `wt add <branch>` creates the worktree and prints its path, but does not change directories without shell integration.
- `wt add <branch> --cd` requests "create it, then enter it" and only works through shell integration.
- Without active shell integration, `wt add --cd` fails with exit code `2` and a fixable hint.
- `shell.cdAfterAdd = true` behaves like implicit `--cd` only in interactive shell integration.
- `wt add --no-cd` disables `shell.cdAfterAdd` for one command.

Helpful failure when `--cd` is used without shell integration:

```text
error: --cd requires shell integration
hint: run `eval "$(wt shell init zsh)"` or use `cd "$(wt add feature/foo | tail -n 1)"`
```

## Wrapper behavior

`wt shell init <shell>` installs completion and a small shell wrapper that delegates to the real binary. The wrapper is responsible for changing directories after a successful `wt add --cd`, `wt cd`, or when `shell.cdAfterAdd` is enabled.

The wrapper should not pipe all `wt` output through `tee` or command substitution. Interactive commands such as `wt hooks edit` must keep direct access to the terminal. For cd handoff, the wrapper passes a temporary `WT_CD_FILE`; `wt add` writes the target path there after success, and the wrapper reads it to `cd`.

## `wt cd`

`wt cd [target]` navigates to an existing worktree when shell integration is enabled. Without shell integration, it prints the resolved path so users can still run:

```bash
cd "$(wt cd foo)"
```

Target resolution order:

1. Exact branch/name/path match.
2. Full-key prefix, such as `feat` for `feat/foo`.
3. Segment-prefix, such as `foo` or `fo` for `feat/foo` when unique.
4. Optional `fzf` picker for unresolved or ambiguous queries when `fzf` is installed and the shell is interactive.
5. Usage error with candidates or a `wt list` hint.

Deterministic `wt cd <target>` should not silently use arbitrary substring matching. For example, `wt cd oo` should not automatically choose `feat/foo`. If `fzf` is available, `wt cd oo` can open a picker prefilled with `oo` so the user confirms the fuzzy match.

Successful shell-integrated `wt cd <target>` should be quiet like the shell builtin `cd`. If shell integration is not active, success output is the destination path.

## Target experience

- `wt add <tab>` completes branch/base candidates.
- `wt delete <tab>` completes existing worktrees.
- `wt config <tab>` completes config actions.
- `wt cd foo<tab>` completes existing worktrees using full-prefix and segment-prefix matching.
- `wt add --cd` changes the interactive shell cwd after successful creation.
- `wt cd <target>` changes the interactive shell cwd to an existing worktree.
- `shell.cdAfterAdd = true` makes successful interactive `wt add` enter the new worktree by default.
- `wt add --no-cd` keeps the shell in place even when auto-cd is enabled.
