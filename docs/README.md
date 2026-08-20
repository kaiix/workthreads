# Repository docs

This directory is the system of record for durable workthreads design and implementation knowledge. Start here, then follow the focused notes for the surface you are changing.

Status metadata lives inside each linked document. See [documentation structure](notes/documentation-structure.md) for the metadata and `.local/` policy.

## Documentation process

### Docs structure

Document: [documentation-structure.md](notes/documentation-structure.md)

Use when changing how repository docs are organized, named, promoted, or verified.

## CLI overview

### CLI overview

Document: [cli-overview.md](notes/cli-overview.md)

Use when understanding the broad `wt` command model and where focused decisions live.

### CLI contracts

Document: [cli-contracts.md](notes/cli-contracts.md)

Use when changing stable outputs, success guarantees, bare `wt`, `wt list`, or exit codes.

## Config

### Defaults

Document: [config-defaults.md](notes/config-defaults.md)

Use when changing built-in config defaults, `wt config init`, config file location, or recommended local workflow.

## Shell

### Shell integration

Document: [shell-integration.md](notes/shell-integration.md)

Use when changing completion, `wt shell init`, `wt cd`, `--cd`, or auto-cd behavior.

## Paths and base refs

### Paths

Document: [paths.md](notes/paths.md)

Use when changing path resolution, generated worktree locations, base-ref inference, or fetch behavior.

## Local file copying

### Copying

Document: [local-file-copying.md](notes/local-file-copying.md)

Use when changing `--copy-local`, granular copy flags, overwrite behavior, or copy implementation.

### Copy exclusions

Document: [copy-exclusions.md](notes/copy-exclusions.md)

Use when implementing or changing `defaults.copyExclude`, its Git-ignore pattern semantics, config behavior, or copy filtering.

## Hooks

### Lifecycle hooks

Document: [hooks.md](notes/hooks.md)

Use when changing post-create/pre-delete hooks, hook locations, helper commands, or `WT_*` environment.

## Delete and cleanup safety

### Delete safety

Document: [delete-safety.md](notes/delete-safety.md)

Use when changing `wt delete`, dirty worktree checks, branch deletion, or delete target resolution.

### Failure cleanup

Document: [failure-cleanup.md](notes/failure-cleanup.md)

Use when changing `wt add --cleanup-on-failure` or partial-create cleanup behavior.

## Implementation

### Tech stack

Document: [tech-stack.md](notes/tech-stack.md)

Use when changing package layout, dependencies, development commands, or implementation guidelines.
