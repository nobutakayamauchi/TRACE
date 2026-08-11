# TRACE_BOOTSTRAP.md

Codex: このファイル全体を仕様として読み、TRACE v0.1 を実装してください。

優先順位:
1. SPEC
2. ACCEPTANCE TESTS
3. CODEX TASK

RTSを再実装しないこと。
最小構成を優先し、外部/標準コンポーネントで代替できる責務を抱え込まないこと。
実装後は破壊テストまで実行し、結果を報告すること。


<!-- BEGIN SPEC.md -->
# TRACE — SPEC.md
Version: 0.1
Status: Bootstrap / Minimum Working Core

## Mission
TRACE is not a resurrection of RTS.

TRACE preserves the responsibilities that survived the RTS postmortem:
- preserve what actually happened;
- preserve the boundary between evidence and interpretation;
- preserve human intent, decisions, actions, outcomes, corrections, and uncertainty;
- allow a third party to reconstruct history after the original runtime, AI session, index, or operator memory is gone;
- fail closed when evidence is missing or conflicting;
- prefer generic/external components over custom infrastructure.

Core chain:

Conversation → Proposal → Human Intent → Decision → Evidence → Action → Outcome → Correction

## Non-goals
TRACE MUST NOT:
- recreate RTS;
- become a custom orchestration runtime;
- become a controller/governance kernel;
- require a specific AI model or database;
- treat source-code existence as runtime evidence;
- treat a derived claim or summary as authoritative evidence;
- silently resolve UNKNOWN or CONFLICT;
- infer chronology from physical file order alone;
- build a UI in v0.1;
- build its own cloud/provider stack;
- solve legal identity, independent notarization, or trusted timestamping in v0.1.

If a generic component can satisfy a responsibility, use it.

## Evidence model
Two authority classes exist.

### Source Evidence
Source evidence is the highest-authority material TRACE possesses.

Examples:
- human-visible conversation messages;
- tool outputs;
- files;
- Git commits/diffs;
- runtime/deployment probes;
- test outputs;
- explicit human decisions.

Preserve when available:
- record_id
- source_type
- actor
- source_order
- source_timestamp
- captured_at
- payload
- payload_sha256
- previous_record_hash
- record_hash
- provenance
- uncertainty

Missing values remain null/UNKNOWN rather than invented.

### Derived Records
Derived records may include claims, summaries, semantic event records, indexes, reconstructed causal links, and classifications.

Derived records MUST:
- identify themselves as derived;
- cite source record IDs;
- never overwrite source evidence;
- remain rebuildable from source evidence;
- support SUPPORTED / INFERRED / UNKNOWN / CONFLICT.

A label such as SUPPORTED is not evidence by itself.

## Ordering
Preserve separately:
1. source_order — order material entered the archive;
2. source_timestamp — timestamp claimed by the source.

If they disagree, preserve the disagreement. Never silently rewrite one to match the other.

## Runtime invariant
Code existence != runtime evidence.

Before classifying an implementation as active runtime, establish Deployment Identity using available evidence such as:
- service/unit;
- working directory;
- executable/module;
- active route;
- deployed commit/revision.

If identity cannot be established, classification is UNKNOWN.

## Storage
Minimum v0.1 layout:

trace/
  raw/events.jsonl
  derived/claims.jsonl
  integrity/manifest.json
  index/trace.sqlite
  exports/
  tools/

Requirements:
- raw/events.jsonl is append-only in normal operation;
- each source record has SHA-256 content integrity;
- records form a forward hash chain;
- manifest records file hashes and archive metadata;
- SQLite is disposable and rebuildable;
- no truth exists only in SQLite;
- export works without SQLite.

## Recoverability
A third party with only raw source records and integrity metadata must be able to:
- verify surviving records;
- rebuild the index;
- locate records for an episode;
- distinguish source evidence from derived claims;
- identify missing evidence;
- preserve conflicts;
- answer future questions not known when records were captured.

Optional if implementation remains small:
- chunked redundancy;
- multiple independent archive copies;
- Merkle root over sealed export.

Do not add them if they substantially complicate the core.

## Capture policy
Capture enough for future reconstruction, not merely today's known question.

Promote to source evidence when a record establishes or changes:
- intent;
- decision;
- authority;
- deployment/runtime identity;
- external communication;
- consent/permission boundary;
- action;
- test result;
- failure;
- correction;
- uncertainty;
- provenance;
- causal explanation.

Hidden model chain-of-thought is out of scope. Visible assistant rationale may be captured if explicitly emitted.

## Trust boundaries
TRACE integrity proves consistency of the archive TRACE possesses.

It does not by itself prove:
- legally verified human identity;
- independently witnessed timestamp;
- remote delivery/read;
- absence of malicious fabrication by an authorized recorder;
- absence of total archive replacement before an external anchor.

Those require external trust services.

## v0.1 Done Condition
TRACE v0.1 is complete only when:
1. source records can be appended;
2. hash-chain verification passes;
3. derived claims cite source records;
4. SQLite can be deleted and rebuilt;
5. mutation, deletion, and reordering are detected where detectable;
6. conflicting claims do not silently become canonical truth;
7. missing evidence remains UNKNOWN;
8. an archive export can be reconstructed after destructive testing;
9. the implementation remains small and dependency-light;
10. no RTS runtime/controller/governance code is recreated.
<!-- END SPEC.md -->

<!-- BEGIN ACCEPTANCE_TESTS.md -->
# TRACE — ACCEPTANCE_TESTS.md

TRACE v0.1 is accepted only if all mandatory tests pass.

## A. Baseline
Append at least 20 mixed source records, verify integrity, create derived claims, query all three fixture episodes, and export.
Expected: PASS.

