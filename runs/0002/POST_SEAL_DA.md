# Run 0002 — Post-Seal DA

Status: `APPEND-ONLY REVIEW`

The first seal froze records `r1-r25`. Subsequent review must not rewrite that prefix.

## F7 — seal self-reference recursion

Problem:

If every manifest/seal maintenance write must itself be appended to the same event chain, the observer creates an infinite recursion:

```text
append event
→ update manifest
→ append "manifest updated"
→ update manifest
→ ...
```

Resolution:

Seal/reseal metadata is integrity metadata about the chain and is not automatically a workload event inside that same chain. Git history or a separate seal lineage may preserve those maintenance operations when useful.

Material observer implementation changes may still be captured as ordinary events during dogfood.

## F8 — human-readable timeline mixed source and interpretation

Problem:

The retrospective timeline used wording such as `promoted` in the evidence table. A Git merge is a source fact; semantic Ultimate Loop promotion is an interpretation that requires its own evidence/decision boundary.

Resolution:

The timeline now reports commit/PR merge facts first and places the Ultimate Loop interpretation in an explicitly derived section.

## Result

Both findings were discovered **after** first seal and resolved without rewriting records `r1-r25`.

This is the first direct dogfood check that the post-seal correction model works as intended:

```text
SEALED PREFIX STAYS FIXED
NEW FINDING → NEW CHANGE → NEW EVENT → RESEAL HEAD
```
