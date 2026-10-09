# N3-W P4 T1 — R3 legacy seal → independent R4 transaction (source-only closure, 2026-10-09)

## 1. Authority, user approval, and STOP boundary

User approved **NEXT_ONE_GATE=N3W_P4_T1_R3_LEGACY_SEAL_R4_INDEPENDENT_TRANSACTION_DESIGN_SOURCE_ONLY** after real T1 R3 SHA-only stop forensic closure. This approval authorizes **GitHub source design, code authoring, synthetic CI, source binding and documentation only**. It is not approval for another T1 production cutover, cleanup, systemd unit reset, replay, board boot or Setup Secret import.

Actual T1 evidence (read-only, supplied by user):

```text
R3_PRIVATE_ROOT_COUNT=1
R3_TRANSACTION_EXISTS=false
R3_SEAL_EXISTS=true
R3_SEAL_SYMLINK=false
R3_SEAL_MODE_0600=true
R3_SAVED_SEAL_READ=PASS
R2_LIVE_REVERIFY=PASS
R3_SEAL_DIFFERENCE_COUNT=1
R3_ONLY_DIFF_FIELD=r2_shadow_inspect_sha256
R3_SEAL_EXTRA_FIELD_COUNT=0
R3_REAL_DEPLOY=STOP_R3_FORENSIC_SEAL_INVALID_BEFORE_TRANSACTION
R3_MANAGER_RUNNING_ORIGINAL_ID=true
R3_BROKER_RUNNING_ORIGINAL_ID=true
R3_BROKER_START_RESTART_UNCHANGED=true
```

The R3 legacy seal's `r2_shadow_inspect_sha256` hashed **all** Docker inspect fields; it differed on reread, whereas all other saved seal fields and fresh R2 live contract verification matched. **No exact inner Docker inspect field was recovered**, so do not claim a particular timestamp or runtime flag changed. The new source does not silently rewrite the R3 historical hash.

## 2. R4 isolated source contract

This branch implements R4 in `tools/execution_packages/n3w/p4_manager_cold_backup/`, retaining immutable R1/R2/R3 previous source commits and private runtime artifacts.

### A. Check and protect the existing R2/R3 history

Before installing any new systemd service or stopping old Manager:

1. Require original R5 root-private authority, old Manager running with original ID, original Broker ID/start/restart, R2 root-private rollback journal and rollback `PASS`, original stopped R2 shadow and empty isolated R2 fresh roots.
2. Revalidate full existing `r3_forensic_seal.verify_r2` identity, shadow parity (six mounts, logging options, network/HostConfig, env/labels, image), and private file permissions.
3. Require saved R3 `0600` seal still present. Require its field set unchanged and all original R2/Broker/Manager/shadow ID and journal SHA fields equal to live revalidation. The **only** allowed historical difference is `r2_shadow_inspect_sha256`, both sides requiring 64 hex characters. Preserve both values unchanged.
4. Require **no R3 transaction file, R3 fresh-root base, R3 shadow/parked/failed candidate** and retain original private R3 stage (0700). Any inconsistent prior R3 cutover residue => STOP.
5. Compute a **protected-state stable shadow digest** over shadow identity, image/name, stopped state, protected Config fields, complete environment and labels, HostConfig including logging and network/security, restart policy, and all six bind-mount source/destination/permission/propagation. Canonicalize exactly `OomKillDisable=None/False` to false, reject true. Exclude unrelated volatile inspect attributes (e.g. Created, restart count, ExitCode, NetworkSettings, GraphDriver).
6. After an explicitly authorized R4 operator execute, write a new independent 0600 `fresh-manager-r4-protected-forensic-seal-private.json` with R3 saved seal SHA, R2 journal SHA, original Manager/Broker/shadow IDs and R2 stable security fingerprint. Do not overwrite R3 seal.
7. The R4 systemd execution preflight must rederive this new stable authority and compare it exactly. An absent, altered or already-existing seal at first-seal time fails closed; mismatch in protected security fields stops before creating R4 transaction or stopping Manager.

### B. New independent R4 transaction

```text
R4_AUTHORIZATION_ID=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_LIVE_DEPLOY_R4
R4_MAC_STAGE=p4-fresh-manager-deploy-r4
R4_PRIVATE_TRANSACTION=fresh-manager-r4-deploy-state-private.json
R4_PRIVATE_FRESH_RW_BASE=fresh-manager-r4-runtime-state
R4_PRIVATE_ENV=fresh-manager-r4-env-private
R4_SHADOW=greenhouse-manager-p4-r4-shadow
R4_PARKED_OLD=greenhouse-manager-p4-r4-rollback
R4_FAILED_CANDIDATE=greenhouse-manager-p4-r4-failed
R4_SYSTEMD_UNIT=n3w-p4-fresh-manager-r4-deploy.service
R4_SRC_SCRIPTS=11
R4_MAC_LAUNCHER_NONPUBLICATED_TO_OPERATOR=true
```

