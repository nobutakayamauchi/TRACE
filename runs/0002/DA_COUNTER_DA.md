# Run 0002 — TRACE Observer Integration DA / Counter-DA

Status: `PRE-SEAL REVIEW`

## Frozen workload

Attach TRACE to Ultimate Loop so that:

1. the WebAI-Bridge run up to attachment can be reconstructed honestly;
2. future material transitions can be captured live;
3. TRACE does not become a governor or promotion authority;
4. source evidence remains distinct from interpretation;
5. missing or conflicting evidence cannot become silent success;
6. the observer remains replaceable.

## Raison d'être result

### DROP?

Rejected. Git history alone does not reliably preserve human decisions, rejected findings, UNKNOWN/CONFLICT states, why gates reopened, or the exact boundary where code-only evidence stopped being sufficient.

### EXTERNALIZE / COMPOSE?

Accepted in part. Do not build a new Ultimate Loop telemetry platform. Reuse the existing TRACE responsibility and GitHub as source evidence.

### IRREDUCIBLE BUILD

Only a thin observation contract and run profile survive. No new orchestration runtime, UI, database, cloud service, or governor is authorized.

## METEOR comparison

### Candidate A — Git history only

Pros: zero new machinery.

Failure: insufficient reconstruction of non-code decisions and evidence semantics.

### Candidate B — new custom Ultimate Loop observer runtime

Pros: maximum control.

Failure: duplicates TRACE responsibility, increases monolith risk, and violates reuse-first pressure.

### Candidate C — TRACE passive adapter/profile

Pros: reuses existing source/derived distinction, uncertainty preservation, integrity model and reconstruction mission while keeping Ultimate Loop independent.

Result: **Candidate C survives the bounded workload.**

## DA findings

### F1 — SHA without repository context

Problem: early GitHub event payloads named commit SHA but not the repository on every record. Future reconstruction could become ambiguous across repositories.

Resolution: require `repository + sha` for durable Git source identity and rebuild the pre-seal chain.

### F2 — source event overstated semantic promotion

Problem: a Git commit/merge can establish repository state, but `PROMOTED` is an Ultimate Loop semantic interpretation. Treating the commit itself as promotion collapses source evidence into a derived claim.

Resolution: source records use `MERGE_RECORDED` / `CHANGE_RECORDED`; promotion interpretation belongs in a derived record with source references.

### F3 — actor was invented

Problem: bootstrap records used `actor: system` even where GitHub metadata did not establish a specific actor in the captured snapshot.

Resolution: unknown actor stays null/UNKNOWN. Do not manufacture an actor.

### F4 — append-only claim conflicted with bootstrap correction

Problem: the initial dogfood chain was edited during its own DA pass. Calling it append-only without a lifecycle boundary would be false.

Resolution: introduce `BUILDING → FIRST SEAL → APPEND-ONLY`. Before first seal, capture/schema corrections may regenerate the draft chain. After first seal, existing records freeze and corrections must be appended as new records.

### F5 — observer could accidentally become authority

Problem: if TRACE status were used as a mandatory success gate everywhere, an evidence recorder could silently become a controller and single point of failure.

Resolution: `TRACE OBSERVER != GOVERNOR`. Observer loss degrades reconstructability. A workload may explicitly require observation, but TRACE has no global promotion/veto authority.

### F6 — hidden reasoning temptation

Problem: a high-speed AI development run may tempt the archive to claim it preserved the model's internal reasoning.

Resolution: hidden chain-of-thought is explicitly excluded. Preserve only visible rationale, tool evidence, decisions, findings, diffs, tests and outcomes that actually exist as source evidence.

## Counter-DA result

No release-blocking contradiction remains inside the bounded observer-integration workload after the above changes, provided the first seal is created only after the source/derived semantics are corrected.

External limitations remain explicit:

- current chat capture is not independently timestamp-notarized;
- GitHub history does not expose hidden model reasoning;
- code/test history does not prove live production behavior;
- TRACE v0 hash-chain consistency is not independent notarization.

## Gate

`READY_FOR_FIRST_SEAL` after the final pre-seal chain rebuild and manifest verification.
