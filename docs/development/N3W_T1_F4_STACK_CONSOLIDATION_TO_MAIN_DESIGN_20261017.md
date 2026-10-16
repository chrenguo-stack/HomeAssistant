# N3-W T1 F4 stack consolidation to main — design

Date: 2026-10-17

```text
TASK=N3W_T1_F4_STACK_CONSOLIDATION_TO_MAIN_DESIGN_20261017_01
RESULT=CLOSED_PASS_READY_FOR_PREPARATION_GATE

MAIN_BASE=b12c69be5c1d1d61887e9be4a776f575141d44c6

PRODUCT_SOURCE_AUTHORITY=19bd98386c4828c0768f2f3936429db8c7a59adf
PRODUCT_SOURCE_AUTHORITY_TREE=f5b66faf690c88d655e01ffc0a5d5ef122b589af
PRODUCT_SOURCE_REVIEW=PASS
PRODUCT_SOURCE_CI=PASS:13/13

IMMUTABLE_EVIDENCE_AUTHORITY=62f2a107d834b31b498e230ee68f66833580f4c5
IMMUTABLE_EVIDENCE_AUTHORITY_TREE=1a2cb562a75d295e3e3296ba3ea5cfbb0dd1ca4a
IMMUTABLE_EVIDENCE_AUTHORITY_CI=PASS:13/13

PAYLOAD_MANIFEST=docs/development/N3W_T1_F4_STACK_CONSOLIDATION_PAYLOAD_MANIFEST_20261017.json
PAYLOAD_FILE_COUNT=63
PRODUCT_SOURCE_FILE_COUNT=19
IMMUTABLE_EVIDENCE_FILE_COUNT=44
MUTABLE_LEDGER_FILE_COUNT=3

CURRENT_F4_DURABLE_LEDGER=REBOOT_ACCEPTED
KF_121_DURABLE_LEDGER_BLOCKER=CLOSED_PASS

HISTORICAL_CHERRY_PICK=false
HISTORICAL_PR_CHAIN_DIRECT_MERGE=false
SIDE_BRANCH_SOURCE_IMPORT=false

CONSOLIDATION_BRANCH_CREATED=false
CONSOLIDATION_PR_CREATED=false
MAIN_MUTATION=false
MERGE=false
BOARD_ACCESS=false
T1_MUTATION=false

NEXT_ONE_GATE=N3W_T1_F4_STACK_CONSOLIDATION_TO_MAIN_PREPARATION_20261017_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

## 1. Design goal

The goal is to integrate the final accepted F4 state into current `main` without replaying the hundreds of historical
experimental commits and without merging the old draft PR stack one PR at a time.

The consolidation will create a fresh branch from the exact current main base and overlay only exact, already-reviewed
F4 blobs.

The historical PRs remain in GitHub as development evidence. They are not used as the integration mechanism.

## 2. Authority split

The consolidation intentionally uses two different authorities.

### Product source authority

All runtime, tool, test, workflow and infrastructure files come from exact reviewed source:

```text
19bd98386c4828c0768f2f3936429db8c7a59adf
```

There are exactly 19 product-source files in the frozen payload. Their blob SHAs on the current F4 branch were
independently compared with the reviewed source head and all 19 are byte-identical.

No later documentation commit is allowed to become a new product-source authority.

### Immutable evidence authority

The durable F4 evidence documents that are not mutable project ledgers come from:

```text
62f2a107d834b31b498e230ee68f66833580f4c5
```

There are exactly 44 immutable evidence files in the frozen payload manifest.

### Mutable project ledgers

These three files are intentionally excluded from the immutable payload manifest:

```text
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
```

They continue to evolve while consolidation is prepared. Their exact blob SHAs must be frozen in the next preparation
gate immediately before the consolidation branch is built.

## 3. Exact payload construction

The frozen manifest contains 63 exact payload entries:

```text
19 product-source files
44 immutable evidence files
63 total immutable payload files
```

The implementation must not cherry-pick historical commits. It must instead create a new branch directly from current
main and overlay the exact blobs listed in the manifest.

Conceptually:

```text
fresh current main tree
+ exact 19 product blobs from reviewed source
+ exact 44 immutable evidence blobs
+ exact 3 mutable ledger blobs frozen in preparation
+ consolidation design / manifest / preparation metadata
= consolidation candidate tree
```

This preserves current main outside the explicit allowlist and prevents unrelated historical branch state from being
pulled into main.

## 4. Recommended commit structure

Use a small, reviewable sequence rather than replaying old history.

### Commit A — exact product snapshot

Apply only the 19 product-source blobs from the reviewed source authority.

Requirements:

- exact path set;
- exact blob SHA;
- exact executable/file mode;
- no documentation;
- no file outside the product allowlist.

### Commit B — durable F4 evidence snapshot

Apply:

- the 44 immutable evidence blobs from the manifest;
- the three freshly frozen mutable ledger blobs;
- the consolidation design and payload manifest;
- the preparation/closure metadata created by the consolidation gate.

No side-branch source is imported.

The final PR to main is then reviewed as a compact tree integration rather than as a replay of 272 historical commits.

## 5. Tree-equivalence proof

Before any merge decision, the consolidation PR must prove all of the following.

### Product proof

For every one of the 19 product paths:

```text
consolidation blob SHA
==
reviewed source blob SHA at 19bd9838...
```

The complete product path set must also match the manifest exactly.

### Evidence proof

For every immutable evidence path:

```text
consolidation blob SHA
==
frozen evidence blob SHA in the manifest
```

The three mutable ledgers must match the exact preparation-gate blobs.

### Main-preservation proof

Every repository path not in the consolidation allowlist must remain exactly equal to the fresh main base.

No hidden deletion, rename or unrelated source import is permitted.

### Scope proof

The final main-to-consolidation diff must contain only:

- F4 workflows;
- F4 infrastructure/systemd material;
- F4 tools;
- F4 tests;
- F4 durable evidence;
- the three project ledgers;
- consolidation metadata.

## 6. CI and source review

The consolidation candidate must run the normal repository CI from its own new commit SHA.

At minimum the review must require:

- N3W T1 F4 activation source CI;
- N3W T1 F4 exact control package;
- Public repository safety CI;
- greenhouse-manager CI;
- all other workflows normally triggered by the PR.

Green CI alone is not sufficient. After CI, perform a focused tree-equivalence review against the manifest and the
reviewed source authority.

Because the consolidation commit has a new Git SHA, any newly generated exact artifact will naturally bind to the new
source head. Byte-identical source files do not imply a byte-identical source-head field in a newly built artifact.
Therefore artifact source-head differences are expected and are not source drift.

## 7. Historical PR treatment

The old draft PRs are retained as historical evidence and are not the merge mechanism.

The direct ancestry suffix:

```text
#595 -> #596 -> #597 -> #598 -> #599 -> #600 -> #605
```

is only part of the larger historical F4 development graph.

PRs #601-#604 form a documentation/live-execution side path from #600. Their unique files are not referenced by the
current authoritative ledgers and are not required in the frozen payload.

PR #606 is another historical forensic documentation branch and is likewise not an ancestor of the accepted #605
tree.

PR #607 contains an alternative postclaim-recovery source path. That source is explicitly excluded from consolidation:
the accepted current implementation instead uses the source-reviewed and live-exercised recovery logic integrated in
`tools/n3w_t1_f4_reboot_authority.py`. Importing #607 would introduce source that was not part of the final accepted
F4 source authority.

After a future consolidation merge, closing old draft PRs as superseded is a separate repository-cleanup decision.

## 8. Merge boundary

This design authorizes no branch creation and no merge.

The next gate may:

1. fresh-rebind main;
2. freeze the three mutable ledger blob SHAs;
3. verify the 63-file payload manifest against both authorities;
4. define the exact new branch name and target PR;
5. prepare the exact two-commit tree construction;
6. STOP before creating or merging anything unless that gate explicitly authorizes branch creation.

```text
NEXT_ONE_GATE=N3W_T1_F4_STACK_CONSOLIDATION_TO_MAIN_PREPARATION_20261017_01
AUTO_EXECUTE_NEXT_GATE=false
MERGE=false
```
