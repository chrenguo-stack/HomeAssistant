# N3-W P4 T1 — R3 whole-inspect SHA drift: exact evidence, stable shadow source-only repair and R4 stop boundary

## 1. Grounded read-only T1 result

After the R3 one-shot STOP, the user ran a read-only comparator using the exact staged R3 scripts and reported:

```text
R3_PRIVATE_ROOT_COUNT=1
R3_TRANSACTION_EXISTS=false
R3_SEAL_EXISTS=true
R3_SEAL_SYMLINK=false
R3_SEAL_MODE_0600=true
R3_SAVED_SEAL_READ=PASS
R2_LIVE_REVERIFY=PASS
R3_SEAL_DIFFERENCE_COUNT=1
DIFF_FIELD=r2_shadow_inspect_sha256
R3_SEAL_EXTRA_FIELD_COUNT=0
R3_SEAL_COMPARISON=MISMATCH
READ_ONLY_FORENSIC=COMPLETE
```

Earlier T1 evidence: `R3_TRANSACTION_STATE=ABSENT`; old Manager running by original container identity; Broker running, original ID, start and restart count unchanged; deployed R3 systemd process STOP `R3_FORENSIC_SEAL_INVALID`. R2 rollback PASS and its shadow remains stopped and intact.

These facts prove that the saved seal differs from current `verify_r2` **only at the digest of the entire `docker inspect` JSON document**. They do **not** reveal which inner field changed, because the legacy seal stores only the digest rather than a copy of the whole inspect document. Do not attribute the exact delta to a particular mutable field without evidence.

## 2. Exact R3 source diagnosis

Original immutable R3 source `9441a73658d21566f981e7986b0e0de9093d14da`, file `r3_forensic_seal.py`:

```python
normalized = json.dumps(shadow, sort_keys=True, separators=(",", ":")).encode("utf-8")
...
"r2_shadow_inspect_sha256": hashlib.sha256(normalized).hexdigest()
...
require(saved == verify_r2(private), "R3_SEAL_R2_EVIDENCE_DRIFT")
```

This hashes **every field** of Docker's entire shadow inspect response, including fields not protected by the actual product cutover contract; it then requires exact equality on repeated reads. Meanwhile, the source `verify_r2` independently passed all live R2 original-Manager/Broker, journal, stopped-shadow security/mount/config, and empty RW-source checks.

**Root failure mechanism: overbroad whole-inspect digest scope.** A value in the full inspect response differed across reads; the specific nested field is not recoverable from saved SHA alone. This is an integrity/availability false-stop risk, not evidence that the strict product contract was violated.

## 3. Source-only bounded repair prototype (NOT authorized for live deployment)

Added `tools/execution_packages/n3w/p4_manager_cold_backup/r4_shadow_stable_fingerprint.py` and `test_r4_shadow_stable_fingerprint.py` in PR #540.

- Build deterministic fingerprint from **protected** stopped-shadow fields only: identity/name/image, stopped state, Config fields in `CONFIG_COMPARE`, complete Env map, labels, HostConfig fields in `HOST_COMPARE`, restart policy, and six bind-mount source/destination/mode/propagation fields.
- Allow only the previously reviewed `OomKillDisable=None/False` default-value equivalence; `True` remains forbidden.
- Exclude unprotected mutable whole-inspect fields such as timestamps, exit status, Docker graph-driver and network status metadata.
- Before any use of the legacy R3 seal, rerun `r3.verify_r2` with the existing unchanged, strict original R5 rollback authority, old Manager/Broker identity, shadow parity and fresh-source checks.
- Read the existing legacy R3 private seal `0600` and allow its mismatch **only** if its sole changed key is `r2_shadow_inspect_sha256`. Reject any difference in R2 journal SHA, saved original/Broker/shadow IDs, rollback result, phase, or field set. Require legitimate 64-character hex digests.
- Return a new read-only R4 review document containing the unchanged legacy-seal bytes SHA, stable fingerprint, original-manager/Broker/shadow identifiers and explicit classification of the historical full-inspect digest discrepancy. The prototype **does not write a new seal** or touch T1.
- Do not overwrite, remove, silently normalize or reset the historical R3 seal, R2 journal, R2/R3 stage, R2 shadow, R2 fresh sources, original old RW sources or R5 backup.

```text
TASK=N3W_P4_T1_R3_FULL_INSPECT_HASH_DRIFT_SOURCE_REVIEW
SOURCE_PROTOTYPE_COMMIT=52360b8557ebdf475f12aec454b6ebab0dc4440a
REGRESSION_TEST_COMMIT=a69c4f9aa19b4ef92f22e254f3e26f516fc7ccd5
EXACT_TEST_CI_RUN=37946798766
SYNTHETIC_TESTS=129_PASS
MANAGER_CI_RUN=37946798817
MANAGER_CI=PASS
PUBLIC_SAFETY_CI_RUN=37946798831
PUBLIC_SAFETY_CI=PASS
SOURCE_ONLY_GATE=CLOSED_PASS
LIVE_R4_DEPLOYMENT=false
R3_TRANSACTION_PRESENT=false
OLD_MANAGER_BROKER_MUTATED=false
```

Regression tests verify that unrelated inspection time/exit/restart/graph metadata changes do not affect protected-state fingerprint; that image/ID/log/rootfs/network/env/mount/restart-policy drift does; and that a legacy R3 SHA-only difference is classified distinctly while any protected evidence drift is rejected.

## 4. R4 gate and authorization boundary

```text
NEXT_ONE_GATE=N3W_P4_T1_R3_LEGACY_SEAL_R4_INDEPENDENT_TRANSACTION_DESIGN_SOURCE_ONLY
ORIGINAL_MANAGER_RUNNING=LAST_READONLY_TRUE
BROKER_RUNNING_UNCHANGED=LAST_READONLY_TRUE
R3_PREVIOUS_LIVE_RESULT=STOP_BEFORE_TRANSACTION
R3_SEAL_HASH_DRIFT_CLASS=WHOLE_INSPECT_SHA_SCOPE_OVERBROAD
SPECIFIC_INNER_INSPECT_FIELD=UNKNOWN_NOT_RECOVERABLE_FROM_SAVED_DIGEST
R3_LEGACY_SEAL=KEEP_UNCHANGED
R3_STAGE_AND_FAILED_UNIT=KEEP
R2_JOURNAL_AND_SHADOW=KEEP
R4_NEW_TRANSACTION_AND_STAGE=NOT_BUILT
R4_LIVE_AUTHORIZATION=false
AUTO_RETRY=false
BROKER_MUTATION=false
BOARD_BOOT=false
SETUP_SECRET_IMPORT=false
MERGE=false
```

An independently versioned, isolated R4 one-shot would need a new transaction name, fresh RW roots, unit, source binding and private forensic seal. It must first compare the immutable R3 saved seal to the now-verified R2 contract and require the *only* allowed historical discrepancy; then persist a new canonical stable fingerprint without destroying R3 evidence. Final operator rollback, startup, six-mount identity and zero baseline remain unchanged. It is not authorized to run until source/CI closure and a separate explicit R4 live authorization.

This artifact records facts only from the user's sanitized real T1 evidence and the exact GitHub source review. No private secret, path or Docker ID is archived.
