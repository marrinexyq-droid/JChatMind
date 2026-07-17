# Domain docs

This repository uses a single-context domain-documentation layout.

## Before exploring

Read the following sources when they exist and are relevant to the work:

- `CONTEXT.md` at the repository root for the domain glossary and context.
- ADRs under `docs/adr/` that affect the area being changed.

If these files do not exist, proceed silently. Do not propose creating them up front. Domain-modeling workflows create them lazily when terminology or architectural decisions are resolved.

## Expected layout

```text
/
├── CONTEXT.md
├── docs/adr/
└── ...
```

Use the vocabulary defined in `CONTEXT.md` in issues, tests, proposals, and implementation names. If required language is missing, record the gap for domain modeling instead of inventing competing synonyms.

If proposed work conflicts with an existing ADR, identify the conflict explicitly rather than silently overriding the decision.
