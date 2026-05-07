# workthreads

`workthreads` provides the `wt` CLI: a developer-first workflow tool for creating, preparing, listing, and deleting git worktrees.

## Setup

Prerequisites:

- Git
- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)

Install dependencies for local development:

```bash
uv sync
```

Run the CLI from the repo during development:

```bash
uv run wt --help
```

Install `wt` once so it is available globally on your PATH and you do not need to use `uv run` every time:

```bash
uv tool install -e .
wt --help
```

Alternative user-level install without uv-managed tools:

```bash
python3 -m pip install --user -e .
wt --help
```

## Shell setup

Full shell integration includes completion and `wt add --cd` support:

```bash
eval "$(wt init zsh)"   # zsh
eval "$(wt init bash)"  # bash
eval "$(wt init fish)"  # fish
```

Completion only:

```bash
eval "$(wt completion zsh)"
```

## Basic usage

Configure `wt` defaults for this repo:

```bash
wt config set defaults.base origin/main
wt config set defaults.copyLocal true
```

Repo configuration is written to `wt.toml` at the repository root. It can stay untracked for local workflow settings, or be committed only when the repo intentionally wants shared defaults.

By default, `wt add feature/payment-retry` creates `.worktrees/feature/payment-retry` under the repo root.

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

Create and enter the new worktree when shell integration is enabled:

```bash
wt add feature/payment-retry --cd
```

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
uv run wt completion zsh
```