R4 stages and creates **three new empty RW directory sources**, reusing the exact existing three RO secret mounts and keeping the six-bind contract. Old three RW sources, original old Manager and R5 archived backup are never overwritten. No legacy Compose recreate, no Broker/system/TLS mutation. The stopped R4 shadow must match identity/security/config before stopping original Manager. Postflight checks empty registration/credential/replay rows and empty relay key root, no sender traffic expected because boards are unpowered. On failure, preserve R4 evidence and attempt supervised identity-bound rollback; no automatic retry. The operator main routes to the guarded final-verification rollback path.

## 3. Exact source, tests and CI

```text
SOURCE_ONLY_TASK=N3W_P4_T1_R3_LEGACY_SEAL_R4_INDEPENDENT_TRANSACTION_DESIGN_SOURCE_ONLY
SOURCE_PROTECTED_11_FILE_REF=2d9ee7999d525e0812774a106863e2e6bf55d5ec
R4_LAUNCHER_SOURCE_COMMIT=f868b08c08e35606b2b1aca15549e83ffc23fb92
R4_LAUNCHER_BLOB_SHA1=508ec56425905cdbfff174daf1b82619a9e44edd
R4_TEST_SOURCE_COMMIT=37b4d080974c5b5198406374a8737217585c01b5
SYNTHETIC_CI_RUN=37947791861
SYNTHETIC_TESTS=132_PASS
GREENHOUSE_MANAGER_CI_RUN=37947791855
GREENHOUSE_MANAGER_CI=PASS
PUBLIC_SAFETY_CI_RUN=37947791972
PUBLIC_SAFETY_CI=PASS
SOURCE_ONLY_RESULT=PASS_PENDING_INDEPENDENT_REVIEW
R4_REAL_T1_EXECUTION=NOT_STARTED
R4_LIVE_AUTHORIZATION=false
NO_T1_ACCESS_IN_THIS_GATE=true
NO_PR_MERGE=true
```

Tests include: dynamic Docker inspect fields do not alter protected fingerprint; drift of image/container ID/mount/network/logging/secrets/restart policy does alter it; only the legacy R3 full-inspect digest difference is classified; any drift in original Manager/Broker/shadow ID, R2 journal, rollback status, R3 seal content or stable protected fingerprint is rejected. R4 seal is 0600, one-write/no replay and guards against R3 transaction/candidate residue. R4 main operator seals before guarded execute, authorization checks precede sealing, no false success on final-verification rollback failure, and source-bound Mac stage verifies eleven Git blobs.

Source-only CI is not physical acceptance. It does not prove the R4 live image starts, the 3 empty new roots are accepted on T1, or any board telemetry.

## 4. Next independent gate; no implied production authorization

```text
NEXT_ONE_GATE=N3W_P4_T1_R4_EXACT_SOURCE_INDEPENDENT_REVIEW_AND_PRELIVE_GATE
SOURCE_ONLY_COMPLETED=true
THIRD_R3_LIVE_ATTEMPT=STOP_UNCLAIMED_TRANSACTION
FOURTH_R4_LIVE_ATTEMPT=NOT_AUTHORIZED
OLD_MANAGER_ORIGINAL_RUNNING=LAST_READONLY_PROVEN
BROKER_ORIGINAL_UNCHANGED=LAST_READONLY_PROVEN
R2_JOURNAL_SHADOW_FRESH_ROOTS=KEEP
R3_SEAL_AND_STAGE_AND_FAILED_UNIT=KEEP
R4_STAGE_OR_SEAL_ON_T1=NOT_CREATED
BOARD_FIRST_NORMAL_BOOT=false
SETUP_SECRET_IMPORT=false
R5_BACKUP_ORIGINAL_RW_SOURCES=KEEP
NO_AUTO_RETRY=true
```

The next independent review should scrutinize the time-of-check/time-of-use window in R4 seal creation and second preflight, the possibility that R2 shadow protected fields changed despite an unchanged stored legacy-seal non-SHA key, regression scope, supervised rollback, R4 distinct transaction names, root-private evidence handling, and exact source manifests. Do not supply or run a live R4 Mac command before that gate closes and the user separately authorizes it.
