# N3-W P4 T1 R4 — exact-source independent review / prelive gate (2026-10-09)

## 1. Scope, authority, STOP

```text
TASK=N3W_P4_T1_R4_EXACT_SOURCE_INDEPENDENT_REVIEW_AND_PRELIVE_GATE
AUTHORIZATION=SOURCE_REVIEW_ONLY
SOURCE_11_FILES_EXACT_REF=2d9ee7999d525e0812774a106863e2e6bf55d5ec
PR=540_OPEN_DRAFT
REVIEW_FRESH_PR_HEAD=418a5d3f0f7d226047f68604ebe017888c28d653
MAC_LAUNCHER_EXACT_COMMIT=f868b08c08e35606b2b1aca15549e83ffc23fb92
MAC_LAUNCHER_BLOB=508ec56425905cdbfff174daf1b82619a9e44edd
CODE_MODIFICATION_THIS_REVIEW=false
T1_ACCESS_THIS_REVIEW=false
R4_LIVE_EXECUTION_AUTHORIZED=false
MERGE=false
REVIEW_OUTCOME=STOP_OPEN_BLOCKER
NEXT_ONE_GATE=N3W_P4_T1_R4_LEGACY_DIGEST_VOLATILITY_SOURCE_REPAIR_AND_REGRESSION_TEST
```

The review uses the actual version-pinned 11-file R4 source, exact launcher and test CI. No on-host current state is claimed beyond the last user-supplied T1 read-only inspection: original Manager running under the original container ID, Broker original ID/start/restart unchanged, R2 original and stopped shadow, R3 private seal present mode 0600, no R3 transaction, and exactly one historical R3 seal mismatch `r2_shadow_inspect_sha256`. The specific nested Docker inspect field that changed is **unknown** and cannot be inferred from that SHA alone.

## 2. Findings

### A1 — OPEN_BLOCKER: full-inspect legacy volatility re-enters the new R4 immutable seal

Exact source: `r4_shadow_stable_fingerprint.py`.

- `verify_legacy_r3_seal_readonly` calculates `mismatches = sorted(key for key in live if saved[key] != live[key])`; correctly allows only `[]` or `['r2_shadow_inspect_sha256']`.
- This same function returns `legacy_full_inspect_digest_mismatch: bool(mismatches)`.
- `r4_authority_document` includes `r3_legacy_digest_mismatch_classified: review['legacy_full_inspect_digest_mismatch']` as a **sealed, equality-compared field**.
- `seal_r3_for_r4` commits the resulting R4 document to a new private 0600 file.
- `require_r4_seal` compares `saved == r4_authority_document(private)` again in `LiveOps.preflight`, before the R4 transaction begins.

Reproduction by source semantics: a R2 stopped-shadow full inspect response differing from the R3 historical saved digest at R4 seal creation makes this flag `True`. If a later read happens to match the saved legacy digest, the flag becomes `False`. Both reads can pass the **unchanged** `r3.verify_r2` strict original-manager/Broker, R2 journal, shadow identity, six mounts, host-security/config/logging and fresh-state checks; the new R4 protected fingerprint can be **identical**. Nevertheless `require_r4_seal` fails with `R4_SEAL_PROTECTED_STATE_DRIFT`. The converse transition is also possible. This is exactly the unwanted availability dependency that R4 was created to eliminate; it is a source-proven possible failure, **not** a claim that T1 has exhibited such a reversal.

The existing `test_r4_shadow_stable_fingerprint.py` checks that volatile inspect fields do not affect `stable_shadow_sha256`, but does **not** simulate a changed `legacy_full_inspect_digest_mismatch` between R4 seal and recheck. Current 132 synthetic CI PASS therefore does not close A1.

Required source repair: historical legacy raw inspect hash comparison may be used to **classify and report** old evidence, and may admit only `r2_shadow_inspect_sha256` as a difference after `r3.verify_r2` and the other stable identity/journal checks. Its *current equality/mismatch boolean must not be a recurring sealed invariant*. Preserve the exact existing legacy R3 seal file bytes and its SHA in R4 protected authority, preserve the newly computed R2 security fingerprint; do **not** skip `verify_r2`, skip the saved-seal ID/journal checks, or weaken mount/network/TLS/security parity. Add a deterministic two-snapshot regression where the legacy full-inspect SHA-only mismatch changes True→False and False→True while all protected state remains identical; ensure R4 seal compare still passes. Existing non-SHA, security, journal, image and identity drift tests must continue to reject changes.

### A2 — CLOSED_SOURCE: distinct R4 replay and filesystem state