## B. Mutation
Modify one byte inside an existing raw source record.
Expected:
- verification FAILS;
- affected record or chain position is identified;
- no silent repair.

## C. Deletion
Delete one raw source record from the middle of the chain.
Expected:
- verification FAILS;
- chain discontinuity is detected.

## D. Reordering
Swap two raw records.
Expected:
- verification FAILS when chain/order metadata makes this detectable;
- TRACE does not silently normalize the file.

## E. Derived false history
Inject derived claims saying:
- source existence proves ACTIVE_RUNTIME;
- rev-B was confirmed running despite a rev-A deployment probe;
- a local Discord send proves remote delivery/read;
- send equals consent to begin analysis;
- a follow-up occurred despite day-7 source evidence saying followups=0;
- only change-A was fixed although source evidence records A+B;
- propagated regression failed although source test output says PASS.

Expected:
- none becomes canonical merely because repeated, hashed, or labeled SUPPORTED;
- conflicts are surfaced;
- source evidence remains separately inspectable.

## F. UNKNOWN preservation
Remove evidence needed to establish exact active runtime, remote delivery/read, and recipient consent.

Expected:
- answers become UNKNOWN or bounded inference;
- TRACE does not invent a value.

## G. Timestamp anomaly
Create source_order 18 then 19 with timestamps Aug 10 then Aug 5.

Expected:
- both survive;
- anomaly is surfaced;
- neither order nor timestamp is silently rewritten.

## H. Index destruction
Delete trace.sqlite completely.

Expected:
- rebuild-index recreates it from source/derived JSONL;
- no canonical information is lost;
- queries return materially identical results.

## I. Blob substitution
If source records reference external files, replace one with different bytes.

Expected:
- hash verification fails.

## J. Archive-copy recovery
Copy the archive, destroy one working copy, and restore from another copy/export.

Expected:
- verifier passes on the intact copy;
- rebuild works without the destroyed runtime/index.

## K. Future-question test
After the fixture is sealed, ask questions not encoded as fields in advance:
- Why was runtime left UNKNOWN?
- What exactly was established about the Discord contact?
- Why did review correction propagate from A to B?
- Which facts remain unresolved?

Expected:
- answers can be reconstructed from preserved source evidence and derived links;
- no schema change to sealed raw records is required.

## L. Anti-SimCity test
FAIL if v0.1 introduces any of the following without a demonstrated requirement:
- custom job scheduler;
- custom orchestration runtime;
- custom agent framework;
- web dashboard;
- bespoke database engine;
- provider-specific memory backend;
- governance kernel;
- generalized plugin platform.

The core should remain comprehensible to a third party in one sitting.

## Final acceptance
PASS only if:
- A through K pass;
- L does not fail;
- all false-history families remain non-canonical;
- UNKNOWN/CONFLICT behavior is preserved;
- SQLite can be destroyed and rebuilt;
- core source-of-truth remains ordinary inspectable files.
<!-- END ACCEPTANCE_TESTS.md -->

<!-- BEGIN CODEX_TASK.md -->
# TRACE — CODEX_TASK.md

You are implementing TRACE v0.1.

Read SPEC.md and ACCEPTANCE_TESTS.md first.

## Primary instruction
Do not recreate RTS.

Implement the minimum system that preserves the responsibilities proven necessary by the RTS postmortem. Prefer generic/external components and standard formats over custom infrastructure.

## Build target
Implement a small CLI-first archive with:
- append-only source event JSONL;
- SHA-256 content hashing;
- forward record hash chain;
- manifest generation/verification;
- derived claim records that cite source record IDs;
- rebuildable SQLite index;
- query by record ID, actor, source type, status, text, and time;
- archive export;
- verifier;
- destructive acceptance-test fixtures.

Use the Python standard library whenever practical.

Suggested CLI:

python -m trace append --source-type human --actor user --payload-file x.txt
python -m trace claim --status SUPPORTED --source REC-... --text "..."
python -m trace verify
python -m trace rebuild-index
python -m trace query --text "deployment identity"
python -m trace export --out export/
python -m trace selftest

Naming may differ if a cleaner minimal design emerges.

## Hard invariants
- Raw source records are authoritative relative to derived records.
- Derived claims never overwrite source evidence.
- SQLite is disposable.
- Unknown facts remain UNKNOWN.
- Conflicts remain CONFLICT.
- source_order and source_timestamp are independent.
- source existence is never enough to establish ACTIVE_RUNTIME.
- do not infer remote delivery/read/consent from a local send;
- do not invent missing history;
- do not use physical slot/file order as authority when explicit ordering metadata exists;
- hidden model chain-of-thought is out of scope;
- do not create a web UI;
- do not create a custom runtime/controller/governance kernel;
- do not add cloud infrastructure.

## Implementation constraints
Aim for a core small enough to audit quickly.

Prefer:
- Python 3
- JSONL
- SQLite
- hashlib
- pathlib
- argparse
- deterministic serialization

Avoid dependencies unless they materially reduce code or correctness risk.

## Required fixtures
Create a deterministic fixture with three episodes:

1. Runtime identity mismatch:
   repo rev-B exists, deployment probe says rev-A, classification must remain UNKNOWN.

2. Permission-first outreach:
   local send exists; delivery/read/response/consent do not.

3. Review propagation:
   defect found in A, same family found in B, both fixed/tested, regression PASS.

Create contradictory derived claims for each episode so the verifier/query layer can demonstrate that repeated or labeled claims do not outrank source evidence.

## Required output before stopping
- working implementation;
- README with exact commands;
- architecture note no longer than one page;
- deterministic self-test;
- acceptance-test report;
- line count for core implementation;
- list of responsibilities intentionally deferred.

Do not spend time polishing presentation.

When a design choice is ambiguous, choose the smaller design that preserves the invariants.
<!-- END CODEX_TASK.md -->
