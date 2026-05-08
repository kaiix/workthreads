# Documentation structure

Status: active
Surface: repository docs
Verified against: docs/README.md, docs/notes/

This note defines how repository knowledge should be organized so agents and humans can find the right source of truth without loading one large manual.

## Principles

- Treat `docs/` as the durable repository knowledge base.
- Treat `docs/README.md` as the table of contents.
- Keep focused notes small enough to review and verify.
- Prefer progressive disclosure: map first, then detailed notes.
- Keep draft plans and exploratory notes under `.local/` until a decision should become durable repository knowledge.

## Metadata

Focused docs should start with a small metadata block:

```markdown
# wt config defaults

Status: active
Surface: config
Verified against: src/workthreads/config.py, tests/test_config.py
```

Use only these status values for now:

| Status | Meaning |
| --- | --- |
| `draft` | Under discussion; not authoritative. |
| `active` | Current source of truth. |
| `historical` | Kept for context, not authoritative. |

Use prose and links for deferred, rejected, or superseded decisions instead of adding more status values.

`Verified against` should point to the code, tests, or docs that make the note checkable. Active notes should include it when there is a concrete implementation to verify.

## Naming

Use short, domain-oriented filenames:

- `config-defaults.md`
- `tech-stack.md`
- `shell-integration.md`
- `delete-safety.md`

Do not repeat `workthreads` or `wt` in every filename. The repository and directory already provide product context. Use the product or command name in the document title when helpful.

Use a product prefix only when one directory contains docs for multiple products or when a doc is intended to be copied outside the repo.

## `.local/`

`.local/` is for workspace-local material that guides current work but is not durable repository knowledge.

- `.local/plans/`: implementation plans, migration plans, review plans, and task breakdowns.
- `.local/notes/`: research notes, exploratory analysis, comparisons, and temporary discussion material.

`.local/` is intentionally not tracked. In this checkout, `git check-ignore` reports `.local/` is ignored by a higher-level gitignore, so plans and notes there are local workspace artifacts rather than repository artifacts.

Promotion rule:

- If a `.local/` draft captures a durable decision, summarize the accepted decision in `docs/`.
- If it is only useful for the current task, leave it in `.local/`.
- Do not make agents depend on `.local/` for current product behavior; durable behavior belongs in `docs/` and tests.

## Future checks

A future docs check can verify that every `docs/notes/*.md` file is linked from `docs/README.md`, every note has a valid `Status`, active notes have `Verified against` when applicable, and internal links resolve.
