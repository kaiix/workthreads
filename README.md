# workthreads

`workthreads` provides the `wt` CLI: a developer-first workflow tool for creating, preparing, listing, and deleting git worktrees.

## Setup

Prerequisites:

- Git
- Python 3.12+

Install the latest release from PyPI:

```bash
uv tool install workthreads
wt --help
```

Alternative user-level install without uv-managed tools:

```bash
python3 -m pip install --user workthreads
wt --help
```

For local development, install [`uv`](https://docs.astral.sh/uv/) and sync dependencies:

```bash
uv sync
```

Run the CLI from the repo during development:

```bash
uv run wt --help
```

Install the local checkout once so it is available globally on your PATH and you do not need to use `uv run` every time:

```bash
uv tool install -e .
wt --help
```

## Shell setup

Full shell integration includes completion, `wt add --cd`, and `wt cd` support:

```bash
eval "$(wt shell init zsh)"   # zsh
eval "$(wt shell init bash)"  # bash
wt shell init fish | source   # fish
```

Completion only:

```bash
eval "$(wt shell completion zsh)"
```

## Basic usage

Configure `wt` defaults for this repo:

```bash
wt config init
wt config edit
```

Repo configuration lives in `wt.toml` at the repository root. It can stay untracked for local workflow settings, or be committed only when the repo intentionally wants shared defaults. Use `wt config path` to print the active path.

By default, `wt add feature/payment-retry` creates `.worktrees/feature/payment-retry` under the repo root. `wt add` fetches the remote for the selected base ref when that remote is configured; use `--no-fetch` to skip this for one command.

Built-in workflow defaults:

```toml
[defaults]
fetch = true
copyLocal = true
deleteBranch = true

[shell]
cdAfterAdd = true
```

By default, `wt` infers the base from the repository. Set `defaults.base` to choose a ref or pass `--base` for one command. To override a global base and use inference in this repo, set `base = ""` in `wt.toml`.

Ignored and untracked files (including files like `.env`) are copied by default. Set `copyLocal = false` to opt out, or use `copyExclude = [".venv/", "node_modules/", ".cache/"]` to omit selected files from every copy mode. Each entry uses root-level Git-ignore semantics, including directory patterns, `**`, and ordered `!` negation. Repo config replaces the global exclusion array.

Create a worktree:

```bash
wt add feature/payment-retry
```

Create one at an exact path and copy ignored/untracked local files:

```bash
wt add feature/payment-retry \
  --base origin/main \
  --path ../external-worktrees/payment-retry \
  --copy-local
```

Full shell integration enters newly created worktrees by default. To stay in the current directory for one command:

```bash
wt add feature/payment-retry --no-cd
```

Jump to an existing worktree when shell integration is enabled:

```bash
wt cd payment-retry
```

`wt cd` accepts exact names and unique prefixes. For a worktree named `feat/foo`, both `wt cd feat` and `wt cd foo` can resolve it when unique. If `fzf` is installed, unresolved or ambiguous queries open a filtered picker instead of silently choosing a fuzzy match.

List worktrees:

```bash
wt list
```

Delete the current linked worktree:

```bash
wt delete
```

Delete a named worktree from elsewhere:

```bash
wt delete feature/payment-retry
```

`wt delete` also deletes the local branch by default, even if it has unmerged commits. Pass `--keep-branch` or set `defaults.deleteBranch = false` to keep it.

## Hooks

Configure lifecycle hooks:

```bash
wt hooks init
wt hooks edit post-create
```

Hooks receive stable `WT_*` environment variables such as `WT_EVENT`, `WT_REPO_ROOT`, `WT_WORKTREE_PATH`, `WT_BRANCH`, and `WT_BASE`.

Recommended repo-local hook script layout:

```text
.git/
  workthreads/
    hooks/
      post-create.sh
      pre-delete.sh
```

Use `wt hooks dir` or `wt hooks path post-create` to inspect the generated paths.

User-global hook scripts are also fine:

```text
~/.config/
  workthreads/
    hooks/
      post-create.sh
      pre-delete.sh
```

Shared hook scripts are possible, but should be intentional project policy rather than the default:

```text
scripts/
  wt/
    post-create.sh
    pre-delete.sh
```

## Development

Run tests:

```bash
uv run pytest
```

Run a quick CLI smoke check:

```bash
uv run wt
uv run wt shell completion zsh
```
