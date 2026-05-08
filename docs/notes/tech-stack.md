# wt implementation tech stack

Status: active
Surface: implementation
Verified against: pyproject.toml, src/workthreads/, tests/

## Purpose

This document defines the implementation stack for the workthreads `wt` CLI. It is intentionally separate from the product and command design so workflow decisions and implementation decisions stay easy to review separately.

## Stack Choices

The first implementation should use a Python CLI stack that is easy to install, test, and iterate on.

| Area | Choice | Notes |
| --- | --- | --- |
| Language | Python | Prefer straightforward standard-library process and filesystem handling, with typed internal boundaries where useful. |
| Project metadata | `pyproject.toml` | Single source for package metadata, dependencies, console script entry point, pytest config, and tool config. |
| Environment and dependency manager | `uv` | Use `uv sync` for development setup and `uv run ...` for local commands/tests. |
| Test runner | `pytest` | Unit-test command parsing, git command orchestration, path resolution, file copy behavior, hook behavior, shell integration, and workflow contracts. |
| Terminal formatting | Rich | Use Rich for human-readable tables and terminal output while keeping stable plain-text command contracts. |
| Source layout | `src/` based layout | Put importable code under `src/workthreads/` to avoid accidental imports from the repo root. |

## Recommended Layout

```text
pyproject.toml
src/
  workthreads/
    __init__.py
    __main__.py
    cli.py
    config.py
    git.py
    hooks.py
    metadata.py
    output.py
    paths.py
    shell.py
    copy.py
    errors.py
tests/
  test_cli_contracts.py
  test_config.py
  test_paths.py
  test_copy.py
  test_hooks.py
  test_hooks_helpers.py
  test_cd.py
  test_workflows.py
```

## Console Entry Point

```toml
[project.scripts]
wt = "workthreads.cli:main"
```

## Development Commands

```bash
uv sync
uv run wt --help
uv run pytest
```

## Implementation Guidelines

- Keep command parsing thin; put workflow logic in testable modules.
- Keep git interactions behind a small adapter so tests can use fake command runners.
- Keep human output readable and preserve stable plain-text contracts where commands are scripted.
- Use Rich only for terminal-facing output; never make scripts depend on Rich formatting.
- Prefer explicit errors with suggested next actions over generic tracebacks.
- Model workflows as staged operations so failures can report the exact stage and cleanup can be precise.