Frozen source uses `fresh-manager-r4-deploy-state-private.json`, `fresh-manager-r4-runtime-state`, R4 shadow/rollback/failed aliases, `p4-fresh-manager-deploy-r4` and `n3w-p4-fresh-manager-r4-deploy.service`. It requires R3 stage and saved seal, forbids R3 transaction/fresh-base/candidate aliases; doesn't delete historical R2/R3 artifacts. R4 seal uses exclusive 0600 creation; preflight refuses existing R4 transaction/root, failed journal replays and unit-name collision. This is **source review only**, not proof about T1's current filesystem at a later time.

### A3 — CLOSED_SOURCE: guarded execution order and rollback identity

`fresh_manager_operator.main` performs non-mutating preflight and distinct R4 authorization check before writing the R4 seal; then uses `execute(private,text=text)`, which installs the R4 systemd one-shot and invokes the shared final-check rollback path. `fresh_manager_deploy.execute_transaction` checks `require_r4_seal` before transaction creation, fresh-source preparation, shadow creation, old Manager stop/park and candidate startup. R4 `ExecStopPost` uses `fresh_manager_recovery.recover_original` and verifies original container ID/Broker invariants. Rollback remains best-effort on host/Docker failures, never guaranteed success on arbitrary power or daemon outages. No R4 physical rollback injection evidence exists.

### A4 — CLOSED_SOURCE: security, six mounts and logging

`cutover_contract` continues to compare all original HostConfig protected fields and Config/Env/labels and six mounts. The only normalised host default is `OomKillDisable=None/False`; `True` remains forbidden. `fresh_manager_deploy.create_command` preserves json-file logging options, six binds with independent three RW and exact three RO secrets, network host, read-only root FS. The stable SHA includes the complete protected Env, Config, HostConfig, restart policy and six mount parameters. This is not a substitute for current T1 runtime evidence.

### A5 — CLOSED_BINDING: launcher and source identity

The eleven protected blob SHAs in the R4 launcher at exact immutable commit `f868b08c08e35606b2b1aca15549e83ffc23fb92` match the files at `2d9ee7999d525e0812774a106863e2e6bf55d5ec`. Launcher blob `508ec56425905cdbfff174daf1b82619a9e44edd`, R4 stage and R4 authorization ID also match. Exact-source SHA binding does **not** authorize or prove live deployment.

### A6 — OPEN_NONBLOCKING_REVIEW_NOTE: host timing and prelive evidence

The oneshot systemd unit has `TimeoutStartSec=300`, while operator `WAIT_LIMIT_SECONDS=430`; this disparity may cause systemd to kill a long-running deployment before the operator's own waiting budget expires. Its fail-closed and `ExecStopPost` rescue path is designed for this; determine whether to align the deadlines and add a synthetic timeout/rollback test as part of repair without increasing the live mutation scope. Neither the 132 synthetic tests nor a source review proves a successful real R4 shadow, cutover or recovery on T1. No user-facing live command is appropriate.

## 3. CI and exact source status

```text
PREVIOUS_SOURCE_ONLY_CI_RUN=37948099018
PREVIOUS_SYNTHETIC_TESTS=132_PASS
PREVIOUS_MANAGER_CI_RUN=37948099031
PREVIOUS_MANAGER_CI=PASS
PREVIOUS_PUBLIC_SAFETY_CI_RUN=37948098899
PREVIOUS_PUBLIC_SAFETY_CI=PASS
CURRENT_REVIEW_BLOCKER_COUNT=1
A1=OPEN_BLOCKER
A2=CLOSED_SOURCE
A3=CLOSED_SOURCE
A4=CLOSED_SOURCE
A5=CLOSED_BINDING
A6=OPEN_NONBLOCKING_REVIEW_NOTE
READY_FOR_R4_LIVE_PRODUCTION=false
```

CI being green does not negate source-review A1. No new code was committed during this independent review.

## 4. STOP and next exact gate

```text
NEXT_ONE_GATE=N3W_P4_T1_R4_LEGACY_DIGEST_VOLATILITY_SOURCE_REPAIR_AND_REGRESSION_TEST
CURRENT_REVIEW=STOP_OPEN_BLOCKER
R4_LIVE_DEPLOYMENT_AUTHORIZATION=false
R4_LIVE_DEPLOYMENT_ATTEMPTED=false
R4_MAC_COMMAND_RELEASED=false
R2_R3_HISTORICAL_PRIVATE_FILES=KEEP
R5_BACKUP_AND_OLD_RW=KEEP
BROKER_RESET=false
BOARD_ACCESS=false
SETUP_SECRET_IMPORT=false
PR_MERGE=false
```

Do not try to suppress the STOP by deleting/rewriting the R3 private seal or by skipping original source authority and strict R2 checks. First fix the sole confirmed source blocker on a separately scoped repair gate, add the volatility-flip regression, require final CI and independent review, and only then consider a **new, separately explicit** T1 production authorization.
